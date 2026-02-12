"""
PMOVES.AI Health Check for pmoves-cipher-mcp
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict
import asyncio


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """Health checker for MCP bridge."""

    def __init__(self, service_name: str = "cipher-mcp"):
        self.service_name = service_name
        self.custom_checks: Dict[str, Callable] = {}

    def add_custom_check(self, name: str, check_fn: Callable) -> None:
        """Add custom health check."""
        self.custom_checks[name] = check_fn

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {
            "status": HealthStatus.HEALTHY,
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for name, check_fn in self.custom_checks.items():
            try:
                result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
                results[name] = bool(result)
                if not result:
                    results["status"] = HealthStatus.DEGRADED
            except Exception:
                results[name] = False
                results["status"] = HealthStatus.UNHEALTHY

        return results


__all__ = ["HealthChecker", "HealthStatus"]
