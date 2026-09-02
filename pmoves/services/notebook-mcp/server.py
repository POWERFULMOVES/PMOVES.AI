"""notebook-mcp — an MCP server wrapping the PMOVES Open Notebook REST API.

The "build once, mount twice" wrapper: exposes Open Notebook's save + search as
MCP tools so ANY agent can use notebook — Agent Zero via its runtime MCP client
(:8081), deepseek-harness via `dsh-mcp-client`, and any other MCP consumer. It
reuses the exact endpoints/payloads already proven by the `pmoves_notes` Agent
Zero plugin (tools surface as `mcp__notebook__save_note` / `mcp__notebook__search_notes`).

Env:
  OPEN_NOTEBOOK_API_URL    default http://open-notebook:5055 (internal alias)
  OPEN_NOTEBOOK_API_TOKEN  fallback Bearer token (optional; warns if sent over plain http)
  MCP_HOST / MCP_PORT      bind for the streamable-http transport (default 0.0.0.0:8092)
  MCP_TRANSPORT            "streamable-http" (default) | "sse" | "stdio"
  NOTEBOOK_MCP_TENANT_TOKEN_HEADER
                           inbound header carrying the caller's Open Notebook
                           token (default X-Open-Notebook-Token)
  NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN
                           "true" => fail closed: a request WITHOUT a per-request
                           token is refused instead of falling back to the shared
                           env token. Set this whenever more than one tenant can
                           reach this server.

Tenancy: the credential is resolved PER REQUEST. A mounting harness (dsh
`ctx.credentials`, an A0 per-context header, a gateway) passes that tenant's
Open Notebook token in NOTEBOOK_MCP_TENANT_TOKEN_HEADER and only that tenant's
notebook is touched. OPEN_NOTEBOOK_API_TOKEN remains as a single-tenant
convenience fallback; with NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN=true the fallback is
disabled entirely, so a multi-tenant deployment cannot silently collapse every
caller onto one Open Notebook account.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.getenv("OPEN_NOTEBOOK_API_URL", "http://open-notebook:5055").rstrip("/")
TOKEN = os.getenv("OPEN_NOTEBOOK_API_TOKEN", "")
TENANT_TOKEN_HEADER = os.getenv(
    "NOTEBOOK_MCP_TENANT_TOKEN_HEADER", "X-Open-Notebook-Token"
).strip().lower()
_TRUTHY = {"1", "true", "yes", "on"}
REQUIRE_TENANT_TOKEN = (
    os.getenv("NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN", "").strip().lower() in _TRUTHY
)

mcp = FastMCP(
    "notebook",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8092")),
)


class TenantCredentialError(RuntimeError):
    """No per-request Open Notebook credential and the shared fallback is disabled."""


def _request_token() -> str:
    """Token supplied by the caller on the in-flight MCP request, else "".

    HTTP transports (streamable-http / sse) carry the originating Starlette
    request on the request context; stdio has none. Never raises — a missing
    context simply means "no per-request credential".
    """
    try:
        request = mcp.get_context().request_context.request
        headers = getattr(request, "headers", None)
        if headers is None:
            return ""
        return (headers.get(TENANT_TOKEN_HEADER) or "").strip()
    except Exception:  # noqa: BLE001 - no active request context
        return ""


def _resolve_token() -> str:
    """The Open Notebook credential for THIS request.

    Per-request header wins. The process-wide env token is only a single-tenant
    fallback and is refused outright when REQUIRE_TENANT_TOKEN is set, so a
    shared deployment cannot serve every tenant from one account.
    """
    token = _request_token()
    if token:
        return token
    if REQUIRE_TENANT_TOKEN:
        raise TenantCredentialError(
            f"no per-request credential: send this tenant's Open Notebook token in "
            f"the {TENANT_TOKEN_HEADER!r} header "
            f"(NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN is set, so the shared "
            f"OPEN_NOTEBOOK_API_TOKEN fallback is disabled)."
        )
    return TOKEN


def _headers(token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        if API_URL.lower().startswith("http://"):
            # Same warning the pmoves_notes plugin emits: a bearer over plain http
            # is fine on the internal pmoves_app network, not for external endpoints.
            print(
                "[notebook-mcp] WARNING: Open Notebook token set but API_URL is "
                "http:// — token sent unencrypted (ok on the internal network only)."
            )
        headers["Authorization"] = f"Bearer {token}"
    return headers


@mcp.tool()
async def save_note(content: str, title: str = "", tags: list[str] | None = None) -> str:
    """Save a note to the PMOVES Open Notebook knowledge base.

    Args:
        content: The note body (required).
        title: Optional title; derived from the first line if omitted.
        tags: Optional tags; folded into the body (Open Notebook /api/notes has no
              tags field) alongside an "agent-created" marker.

    Returns the saved note id, or an error string (never raises).
    """
    content = content if isinstance(content, str) else str(content or "")
    if not content.strip():
        return "save_note error: 'content' is required."

    try:
        token = _resolve_token()
    except TenantCredentialError as exc:
        return f"save_note error: {exc}"

    tags = list(tags) if isinstance(tags, (list, tuple)) else []
    if not title:
        first = (content.splitlines() or [content])[0]
        title = (first[:60] + "...") if len(first) > 60 else first

    # Open Notebook POST /api/notes accepts {content, title, note_type} only — fold
    # tags into the body so categorization survives (mirrors the pmoves_notes plugin).
    body = content + "\n\n_tags: " + ", ".join(tags + ["agent-created"]) + "_"
    payload = {"content": body, "title": title, "note_type": "human"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{API_URL}/api/notes", json=payload, headers=_headers(token))
            if resp.status_code != 200:
                return f"save_note failed: HTTP {resp.status_code} — {resp.text}"
            result = resp.json()
    except Exception as exc:  # surface as a tool result, never crash the server
        return f"save_note error: {exc}"

    if not isinstance(result, dict):
        return "save_note failed: unexpected response shape (expected JSON object)."
    note_id = result.get("id", "unknown")
    await _publish_nats(
        "agent.notes.saved.v1",
        {"note_id": note_id, "title": title, "tags": tags,
         "timestamp": datetime.now(timezone.utc).isoformat()},
    )
    return f"Note saved to Open Notebook (id={note_id}, title={title!r})."


@mcp.tool()
async def search_notes(query: str, limit: int = 10) -> str:
    """Search the PMOVES Open Notebook knowledge base for notes.

    Args:
        query: Search text (required).
        limit: Max results (1-50, default 10).

    Returns a JSON string of matching notes (id, title, snippet, note_type), or an
    error string (never raises).
    """
    query = (query if isinstance(query, str) else str(query or "")).strip()
    if not query:
        return "search_notes error: 'query' is required."

    try:
        token = _resolve_token()
    except TenantCredentialError as exc:
        return f"search_notes error: {exc}"

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    # Open Notebook search is POST /api/search (scope to notes, text search).
    payload = {
        "query": query, "type": "text", "limit": min(max(limit, 1), 50),
        "search_sources": False, "search_notes": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{API_URL}/api/search", json=payload, headers=_headers(token))
            if resp.status_code != 200:
                return f"search_notes failed: HTTP {resp.status_code} — {resp.text}"
            results = resp.json()
    except Exception as exc:
        return f"search_notes error: {exc}"

    raw = results.get("results", []) if isinstance(results, dict) else []
    summary = []
    for n in raw if isinstance(raw, list) else []:
        if not isinstance(n, dict):
            continue
        c = n.get("content") or ""
        c = c if isinstance(c, str) else str(c)
        summary.append({
            "id": n.get("id"), "title": n.get("title"),
            "snippet": (c[:200] + "...") if len(c) > 200 else c,
            "note_type": n.get("note_type"),
        })
    await _publish_nats(
        "agent.notes.searched.v1",
        {"query": query, "results_count": len(summary),
         "timestamp": datetime.now(timezone.utc).isoformat()},
    )
    return json.dumps({"query": query, "count": len(summary), "results": summary}, indent=2)


async def _publish_nats(subject: str, data: dict) -> None:
    """Best-effort NATS publish; never raises (mirrors the plugin's event trail)."""
    try:
        import nats  # optional dependency

        nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222"))
        try:
            await nc.publish(subject, json.dumps(data).encode())
        finally:
            await nc.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[notebook-mcp] NATS publish to {subject} failed: {exc}")


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if REQUIRE_TENANT_TOKEN:
        mode = "per-request credentials REQUIRED"
    elif TOKEN:
        mode = (
            "per-request credentials optional, shared OPEN_NOTEBOOK_API_TOKEN fallback "
            "ACTIVE — single-tenant only; set NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN=true "
            "if more than one tenant can reach this server"
        )
    else:
        mode = "per-request credentials only (no shared fallback configured)"
    print(f"[notebook-mcp] starting: transport={transport} api={API_URL} tenancy: {mode}")
    mcp.run(transport=transport)
