"""
PMOVES Service Registry for dynamic service URL resolution.

This module provides a centralized service discovery mechanism with a fallback chain:
1. Environment variables (static, configured overrides)
2. Supabase service catalog (dynamic, runtime)
3. NATS service announcements (real-time, cached)
4. Docker DNS (development fallback)

Usage:
    from services.common.service_registry import get_service_url, ServiceInfo

    # Simple URL resolution
    url = await get_service_url("hirag-v2")

    # With custom default port
    url = await get_service_url("custom-service", default_port=9000)

    # Get full service info
    info = await get_service_info("hirag-v2")
    print(f"{info.name}: {info.health_check_url}")
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, ClassVar

from supabase import Client


class ServiceTier(str, Enum):
    """PMOVES service tiers following 6-tier environment architecture."""

    DATA = "data"
    API = "api"
    LLM = "llm"
    WORKER = "worker"
    MEDIA = "media"
    AGENT = "agent"
    UI = "ui"


@dataclass(frozen=True)
class ServiceInfo:
    """
    Immutable service metadata from the service catalog.

    Attributes:
        slug: Unique service identifier (e.g., "hirag-v2", "agent-zero")
        name: Human-readable service name
        description: Service description
        health_check_url: Full URL to health check endpoint
        default_port: Default container port
        env_var: Environment variable name for custom URL override
        tier: Service tier classification
        tags: Additional metadata tags
        metadata: Extended metadata as JSON
        active: Whether service is enabled
    """

    slug: str
    name: str
    description: str
    health_check_url: str
    default_port: int | None
    env_var: str | None
    tier: ServiceTier
    tags: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    active: bool = True

    @property
    def base_url(self) -> str:
        """Extract base URL from health_check_url."""
        # Remove /healthz or /health suffix if present
        url = self.health_check_url
        for suffix in ("/healthz", "/health", "/metrics", "/ping"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        return url.rstrip("/")


@dataclass
class ServiceAnnouncement:
    """NATS service announcement message format.

    Services publish announcements on the `services.announce.v1` subject
    to notify other services of their availability and configuration.
    """

    slug: str
    name: str
    url: str
    health_check: str
    tier: ServiceTier
    port: int
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    # Subject for service announcements
    SUBJECT: ClassVar[str] = "services.announce.v1"

    def to_json(self) -> str:
        """Convert to JSON for NATS publishing."""
        return json.dumps(
            {
                "slug": self.slug,
                "name": self.name,
                "url": self.url,
                "health_check": self.health_check,
                "tier": self.tier.value,
                "port": self.port,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_json(cls, data: str | dict) -> ServiceAnnouncement:
        """Parse from JSON message."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(
            slug=data["slug"],
            name=data["name"],
            url=data["url"],
            health_check=data["health_check"],
            tier=ServiceTier(data["tier"]),
            port=data["port"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
        )


class ServiceRegistryError(Exception):
    """Base exception for service registry errors."""

    pass


class ServiceNotFoundError(ServiceRegistryError):
    """Raised when a service cannot be found in the catalog."""

    def __init__(self, slug: str, message: str | None = None) -> None:
        self.slug = slug
        super().__init__(message or f"Service '{slug}' not found in service catalog")


class ServiceHealthCheckError(ServiceRegistryError):
    """Raised when a service health check fails."""

    def __init__(self, slug: str, url: str, status_code: int | None = None) -> None:
        self.slug = slug
        self.url = url
        self.status_code = status_code
        message = f"Health check failed for '{slug}' at {url}"
        if status_code:
            message += f" (status: {status_code})"
        super().__init__(message)


# In-memory cache for NATS announcements
_nats_service_cache: dict[str, ServiceInfo] = {}
_nats_cache_timestamp: float = 0.0
_NATS_CACHE_TTL: float = 300.0  # 5 minutes


def _get_env_url(slug: str) -> str | None:
    """Check for environment variable override.

    Environment variables are checked in the following order:
    1. <SLUG>_URL (e.g., HIRAG_V2_URL)
    2. <SLUG WITH DASHES>_URL (e.g., HIRAG-V2-URL)
    3. UPPERCASE_SLUG_URL (e.g., HIRAGV2_URL)

    Args:
        slug: Service slug (e.g., "hirag-v2")

    Returns:
        URL from environment or None
    """
    # Try various environment variable patterns
    env_var_patterns = [
        slug.upper().replace("-", "_") + "_URL",  # HIRAG_V2_URL
        slug.upper().replace("-", "") + "_URL",  # HIRAGV2_URL
        slug.upper() + "_URL",  # HIRAG-V2_URL
    ]

    for pattern in env_var_patterns:
        if url := os.getenv(pattern):
            return url

    return None


