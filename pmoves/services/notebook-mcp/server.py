"""notebook-mcp — an MCP server wrapping the PMOVES Open Notebook REST API.

The "build once, mount twice" wrapper: exposes Open Notebook's save + search as
MCP tools so ANY agent can use notebook — Agent Zero via its runtime MCP client
(:8081), deepseek-harness via `dsh-mcp-client`, and any other MCP consumer. It
reuses the exact endpoints/payloads already proven by the `pmoves_notes` Agent
Zero plugin (tools surface as `mcp__notebook__save_note` / `mcp__notebook__search_notes`).

Env:
  OPEN_NOTEBOOK_API_URL    default http://open-notebook:5055 (internal alias)
  OPEN_NOTEBOOK_API_TOKEN  Bearer token (optional; warns if sent over plain http)
  MCP_HOST / MCP_PORT      bind for the streamable-http transport (default 0.0.0.0:8092)
  MCP_TRANSPORT            "streamable-http" (default) | "sse" | "stdio"

Tenant note: this wrapper reads ONE Open Notebook token from env. The per-tenant
credential-injection seam (agent workspace identity -> that tenant's token) lives
in the mounting harness (dsh `ctx.credentials`, or an A0 per-context header), not
here — this server stays a thin, stateless REST->MCP bridge.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.getenv("OPEN_NOTEBOOK_API_URL", "http://open-notebook:5055").rstrip("/")
TOKEN = os.getenv("OPEN_NOTEBOOK_API_TOKEN", "")

mcp = FastMCP(
    "notebook",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8092")),
)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        if API_URL.lower().startswith("http://"):
            # Same warning the pmoves_notes plugin emits: a bearer over plain http
            # is fine on the internal pmoves_app network, not for external endpoints.
            print(
                "[notebook-mcp] WARNING: OPEN_NOTEBOOK_API_TOKEN set but API_URL is "
                "http:// — token sent unencrypted (ok on the internal network only)."
            )
        headers["Authorization"] = f"Bearer {TOKEN}"
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
            resp = await client.post(f"{API_URL}/api/notes", json=payload, headers=_headers())
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
            resp = await client.post(f"{API_URL}/api/search", json=payload, headers=_headers())
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
    print(f"[notebook-mcp] starting: transport={transport} api={API_URL}")
    mcp.run(transport=transport)
