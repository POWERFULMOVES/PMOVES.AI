"""
CHIT Bus Cache Invalidation for the Semantic Cache (PMOVES.AI).

This module implements cache invalidation via the CHIT Geometry Bus using
NATS JetStream event distribution. It provides five integrated components:

1. **NATS Invalidation Subscriber** -- Listens on ``cache.invalidate.*``
   subjects and routes flush/delete operations to the pgvector-backed
   semantic cache.

2. **Model Change Listener** -- Reacts to ``model.registry.changed``
   events by emitting targeted invalidations for updated models.

3. **Embedding Model Hot-Swap Handler** -- Compares embedding dimensions
   when ``embedding.model.changed`` is received and flushes stale entries
   when the dimension changes.

4. **Manual Invalidation Endpoint** -- Exposes ``POST /admin/cache/invalidate``
   for operators to trigger invalidation on demand.

5. **Circuit Breaker Integration** -- Wraps pgvector cache operations in a
   3-state circuit breaker (CLOSED / OPEN / HALF_OPEN).  After 3 consecutive
   failures the breaker opens; all requests passthrough to TensorZero.  After
   a 30 s timeout a single probe request is allowed (half-open).

Fail-open guarantee
-------------------
Any NATS error -- connection loss, malformed payload, subject mismatch -- is
logged and swallowed.  Cache lookups continue to work; on failure they simply
passthrough to TensorZero, never blocking inference.

NATS subjects (CHIT Geometry Bus)
----------------------------------
==================================== ================================
Subject                              Purpose
==================================== ================================
``geometry.cgp.v1``                  CGP packets
``tokenism.cgp.ready.v1``            Tokenism readiness events
``tokenism.prosodic.bpm.v1``         BPM / prosodic events
``chat.*``                           Chat routing
``p7.nats.launch`` / ``.session``    Room lifecycle
``cache.invalidate.*``               **This module's inbound subject**
``model.registry.changed``           Model registry updates
``embedding.model.changed``          Embedding model hot-swap events
==================================== ================================

NATS message format
-------------------
.. code-block:: json

    {
      "event": "cache.invalidate",
      "type": "model|dimension|all|hash",
      "target": "glm-4-plus|1024|*|abc123...",
      "source": "model_registry|embedding_gateway|admin",
      "timestamp": "2026-07-09T12:00:00Z",
      "agent": "semantic-cache-proxy"
    }

Environment variables
---------------------
+-------------------------+-------------------------------------------+
| Variable                | Description                               |
+=========================+===========================================+
| ``NATS_URL``            | NATS server URL (default:                |
|                         | ``nats://nats:pmoves@nats:4222``)         |
+-------------------------+-------------------------------------------+
| ``NATS_INVALIDATE_SUB`` | Inbound subject (default:                |
|                         | ``cache.invalidate.*``)                   |
+-------------------------+-------------------------------------------+
| ``CACHE_TABLE``         | Supabase table name (default:             |
|                         | ``llm_semantic_cache``)                   |
+-------------------------+-------------------------------------------+
| ``CB_FAILURE_THRESHOLD``| Failures before opening breaker (def: 3)  |
+-------------------------+-------------------------------------------+
| ``CB_TIMEOUT_SECONDS``  | Seconds before half-open probe (def: 30)  |
+-------------------------+-------------------------------------------+

Usage
-----
::

    import asyncio
    from pmoves.services.semantic_cache.chit_invalidation import CHITInvalidator

    invalidator = CHITInvalidator()
    asyncio.run(invalidator.start())

    # ... later ...
    asyncio.run(invalidator.stop())

Dependencies
------------
- ``nats-py`` (NATS JetStream async client)
- ``prometheus_client`` (metrics, from sibling ``metrics.py``)
- ``structlog`` (structured logging, optional -- falls back to stdlib)

Author
------
PMOVES Semantic Cache Team (issue #1427)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Protocol

# ---------------------------------------------------------------------------
# Optional dependencies -- fail gracefully if absent
# ---------------------------------------------------------------------------

try:
    import structlog

    _logger = structlog.get_logger("chit_invalidator")
except Exception:  # pragma: no cover
    _logger = logging.getLogger("chit_invalidator")

try:
    from nats.aio.client import Client as NATS
    from nats.aio.subscription import Subscription
    from nats.js.api import ConsumerConfig

    _HAS_NATS = True
except Exception:  # pragma: no cover
    NATS = None  # type: ignore[misc, assignment]
    Subscription = None  # type: ignore[misc, assignment]
    ConsumerConfig = None  # type: ignore[misc, assignment]
    _HAS_NATS = False

# ---------------------------------------------------------------------------
# Metrics (from sibling module -- created by issue #1427)
# ---------------------------------------------------------------------------

try:
    from pmoves.services.semantic_cache.metrics import (
        cache_entries_total,
        cache_evictions_total,
        cache_invalidations_total,
    )
except Exception:
    # Fallback stubs when metrics module is unavailable (e.g. unit tests)
    class _StubCounter:
        def labels(self, **kw: Any) -> "_StubCounter":
            return self

        def inc(self, amount: float = 1) -> None:
            pass

    class _StubGauge:
        def set(self, value: float) -> None:
            pass

    cache_entries_total = _StubGauge()
    cache_evictions_total = _StubCounter()
    cache_invalidations_total = _StubCounter()

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

LOG_FMT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger: logging.Logger | Any = _logger


def _sl(
    level: str,
    msg: str,
    **kwargs: Any,
) -> None:
    """Structured log helper compatible with stdlib *and* structlog.

    Keyword arguments are serialised as ``key=value`` pairs and appended
    to the message string so the call works regardless of which logger is
    active.
    """
    if kwargs:
        pairs = " ".join(f"{k}={v!r}" for k, v in kwargs.items())
        msg = f"{msg} | {pairs}"
    fn = getattr(logger, level, logger.info)
    fn(msg)


def _iso_now() -> str:
    """Return UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class _Settings:
    """Runtime configuration loaded from environment."""

    NATS_URL: str = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
    NATS_INVALIDATE_SUB: str = os.getenv(
        "NATS_INVALIDATE_SUB", "cache.invalidate.*"
    )
    NATS_MODEL_CHANGED_SUB: str = os.getenv(
        "NATS_MODEL_CHANGED_SUB", "model.registry.changed"
    )
    NATS_EMBEDDING_CHANGED_SUB: str = os.getenv(
        "NATS_EMBEDDING_CHANGED_SUB", "embedding.model.changed"
    )
    CACHE_TABLE: str = os.getenv("CACHE_TABLE", "llm_semantic_cache")
    CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    CB_TIMEOUT_SECONDS: float = float(os.getenv("CB_TIMEOUT_SECONDS", "30"))
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    NATS_RECONNECT_ATTEMPTS: int = int(
        os.getenv("NATS_RECONNECT_ATTEMPTS", "10")
    )
    NATS_RECONNECT_DELAY: float = float(
        os.getenv("NATS_RECONNECT_DELAY", "2.0")
    )


