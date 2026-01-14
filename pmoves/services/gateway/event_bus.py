"""Async helper for publishing/recording PMOVES contract events."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Any, Deque, Iterable, List, Optional

try:  # pragma: no cover - optional dependency during docs builds
    from nats.aio.client import Client as NATS
except Exception:  # pragma: no cover - the service can operate without NATS
    NATS = None  # type: ignore[misc]

from pmoves.services.common import events as event_utils

logger = logging.getLogger("pmoves.gateway.events")


class EventBus:
    """Minimal NATS wrapper that validates payloads against contracts."""

    def __init__(
        self,
        *,
        nats_url: Optional[str],
        subscribe_topics: Iterable[str] | None = None,
        history_size: int = 100,
    ) -> None:
        self._nats_url = (nats_url or "").strip()
        self._topics = list(dict.fromkeys(subscribe_topics or []))
        self._history: Deque[dict[str, Any]] = deque(maxlen=history_size)
        self._nc: Optional["NATS"] = None
        self._lock = asyncio.Lock()

    @property
    def topics(self) -> List[str]:
        return list(self._topics)

    def recent(self, limit: int = 20) -> List[dict[str, Any]]:
        limit = max(0, limit)
        return list(list(self._history)[0:limit])

    async def start(self) -> None:
        if not self._nats_url or NATS is None:
            if not self._nats_url:
                logger.info("Event bus disabled (NATS_URL not set)")
            else:
                logger.warning("Event bus disabled (nats-py not installed)")
            return
        async with self._lock:
            if self._nc is not None:
                return
            nc = NATS()
            try:
                await nc.connect(servers=[self._nats_url], allow_reconnect=True, connect_timeout=1.0)
            except Exception as exc:  # pragma: no cover - depends on runtime service availability
                logger.warning("Unable to connect to NATS at %s: %s", self._nats_url, exc)
                return
            for topic in self._topics:
                try:
                    await nc.subscribe(topic, cb=self._on_message)
                except Exception as exc:
                    logger.warning("Failed subscribing to %s: %s", topic, exc)
            self._nc = nc
            logger.info("Event bus connected to %s", self._nats_url)

    async def stop(self) -> None:
        async with self._lock:
            if self._nc is None:
                return
            try:
                await self._nc.drain()
            except Exception:
                pass
            self._nc = None

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "gateway",
    ) -> dict[str, Any]:
        envelope = event_utils.envelope(
            topic,
            payload,
            correlation_id=correlation_id,
            parent_id=parent_id,
            source=source,
        )
        data = json.dumps(envelope).encode("utf-8")
        if self._nc is not None:
            try:
                await self._nc.publish(topic, data)
            except Exception as exc:  # pragma: no cover - depends on runtime availability
                logger.warning("NATS publish failed for %s: %s", topic, exc)
        else:
            # Fallback to fire-and-forget publish helper (opens a short-lived connection)
            try:
                await event_utils.publish(
                    topic,
                    payload,
                    correlation_id=correlation_id,
                    parent_id=parent_id,
                    source=source,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Direct publish fallback failed for %s: %s", topic, exc)
        self._record(envelope)
        return envelope

    def _record(self, envelope: dict[str, Any]) -> None:
        self._history.appendleft(envelope)

    def record_local(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = {"topic": topic, "payload": payload}
        self._record(envelope)
        return envelope

    async def _on_message(self, msg) -> None:  # type: ignore[no-untyped-def]
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception:
            logger.debug("Received non-JSON message on %s", getattr(msg, "subject", "?"))
            return
        if isinstance(data, dict):
            envelope = data
        else:
            envelope = {"topic": getattr(msg, "subject", ""), "payload": data}
        envelope.setdefault("topic", getattr(msg, "subject", ""))
        if isinstance(envelope.get("payload"), dict):
            topic = envelope.get("topic")
            try:
                event_utils.load_schema(topic)  # validate topic exists
            except Exception:
                logger.debug("Received event with unknown topic %s", topic)
        self._record(envelope)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"EventBus(url={self._nats_url!r}, topics={self._topics!r})"
