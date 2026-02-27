"""
PMOVES.AI Service Announcer for pmoves-cipher-mcp

NATS service discovery for the Cipher MCP bridge.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


try:
    from pmoves_common import ServiceTier
except ImportError:
    from enum import Enum
    class ServiceTier(str, Enum):
        DATA = "data"
        API = "api"
        LLM = "llm"
        MEDIA = "media"
        AGENT = "agent"
        WORKER = "worker"
        UI = "ui"


@dataclass
class ServiceAnnouncement:
    """Service announcement for NATS."""

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
        """Convert to JSON."""
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
    """NATS service announcer."""

    def __init__(
        self,
        slug: str = "cipher-mcp",
        name: str = "Cipher MCP Bridge",
        url: str = None,
        port: int = 8082,
        tier: ServiceTier | str = ServiceTier.API,
        nats_url: str = None,
        metadata: Dict[str, Any] = None,
    ):
        self.slug = slug
        self.name = name
        self.url = url or os.getenv("CIPHER_MCP_URL", "http://localhost:8082")
        self.port = port
        self.tier = ServiceTier(tier) if isinstance(tier, str) else tier
        self.health_check = f"{self.url.rstrip('/')}/healthz"
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
        self.metadata = metadata or {
            "bridge_for": "cipher-memory",
            "protocol": "mcp",
            "transport": "stdio",
        }

    async def announce(self) -> bool:
        """Publish to NATS."""
        try:
            from nats.aio.client import Client as NATS

            announcement = ServiceAnnouncement(
                slug=self.slug,
                name=self.name,
                url=self.url,
                health_check=self.health_check,
                tier=self.tier,
                port=self.port,
                metadata=self.metadata,
            )

            nc = NATS()
            await nc.connect(self.nats_url, connect_timeout=5)
            await nc.publish(
                ServiceAnnouncement.SUBJECT,
                announcement.to_json().encode(),
            )
            await nc.flush()
            await nc.close()

            return True
        except Exception as e:
            print(f"Failed to announce: {e}", file=sys.stderr)
            return False


async def announce_service(**kwargs) -> bool:
    """Convenience function."""
    announcer = ServiceAnnouncer(**kwargs)
    return await announcer.announce()


__all__ = ["ServiceAnnouncer", "ServiceAnnouncement", "announce_service"]
