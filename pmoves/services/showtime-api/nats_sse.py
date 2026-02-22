"""NATS to SSE bridge.

Subscribes to multiple NATS subjects and fans out messages
as Server-Sent Events via FastAPI StreamingResponse.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from nats.aio.client import Client as NATS

from prometheus_client import Counter

logger = logging.getLogger("showtime.nats_sse")

SSE_MESSAGES_DROPPED = Counter(
    "showtime_sse_messages_dropped_total",
    "SSE messages dropped due to full queue",
)

NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")

# Subjects to subscribe to for the SSE stream
SSE_SUBJECTS = [
    "a2ui.render.v1",
    "geometry.cgp.v1",
    "geometry.packet.encoded.v1",
    "ingest.>",
    "botz.heartbeat.v1",
    "showtime.>",
]


async def nats_event_generator() -> AsyncGenerator[str, None]:
    """Connect to NATS and yield SSE-formatted events."""
    nc = NATS()
    queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue(maxsize=256)
    _drop_count = 0

    try:
        await nc.connect(NATS_URL)
        logger.info("NATS connected for SSE bridge at %s", NATS_URL)
    except Exception as exc:
        logger.error("NATS connection failed: %s", exc)
        yield f"event: showtime.error\ndata: {json.dumps({'error': 'NATS connection failed', 'detail': str(exc)})}\n\n"
        return

    async def _handler(msg):
        nonlocal _drop_count
        try:
            queue.put_nowait((msg.subject, msg.data))
        except asyncio.QueueFull:
            SSE_MESSAGES_DROPPED.inc()
            _drop_count += 1
            if _drop_count % 100 == 1:
                logger.warning("SSE queue full, dropped %d messages total", _drop_count)

    subs = []
    for subject in SSE_SUBJECTS:
        sub = await nc.subscribe(subject, cb=_handler)
        subs.append(sub)

    # Send initial connection event
    yield f"event: showtime.connected\ndata: {json.dumps({'subjects': SSE_SUBJECTS})}\n\n"

    try:
        while True:
            try:
                subject, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                try:
                    payload = json.loads(data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = {"raw": data.decode("utf-8", errors="replace")}
                yield f"event: {subject}\ndata: {json.dumps(payload)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        for sub in subs:
            try:
                await sub.unsubscribe()
            except Exception as exc:
                logger.debug("Failed to unsubscribe: %s", exc)
        if nc.is_connected:
            await nc.drain()
