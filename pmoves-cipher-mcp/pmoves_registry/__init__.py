"""
PMOVES.AI Service Registry for pmoves-cipher-mcp

Service discovery for the Cipher MCP bridge.

Usage:
    from pmoves_registry import get_service_url, ServiceInfo

    # Get Cipher URL
    cipher_url = await get_service_url("cipher-memory", default_port=3000)
"""

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Optional


# Import ServiceTier from shared types
try:
    from pmoves_common import ServiceTier
except ImportError:
    from enum import Enum

    class ServiceTier(str, Enum):
        """PMOVES service tiers (6-tier architecture)."""
        DATA = "data"
        API = "api"
        LLM = "llm"
        MEDIA = "media"
        AGENT = "agent"
        WORKER = "worker"


@dataclass(frozen=True)
class ServiceInfo:
    """
    Immutable service metadata from the service catalog.
    """
    slug: str
    name: str
    description: str
    health_check_url: str
    default_port: int | None
    tier: ServiceTier
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        """Extract base URL from health_check_url."""
        url = self.health_check_url
        for suffix in ("/healthz", "/health", "/metrics", "/ping"):
            if url.endswith(suffix):
                url = url[:-len(suffix)]
                break
        return url.rstrip("/")


class ServiceNotFoundError(Exception):
    """Raised when a service cannot be found."""
    def __init__(self, slug: str, message: str | None = None):
        self.slug = slug
        super().__init__(message or f"Service '{slug}' not found in service catalog")


def _get_env_url(slug: str) -> str | None:
    """Check for environment variable override."""
    env_var_patterns = [
        slug.upper().replace("-", "_") + "_URL",
        slug.upper().replace("-", "") + "_URL",
        slug.upper() + "_URL",
    ]

    for pattern in env_var_patterns:
        if url := os.getenv(pattern):
            return url

    return None


def _fallback_dns_url(slug: str, default_port: int) -> str:
    """Generate fallback URL using Docker DNS."""
    return f"http://{slug}:{default_port}"


async def get_service_info(
    slug: str,
    *,
    default_port: int = 80,
) -> ServiceInfo:
    """
    Get complete service information using fallback chain.
    """
    # 1. Check environment variable override
    if env_url := _get_env_url(slug):
        return ServiceInfo(
            slug=slug,
            name=f"{slug} (from env)",
            description=f"Service URL from environment variable",
            health_check_url=env_url,
            default_port=default_port,
            tier=ServiceTier.API,
        )

    # 2. Fallback to DNS-based URL
    fallback_url = _fallback_dns_url(slug, default_port)
    return ServiceInfo(
        slug=slug,
        name=f"{slug} (fallback)",
        description=f"Service resolved via Docker DNS fallback",
        health_check_url=fallback_url,
        default_port=default_port,
        tier=ServiceTier.API,
    )


async def get_service_url(
    slug: str,
    *,
    default_port: int = 80,
    use_base_url: bool = True,
) -> str:
    """
    Resolve service URL with fallback chain.
    """
    info = await get_service_info(slug, default_port=default_port)
    return info.base_url if use_base_url else info.health_check_url


async def check_service_health(
    slug: str,
    *,
    default_port: int = 80,
    timeout: float = 5.0,
) -> bool:
    """
    Check if a service is healthy by calling its health endpoint.
    """
    import httpx

    info = await get_service_info(slug, default_port=default_port)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(info.health_check_url)
            return response.status_code == 200
    except Exception:
        return False


# Common service URLs for Cipher MCP bridge
class CipherServices:
    """Common PMOVES service URLs used by Cipher MCP bridge."""

    # Cipher Memory (backend)
    CIPHER_MEMORY = "http://cipher-memory:3000"

    @classmethod
    def get(cls, service: str) -> str:
        """Get a common service URL by name."""
        return getattr(cls, service.upper(), None)


__all__ = [
    "ServiceInfo",
    "ServiceNotFoundError",
    "get_service_url",
    "get_service_info",
    "check_service_health",
    "CipherServices",
]