def _get_supabase_client() -> Client | None:
    """Get Supabase client if configured.

    Returns:
        Supabase client or None if not configured
    """
    try:
        from services.common.supabase import client as get_client

        return get_client()
    except Exception:
        # Supabase not configured or credentials missing
        return None


def _fetch_from_supabase(slug: str) -> ServiceInfo | None:
    """Fetch service info from Supabase service catalog.

    Args:
        slug: Service slug to look up

    Returns:
        ServiceInfo if found, None otherwise
    """
    client = _get_supabase_client()
    if not client:
        return None

    try:
        response = (
            client.table("service_catalog")
            .select("*")
            .eq("slug", slug)
            .eq("active", True)
            .maybe_single()
            .execute()
        )

        if not response.data:
            return None

        data = response.data
        return ServiceInfo(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description", ""),
            health_check_url=data["health_check_url"],
            default_port=data.get("default_port"),
            env_var=data.get("env_var"),
            tier=ServiceTier(data["tier"]),
            tags=data.get("tags", {}),
            metadata=data.get("metadata", {}),
            active=data.get("active", True),
        )
    except Exception:
        # Query failed - catalog might not exist yet
        return None


def _get_from_nats_cache(slug: str) -> ServiceInfo | None:
    """Get service info from NATS announcement cache.

    Args:
        slug: Service slug to look up

    Returns:
        ServiceInfo if found in cache, None otherwise
    """
    global _nats_service_cache, _nats_cache_timestamp

    # Check cache expiration
    if asyncio.get_event_loop().time() - _nats_cache_timestamp > _NATS_CACHE_TTL:
        _nats_service_cache.clear()
        return None

    return _nats_service_cache.get(slug)


def _fallback_dns_url(slug: str, default_port: int) -> str:
    """Generate fallback URL using Docker DNS.

    Args:
        slug: Service slug (used as DNS name)
        default_port: Port to use if service has no default

    Returns:
        Fallback service URL
    """
    return f"http://{slug}:{default_port}"


async def get_service_info(
    slug: str,
    *,
    default_port: int = 80,
    use_nats_cache: bool = True,
) -> ServiceInfo:
    """
    Get complete service information using fallback chain.

    Resolution order:
        1. Environment variable override
        2. NATS announcement cache (if enabled and fresh)
        3. Supabase service catalog
        4. Constructed URL (with warning)

    Args:
        slug: Service slug to resolve
        default_port: Port for fallback URL construction
        use_nats_cache: Whether to check NATS announcement cache

    Returns:
        ServiceInfo with service metadata

    Raises:
        ServiceNotFoundError: If service cannot be resolved
    """
    # 1. Check environment variable override
    if env_url := _get_env_url(slug):
        # Create minimal ServiceInfo from env URL
        return ServiceInfo(
            slug=slug,
            name=f"{slug} (from env)",
            description=f"Service URL from environment variable",
            health_check_url=env_url,
            default_port=default_port,
            env_var=None,
            tier=ServiceTier.API,  # Default tier
            active=True,
        )

    # 2. Check NATS cache
    if use_nats_cache:
        if cached := _get_from_nats_cache(slug):
            return cached

    # 3. Check Supabase catalog
    if catalog_info := _fetch_from_supabase(slug):
        return catalog_info

    # 4. Fallback to DNS-based URL
    fallback_url = _fallback_dns_url(slug, default_port)
    return ServiceInfo(
        slug=slug,
        name=f"{slug} (fallback)",
        description=f"Service resolved via Docker DNS fallback",
        health_check_url=fallback_url,
        default_port=default_port,
        env_var=None,
        tier=ServiceTier.API,
        active=True,
    )