settings = _Settings()


# ---------------------------------------------------------------------------
# Circuit Breaker (3-state: CLOSED / OPEN / HALF_OPEN)
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing; passthrough to TensorZero
    HALF_OPEN = "half_open" # Probing with single request


class CircuitBreaker:
    """Simple 3-state circuit breaker for pgvector cache operations.

    * **CLOSED**   -- requests go to cache; failures are counted.
    * **OPEN**     -- after *threshold* consecutive failures; all requests
      passthrough to TensorZero.
    * **HALF_OPEN** -- after *timeout_seconds* in OPEN; one probe request
      is allowed.  Success -> CLOSED, failure -> OPEN.
    """

    def __init__(
        self,
        failure_threshold: int = settings.CB_FAILURE_THRESHOLD,
        timeout_seconds: float = settings.CB_TIMEOUT_SECONDS,
        name: str = "pgvector-cache",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.name = name
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self._state == CircuitState.HALF_OPEN

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                _sl("info", "circuit-breaker.half-open.success", breaker=self.name,
                    action="closing",
                )
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._last_failure_time = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                _sl(
                    "warning",
                    "circuit-breaker.half-open.failure",
                    breaker=self.name,
                    action="reopening",
                )
                self._state = CircuitState.OPEN
                return

            if self._failures >= self.failure_threshold:
                _sl(
                    "error",
                    "circuit-breaker.tripped",
                    breaker=self.name,
                    failures=self._failures,
                    threshold=self.failure_threshold,
                    new_state="OPEN",
                )
                self._state = CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Return *True* if the caller may attempt cache operation."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                return True  # one request allowed

            # OPEN -- check if timeout elapsed -> transition to HALF_OPEN
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.timeout_seconds:
                    _sl(
                        "info",
                        "circuit-breaker.timeout.elapsed",
                        breaker=self.name,
                        elapsed=elapsed,
                        new_state="HALF_OPEN",
                    )
                    self._state = CircuitState.HALF_OPEN
                    return True

            return False

    async def call[
        T
    ](
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute *fn* under circuit breaker protection.

        If the breaker is OPEN and timeout has not elapsed, raises
        ``CircuitBreakerOpen`` so the caller can passthrough to TensorZero.
        """
        if not await self.can_execute():
            raise CircuitBreakerOpen(self.name)

        try:
            result = await fn(*args, **kwargs)
            await self.record_success()
            return result
        except Exception:
            await self.record_failure()
            raise


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is OPEN (cache unavailable)."""

    def __init__(self, breaker_name: str) -> None:
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN")
        self.breaker_name = breaker_name


# ---------------------------------------------------------------------------
# CacheStore protocol (duck-type compatible with cache_store.py)
# ---------------------------------------------------------------------------


class CacheStore(Protocol):
    """Minimal protocol matching the CacheStore from cache_store.py."""

    async def lookup(
        self,
        embedding: list[float],
        messages_hash: str,
        model: str,
        threshold: float,
        top_k: int = 1,
    ) -> Optional[dict[str, Any]]:
        ...

    async def store(
        self,
        embedding: list[float],
        messages_hash: str,
        response: dict[str, Any],
        model: str,
    ) -> None:
        ...

    async def increment_hit(self, entry_id: str) -> None:
        ...

    async def count(self) -> int:
        ...

    # -- invalidation extensions (expected on CacheStore) --

    async def flush_model(self, model_name: str) -> int:
        """Delete all entries for *model_name*; return rows deleted."""
        ...

    async def flush_dimension(self, dimension: int) -> int:
        """Delete all entries with embedding *dimension*; return rows deleted."""
        ...

    async def flush_all(self) -> int:
        """Delete **all** cache entries; return rows deleted."""
        ...

    async def delete_by_hash(self, query_hash: str) -> int:
        """Delete entry matching *query_hash*; return rows deleted."""
        ...


# ---------------------------------------------------------------------------
# NATS message model
# ---------------------------------------------------------------------------


@dataclass
class InvalidationEvent:
    """Normalised representation of a cache invalidation message."""

    event: str = "cache.invalidate"
    type: str = "all"                # model | dimension | all | hash
    target: str = "*"
    source: str = "unknown"          # model_registry | embedding_gateway | admin
    timestamp: str = field(default_factory=_iso_now)
    agent: str = "semantic-cache-proxy"

    @classmethod
    def from_payload(cls, payload: bytes) -> "InvalidationEvent":
        """Parse JSON payload; return event or raise ValueError."""
        data = json.loads(payload.decode("utf-8"))
        return cls(
            event=data.get("event", "cache.invalidate"),
            type=data.get("type", "all"),
            target=str(data.get("target", "*")),
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", _iso_now()),
            agent=data.get("agent", "semantic-cache-proxy"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "type": self.type,
            "target": self.target,
            "source": self.source,
            "timestamp": self.timestamp,
            "agent": self.agent,
        }


# ---------------------------------------------------------------------------
# CHITInvalidator -- the main class
# ---------------------------------------------------------------------------


class CHITInvalidator:
    """CHIT Geometry Bus cache invalidation coordinator.

    Manages NATS subscriptions, routes invalidation events to the cache
    store, exposes an admin endpoint, and integrates with the circuit
    breaker for resilient cache operations.
    """

    def __init__(
        self,
        cache_store: Optional[CacheStore] = None,
        nats_url: str = settings.NATS_URL,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self._cache = cache_store
        self._nats_url = nats_url
        self._nc: Any = None
        self._js: Any = None
        self._subs: list[Any] = []
        self._cb = circuit_breaker or CircuitBreaker(
            failure_threshold=settings.CB_FAILURE_THRESHOLD,
            timeout_seconds=settings.CB_TIMEOUT_SECONDS,
            name="pgvector-cache",
        )
        self._shutdown_event = asyncio.Event()
        self._current_embedding_model: str = ""
        self._current_embedding_dim: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to NATS, subscribe to all relevant subjects, begin serving."""
        if not _HAS_NATS:
            _sl("error", "nats.unavailable", message="nats-py not installed; CHIT invalidation disabled",
            )
            return

        await self._connect_nats()
        await self._subscribe_invalidation()
        await self._subscribe_model_registry()
        await self._subscribe_embedding_changes()

        _sl("info", "chit_invalidator.started", nats_url=self._nats_url,
            subscriptions=len(self._subs),
        )

    async def stop(self) -> None:
        """Unsubscribe, drain NATS connection, and clean up."""
        self._shutdown_event.set()
        for sub in self._subs:
            try:
                await sub.unsubscribe()
            except Exception as exc:
                _sl("debug", "unsubscribe.error", exc=str(exc))
        self._subs.clear()

        if self._nc:
            try:
                await self._nc.drain()
                await self._nc.close()
            except Exception as exc:
                _sl("debug", "nats.close.error", exc=str(exc))
            finally:
                self._nc = None
                self._js = None

        logger.info("chit_invalidator.stopped")

    # ------------------------------------------------------------------
    # NATS connection management (async, with reconnect)
    # ------------------------------------------------------------------

    async def _connect_nats(self) -> None:
        """Establish NATS connection with retry/backoff."""
        self._nc = NATS()

        async def _on_disconnect(cb_nc: Any) -> None:
            _sl("warning", "nats.disconnected", status=cb_nc.last_error)

        async def _on_reconnect(cb_nc: Any) -> None:
            _sl("info", "nats.reconnected", server=cb_nc.connected_url.netloc)

        options: dict[str, Any] = {
            "servers": self._nats_url,
            "max_reconnect_attempts": settings.NATS_RECONNECT_ATTEMPTS,
            "reconnect_time_wait": settings.NATS_RECONNECT_DELAY,
            "disconnected_cb": _on_disconnect,
            "reconnected_cb": _on_reconnect,
            "error_cb": lambda exc: _sl("error", "nats.error", exc=str(exc)
            ),
        }

        last_exc: Optional[Exception] = None
        for attempt in range(1, settings.NATS_RECONNECT_ATTEMPTS + 1):
            try:
                await self._nc.connect(**options)
                self._js = self._nc.jetstream()
                _sl("info", "nats.connected", server=self._nc.connected_url.netloc,
                    attempt=attempt,
                )
                return
            except Exception as exc:
                last_exc = exc
                _sl("warning", "nats.connect.retry", attempt=attempt,
                    max_attempts=settings.NATS_RECONNECT_ATTEMPTS,
                    exc=str(exc),
                )
                await asyncio.sleep(settings.NATS_RECONNECT_DELAY)

        _sl("error", "nats.connect.failed", attempts=settings.NATS_RECONNECT_ATTEMPTS,
            exc=str(last_exc),
        )
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Subscription setup
    # ------------------------------------------------------------------

    async def _subscribe_invalidation(self) -> None:
        """Subscribe to ``cache.invalidate.*`` pattern."""
        if not self._js:
            return
        sub = await self._js.subscribe(
            settings.NATS_INVALIDATE_SUB,
            cb=self._on_invalidation_message,
            durable="chit-invalidator",
            config=ConsumerConfig(deliver_policy="new"),
        )
        self._subs.append(sub)
        _sl("info", "nats.subscribed", subject=settings.NATS_INVALIDATE_SUB,
            durable="chit-invalidator",
        )

    async def _subscribe_model_registry(self) -> None:
        """Subscribe to ``model.registry.changed`` events."""
        if not self._js:
            return
        sub = await self._js.subscribe(
            settings.NATS_MODEL_CHANGED_SUB,
            cb=self._on_model_registry_message,
            durable="chit-model-listener",
            config=ConsumerConfig(deliver_policy="new"),
        )
        self._subs.append(sub)
        _sl("info", "nats.subscribed", subject=settings.NATS_MODEL_CHANGED_SUB,
            durable="chit-model-listener",
        )

    async def _subscribe_embedding_changes(self) -> None:
        """Subscribe to ``embedding.model.changed`` events."""
        if not self._js:
            return
        sub = await self._js.subscribe(
            settings.NATS_EMBEDDING_CHANGED_SUB,
            cb=self._on_embedding_changed_message,
            durable="chit-embedding-listener",
            config=ConsumerConfig(deliver_policy="new"),
        )
        self._subs.append(sub)
        _sl("info", "nats.subscribed", subject=settings.NATS_EMBEDDING_CHANGED_SUB,
            durable="chit-embedding-listener",
        )

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _on_invalidation_message(self, msg: Any) -> None:
        """Handle incoming ``cache.invalidate.*`` messages."""
        try:
            event = InvalidationEvent.from_payload(msg.data)
            _sl("info", "invalidation.received", type=event.type,
                target=event.target,
                source=event.source,
            )
            await self._process_invalidation(event)
            await msg.ack()
        except Exception as exc:
            _sl("error", "invalidation.handler.error", exc=str(exc),
                action="nacking",
            )
            # Do not re-raise -- fail-open
            try:
                await msg.nak()
            except Exception:
                pass

    async def _on_model_registry_message(self, msg: Any) -> None:
        """Handle ``model.registry.changed`` -- emit cache invalidation."""
        try:
            data = json.loads(msg.data.decode("utf-8"))
            model_name = data.get("model_name", "")
            action = data.get("action", "")  # updated | deleted

            if not model_name:
                await msg.ack()
                return

            _sl("info", "model.registry.changed", model=model_name,
                action=action,
            )

            if action in ("updated", "deleted"):
                # Emit invalidation for the affected model
                await self._publish_invalidation(
                    inv_type="model",
                    target=model_name,
                    source="model_registry",
                )
                cache_invalidations_total.labels(
                    source="model_change"
                ).inc()

            await msg.ack()
        except Exception as exc:
            _sl("error", "model.registry.error", exc=str(exc))
            try:
                await msg.nak()
            except Exception:
                pass

    async def _on_embedding_changed_message(self, msg: Any) -> None:
        """Handle ``embedding.model.changed`` -- hot-swap dimension check."""
        try:
            data = json.loads(msg.data.decode("utf-8"))
            new_model = data.get("model_name", "")
            new_dim = data.get("dimensions", 0)

            _sl("info", "embedding.model.changed", new_model=new_model,
                new_dimensions=new_dim,
                old_model=self._current_embedding_model,
                old_dimensions=self._current_embedding_dim,
            )

            if (
                self._current_embedding_dim
                and self._current_embedding_dim != new_dim
            ):
                # Dimension changed -- flush entries with old dimension
                _sl("warning", "embedding.dimension.changed", old_model=self._current_embedding_model,
                    old_dim=self._current_embedding_dim,
                    new_model=new_model,
                    new_dim=new_dim,
                )
                await self._publish_invalidation(
                    inv_type="dimension",
                    target=str(self._current_embedding_dim),
                    source="embedding_gateway",
                )
                cache_invalidations_total.labels(
                    source="embedding_swap"
                ).inc()

            self._current_embedding_model = new_model
            self._current_embedding_dim = new_dim

            await msg.ack()
        except Exception as exc:
            _sl("error", "embedding.changed.error", exc=str(exc))
            try:
                await msg.nak()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Invalidation routing
    # ------------------------------------------------------------------

    async def _process_invalidation(self, event: InvalidationEvent) -> None:
        """Route an invalidation event to the correct cache store method."""
        if self._cache is None:
            _sl("warning", "invalidation.no_cache", message="CacheStore not attached; skipping",
            )
            return

        handler_map: dict[str, Callable[..., Awaitable[int]]] = {
            "model": self._handle_flush_model,
            "dimension": self._handle_flush_dimension,
            "all": self._handle_flush_all,
            "hash": self._handle_delete_hash,
        }

        handler = handler_map.get(event.type)
        if handler is None:
            _sl("warning", "invalidation.unknown_type", type=event.type,
                known=list(handler_map.keys()),
            )
            return

        try:
            deleted = await handler(event.target)
            cache_evictions_total.labels(reason="invalidation").inc(
                amount=deleted
            )
            cache_invalidations_total.labels(source=event.source).inc()
            _sl("info", "invalidation.completed", type=event.type,
                target=event.target,
                deleted=deleted,
            )
        except CircuitBreakerOpen:
            _sl("warning", "invalidation.circuit_open", type=event.type,
                target=event.target,
                action="passthrough_to_tensorzero",
            )
        except Exception as exc:
            _sl("error", "invalidation.execution.error", type=event.type,
                target=event.target,
                exc=str(exc),
            )

    # -- typed handlers ------------------------------------------------

    async def _handle_flush_model(self, model_name: str) -> int:
        """Flush all entries for *model_name* via circuit breaker."""
        if self._cache is None:
            return 0
        return await self._cb.call(self._cache.flush_model, model_name)

    async def _handle_flush_dimension(self, dim_str: str) -> int:
        """Flush all entries with embedding dimension *dim_str*."""
        if self._cache is None:
            return 0
        dimension = int(dim_str)
        return await self._cb.call(
            self._cache.flush_dimension, dimension
        )

    async def _handle_flush_all(self, _: str) -> int:
        """Flush the entire cache."""
        if self._cache is None:
            return 0
        return await self._cb.call(self._cache.flush_all)

    async def _handle_delete_hash(self, query_hash: str) -> int:
        """Delete a specific entry by query hash."""
        if self._cache is None:
            return 0
        return await self._cb.call(
            self._cache.delete_by_hash, query_hash
        )

    # ------------------------------------------------------------------
    # Publishing (outbound NATS messages)
    # ------------------------------------------------------------------

    async def _publish_invalidation(
        self,
        inv_type: str,
        target: str,
        source: str,
    ) -> None:
        """Publish an invalidation request to the CHIT bus."""
        if not self._nc or not self._nc.is_connected:
            _sl("warning", "nats.not_connected", action="skip_publish",
                type=inv_type,
                target=target,
            )
            return

        event = InvalidationEvent(
            type=inv_type,
            target=target,
            source=source,
        )
        payload = json.dumps(event.to_dict()).encode("utf-8")
        subject = f"cache.invalidate.{inv_type}"

        try:
            await self._nc.publish(subject, payload)
            _sl("info", "invalidation.published", subject=subject,
                type=inv_type,
                target=target,
            )
        except Exception as exc:
            _sl("error", "invalidation.publish.error", subject=subject,
                exc=str(exc),
            )

    # ------------------------------------------------------------------
    # Manual invalidation endpoint
    # ------------------------------------------------------------------

    async def handle_admin_invalidate(
        self,
        request_body: bytes,
        auth_header: Optional[str] = None,
    ) -> dict[str, Any]:
        """Handle ``POST /admin/cache/invalidate`` requests.

        Expected JSON body::

            {"type": "model|dimension|all|hash", "target": "..."}

        Returns a status dict with ``deleted`` count or error info.
        """
        # -- auth check ------------------------------------------------
        if settings.ADMIN_API_KEY:
            expected = f"Bearer {settings.ADMIN_API_KEY}"
            if auth_header != expected:
                _sl("warning", "admin.invalidate.unauthorized", auth_header_provided=bool(auth_header),
                )
                return {
                    "status": "error",
                    "code": 401,
                    "message": "Unauthorized -- invalid or missing API key",
                }

        # -- parse body ------------------------------------------------
        try:
            body = json.loads(request_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return {
                "status": "error",
                "code": 400,
                "message": f"Invalid JSON body: {exc}",
            }

        inv_type = body.get("type", "")
        target = body.get("target", "")

        valid_types = {"model", "dimension", "all", "hash"}
        if inv_type not in valid_types:
            return {
                "status": "error",
                "code": 400,
                "message": (
                    f"Invalid type '{inv_type}'. "
                    f"Must be one of: {', '.join(sorted(valid_types))}"
                ),
            }

        if inv_type != "all" and not target:
            return {
                "status": "error",
                "code": 400,
                "message": f"Field 'target' is required for type '{inv_type}'",
            }

        # -- execute ---------------------------------------------------
        event = InvalidationEvent(
            type=inv_type,
            target=target or "*",
            source="admin",
        )

        try:
            await self._process_invalidation(event)
            cache_invalidations_total.labels(source="manual").inc()
            _sl("info", "admin.invalidate.success", type=inv_type,
                target=target,
            )
            return {
                "status": "ok",
                "code": 200,
                "invalidated": {
                    "type": inv_type,
                    "target": target,
                },
            }
        except CircuitBreakerOpen:
            return {
                "status": "degraded",
                "code": 503,
                "message": (
                    "Circuit breaker OPEN -- cache unavailable; "
                    "requests passthrough to TensorZero"
                ),
            }
        except Exception as exc:
            _sl("error", "admin.invalidate.error", type=inv_type,
                target=target,
                exc=str(exc),
            )
            return {
                "status": "error",
                "code": 500,
                "message": str(exc),
            }

    # ------------------------------------------------------------------
    # Circuit breaker passthrough helpers
    # ------------------------------------------------------------------

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Access the internal circuit breaker (for health checks)."""
        return self._cb

    @property
    def cache_store(self) -> Optional[CacheStore]:
        """Access the attached cache store."""
        return self._cache

    def attach_cache_store(self, store: CacheStore) -> None:
        """Attach (or swap) the CacheStore at runtime."""
        self._cache = store
        logger.info("cache_store.attached")

    # ------------------------------------------------------------------
    # Health / status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a snapshot of the invalidator's current state."""
        return {
            "nats_connected": (
                self._nc.is_connected if self._nc else False
            ),
            "circuit_breaker": {
                "state": self._cb.state.value,
                "failures": self._cb._failures,
                "threshold": self._cb.failure_threshold,
                "timeout_seconds": self._cb.timeout_seconds,
            },
            "subscriptions": len(self._subs),
            "current_embedding_model": self._current_embedding_model,
            "current_embedding_dim": self._current_embedding_dim,
            "cache_store_attached": self._cache is not None,
            "timestamp": _iso_now(),
        }
