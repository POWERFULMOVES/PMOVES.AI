#!/usr/bin/env python3
"""PMOVES Tailscale MCP Server — stdio bridge over the local `tailscale` CLI.

Usage:
    uv run --directory ./pmoves-tailscale-mcp python -m tailscale_mcp.server

.claude/mcp.json snippet (operator copies in after first smoke-test):
    "pmoves-tailscale": {
      "command": "uv",
      "args": ["--directory", "./pmoves-tailscale-mcp", "run", "python", "-m", "tailscale_mcp.server"],
      "env": {
        "TAILSCALE_BIN": "",                        # optional: explicit tailscale path
        "TAILSCALE_SSH_ALLOWED_HOSTS": ""           # optional: comma-list to restrict ts_ssh
      }
    }

No TAILSCALE_API_KEY required — this wraps the joined local daemon. It complements the
admin-API `tailscale` MCP (route approval, ACL, device mgmt), it does not replace it.
"""

from __future__ import annotations

import asyncio

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from tailscale_mcp.tools import TOOL_HANDLERS, TOOLS

app = Server("pmoves-tailscale")


@app.list_tools()
async def list_tools() -> list:
    """Return the tool catalog (ts_status, ts_exit_node, ts_serve, ts_funnel, ts_ssh, …)."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Dispatch a tool call to its handler; surface errors without crashing the server."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        return await handler(**(arguments or {}))
    except TypeError as exc:
        return [TextContent(type="text", text=f"Invalid arguments for {name}: {exc}")]
    except Exception as exc:  # surface to caller; do not crash the server
        return [TextContent(type="text", text=f"Error executing {name}: {exc}")]


async def main() -> None:
    """Run the stdio MCP server loop."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pmoves-tailscale",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
