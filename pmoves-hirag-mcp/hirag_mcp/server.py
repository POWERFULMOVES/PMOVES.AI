#!/usr/bin/env python3
"""PMOVES Hi-RAG MCP Server — stdio bridge for PMOVES knowledge retrieval.

Usage:
    uv run --directory ./pmoves-hirag-mcp python -m hirag_mcp.server

.claude/mcp.json snippet (operator copies in after first smoke-test):
    "pmoves-hirag": {
      "command": "uv",
      "args": ["--directory", "./pmoves-hirag-mcp", "run", "python", "-m", "hirag_mcp.server"],
      "env": {
        "HIRAG_URL": "http://localhost:8086",
        "HIRAG_GPU_URL": "http://localhost:8087",
        "OPEN_NOTEBOOK_API_URL": "",
        "OPEN_NOTEBOOK_API_TOKEN": ""
      }
    }
"""

from __future__ import annotations

import asyncio

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from hirag_mcp.tools import TOOL_HANDLERS, TOOLS

app = Server("pmoves-hirag")


@app.list_tools()
async def list_tools() -> list:
    """Return the tool catalog (hirag_query, notebook_search, service_health)."""
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
                server_name="pmoves-hirag",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
