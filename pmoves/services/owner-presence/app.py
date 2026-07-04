"""
PMOVES Owner Presence Service
=============================
Listens for owner activity signals and applies a hysteresis state machine
(PRESENT → GRACE → ABSENT) to determine presence state over time.

Endpoints:
    GET  /healthz
    POST /api/v1/presence/signal
    GET  /api/v1/presence/status
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

LOG = logging.getLogger("owner-presence")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

PRESENCE_GRACE_SECS = int(os.getenv("PRESENCE_GRACE_SECS", "900"))  # 15 min default
CHECK_INTERVAL_SECS = int(os.getenv("CHECK_INTERVAL_SECS", "60"))
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
NATS_SUBJECT_SIGNAL = "owner.signal.active.v1"
NATS_SUBJECT_DETECTED = "owner.presence.detected.v1"
NATS_SUBJECT_ABSENT = "owner.presence.absent.v1"

# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #

class PresenceState(str, Enum):
    PRESENT = "PRESENT"
    GRACE = "GRACE"
    ABSENT = "ABSENT"


class PresenceTracker:
    def __init__(self, grace_secs: int):
        self.state: PresenceState = PresenceState.ABSENT
        self.last_signal_time: float = 0.0
        self.grace_secs = grace_secs
        self._lock = asyncio.Lock()

    def signal(self):
        self.last_signal_time = time.time()
        if self.state != PresenceState.PRESENT:
            self.state = PresenceState.PRESENT
            LOG.info("Presence state -> PRESENT")
            return PresenceState.PRESENT
        return None

    async def evaluate(self) -> Optional[tuple]:
        """Returns (new_state, subject_to_publish) or None if no transition."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_signal_time
            prev = self.state

            if self.last_signal_time == 0.0:
                return None

            if elapsed < self.grace_secs:
                if self.state == PresenceState.ABSENT:
                    self.state = PresenceState.PRESENT
            elif elapsed < self.grace_secs * 2:
                if self.state == PresenceState.PRESENT:
                    self.state = PresenceState.GRACE
                    LOG.info("Presence state -> GRACE (no signal for %.0fs)", elapsed)
            else:
                if self.state != PresenceState.ABSENT:
                    self.state = PresenceState.ABSENT
                    LOG.info("Presence state -> ABSENT (no signal for %.0fs)", elapsed)

            if prev != self.state:
                if self.state == PresenceState.PRESENT:
                    return (self.state, NATS_SUBJECT_DETECTED)
                elif self.state == PresenceState.ABSENT:
                    return (self.state, NATS_SUBJECT_ABSENT)
            return None


tracker = PresenceTracker(PRESENCE_GRACE_SECS)

# --------------------------------------------------------------------------- #
# NATS integration
# --------------------------------------------------------------------------- #

class NATSManager:
    def __init__(self):
        self._nc = None
        self._sub = None

    async def connect(self):
        try:
            from nats.aio.client import Client as NATSClient
            self._nc = NATSClient()
            await self._nc.connect(servers=[NATS_URL])
            LOG.info("Connected to NATS at %s", NATS_URL)
            await self._nc.subscribe(NATS_SUBJECT_SIGNAL, cb=self._on_signal)
            LOG.info("Subscribed to %s", NATS_SUBJECT_SIGNAL)
        except Exception as exc:
            LOG.warning("NATS connect failed (%s); running in API-only mode", exc)
            self._nc = None

    async def _on_signal(self, msg):
        LOG.info("Received signal on %s", msg.subject)
        transition = tracker.signal()
        if transition:
            await self.publish(NATS_SUBJECT_DETECTED, {"state": "PRESENT", "ts": time.time()})

    async def publish(self, subject: str, payload: Dict[str, Any]):
        import json
        body = json.dumps(payload).encode()
        if self._nc:
            await self._nc.publish(subject, body)
        LOG.info("NATS publish subject=%s bytes=%d", subject, len(body))


nats_mgr = NATSManager()


async def presence_loop():
    """Background task that evaluates presence every CHECK_INTERVAL_SECS."""
    LOG.info("Starting presence evaluation loop (interval=%ds, grace=%ds)", CHECK_INTERVAL_SECS, PRESENCE_GRACE_SECS)
    while True:
        try:
            result = await tracker.evaluate()
            if result:
                new_state, subject = result
                await nats_mgr.publish(subject, {"state": new_state.value, "ts": time.time()})
        except Exception:
            LOG.exception("Error in presence evaluation loop")
        await asyncio.sleep(CHECK_INTERVAL_SECS)


# --------------------------------------------------------------------------- #
# API models
# --------------------------------------------------------------------------- #

class SignalRequest(BaseModel):
    source: str = Field("api", description="Signal source identifier")


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #

app = FastAPI(title="PMOVES Owner Presence", version="1.0.0")
_loop_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def _startup():
    global _loop_task
    await nats_mgr.connect()
    _loop_task = asyncio.create_task(presence_loop())


@app.on_event("shutdown")
async def _shutdown():
    if _loop_task:
        _loop_task.cancel()


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "grace_secs": PRESENCE_GRACE_SECS}


@app.post("/api/v1/presence/signal")
async def signal(req: SignalRequest):
    transition = tracker.signal()
    if transition:
        await nats_mgr.publish(NATS_SUBJECT_DETECTED, {"state": "PRESENT", "source": req.source})
    return {"state": tracker.state.value, "last_signal": tracker.last_signal_time}


@app.get("/api/v1/presence/status")
async def status():
    now = time.time()
    elapsed = now - tracker.last_signal_time if tracker.last_signal_time else None
    return {
        "state": tracker.state.value,
        "last_signal_time": tracker.last_signal_time,
        "seconds_since_signal": int(elapsed) if elapsed else None,
        "grace_secs": PRESENCE_GRACE_SECS,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)
