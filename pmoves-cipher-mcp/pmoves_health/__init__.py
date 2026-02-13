"""
PMOVES.AI Health Check for pmoves-cipher-mcp

Health check endpoint for the Cipher MCP bridge.

Note: The MCP bridge uses stdio transport and doesn't have an HTTP
health endpoint. This module is provided for PMOVES.AI compliance
and for potential future HTTP-based monitoring.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
import os
import asyncio


try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


HEALTH_CHECK_PATH = "/healthz"
HEALTH_CHECK_TIMEOUT = 5.0


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """
    Health checker for pmoves-cipher-mcp.

    Note: The MCP bridge uses stdio transport. This is provided
    for PMOVES.AI compliance and potential HTTP monitoring.
    """

    def __init__(self, service_name: str = "pmoves-cipher-mcp"):
        self.service_name = service_name
        self.custom_checks: Dict[str, Callable] = {}

    def add_custom_check(self, name: str, check_fn: Callable) -> None:
        """Add a custom health check function."""
        self.custom_checks[name] = check_fn

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks and return status."""
        results = {
            "status": HealthStatus.HEALTHY,
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transport": "stdio",
        }

        # Check if Cipher backend is reachable
        cipher_url = os.getenv("CIPHER_URL", "http://localhost:3000")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{cipher_url}/health")
                results["cipher_connected"] = response.status_code == 200
        except Exception:
            results["cipher_connected"] = False
            results["status"] = HealthStatus.DEGRADED

        # Run custom checks
        for name, check_fn in self.custom_checks.items():
            try:
                result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
                results[name] = bool(result)
            except Exception:
                results[name] = False

        return results


# Global health checker instance
_health_checker = HealthChecker()


def add_custom_check(name: str, check_fn: Callable) -> None:
    """Add a custom health check function."""
    _health_checker.add_custom_check(name, check_fn)


async def get_health_status() -> Dict[str, Any]:
    """Get current health status."""
    return await _health_checker.check_all()


if FASTAPI_AVAILABLE:
    health_check_router = APIRouter()

    @health_check_router.get(HEALTH_CHECK_PATH)
    async def healthz():
        """
        Standard health check endpoint.

        Returns:
            - 200 with status "healthy" or "degraded"
            - 503 with status "unhealthy"
        """
        status = await get_health_status()

        if status.get("status") == HealthStatus.UNHEALTHY:
            return JSONResponse(content=status, status_code=503)
        return status

    def create_health_app(service_name: str = "pmoves-cipher-mcp") -> "FastAPI":
        """Create a minimal FastAPI app with health check."""
        from fastapi import FastAPI
        app = FastAPI(title=service_name)
        app.include_router(health_check_router)
        return app


__all__ = [
    "HealthChecker",
    "HealthStatus",
    "get_health_status",
    "add_custom_check",
]

if FASTAPI_AVAILABLE:
    __all__.extend(["health_check_router", "create_health_app"])
