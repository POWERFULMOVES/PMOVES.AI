"""MCP surface for TitanMail (official `mcp` Python SDK, FastMCP, 1.x line).

Serves BOTH transports from one process:
  * streamable-http at /mcp   -- what Agent Zero's A0_SET_mcp_servers entries use
  * SSE at /sse (+ /messages/) -- what MCP_SERVER_NODE_MAP's PMOVES_*_MCP_ENDPOINT rows use
plus an unauthenticated GET /healthz.

Optional inbound auth: when TITANMAIL_MCP_TOKEN is set, every path except /healthz
requires ``Authorization: Bearer <token>``.
"""
from __future__ import annotations

import hmac
import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .service import TitanMailService
from .timewindow import RELATIVE_GRAMMAR

INSTRUCTIONS = (
    "TitanMail: date-exact email retrieval. The server owns the clock: call now() for the "
    "current instant instead of assuming one. Every window is absolute and half-open "
    "(after <= t < before) and every datetime MUST carry an offset (Z or +/-HH:MM). Relative "
    f"phrases go in `relative` and are resolved server-side ({RELATIVE_GRAMMAR}). Each response "
    "echoes envelope.window (the exact bounds used) and envelope.server_time_utc."
)

TOOL_NAMES = ("search_messages", "get_message", "list_threads", "dedup_report", "now")


def build_mcp(service: TitanMailService, *, host: str = "127.0.0.1", port: int = 8092) -> FastMCP:
    mcp = FastMCP("titanmail", instructions=INSTRUCTIONS, host=host, port=port)

    @mcp.tool()
    async def search_messages(query: str = "", after_iso: str = "", before_iso: str = "",
                              limit: int = 50, relative: str = "") -> dict:
        """Search messages inside an absolute time window.

        Args:
            query: free-text terms (all must match). Date operators (after:, before:, older_than:
                ...) are REJECTED -- put the window in after_iso/before_iso.
            after_iso: inclusive lower bound, ISO-8601 WITH offset, e.g. 2026-10-01T00:00:00-04:00.
            before_iso: exclusive upper bound, ISO-8601 WITH offset.
            limit: max messages returned (1-500, default 50). total_in_window is always exact.
            relative: alternative to after_iso/before_iso, resolved by the server's clock:
                today | yesterday | this week | last week | this month | last month |
                last N hours | last N days | last N weeks.
        Returns envelope (server time + resolved window), total_in_window, messages[].
        """
        return await service.search_messages(query, after_iso, before_iso, limit, relative)

    @mcp.tool()
    async def get_message(id: str) -> dict:  # noqa: A002
        """Fetch one message (headers + text body) by its transport id from search_messages."""
        return await service.get_message(id)

    @mcp.tool()
    async def list_threads(after_iso: str = "", before_iso: str = "", relative: str = "") -> dict:
        """Group the messages inside an absolute window into threads (provider thread id, else
        In-Reply-To/References). Same window rules as search_messages."""
        return await service.list_threads(after_iso, before_iso, relative)

    @mcp.tool()
    async def dedup_report(after_iso: str = "", before_iso: str = "", relative: str = "") -> dict:
        """Report duplicate clusters inside an absolute window using deterministic keys
        (Message-ID, then from+to+subject+body-hash within a short time window). Read-only:
        nothing is deleted or merged in the mailbox."""
        return await service.dedup_report(after_iso, before_iso, relative)

    @mcp.tool()
    async def now() -> dict:
        """The server's exact current datetime, timezone and UTC offset. Use this instead of
        assuming what 'today' is."""
        return service.now()

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request: Request) -> JSONResponse:  # noqa: ARG001
        return JSONResponse({"status": "ok", "service": "titanmail-mcp", "version": __version__,
                             "server_time_utc": service.now()["server_time_utc"],
                             "transport": service.transport.name})

    return mcp


class BearerGate:
    """Pure-ASGI bearer check (BaseHTTPMiddleware would buffer the SSE stream)."""

    def __init__(self, app: Any, token: str, open_paths: tuple[str, ...] = ("/healthz",)):
        self.app = app
        self.token = token
        self.open_paths = open_paths

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.token or scope.get("path") in self.open_paths:
            return await self.app(scope, receive, send)
        auth = ""
        for k, v in scope.get("headers") or []:
            if k.lower() == b"authorization":
                auth = v.decode("latin-1")
        if not hmac.compare_digest(auth.encode(), f"Bearer {self.token}".encode()):
            resp = JSONResponse({"error": "unauthorized"}, status_code=401)
            return await resp(scope, receive, send)
        return await self.app(scope, receive, send)


def build_asgi(mcp: FastMCP, token: str = "") -> Any:
    """One Starlette app carrying streamable-http (/mcp), SSE (/sse, /messages/) and /healthz."""
    http_app = mcp.streamable_http_app()
    sse_app = mcp.sse_app()
    custom = set(id(r) for r in mcp._custom_starlette_routes)  # noqa: SLF001
    routes = list(http_app.routes) + [r for r in sse_app.routes if id(r) not in custom]
    app = Starlette(routes=routes, lifespan=lambda _app: mcp.session_manager.run())
    return BearerGate(app, token) if token else app


def payload_of(result: Any) -> Optional[dict]:
    """Extract the JSON dict from FastMCP.call_tool's return across SDK 1.x variants."""
    if isinstance(result, tuple) and len(result) == 2:
        if isinstance(result[1], dict):
            structured = result[1]
            return structured.get("result", structured) if set(structured) == {"result"} else structured
        result = result[0]
    if isinstance(result, dict):
        return result
    for block in result or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    return None
