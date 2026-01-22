"""
NATS Service Announcement Listener for PMOVES service discovery.

This module provides a listener for service announcements on NATS.
Services publish announcements when they start up, allowing other services
to discover them dynamically without relying solely on static configuration.

Subject: services.announce.v1

Usage:
    from services.common.nats_service_listener import (
        ServiceAnnouncementListener,
        announce_service,
    )

    # Subscribe to service announcements
    listener = ServiceAnnouncementListener(nats_url="nats://nats:4222")
    await listener.start()
    # ... service runs ...
    await listener.stop()

    # Announce own service on startup
    await announce_service(
        nats_url="nats://nats:4222",
        slug="my-service",
        name="My Service",
        url="http://my-service:8080",
        health_check="http://my-service:8080/healthz",
        tier=ServiceTier.API,
        port=8080,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import timezone
from typing import Any, Awaitable, Callable, Optional

import nats
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

from services.common.service_registry import (
    ServiceAnnouncement,
    ServiceInfo,
    ServiceTier,
    update_nats_cache,
)

logger = logging.getLogger(__name__)


# Default NATS URL from environment or default
DEFAULT_NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")

# Subject for service announcements
SERVICE_ANNOUNCE_SUBJECT = "services.announce.v1"


class ServiceAnnouncementListener:
    """
    Listener for service announcements on NATS.

    Subscribes to the service announcement subject and updates the
    local service registry cache when announcements are received.

    Example:
        >>> listener = ServiceAnnouncementListener()
        >>> await listener.start()
        >>> # Announcements are now being processed
        >>> await listener.stop()
    """

    def __init__(
        self,
        nats_url: str | None = None,
        subject: str = SERVICE_ANNOUNCE_SUBJECT,
        on_announcement: Callable[[ServiceInfo], Awaitable[None]] | None = None,
    ):
        """Initialize the service announcement listener.

        Args:
            nats_url: NATS connection URL (default: from NATS_URL env var)
            subject: NATS subject for service announcements
            on_announcement: Optional callback for each announcement
        """
        self.nats_url = nats_url or DEFAULT_NATS_URL
        self.subject = subject
        self.on_announcement = on_announcement

        self._nc: NATS | None = None
        self._sub: Any | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def is_connected(self) -> bool:
        """Check if NATS client is connected."""
        return self._nc is not None and self._nc.is_connected

    async def start(self) -> bool:
        """
        Start listening for service announcements.

        Returns:
            True if started successfully, False otherwise

        Raises:
            RuntimeError: If listener is already running
        """
        if self._running:
            raise RuntimeError("ServiceAnnouncementListener already running")

        try:
            # Connect to NATS
            self._nc = NATS()
            await self._nc.connect(self.nats_url)
            logger.info(f"Connected to NATS at {self.nats_url}")

            # Subscribe to service announcements
            self._sub = await self._nc.subscribe(
                self.subject, cb=self._on_message, queue="service-listeners"
            )
            logger.info(f"Subscribed to {self.subject}")

            self._running = True
            return True

        except Exception as e:
            logger.error(f"Failed to start service announcement listener: {e}")
            self._running = False
            return False

    async def stop(self) -> None:
        """Stop listening for service announcements."""
        if not self._running:
            return

        self._running = False

        # Unsubscribe
        if self._sub:
            try:
                await self._sub.unsubscribe()
            except Exception as e:
                logger.warning(f"Error unsubscribing: {e}")
            self._sub = None

        # Close connection
        if self._nc:
            try:
                await self._nc.close()
            except Exception as e:
                logger.warning(f"Error closing NATS connection: {e}")
            self._nc = None

        # Wait for task to complete
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Service announcement listener stopped")

    async def _on_message(self, msg: Msg) -> None:
        """Handle incoming service announcement message.

        Args:
            msg: NATS message containing service announcement
        """
        try:
            data = json.loads(msg.data.decode())

            # Parse announcement
            announcement = ServiceAnnouncement.from_json(data)

            # Update service registry cache
            update_nats_cache(announcement)

            logger.debug(
                f"Service announcement received: {announcement.slug} "
                f"at {announcement.url}"
            )

            # Call custom callback if provided
            if self.on_announcement:
                info = ServiceInfo(
                    slug=announcement.slug,
                    name=announcement.name,
                    description="From NATS announcement",
                    health_check_url=announcement.health_check,
                    default_port=announcement.port,
                    env_var=None,
                    tier=announcement.tier,
                    metadata=announcement.metadata,
                    active=True,
                )
                try:
                    await self.on_announcement(info)
                except Exception as e:
                    logger.error(f"Error in announcement callback: {e}")

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in service announcement: {e}")
        except Exception as e:
            logger.error(f"Error processing service announcement: {e}")

    async def run_forever(self) -> None:
        """Run the listener until stopped.

        This method keeps the listener alive and is useful for
        running in a background task.
        """
        self._task = asyncio.current_task()
        while self._running:
            await asyncio.sleep(1)


async def announce_service(
    nats_url: str | None = None,
    slug: str = "",
    name: str = "",
    url: str = "",
    health_check: str = "",
    tier: ServiceTier = ServiceTier.API,
    port: int = 80,
    metadata: dict[str, Any] | None = None,
    retry: bool = True,
) -> bool:
    """
    Announce a service to the PMOVES service mesh.

    Publishes a service announcement to NATS, allowing other services
    to discover this one dynamically.

    Args:
        nats_url: NATS connection URL (default: from NATS_URL env var)
        slug: Unique service identifier (e.g., "hirag-v2")
        name: Human-readable service name
        url: Base service URL
        health_check: Health check endpoint URL
        tier: Service tier classification
        port: Service port
        metadata: Additional service metadata
        retry: Whether to retry on connection failure

    Returns:
        True if announcement published successfully, False otherwise

    Example:
        >>> await announce_service(
        ...     slug="hirag-v2",
        ...     name="Hi-RAG Gateway v2",
        ...     url="http://hi-rag-gateway-v2:8086",
        ...     health_check="http://hi-rag-gateway-v2:8086/healthz",
        ...     tier=ServiceTier.API,
        ...     port=8086,
        ... )
        True
    """
    from datetime import datetime

    nats_url = nats_url or DEFAULT_NATS_URL

    # Create announcement
    announcement = ServiceAnnouncement(
        slug=slug,
        name=name,
        url=url,
        health_check=health_check,
        tier=tier,
        port=port,
        timestamp=datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        metadata=metadata or {},
    )

    # Connect and publish
    nc: NATS | None = None
    backoff = 1.0
    max_backoff = 30.0

    while True:
        try:
            nc = NATS()
            await nc.connect(nats_url)

            await nc.publish(SERVICE_ANNOUNCE_SUBJECT, announcement.to_json().encode())
            logger.info(f"Service announcement published: {slug} at {url}")
            return True

        except Exception as e:
            logger.warning(f"Failed to publish service announcement: {e}")
            if not retry:
                return False
            logger.info(f"Retrying in {backoff:.1f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        finally:
            if nc:
                try:
                    await nc.close()
                except Exception:
                    pass


async def announce_service_from_env(
    nats_url: str | None = None,
    slug: str = "",
    name: str = "",
    health_check: str = "",
    tier: ServiceTier = ServiceTier.API,
    port: int = 80,
    retry: bool = True,
) -> bool:
    """
    Announce a service using environment configuration.

    Convenience function that reads service URL from environment
    variables and constructs the announcement automatically.

    Args:
        nats_url: NATS connection URL
        slug: Service slug (also used to find env var)
        name: Service name
        health_check: Health check endpoint path (e.g., "/healthz")
        tier: Service tier classification
        port: Service port
        retry: Whether to retry on connection failure

    Returns:
        True if announcement published successfully

    Example:
        >>> # Assuming HIRAG_V2_URL=http://hi-rag-gateway-v2:8086
        >>> await announce_service_from_env(
        ...     slug="hirag-v2",
        ...     name="Hi-RAG Gateway v2",
        ...     health_check="/healthz",
        ...     tier=ServiceTier.API,
        ...     port=8086,
        ... )
        True
    """
    # Try to get URL from environment
    env_var = slug.upper().replace("-", "_") + "_URL"
    url = os.getenv(env_var)

    if not url:
        logger.warning(f"Environment variable {env_var} not set, using DNS fallback")
        url = f"http://{slug}:{port}"

    # Construct health check URL
    if not health_check.startswith("/"):
        health_check = "/" + health_check
    health_check_url = url.rstrip("/") + health_check

    return await announce_service(
        nats_url=nats_url,
        slug=slug,
        name=name,
        url=url,
        health_check=health_check_url,
        tier=tier,
        port=port,
        retry=retry,
    )


class ServiceAnnouncer:
    """
    Context manager for announcing a service on startup and shutdown.

    Automatically announces service availability on entry and
    publishes a shutdown announcement on exit (optional).

    Example:
        >>> async with ServiceAnnouncer(
        ...     slug="my-service",
        ...     name="My Service",
        ...     url="http://my-service:8080",
        ...     health_check="http://my-service:8080/healthz",
        ...     tier=ServiceTier.API,
        ...     port=8080,
        ... ):
        ...     # Service runs here
        ...     await asyncio.sleep(3600)  # Run for an hour
    """

    def __init__(
        self,
        slug: str = "",
        name: str = "",
        url: str = "",
        health_check: str = "",
        tier: ServiceTier = ServiceTier.API,
        port: int = 80,
        metadata: dict[str, Any] | None = None,
        nats_url: str | None = None,
        announce_on_exit: bool = False,
    ):
        """Initialize the service announcer.

        Args:
            slug: Service slug
            name: Service name
            url: Service URL
            health_check: Health check URL
            tier: Service tier
            port: Service port
            metadata: Additional metadata
            nats_url: NATS connection URL
            announce_on_exit: Whether to announce on context exit
        """
        self.slug = slug
        self.name = name
        self.url = url
        self.health_check = health_check
        self.tier = tier
        self.port = port
        self.metadata = metadata
        self.nats_url = nats_url
        self.announce_on_exit = announce_on_exit

    async def __aenter__(self) -> ServiceAnnouncer:
        """Announce service on context entry."""
        await announce_service(
            nats_url=self.nats_url,
            slug=self.slug,
            name=self.name,
            url=self.url,
            health_check=self.health_check,
            tier=self.tier,
            port=self.port,
            metadata=self.metadata,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Optionally announce on context exit."""
        if self.announce_on_exit:
            # Publish shutdown announcement
            # (Could be enhanced with a different subject/message type)
            pass


# Module exports
__all__ = [
    "ServiceAnnouncementListener",
    "announce_service",
    "announce_service_from_env",
    "ServiceAnnouncer",
    "SERVICE_ANNOUNCE_SUBJECT",
]