async def get_service_url(
    slug: str,
    *,
    default_port: int = 80,
    use_base_url: bool = True,
) -> str:
    """
    Resolve service URL with fallback chain.

    Args:
        slug: Service slug to resolve
        default_port: Port for fallback URL construction
        use_base_url: Return base URL instead of health_check_url

    Returns:
        Resolved service URL

    Example:
        >>> await get_service_url("hirag-v2")
        "http://hi-rag-gateway-v2:8086"

        >>> await get_service_url("custom-service", default_port=9000)
        "http://custom-service:9000"
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

    Args:
        slug: Service slug to check
        default_port: Port for fallback URL construction
        timeout: HTTP request timeout in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    import httpx

    info = await get_service_info(slug, default_port=default_port)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(info.health_check_url)
            return response.status_code == 200
    except Exception:
        return False


async def list_services_by_tier(tier: ServiceTier) -> list[ServiceInfo]:
    """
    List all active services in a specific tier.

    Args:
        tier: Service tier to filter by

    Returns:
        List of ServiceInfo objects for the tier
    """
    client = _get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("service_catalog")
            .select("*")
            .eq("tier", tier.value)
            .eq("active", True)
            .execute()
        )

        return [
            ServiceInfo(
                slug=item["slug"],
                name=item["name"],
                description=item.get("description", ""),
                health_check_url=item["health_check_url"],
                default_port=item.get("default_port"),
                env_var=item.get("env_var"),
                tier=ServiceTier(item["tier"]),
                tags=item.get("tags", {}),
                metadata=item.get("metadata", {}),
                active=item.get("active", True),
            )
            for item in response.data
        ]
    except Exception:
        return []


async def list_all_services() -> list[ServiceInfo]:
    """List all active services in the catalog.

    Returns:
        List of all active ServiceInfo objects
    """
    client = _get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("service_catalog")
            .select("*")
            .eq("active", True)
            .execute()
        )

        return [
            ServiceInfo(
                slug=item["slug"],
                name=item["name"],
                description=item.get("description", ""),
                health_check_url=item["health_check_url"],
                default_port=item.get("default_port"),
                env_var=item.get("env_var"),
                tier=ServiceTier(item["tier"]),
                tags=item.get("tags", {}),
                metadata=item.get("metadata", {}),
                active=item.get("active", True),
            )
            for item in response.data
        ]
    except Exception:
        return []


def update_nats_cache(announcement: ServiceAnnouncement) -> None:
    """
    Update NATS service announcement cache.

    Call this when receiving a service announcement on NATS.

    Args:
        announcement: Service announcement to cache

    Example:
        >>> from services.common.service_registry import ServiceAnnouncement, update_nats_cache
        >>> ann = ServiceAnnouncement(
        ...     slug="hirag-v2",
        ...     name="Hi-RAG Gateway v2",
        ...     url="http://hi-rag-gateway-v2:8086",
        ...     health_check="http://hi-rag-gateway-v2:8086/healthz",
        ...     tier=ServiceTier.API,
        ...     port=8086,
        ...     timestamp="2025-01-15T12:00:00Z"
        ... )
        >>> update_nats_cache(ann)
    """
    global _nats_service_cache, _nats_cache_timestamp

    info = ServiceInfo(
        slug=announcement.slug,
        name=announcement.name,
        description=f"Service from NATS announcement",
        health_check_url=announcement.health_check,
        default_port=announcement.port,
        env_var=None,
        tier=announcement.tier,
        metadata=announcement.metadata,
        active=True,
    )

    _nats_service_cache[announcement.slug] = info
    _nats_cache_timestamp = asyncio.get_event_loop().time()


def clear_nats_cache() -> None:
    """Clear the NATS service announcement cache."""
    global _nats_service_cache, _nats_cache_timestamp
    _nats_service_cache.clear()
    _nats_cache_timestamp = 0


# Synchronous convenience functions for non-async contexts

def get_service_url_sync(slug: str, *, default_port: int = 80) -> str:
    """
    Synchronous version of get_service_url for non-async contexts.

    This runs the async function in a new event loop.
    Only use this in contexts where you cannot use async/await.

    Args:
        slug: Service slug to resolve
        default_port: Port for fallback URL construction

    Returns:
        Resolved service URL
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(get_service_url(slug, default_port=default_port))


@lru_cache(maxsize=128)
def get_service_url_cached(slug: str, *, default_port: int = 80) -> str:
    """
    Cached version of get_service_url for high-frequency calls.

    The cache is process-global and persists for the lifetime of the process.
    Use this for performance-critical paths where service URLs don't change.

    Args:
        slug: Service slug to resolve
        default_port: Port for fallback URL construction

    Returns:
        Resolved service URL (cached)

    Note:
        Cache can be cleared with get_service_url_cached.cache_clear()
    """
    return get_service_url_sync(slug, default_port=default_port)


# Module exports
__all__ = [
    # Core functions
    "get_service_url",
    "get_service_info",
    "check_service_health",
    "list_services_by_tier",
    "list_all_services",
    # Sync variants
    "get_service_url_sync",
    "get_service_url_cached",
    # Cache management
    "update_nats_cache",
    "clear_nats_cache",
    # Types
    "ServiceInfo",
    "ServiceAnnouncement",
    "ServiceTier",
    # Exceptions
    "ServiceRegistryError",
    "ServiceNotFoundError",
    "ServiceHealthCheckError",
]
