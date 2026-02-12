#!/usr/bin/env python3
"""
Cipher MCP Server

MCP (Model Context Protocol) server for Claude Code CLI integration.
Bridges Claude Code to Cipher Memory via stdio transport.

Usage:
    python -m cipher_mcp.server

    Or via Claude Code config:
    {
      "mcpServers": {
        "pmoves-cipher": {
          "command": "uv",
          "args": ["--directory", "/path/to/pmoves-cipher-mcp", "run", "python", "-m", "cipher_mcp.server"]
        }
      }
    }
"""

import asyncio
import json
import sys
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server

from cipher_mcp.tools import TOOLS, TOOL_HANDLERS


# Create MCP server instance
app = Server("pmoves-cipher")


@app.list_tools()
async def list_tools() -> list:
    """List available MCP tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """
    Handle tool calls from Claude Code.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool response as list of TextContent
    """
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [{"type": "text", "text": f"Unknown tool: {name}"}]

    try:
        return await handler(**arguments)
    except Exception as e:
        return [{"type": "text", "text": f"Error executing {name}: {e}"}]


async def main():
    """Run the MCP server."""
    # Run server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pmoves-cipher",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
