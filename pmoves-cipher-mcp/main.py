#!/usr/bin/env python3
"""
pmoves-cipher-mcp Entry Point

Main entry point for the Cipher MCP bridge.
"""

import asyncio
import sys


async def announce_mcp_bridge():
    """Announce MCP bridge to PMOVES service mesh."""
    from pmoves_announcer import announce_service

    return await announce_service(
        slug="cipher-mcp",
        name="Cipher MCP Bridge",
        url="http://cipher-mcp:8082",
        port=8082,
        tier="api",
        metadata={
            "bridge_for": "cipher-memory",
            "protocol": "mcp",
            "transport": "stdio",
        },
    )


async def health_check():
    """Run health checks for MCP bridge."""
    from pmoves_health import HealthChecker
    from pmoves_registry import get_cipher_url

    checker = HealthChecker("cipher-mcp")

    # Check Cipher connectivity
    cipher_url = get_cipher_url()

    async def check_cipher():
        try:
            from cipher_mcp.client import CipherClient
            client = CipherClient(base_url=cipher_url)
            await client.health_check()
            return True
        except Exception:
            return False

    checker.add_custom_check("cipher_connected", check_cipher)

    return await checker.check_all()


async def main():
    """Main entry point."""
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if command == "announce":
        success = await announce_mcp_bridge()
        print(f"Announced: {success}")
        sys.exit(0 if success else 1)

    elif command == "health":
        health = await health_check()
        print(f"Status: {health['status']}")
        for key, value in health.items():
            if key not in ("status", "service", "timestamp"):
                print(f"  {key}: {value}")
        sys.exit(0 if health["status"] in ("healthy", "degraded") else 1)

    elif command == "serve":
        # Start MCP server (default)
        from cipher_mcp.server import main as serve_main
        await serve_main()

    else:
        print(f"Usage: python -m cipher_mcp.server [announce|health|serve]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
