"""Shared NATS client wrapper for PMOVES services.

Provides a reusable, properly configured NATS connection with sensible
defaults for reconnection, timeout, and error handling.

Consolidates the NATS boilerplate repeated across 30+ services.

Includes optional OpenTelemetry trace context propagation for
distributed tracing across NATS message boundaries.

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

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_NATS_URL = os.getenv("NATS_URL", "")


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
# Trace-propagating publish / subscribe helpers
# -----------------------------------------------------------------------

# Graceful import — tracing is opt-in
try:
    from opentelemetry.trace import SpanKind
    from services.common.tracing import (
        inject_trace_headers,
        extract_trace_headers,
        trace_nats_message,
        get_tracer,
    )
    _trace_available = True
except (ImportError, Exception):
    _trace_available = False


async def traced_publish(
    nc: Any,
    subject: str,
    payload: bytes,
    headers: dict[str, str] | None = None,
) -> None:
    """Publish a NATS message with trace context propagation.

    Injects the current W3C ``traceparent`` header into the NATS message
    headers so downstream consumers can link their spans to the producer.

    Falls back to a plain ``nc.publish()`` when tracing is not available.

    Args:
        nc: A connected NATS client.
        subject: NATS subject to publish to.
        payload: Message body as bytes.
        headers: Optional existing headers (trace context will be merged in).
    """
    hdrs = dict(headers) if headers else {}

    if _trace_available:
        try:
            hdrs = inject_trace_headers(hdrs)
        except Exception as exc:
            logger.debug("Failed to inject trace headers: %s", exc)

    await nc.publish(subject, payload, headers=hdrs or None)


def make_traced_callback(
    service_name: str,
    subject: str,
    handler: Callable,
) -> Callable:
    """Wrap a NATS subscription callback with trace context extraction.

    When a message arrives, the wrapper extracts ``traceparent`` from the
    message headers, creates a child span, and calls *handler* inside that
    span context.  The handler receives the original NATS message.

    Falls back to calling *handler* directly when tracing is not available.

    Usage::

        async def on_message(msg):
            ...

        await nc.subscribe(
            "compute.nodes.heartbeat",
            cb=make_traced_callback("my-service", "compute.nodes.heartbeat", on_message),
        )
    """
    if not _trace_available:
        return handler

    async def _wrapped(msg: Any) -> None:
        # NATS headers are a dict-like; coerce to plain dict for propagator.
        msg_headers: dict[str, str] = {}
        if hasattr(msg, "headers") and msg.headers:
            msg_headers = dict(msg.headers)

        ctx = extract_trace_headers(msg_headers)
        tracer = get_tracer(service_name)

        with tracer.start_as_current_span(
            f"nats.receive {subject}",
            context=ctx,
            kind=SpanKind.CONSUMER if _trace_available else None,
            attributes={
                "messaging.system": "nats",
                "messaging.destination": subject,
                "messaging.operation": "receive",
            },
        ) as span:
            if span is not None:
                if ctx is not None:
                    span.set_attribute("messaging.trace_propagated", True)
                if hasattr(msg, "data") and msg.data is not None:
                    span.set_attribute("message.size", len(msg.data))
            await handler(msg)

    return _wrapped

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



# -----------------------------------------------------------------------
# CGP publish convenience
# -----------------------------------------------------------------------

async def publish_cgp(
    cgp_packet: dict[str, Any],
    subject: str,
    nats_url: str = "",
) -> bool:
    """Publish a CGP v0.2 packet to a NATS subject (best-effort).

    Wraps :func:`create_nats_connection` for one-shot publish-and-drain.
    Returns True on success, False if skipped or failed.

    Args:
        cgp_packet: CGP v0.2 packet dict (must be JSON-serializable).
        subject: NATS subject to publish to (e.g. ``tokenism.prosodic.bpm.v1``).
        nats_url: NATS server URL. Falls back to ``NATS_URL`` env var.
            Raises ValueError if neither is set.
    """
    if not nats_url:
        nats_url = os.getenv("NATS_URL", "")
    if not nats_url:
        logger.warning("publish_cgp: NATS_URL not set — skipping publish to %s", subject)
        return False

    try:
        async with nats_connection(name="cgp-publisher") as nc:
            await traced_publish(nc, subject, json.dumps(cgp_packet).encode("utf-8"))
        return True
    except Exception as exc:
        logger.warning("publish_cgp failed on %s: %s", subject, exc)
        return False

__all__ = [
    "NatsConnectionConfig",
    "create_nats_connection",
    "nats_connection",
    "make_logging_error_cb",
    "make_logging_disconnected_cb",
    "make_logging_reconnected_cb",
    "traced_publish",
    "make_traced_callback",
    "publish_cgp",
    "DEFAULT_NATS_URL",
]
