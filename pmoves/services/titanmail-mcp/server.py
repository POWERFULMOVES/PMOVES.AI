"""titanmail-mcp entrypoint.

Env (templates in pmoves/env.shared.example; never put real values in this repo):
  MCP_HOST / MCP_PORT        bind (default 0.0.0.0:8092 inside the container)
  MCP_TRANSPORT              "http" (default: streamable-http /mcp + SSE /sse + /healthz)
                             | "stdio" (for a local stdio client)
  TITANMAIL_MCP_TOKEN        optional inbound Bearer token (all paths but /healthz)
  TITANMAIL_TRANSPORT        mailpit (default) | composio-gmail | composio-outlook
  TITANMAIL_MAILPIT_URL      default http://mailpit:8025
  TITANMAIL_TZ               IANA zone for calendar phrases ("today", "last week"); default UTC
  COMPOSIO_API_KEY           Composio project key (composio transports only; never logged)
"""
from __future__ import annotations

import os
import sys

from titanmail.config import build_service
from titanmail.mcp_app import build_asgi, build_mcp


def _log(msg: str) -> None:
    # stdout carries JSON-RPC frames in stdio mode -- diagnostics go to stderr.
    print(msg, file=sys.stderr, flush=True)


def main() -> None:
    service = build_service()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8092"))
    mode = os.getenv("MCP_TRANSPORT", "http").strip().lower()
    mcp = build_mcp(service, host=host, port=port)
    _log(f"[titanmail-mcp] starting mode={mode} bind={host}:{port} "
         f"transport={service.transport.name} tz={service.now()['server_tz']}")
    if mode == "stdio":
        mcp.run(transport="stdio")
        return
    import uvicorn

    app = build_asgi(mcp, token=os.getenv("TITANMAIL_MCP_TOKEN", ""))
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()
