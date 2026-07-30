"""In-memory state for the nats_event_bus service.

Three concerns live here:

1. EventCache — a per-topic ring buffer of the most recent envelopes.
   Thread-safe via a single asyncio.Lock; per-topic access is O(N) at
   worst (N=cache_size) and O(1) for append.

2. NatsSubscriber — best-effort background task that subscribes to the
   configured topics and fills EventCache from incoming messages.
   Disables itself cleanly when NATS is unreachable; the HTTP surface
   continues to work because POST /v1/publish writes directly to the
   cache + only attempts a NATS publish if the env says so.

3. DIRECTORY_TOPIC / PRESENCE_TOPIC constants — the convenience
   subjects used by app.py for /v1/snapshot/room-directory and
   /v1/presence/{room_id}.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set


logger = logging.getLogger("nats_event_bus.state")


# The 5 slice-3 subjects + 3 slice-6 helpdesk subjects this service
# knows about by default. New subjects can be added by extending this
# list — the EventCache and subscriber both iterate it. The
# EventCache.append() also auto-registers unknown topics at runtime
# (defense in depth), so this list is the eager-default set rather
# than a closed allow-list.
DEFAULT_TOPICS: List[str] = [
    "comfy.collab.prompt.v1",
    "comfy.collab.progress.v1",
    "comfy.collab.artifact.v1",
    "room.presence.v1",
    "room.directory.v1",
    "helpdesk.intake.opened.v1",
    "helpdesk.intake.routed.v1",
    "helpdesk.room.suggested.v1",
]

# Convenience aliases used by /v1/snapshot/* and /v1/presence/{room_id}.
DIRECTORY_TOPIC = "room.directory.v1"
PRESENCE_TOPIC = "room.presence.v1"


class EventCache:
    """Per-topic ring buffer of envelopes (newest at the right).

    Envelopes are stored as-is (validated dicts from common.events).
    The cache is the only state the HTTP surface needs; the NATS
    subscriber (if running) keeps it warm."""

    def __init__(self, topics: Optional[List[str]] = None, cache_size: int = 100):
        self._topics: List[str] = list(topics) if topics is not None else list(DEFAULT_TOPICS)
        self._cache_size = cache_size
        self._buffers: Dict[str, Deque[Dict[str, Any]]] = {
            t: deque(maxlen=cache_size) for t in self._topics
        }
        self._lock = asyncio.Lock()

    @property
    def topics(self) -> List[str]:
        return list(self._topics)

    async def append(self, topic: str, envelope: Dict[str, Any]) -> None:
        if topic not in self._buffers:
            # Auto-register unknown topics so producers don't have to
            # restart the service to add a new subject.
            async with self._lock:
                if topic not in self._buffers:
                    self._buffers[topic] = deque(maxlen=self._cache_size)
                    self._topics.append(topic)
                    logger.info("auto-registered new topic %s", topic)
        async with self._lock:
            self._buffers[topic].append(envelope)

    async def recent(self, topic: str, since: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Return envelopes for `topic`, optionally filtered to those newer than `since` (ISO-8601 ts).

        `limit` is clamped to the cache size. Order: oldest -> newest."""
        if topic not in self._buffers:
            return []
        async with self._lock:
            buf = list(self._buffers[topic])
        if since is not None:
            buf = [e for e in buf if e.get("ts", "") > since]
        return buf[-limit:]

    async def latest(self, topic: str) -> Optional[Dict[str, Any]]:
        if topic not in self._buffers or not self._buffers[topic]:
            return None
        async with self._lock:
            return self._buffers[topic][-1]

    async def filter(self, topic: str, predicate) -> List[Dict[str, Any]]:
        """Return all envelopes for `topic` matching `predicate(envelope)`.

        Used by /v1/presence/{room_id} and similar convenience reads."""
        if topic not in self._buffers:
            return []
        async with self._lock:
            buf = list(self._buffers[topic])
        return [e for e in buf if predicate(e)]


class NatsSubscriber:
    """Best-effort NATS subscriber. Disabled cleanly when NATS is unreachable.

    Lifecycle:
    - start() schedules _run() as an asyncio task.
    - _run() tries to connect; on success it subscribes to all
      configured topics and pumps messages into EventCache.
    - On connection error it sleeps and retries with backoff.
    - stop() cancels the task and drains.
    """

    def __init__(
        self,
        cache: EventCache,
        topics: Optional[List[str]] = None,
        nats_url: Optional[str] = None,
    ):
        self._cache = cache
        self._topics: Set[str] = set(topics) if topics is not None else set(cache.topics)
        self._nats_url = nats_url or os.environ.get("NATS_URL", "")
        self._task: Optional[asyncio.Task] = None
        self._nc: Any = None
        self._connected = False
        self._stopped = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def enabled(self) -> bool:
        return bool(self._nats_url) and not self._stopped

    async def start(self) -> None:
        if not self._nats_url:
            logger.info("NATS_URL not set — subscriber disabled")
            return
        if self._task is not None:
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="nats_event_bus.subscriber")

    async def stop(self) -> None:
        self._stopped = True
        if self._nc is not None:
            try:
                await self._nc.close()
            except Exception:  # noqa: BLE001 — best-effort
                pass
            self._nc = None
            self._connected = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    async def _run(self) -> None:
        # Imported lazily so the module loads in test envs without nats-py.
        from nats.aio.client import Client as NATS

        backoff = 1.0
        while not self._stopped:
            try:
                nc = NATS()
                await nc.connect(servers=[self._nats_url], connect_timeout=2)
                self._nc = nc
                self._connected = True
                logger.info("nats_event_bus subscriber connected to %s", self._nats_url)
                backoff = 1.0

                async def handler(msg):
                    try:
                        env = json.loads(msg.data.decode())
                    except Exception as e:  # noqa: BLE001
                        logger.warning("subscriber: failed to decode message on %s: %s", msg.subject, e)
                        return
                    await self._cache.append(msg.subject, env)

                for t in self._topics:
                    # no_echo=True prevents this connection from
                    # receiving its own publishes on /v1/publish, which
                    # would otherwise cause every published envelope
                    # to be appended to the cache twice (local append
                    # in the request handler + echo via the subscriber).
                    await nc.subscribe(t, cb=handler, no_echo=True)

                # Park until disconnect; nats-py will call us back if it dies.
                while not self._stopped and nc.is_connected:
                    await asyncio.sleep(0.5)
                self._connected = False
                try:
                    await nc.close()
                except Exception:  # noqa: BLE001
                    pass
                self._nc = None
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                self._connected = False
                logger.warning("nats_event_bus subscriber error: %s — retrying in %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
