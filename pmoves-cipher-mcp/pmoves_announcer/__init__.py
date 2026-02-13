"""
PMOVES.AI Service Announcer for pmoves-cipher-mcp

NATS service discovery announcer for the Cipher MCP bridge.
This is a lightweight MCP bridge service that doesn't typically announce
to NATS since it uses stdio transport, but the module is included
for PMOVES.AI integration compliance.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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


@dataclass
class ServiceAnnouncement:
    """
    Service announcement message format for NATS.
    """
    slug: str
    name: str
    url: str
    health_check: str
    tier: ServiceTier
    port: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    SUBJECT: str = "services.announce.v1"

    def to_json(self) -> str:
        """Convert to JSON for NATS publishing."""
        data = {
            "slug": self.slug,
            "name": self.name,
            "url": self.url,
            "health_check": self.health_check,
            "tier": self.tier.value if isinstance(self.tier, ServiceTier) else self.tier,
            "port": self.port,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        return json.dumps(data)


class ServiceAnnouncer:
    """
    NATS service announcer for pmoves-cipher-mcp.

    Note: The MCP bridge uses stdio transport and typically doesn't
    announce to NATS. This module is provided for PMOVES.AI compliance.
    """

    def __init__(
        self,
        slug: str = "pmoves-cipher-mcp",
        name: str = "PMOVES Cipher MCP Bridge",
        url: str = None,
        port: int = -1,
        tier: ServiceTier | str = ServiceTier.API,
        health_check: str = None,
        nats_url: str = None,
        metadata: Dict[str, Any] = None,
    ):
        self.slug = slug
        self.name = name
        self.url = url or "stdio://local"
        self.port = port

        if isinstance(tier, str):
            tier = ServiceTier(tier.lower())
        self.tier = tier

        self.health_check = health_check or "none"
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://nats:4222")
        self.metadata = metadata or {
            "transport": "stdio",
            "mcp_server": "pmoves-cipher",
        }

    def create_announcement(self) -> ServiceAnnouncement:
        """Create a service announcement object."""
        return ServiceAnnouncement(
            slug=self.slug,
            name=self.name,
            url=self.url,
            health_check=self.health_check,
            tier=self.tier,
            port=self.port,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=self.metadata,
        )

    async def announce(self) -> bool:
        """Publish service announcement to NATS (no-op for stdio)."""
        return True


async def announce_service(
    slug: str = "pmoves-cipher-mcp",
    name: str = "PMOVES Cipher MCP Bridge",
    url: str = None,
    port: int = -1,
    tier: ServiceTier | str = ServiceTier.API,
    health_check: str = None,
    nats_url: str = None,
    metadata: Dict[str, Any] = None,
) -> bool:
    """Convenience function to announce MCP bridge service (no-op for stdio)."""
    return True


__all__ = ["ServiceAnnouncement", "ServiceAnnouncer", "announce_service"]
