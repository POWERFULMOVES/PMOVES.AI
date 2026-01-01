"""
NATS event publishing for GitHub Runner Controller.

Following PMOVES SDK pattern: standardized event envelope format
with correlation IDs, versioning, and source attribution.
"""

import asyncio
import json
import logging
import re
import uuid
import datetime
from datetime import timezone
from typing import Any, Dict, Optional

import nats
from nats.aio.client import Client as NATS

from metrics import NATS_EVENTS_PUBLISHED, NATS_EVENTS_FAILED

logger = logging.getLogger("github-runner-ctl")


def create_event_envelope(
    topic: str,
    payload: Dict[str, Any],
    source: str = "github-runner-ctl",
    correlation_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a PMOVES-standard event envelope.

    Args:
        topic: NATS subject for this event
        payload: Event data
        source: Service publishing this event
        correlation_id: Optional correlation ID for tracing
        parent_id: Optional parent event ID for causality

    Returns:
        Dictionary with PMOVES envelope structure
    """
    return {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "ts": datetime.datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "version": "v1",
        "source": source,
        "payload": payload,
        "correlation_id": correlation_id,
        "parent_id": parent_id,
    }


class NATSPublisher:
    """NATS event publisher with connection management and offline buffering."""

    # Maximum number of events to buffer while disconnected
    MAX_BUFFER_SIZE = 1000

    def __init__(
        self,
        nats_url: str,
        max_buffer_size: int = MAX_BUFFER_SIZE,
        nats_user: Optional[str] = None,
        nats_pass: Optional[str] = None,
    ):
        """Initialize NATS publisher.

        Args:
            nats_url: NATS connection URL (e.g., "nats://nats:4222")
            max_buffer_size: Maximum events to buffer while disconnected
            nats_user: Optional NATS username (overrides URL if provided)
            nats_pass: Optional NATS password (overrides URL if provided)
        """
        # Build authenticated URL if credentials provided separately
        if nats_user and nats_pass:
            # Extract host and port from existing URL
            match = re.match(r'nats://([^:]+):(\d+)', nats_url)
            if match:
                host, port = match.groups()
                self.nats_url = f"nats://{nats_user}:{nats_pass}@{host}:{port}"
            else:
                self.nats_url = nats_url
        else:
            self.nats_url = nats_url

        self._nc: Optional[NATS] = None
        self._connected = False
        self._max_buffer_size = max_buffer_size
        self._event_buffer: list[Dict[str, Any]] = []

    @property
    def is_connected(self) -> bool:
        """Check if NATS client is connected."""
        return self._connected and self._nc is not None and self._nc.is_connected

    async def connect(self, retry: bool = True) -> bool:
        """Connect to NATS with exponential backoff.

        Args:
            retry: Whether to retry on connection failure

        Returns:
            True if connected, False otherwise
        """
        backoff = 1.0
        max_backoff = 30.0

        while True:
            try:
                self._nc = NATS()
                await self._nc.connect(self.nats_url)
                self._connected = True
                logger.info(f"Connected to NATS at {self.nats_url}")

                # Flush buffered events after successful reconnection
                if self._event_buffer:
                    logger.info(f"Flushing {len(self._event_buffer)} buffered events...")
                    await self._flush_buffer()

                return True
            except Exception as e:
                logger.warning(f"NATS connection failed: {e}")
                if not retry:
                    return False
                logger.info(f"Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def close(self) -> None:
        """Close NATS connection."""
        if self._nc:
            try:
                await self._nc.close()
                logger.info("NATS connection closed")
            except Exception as e:
                logger.warning(f"Error closing NATS connection: {e}")
            finally:
                self._connected = False
                self._nc = None

    async def publish(
        self,
        subject: str,
        payload: Dict[str, Any],
        source: str = "github-runner-ctl",
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> bool:
        """Publish an event to NATS.

        Args:
            subject: NATS subject to publish to
            payload: Event data
            source: Service name publishing the event
            correlation_id: Optional correlation ID for tracing
            parent_id: Optional parent event ID for causality

        Returns:
            True if published or queued successfully, False otherwise
        """
        if not self.is_connected:
            # Queue event for later delivery instead of dropping
            return await self._queue_event(subject, payload, source, correlation_id, parent_id)

        try:
            envelope = create_event_envelope(
                topic=subject,
                payload=payload,
                source=source,
                correlation_id=correlation_id,
                parent_id=parent_id,
            )
            await self._nc.publish(subject, json.dumps(envelope).encode())
            NATS_EVENTS_PUBLISHED.labels(subject=subject, status="success").inc()
            logger.debug(f"Published {subject}: {envelope['id']}")
            return True
        except Exception as e:
            # Log full error details including payload for debugging
            payload_preview = json.dumps(payload, default=str)[:300]
            logger.error(
                f"Failed to publish {subject}: {e.__class__.__name__}: {e} | "
                f"envelope_id={envelope.get('id', 'unknown')} | "
                f"payload_preview={payload_preview}"
            )
            NATS_EVENTS_FAILED.labels(subject=subject, reason="publish_error").inc()
            return False

    async def publish_runner_event(
        self,
        event_type: str,
        runner: str,
        data: Dict[str, Any],
    ) -> bool:
        """Publish a runner lifecycle event.

        Args:
            event_type: Type of event (registered, removed, enabled, disabled)
            runner: Runner name/ID
            data: Additional event data

        Returns:
            True if published successfully
        """
        subject = f"github.runner.{event_type}.v1"
        payload = {
            "runner": runner,
            "timestamp": datetime.datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **data
        }
        return await self.publish(subject, payload)

    async def publish_job_event(
        self,
        event_type: str,
        runner: str,
        repository: str,
        job_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Publish a job lifecycle event.

        Args:
            event_type: Type of event (queued, started, completed, failed)
            runner: Runner name/ID
            repository: Repository name
            job_id: Optional job identifier
            data: Additional event data

        Returns:
            True if published successfully
        """
        subject = f"github.job.{event_type}.v1"
        payload = {
            "runner": runner,
            "repository": repository,
            "job_id": job_id,
            "timestamp": datetime.datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **(data or {})
        }
        return await self.publish(subject, payload)

    async def publish_alert(
        self,
        alert_type: str,
        runner: str,
        message: str,
        severity: str = "warning",
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Publish a resource alert event.

        Args:
            alert_type: Type of alert (cpu_high, memory_high, disk_low, queue_backlog)
            runner: Runner name/ID
            message: Alert message
            severity: Alert severity (info, warning, critical)
            data: Additional alert data

        Returns:
            True if published successfully
        """
        subject = f"github.runner.{alert_type}.v1"
        payload = {
            "runner": runner,
            "severity": severity,
            "message": message,
            "timestamp": datetime.datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **(data or {})
        }
        return await self.publish(subject, payload)

    async def _queue_event(
        self,
        subject: str,
        payload: Dict[str, Any],
        source: str,
        correlation_id: Optional[str],
        parent_id: Optional[str],
    ) -> bool:
        """Queue an event for later delivery when NATS is disconnected.

        Args:
            subject: NATS subject
            payload: Event data
            source: Service name
            correlation_id: Optional correlation ID
            parent_id: Optional parent event ID

        Returns:
            True if queued successfully, False if buffer is full
        """
        if len(self._event_buffer) >= self._max_buffer_size:
            logger.warning(
                f"Event buffer full ({self._max_buffer_size}), dropping event: {subject}"
            )
            NATS_EVENTS_FAILED.labels(subject=subject, reason="buffer_full").inc()
            return False

        self._event_buffer.append({
            "subject": subject,
            "payload": payload,
            "source": source,
            "correlation_id": correlation_id,
            "parent_id": parent_id,
        })
        NATS_EVENTS_PUBLISHED.labels(subject=subject, status="buffered").inc()
        logger.debug(
            f"Queued event {subject} (buffer size: {len(self._event_buffer)}/{self._max_buffer_size})"
        )
        return True

    async def _flush_buffer(self) -> None:
        """Flush all buffered events to NATS.

        Called after successful reconnection. Events that fail to publish
        are removed from the buffer and logged.
        """
        if not self._event_buffer:
            return

        logger.info(f"Flushing {len(self._event_buffer)} buffered events...")
        flushed_count = 0
        failed_count = 0

        # Process events in order
        while self._event_buffer:
            event = self._event_buffer.pop(0)

            try:
                envelope = create_event_envelope(
                    topic=event["subject"],
                    payload=event["payload"],
                    source=event["source"],
                    correlation_id=event["correlation_id"],
                    parent_id=event["parent_id"],
                )
                await self._nc.publish(event["subject"], json.dumps(envelope).encode())
                NATS_EVENTS_PUBLISHED.labels(subject=event["subject"], status="flushed").inc()
                flushed_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to flush buffered event {event['subject']}: {e}"
                )
                NATS_EVENTS_FAILED.labels(subject=event["subject"], reason="flush_error").inc()
                failed_count += 1

        logger.info(
            f"Buffer flush complete: {flushed_count} sent, {failed_count} failed"
        )

    @property
    def buffer_size(self) -> int:
        """Return the current size of the event buffer."""
        return len(self._event_buffer)
