#!/usr/bin/env python3
"""
PMOVES Cipher MCP Bridge — Entry Point

Starts:
1. Background health-check loop  (pmoves_health)
2. NATS service announcement      (pmoves_announcer)
3. MCP stdio server                (cipher_mcp.server)
"""

import asyncio
import sys

from pmoves_health import health_check
from pmoves_announcer import announce_service
from cipher_mcp.server import main as mcp_main


async def _health_loop(interval: int = 60) -> None:
    """Periodically log health status."""
    while True:
        result = await health_check()
        status = result.get("status", "unknown")
        if status != "healthy":
            print(f"[cipher-mcp] health: {status} — {result.get('detail', '')}", file=sys.stderr)
        await asyncio.sleep(interval)


async def _announce_once() -> None:
    """Announce service on NATS (best-effort)."""
    ok = await announce_service()
    if ok:
        print("[cipher-mcp] announced on NATS", file=sys.stderr)
    else:
        print("[cipher-mcp] NATS announce skipped (not critical)", file=sys.stderr)


async def run() -> None:
    """Launch all components."""
    # Fire-and-forget: announce + health loop
    asyncio.create_task(_announce_once())
    asyncio.create_task(_health_loop())

    # Blocking: MCP server (stdio)
    await mcp_main()


if __name__ == "__main__":
    asyncio.run(run())
