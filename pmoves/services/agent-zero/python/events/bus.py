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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg
import nats

logger = logging.getLogger("pmoves.agent_zero.events.bus")


@dataclass
class Event:
    """
    Event envelope for agent communication.

    Attributes:
        id: Unique event identifier (timestamp-based)
        timestamp: ISO format timestamp in UTC
        type: Event type (e.g., "AGENT_STARTED", "TASK_COMPLETED")
        source: Source service name (e.g., "agent-zero", "archon")
        data: Event payload (validated against schema if available)
        metadata: Additional metadata (optional)
        correlation_id: For tracking related events across services
    """
    id: str = field(default_factory=lambda: f"evt-{int(asyncio.get_event_loop().time() * 1000)}")
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
    - Metrics tracking (published, processed, failed)
    - Async error handling

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

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        """
        Initialize event bus.

        Args:
            nats_url: NATS server URL (default: localhost:4222)
        """
        self.nats_url = nats_url
        self.nc: Optional[NATSClient] = None
        self.validators: Dict[str, Any] = {}  # event_type -> SchemaValidator
        self.metrics: Dict[str, int] = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
        }
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """
        Connect to NATS server.

        Raises:
            ConnectionError: If connection fails
        """
        async with self._lock:
            if self._connected:
                return

            try:
                self.nc = NATSClient()
                await self.nc.connect(
                    self.nats_url,
                    connect_timeout=10,
                    reconnect_time_wait=2,
                    max_reconnect_attempts=5
                )
                self._connected = True
                logger.info(f"Event bus connected to {self.nats_url}")
            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}")
                raise ConnectionError(f"NATS connection failed: {e}")

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
        Publish an event to the bus.

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
                self.metrics["events_failed"] += 1
                raise ValueError(f"Schema validation failed: {e}")

        # Publish to NATS
        try:
            payload = json.dumps(event.to_dict()).encode()
            await self.nc.publish(subject, payload)
            self.metrics["events_published"] += 1
            logger.debug(f"Published event {event.id} to {subject}")
            return event.id
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            self.metrics["events_failed"] += 1
            raise

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[Event], Any],
        queue_group: Optional[str] = None,
    ) -> None:
        """
        Subscribe to events.

        Args:
            subject: NATS subject (supports wildcards, e.g., "pmoves.>")
            handler: Async callback function receiving Event object
            queue_group: Optional queue group for load balancing

        Example:
            async def handler(event):
                print(f"Received: {event.type}")

            await bus.subscribe("pmoves.agent.>", handler)
        """
        if not self._connected or not self.nc:
            await self.connect()

        async def wrapper(msg: Msg):
            """Wrapper for error handling and metrics."""
            try:
                # Deserialize event
                payload = msg.data.decode()
                data = json.loads(payload)
                event = Event.from_dict(data)

                # Call handler
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)

                self.metrics["events_processed"] += 1
                logger.debug(f"Processed event {event.id} from {msg.subject}")

            except Exception as e:
                self.metrics["events_failed"] += 1
                logger.error(f"Event processing error: {e}", exc_info=True)

        # Subscribe with optional queue group
        try:
            await self.nc.subscribe(subject, cb=wrapper, queue=queue_group)
            logger.info(f"Subscribed to {subject} (queue: {queue_group or 'none'})")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise

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
        """Close NATS connection."""
        async with self._lock:
            if self.nc and self._connected:
                try:
                    await self.nc.close()
                    self._connected = False
                    logger.info("Event bus closed")
                except Exception as e:
                    logger.error(f"Error closing event bus: {e}")

    def get_metrics(self) -> Dict[str, int]:
        """Get current metrics snapshot."""
        return self.metrics.copy()

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        self.metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
        }


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
