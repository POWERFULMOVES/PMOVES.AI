#!/usr/bin/env python3
"""PMOVES NATS MCP Server — stdio bridge for the PMOVES event bus.

Usage:
    uv run --directory ./pmoves-nats-mcp python -m nats_mcp.server

.claude/mcp.json snippet (operator copies in after first smoke-test):
    "pmoves-nats": {
      "command": "uv",
      "args": ["--directory", "./pmoves-nats-mcp", "run", "python", "-m", "nats_mcp.server"],
      "env": { "NATS_URL": "nats://nats:pmoves@127.0.0.1:4222" }
    }
"""

from __future__ import annotations

import asyncio

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from nats_mcp.tools import TOOL_HANDLERS, TOOLS

app = Server("pmoves-nats")


@app.list_tools()
async def list_tools() -> list:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
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
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pmoves-nats",
                server_version="0.2.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
