"""
PMOVES.AI Health Check Module for pmoves-cipher-mcp

Async health check for the Cipher Memory backend.
"""

from pmoves_common import HealthStatus


async def health_check() -> dict:
    """
    Check Cipher Memory service health.

    Returns:
        dict with "status" (HealthStatus value) and optional "detail".
    """
    from cipher_mcp.client import CipherClient, CipherClientError

    try:
        client = CipherClient()
        data = await client.health_check()
        return {"status": HealthStatus.HEALTHY.value, "detail": data}
    except CipherClientError as exc:
        return {"status": HealthStatus.UNHEALTHY.value, "detail": str(exc)}
    except Exception as exc:
        return {"status": HealthStatus.DEGRADED.value, "detail": str(exc)}


__all__ = ["health_check"]
