"""Shared NATS client wrapper for PMOVES services.

Provides a reusable, properly configured NATS connection with sensible
defaults for reconnection, timeout, and error handling.

Consolidates the NATS boilerplate repeated across 30+ services.

Usage::

    from services.common.nats_client import create_nats_connection

    nc = await create_nats_connection()
    # ... use nc ...
    await nc.close()

Or via the context manager::

    async with nats_connection() as nc:
        await nc.subscribe("subject", cb=handler)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")


@dataclass
class NatsConnectionConfig:
    """Configuration for a NATS connection.

    All fields default from environment variables when not explicitly set.
    """
    url: str = field(default_factory=lambda: DEFAULT_NATS_URL)
    servers: Optional[Sequence[str]] = None
    name: Optional[str] = None
    max_reconnect_attempts: int = 60
    reconnect_time_wait: float = 2.0
    connect_timeout: float = 10.0
    ping_interval: float = 120.0
    max_outstanding_pings: int = 2
    error_cb: Optional[Callable] = None
    disconnected_cb: Optional[Callable] = None
    reconnected_cb: Optional[Callable] = None
    closed_cb: Optional[Callable] = None

    def get_servers(self) -> Sequence[str]:
        """Return the list of NATS server URLs."""
        if self.servers:
            return list(self.servers)
        return [self.url]

    def to_connect_kwargs(self) -> dict[str, Any]:
        """Build keyword arguments for nats.connect()."""
        kwargs: dict[str, Any] = {
            "servers": self.get_servers(),
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "reconnect_time_wait": self.reconnect_time_wait,
            "connect_timeout": self.connect_timeout,
            "ping_interval": self.ping_interval,
            "max_outstanding_pings": self.max_outstanding_pings,
        }
        if self.name:
            kwargs["name"] = self.name
        if self.error_cb:
            kwargs["error_cb"] = self.error_cb
        if self.disconnected_cb:
            kwargs["disconnected_cb"] = self.disconnected_cb
        if self.reconnected_cb:
            kwargs["reconnected_cb"] = self.reconnected_cb
        if self.closed_cb:
            kwargs["closed_cb"] = self.closed_cb
        return kwargs


async def create_nats_connection(
    config: NatsConnectionConfig | None = None,
    **overrides: Any,
) -> Any:
    """Create and return a connected NATS client.

    Args:
        config: Optional NatsConnectionConfig. Defaults to one populated
            from environment variables.
        **overrides: Keyword overrides forwarded to nats.connect().

    Returns:
        A connected nats.aio.client.Client instance.

    Raises:
        ConnectionError: If the connection cannot be established.
    """
    import nats

    if config is None:
        config = NatsConnectionConfig()

    kwargs = config.to_connect_kwargs()
    kwargs.update(overrides)

    service_name = config.name or "unknown"
    logger.info("Connecting to NATS at %s (service=%s)", config.url, service_name)

    try:
        nc = await nats.connect(**kwargs)
        logger.info("NATS connected (service=%s)", service_name)
        return nc
    except Exception as exc:
        logger.error("Failed to connect to NATS: %s", exc)
        raise ConnectionError(f"NATS connection failed: {exc}") from exc


@asynccontextmanager
async def nats_connection(
    config: NatsConnectionConfig | None = None,
    **overrides: Any,
) -> AsyncIterator[Any]:
    """Context manager that yields a connected NATS client and drains on exit.

    Usage::

        async with nats_connection(name="my-service") as nc:
            await nc.subscribe("topic", cb=handler)
    """
    nc = await create_nats_connection(config=config, **overrides)
    try:
        yield nc
    finally:
        try:
            await nc.drain()
        except Exception:
            try:
                await nc.close()
            except Exception:
                pass


# -----------------------------------------------------------------------
# Callback helpers
# -----------------------------------------------------------------------

def make_logging_error_cb(service_name: str) -> Callable:
    """Return an async error callback that logs to the given service logger."""
    _log = logging.getLogger(service_name)

    async def _error_cb(exc: Exception) -> None:
        _log.error("NATS error: %s", exc)

    return _error_cb


def make_logging_disconnected_cb(service_name: str) -> Callable:
    """Return an async disconnected callback that logs."""
    _log = logging.getLogger(service_name)

    async def _disconnected_cb() -> None:
        _log.warning("NATS disconnected")

    return _disconnected_cb


def make_logging_reconnected_cb(service_name: str) -> Callable:
    """Return an async reconnected callback that logs."""
    _log = logging.getLogger(service_name)

    async def _reconnected_cb() -> None:
        _log.info("NATS reconnected")

    return _reconnected_cb


__all__ = [
    "NatsConnectionConfig",
    "create_nats_connection",
    "nats_connection",
    "make_logging_error_cb",
    "make_logging_disconnected_cb",
    "make_logging_reconnected_cb",
    "DEFAULT_NATS_URL",
]
