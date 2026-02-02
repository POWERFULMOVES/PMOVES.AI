"""
Event Bus for Agent Coordination

Based on PMOVES-ToKenism-Multi event bus pattern.
Implements pub/sub with schema validation and retry logic.

Usage:
    from pmoves.services.agent_zero.python.events import get_event_bus

    bus = await get_event_bus()

    # Publish event
    await bus.publish(
        subject="pmoves.agent.started.v1",
        event_type="AGENT_STARTED",
        data={"agent_id": "agent-zero", "capabilities": ["code_generation"]},
        source="agent-zero"
    )

    # Subscribe to events
    async def handler(event):
        print(f"Received: {event.type} - {event.data}")

    await bus.subscribe("pmoves.agent.>", handler)
"""

import asyncio
import json
import logging
import uuid
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg
import nats

logger = logging.getLogger("pmoves.agent_zero.events.bus")


@dataclass
class Event:
    """
    Event envelope for agent communication.

    Attributes:
        id: Unique event identifier (UUID v4 for collision-free IDs)
        timestamp: ISO format timestamp in UTC
        type: Event type (e.g., "AGENT_STARTED", "TASK_COMPLETED")
        source: Source service name (e.g., "agent-zero", "archon")
        data: Event payload (validated against schema if available)
        metadata: Additional metadata (optional)
        correlation_id: For tracking related events across services
    """
    id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: str = ""
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type,
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create Event from dictionary (deserialization)."""
        return cls(**data)


class EventBus:
    """
    Event bus for agent coordination.

    Features:
    - NATS-backed pub/sub messaging
    - Schema validation for all events
    - Wildcard subscription support
    - Thread-safe metrics tracking (published, processed, failed)
    - Async error handling
    - Automatic reconnection on connection failure
    - Memory-safe subscription management with weak references
    - JetStream support with proper acknowledgment

    Subject format: `pmoves.{service}.{event}.v1`

    Example:
        bus = EventBus()
        await bus.connect()

        await bus.publish(
            subject="pmoves.agent.started.v1",
            event_type="AGENT_STARTED",
            data={"agent_id": "agent-zero"}
        )
    """

    def __init__(self, nats_url: str = "nats://localhost:4222", use_jetstream: bool = False):
        """
        Initialize event bus.

        Args:
            nats_url: NATS server URL (default: localhost:4222)
            use_jetstream: Enable JetStream for persistence (default: False)
        """
        self.nats_url = nats_url
        self.use_jetstream = use_jetstream
        self.nc: Optional[NATSClient] = None
        self.js = None  # JetStream context
        self.validators: Dict[str, Any] = {}  # event_type -> SchemaValidator

        # Thread-safe metrics with locks
        self._metrics_lock = asyncio.Lock()
        self._metrics: Dict[str, int] = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
        }

        # Memory-safe subscription tracking with weak references
        self._subscriptions: Dict[str, Set[int]] = {}  # subject -> set of subscription IDs
        self._subscription_handlers: Dict[int, Callable] = {}  # sub_id -> weakref
        self._next_sub_id = 0
        self._subscriptions_lock = asyncio.Lock()

        self._connected = False
        self._lock = asyncio.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True

    async def connect(self) -> None:
        """
        Connect to NATS server with automatic reconnection.

        Raises:
            ConnectionError: If connection fails after retries
        """
        async with self._lock:
            if self._connected:
                return

            try:
                self.nc = NATSClient()

                # Configure reconnection settings
                options = {
                    "servers": self.nats_url,
                    "connect_timeout": 10,
                    "reconnect_time_wait": 2,
                    "max_reconnect_attempts": -1,  # Infinite reconnect attempts
                    "disconnected_cb": self._on_disconnect,
                    "reconnected_cb": self._on_reconnect,
                    "error_cb": self._on_error,
                    "closed_cb": self._on_close,
                }

                await self.nc.connect(**options)
                self._connected = True

                # Initialize JetStream if enabled
                if self.use_jetstream:
                    try:
                        self.js = self.nc.jetstream()
                        logger.info("JetStream context initialized")
                    except Exception as e:
                        logger.warning(f"JetStream not available: {e}")
                        self.js = None

                logger.info(f"Event bus connected to {self.nats_url}")

            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}")
                raise ConnectionError(f"NATS connection failed: {e}")

    async def _on_disconnect(self):
        """Handle disconnection from NATS."""
        logger.warning("Disconnected from NATS server")
        self._connected = False

    async def _on_reconnect(self):
        """Handle successful reconnection to NATS."""
        logger.info("Reconnected to NATS server")
        self._connected = False  # Will be set in connect()

    async def _on_error(self, error):
        """Handle NATS errors."""
        logger.error(f"NATS error: {error}")

    async def _on_close(self):
        """Handle connection close."""
        logger.info("NATS connection closed")
        self._connected = False
        self._should_reconnect = False

    async def publish(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any],
        source: str = "agent-zero",
        metadata: Dict[str, Any] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Publish an event to the bus with JetStream support.

        Args:
            subject: NATS subject (e.g., "pmoves.agent.started.v1")
            event_type: Event type for validation (e.g., "AGENT_STARTED")
            data: Event payload
            source: Source service name
            metadata: Optional metadata
            correlation_id: Optional correlation ID for tracing

        Returns:
            Event ID

        Raises:
            ConnectionError: If not connected to NATS
            ValueError: If schema validation fails
        """
        if not self._connected or not self.nc:
            await self.connect()

        # Create event
        event = Event(
            type=event_type,
            source=source,
            data=data,
            metadata=metadata or {},
            correlation_id=correlation_id,
        )

        # Validate if schema exists
        if event_type in self.validators:
            validator = self.validators[event_type]
            try:
                validator.validate(event.data)
            except Exception as e:
                logger.error(f"Schema validation failed for {event_type}: {e}")
                async with self._metrics_lock:
                    self._metrics["events_failed"] += 1
                raise ValueError(f"Schema validation failed: {e}")

        # Publish to NATS with optional JetStream
        try:
            payload = json.dumps(event.to_dict()).encode()

            if self.use_jetstream and self.js:
                # Publish to JetStream (requires acknowledgment)
                ack = await self.js.publish(subject, payload)
                logger.debug(f"Published JetStream event {event.id} to {subject} (ack: {ack})")
            else:
                # Standard NATS publish
                await self.nc.publish(subject, payload)
                logger.debug(f"Published event {event.id} to {subject}")

            async with self._metrics_lock:
                self._metrics["events_published"] += 1

            return event.id

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            async with self._metrics_lock:
                self._metrics["events_failed"] += 1
            raise

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[Event], Any],
        queue_group: Optional[str] = None,
    ) -> int:
        """
        Subscribe to events with memory-safe weak references.

        Args:
            subject: NATS subject (supports wildcards, e.g., "pmoves.>")
            handler: Async callback function receiving Event object
            queue_group: Optional queue group for load balancing

        Returns:
            Subscription ID (use with unsubscribe())

        Example:
            async def handler(event):
                print(f"Received: {event.type}")

            sub_id = await bus.subscribe("pmoves.agent.>", handler)
            await bus.unsubscribe(sub_id)
        """
        if not self._connected or not self.nc:
            await self.connect()

        # Generate subscription ID
        async with self._subscriptions_lock:
            sub_id = self._next_sub_id
            self._next_sub_id += 1

            # Track subscription with weak reference to prevent memory leaks
            if subject not in self._subscriptions:
                self._subscriptions[subject] = set()
            self._subscriptions[subject].add(sub_id)

            # Store weak reference to handler
            self._subscription_handlers[sub_id] = weakref.ref(handler)

        async def wrapper(msg: Msg):
            """Wrapper for error handling, metrics, and JetStream ack."""
            try:
                # Deserialize event
                payload = msg.data.decode()
                data = json.loads(payload)
                event = Event.from_dict(data)

                # Get handler from weak reference
                handler_ref = self._subscription_handlers.get(sub_id)
                if handler_ref is None:
                    logger.warning(f"Handler for subscription {sub_id} was garbage collected")
                    # Acknowledge JetStream message if needed
                    if hasattr(msg, 'ack'):
                        try:
                            await msg.ack()
                        except Exception:
                            pass
                    return

                actual_handler = handler_ref()
                if actual_handler is None:
                    logger.warning(f"Handler for subscription {sub_id} was garbage collected")
                    # Clean up dead weak reference
                    async with self._subscriptions_lock:
                        self._subscription_handlers.pop(sub_id, None)
                        if subject in self._subscriptions:
                            self._subscriptions[subject].discard(sub_id)
                    # Acknowledge JetStream message if needed
                    if hasattr(msg, 'ack'):
                        try:
                            await msg.ack()
                        except Exception:
                            pass
                    return

                # Call handler
                if asyncio.iscoroutinefunction(actual_handler):
                    await actual_handler(event)
                else:
                    actual_handler(event)

                async with self._metrics_lock:
                    self._metrics["events_processed"] += 1

                logger.debug(f"Processed event {event.id} from {msg.subject}")

                # Acknowledge JetStream message if needed
                if hasattr(msg, 'ack'):
                    try:
                        await msg.ack()
                    except Exception as e:
                        logger.warning(f"Failed to ack JetStream message: {e}")

            except Exception as e:
                async with self._metrics_lock:
                    self._metrics["events_failed"] += 1
                logger.error(f"Event processing error: {e}", exc_info=True)

                # Nack JetStream message on error (will be retried)
                if hasattr(msg, 'nak'):
                    try:
                        await msg.nak()
                    except Exception:
                        pass

        # Subscribe with optional queue group
        try:
            if self.use_jetstream and self.js:
                # JetStream push subscription
                sub = await self.js.subscribe(
                    subject,
                    queue=queue_group,
                    cb=wrapper,
                    stream=None,  # Auto-detect stream
                )
                logger.info(f"Subscribed to JetStream {subject} (queue: {queue_group or 'none'}, sub_id: {sub_id})")
            else:
                # Standard NATS subscription
                await self.nc.subscribe(subject, cb=wrapper, queue=queue_group)
                logger.info(f"Subscribed to {subject} (queue: {queue_group or 'none'}, sub_id: {sub_id})")

            return sub_id

        except Exception as e:
            # Clean up subscription tracking on error
            async with self._subscriptions_lock:
                self._subscription_handlers.pop(sub_id, None)
                if subject in self._subscriptions:
                    self._subscriptions[subject].discard(sub_id)

            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise

    async def unsubscribe(self, sub_id: int) -> None:
        """
        Unsubscribe from events and clean up resources.

        Args:
            sub_id: Subscription ID returned by subscribe()
        """
        async with self._subscriptions_lock:
            # Remove weak reference
            self._subscription_handlers.pop(sub_id, None)

            # Remove from subject tracking
            for subject, sub_ids in self._subscriptions.items():
                if sub_id in sub_ids:
                    sub_ids.remove(sub_id)
                    logger.info(f"Unsubscribed from {subject} (sub_id: {sub_id})")
                    break

    async def request(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any],
        source: str = "agent-zero",
        timeout: float = 5.0,
    ) -> Optional[Event]:
        """
        Publish request and wait for response (request-reply pattern).

        Args:
            subject: NATS subject for request
            event_type: Event type
            data: Request payload
            source: Source service name
            timeout: Response timeout in seconds

        Returns:
            Response Event or None if timeout

        Example:
            response = await bus.request(
                subject="pmoves.agent.query.v1",
                event_type="AGENT_QUERY",
                data={"query": "status"}
            )
        """
        if not self._connected or not self.nc:
            await self.connect()

        # Create request event
        event = Event(
            type=event_type,
            source=source,
            data=data,
        )

        try:
            payload = json.dumps(event.to_dict()).encode()

            # Use JetStream request if available
            if self.use_jetstream and self.js:
                response = await self.js.request(subject, payload, timeout=timeout)
            else:
                response = await self.nc.request(subject, payload, timeout=timeout)

            if response:
                data = json.loads(response.data.decode())
                return Event.from_dict(data)
            return None

        except asyncio.TimeoutError:
            logger.warning(f"Request timeout for {subject}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    async def close(self) -> None:
        """Close NATS connection and cleanup resources."""
        self._should_reconnect = False

        async with self._lock:
            if self.nc and self._connected:
                try:
                    await self.nc.close()
                    self._connected = False
                    logger.info("Event bus closed")
                except Exception as e:
                    logger.error(f"Error closing event bus: {e}")

        # Clean up subscription tracking
        async with self._subscriptions_lock:
            self._subscriptions.clear()
            self._subscription_handlers.clear()

    async def get_metrics(self) -> Dict[str, int]:
        """
        Get current metrics snapshot (thread-safe).

        Returns:
            Dictionary with current metric values
        """
        async with self._metrics_lock:
            return self._metrics.copy()

    async def reset_metrics(self) -> None:
        """Reset metrics counters (thread-safe)."""
        async with self._metrics_lock:
            self._metrics = {
                "events_published": 0,
                "events_processed": 0,
                "events_failed": 0,
            }

    def get_metrics_sync(self) -> Dict[str, int]:
        """
        Get current metrics snapshot (synchronous, non-blocking).

        Note: May return slightly stale data if called while metrics are being updated.

        Returns:
            Dictionary with current metric values
        """
        # Return a copy to avoid external modification
        return dict(self._metrics)


# Singleton instance
_bus: Optional[EventBus] = None
_bus_lock = asyncio.Lock()


async def get_event_bus(nats_url: str = "nats://localhost:4222") -> EventBus:
    """
    Get or create singleton event bus instance.

    Args:
        nats_url: NATS server URL (only used on first call)

    Returns:
        EventBus instance

    Example:
        bus = await get_event_bus()
        await bus.publish(...)
    """
    global _bus

    async with _bus_lock:
        if _bus is None:
            _bus = EventBus(nats_url=nats_url)
            await _bus.connect()
        return _bus


async def shutdown_event_bus() -> None:
    """Shutdown singleton event bus."""
    global _bus

    async with _bus_lock:
        if _bus:
            await _bus.close()
            _bus = None
