"""wealth-mcp — an MCP server wrapping the PMOVES Firefly III REST API.

"Build once, mount twice": exposes Firefly III's core money operations as MCP tools
so ANY agent can use wealth — Agent Zero via its runtime MCP client (:8081),
deepseek-harness via `dsh-mcp-client`, Claude/Codex. Tools surface as
`mcp__wealth__list_accounts` / `list_transactions` / `search_transactions` /
`create_transaction`.

Tenancy (supports BOTH Firefly multi-tenancy models):
  - B (shared Firefly + per-tenant PATs): the mounting harness sets a per-request
    `Authorization: Bearer <that tenant's Firefly PAT>`; this server forwards it
    verbatim. That is the tenant seam — one Firefly, one PAT per agent workspace.
  - A (per-tenant Firefly instances): point FIREFLY_API_URL at that tenant's instance
    (per workspace) and use its PAT. Same wrapper, different URL.
A process-level baseline FIREFLY_PAT is the fallback when no inbound header is set.

Env:
  FIREFLY_API_URL   default http://firefly:8080/api/v1 (in-network service DNS)
  FIREFLY_PAT       baseline Personal Access Token (optional; per-request Bearer wins)
  MCP_HOST/MCP_PORT bind for streamable-http (default 0.0.0.0:8092)
  MCP_TRANSPORT     "streamable-http" (default) | "sse" | "stdio"
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import Context, FastMCP

API_URL = os.getenv("FIREFLY_API_URL", "http://firefly:8080/api/v1").rstrip("/")
PAT = os.getenv("FIREFLY_PAT", "")

# Firefly III speaks JSON:API.
_ACCEPT = "application/vnd.api+json"


def _log(msg: str) -> None:
    # stdout is reserved for MCP JSON-RPC frames in stdio mode — diagnostics to stderr.
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP(
    "wealth",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8092")),
)


def _inbound_auth(ctx: Context | None) -> str:
    """The Authorization header on THIS request, if the transport carries one."""
    if ctx is None:
        return ""
    try:
        req = getattr(ctx.request_context, "request", None)
        if req is not None:
            return req.headers.get("authorization", "") or ""
    except Exception:
        pass
    return ""


def _headers(ctx: Context | None = None) -> dict[str, str]:
    headers = {"Accept": _ACCEPT, "Content-Type": "application/json"}
    # Per-tenant PAT (mounting harness) wins over the process baseline.
    inbound = _inbound_auth(ctx)
    if inbound:
        headers["Authorization"] = inbound
        return headers
    if PAT:
        if API_URL.lower().startswith("http://"):
            _log("[wealth-mcp] WARNING: FIREFLY_PAT set but FIREFLY_API_URL is http:// "
                 "— token sent unencrypted (ok on the internal network only).")
        headers["Authorization"] = f"Bearer {PAT}"
    return headers


async def _get(path: str, params: dict, ctx: Context | None) -> tuple[int, object]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{API_URL}{path}", params=params, headers=_headers(ctx))
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, r.text
    except Exception as exc:  # surface as a tool result, never crash the server
        return -1, str(exc)


@mcp.tool()
async def list_accounts(account_type: str = "asset", limit: int = 25, ctx: Context | None = None) -> str:
    """List Firefly accounts, scoped by type.

    Args:
        account_type: asset | expense | revenue | liability | all (default asset).
        limit: max accounts (1-100, default 25).
    Returns a JSON string of accounts (id, name, type, currency, current_balance).
    """
    try:
        limit = min(max(int(limit), 1), 100)
    except (TypeError, ValueError):
        limit = 25
    params = {"limit": limit}
    if account_type and account_type != "all":
        params["type"] = account_type
    status, body = await _get("/accounts", params, ctx)
    if status != 200:
        return f"list_accounts failed: HTTP {status} — {str(body)[:300]}"
    rows = body.get("data", []) if isinstance(body, dict) else []
    out = []
    for a in rows if isinstance(rows, list) else []:
        attr = a.get("attributes", {}) if isinstance(a, dict) else {}
        out.append({
            "id": a.get("id"), "name": attr.get("name"), "type": attr.get("type"),
            "currency": attr.get("currency_code"), "current_balance": attr.get("current_balance"),
        })
    return json.dumps({"count": len(out), "accounts": out}, indent=2)


@mcp.tool()
async def list_transactions(limit: int = 20, account_id: str = "", ctx: Context | None = None) -> str:
    """List recent Firefly transactions (optionally for one account).

    Args:
        limit: max transactions (1-50, default 20).
        account_id: optional account id to scope to that account's transactions.
    Returns a JSON string of transactions (id, date, amount, currency, description, category).
    """
    try:
        limit = min(max(int(limit), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    path = f"/accounts/{account_id}/transactions" if account_id else "/transactions"
    status, body = await _get(path, {"limit": limit}, ctx)
    if status != 200:
        return f"list_transactions failed: HTTP {status} — {str(body)[:300]}"
    return json.dumps(_summarize_txns(body), indent=2)


@mcp.tool()
async def search_transactions(query: str, limit: int = 20, ctx: Context | None = None) -> str:
    """Search Firefly transactions by text query.

    Args:
        query: search text (required) — Firefly query syntax supported.
        limit: max results (1-50, default 20).
    Returns a JSON string of matching transactions.
    """
    query = (query if isinstance(query, str) else str(query or "")).strip()
    if not query:
        return "search_transactions error: 'query' is required."
    try:
        limit = min(max(int(limit), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    status, body = await _get("/search/transactions", {"query": query, "limit": limit}, ctx)
    if status != 200:
        return f"search_transactions failed: HTTP {status} — {str(body)[:300]}"
    result = _summarize_txns(body)
    result["query"] = query
    await _publish_nats("agent.wealth.searched.v1",
                        {"query": query, "results_count": result.get("count", 0),
                         "timestamp": datetime.now(timezone.utc).isoformat()})
    return json.dumps(result, indent=2)


@mcp.tool()
async def create_transaction(
    kind: str, amount: str, description: str, source_id: str = "", destination_id: str = "",
    date: str = "", category: str = "", ctx: Context | None = None,
) -> str:
    """Create a Firefly transaction (withdrawal | deposit | transfer).

    Writes to the ledger — the caller's PAT scopes what it can do. Args:
        kind: withdrawal | deposit | transfer (required).
        amount: decimal string, e.g. "42.50" (required).
        description: transaction description (required).
        source_id / destination_id: Firefly account ids (which are required depends on kind:
            withdrawal needs source; deposit needs destination; transfer needs both).
        date: ISO date (default today).
        category: optional category name.
    Returns the created transaction id, or an error string (never raises).
    """
    kind = (kind or "").strip().lower()
    if kind not in {"withdrawal", "deposit", "transfer"}:
        return "create_transaction error: kind must be withdrawal | deposit | transfer."
    amount = (amount if isinstance(amount, str) else str(amount or "")).strip()
    if not amount:
        return "create_transaction error: 'amount' is required."
    if not (description or "").strip():
        return "create_transaction error: 'description' is required."
    split: dict = {"type": kind, "amount": amount, "description": description,
                   "date": (date or datetime.now(timezone.utc).date().isoformat())}
    if source_id:
        split["source_id"] = source_id
    if destination_id:
        split["destination_id"] = destination_id
    if category:
        split["category_name"] = category
    payload = {"transactions": [split]}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{API_URL}/transactions", json=payload, headers=_headers(ctx))
            if r.status_code not in (200, 201):
                return f"create_transaction failed: HTTP {r.status_code} — {r.text[:400]}"
            body = r.json()
    except Exception as exc:
        return f"create_transaction error: {exc}"
    tid = body.get("data", {}).get("id", "unknown") if isinstance(body, dict) else "unknown"
    await _publish_nats("agent.wealth.transaction_created.v1",
                        {"transaction_id": tid, "kind": kind, "amount": amount,
                         "timestamp": datetime.now(timezone.utc).isoformat()})
    return f"Transaction created in Firefly (id={tid}, {kind} {amount}: {description!r})."


def _summarize_txns(body: object) -> dict:
    rows = body.get("data", []) if isinstance(body, dict) else []
    out = []
    for t in rows if isinstance(rows, list) else []:
        attr = t.get("attributes", {}) if isinstance(t, dict) else {}
        for s in (attr.get("transactions", []) or []):
            out.append({
                "id": t.get("id"), "date": (s.get("date") or "")[:10], "type": s.get("type"),
                "amount": s.get("amount"), "currency": s.get("currency_code"),
                "description": s.get("description"), "category": s.get("category_name"),
            })
    return {"count": len(out), "transactions": out}


async def _publish_nats(subject: str, data: dict) -> None:
    """Best-effort NATS publish; bounded so a black-holed broker can't stall a tool."""
    try:
        import asyncio

        import nats  # optional dependency

        async def _do() -> None:
            nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222"),
                                    connect_timeout=2, allow_reconnect=False, max_reconnect_attempts=0)
            try:
                await nc.publish(subject, json.dumps(data).encode())
                await nc.flush(timeout=2)
            finally:
                await nc.close()

        await asyncio.wait_for(_do(), timeout=5)
    except Exception as exc:  # noqa: BLE001
        _log(f"[wealth-mcp] NATS publish to {subject} failed: {exc}")


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    _log(f"[wealth-mcp] starting: transport={transport} api={API_URL}")
    mcp.run(transport=transport)
