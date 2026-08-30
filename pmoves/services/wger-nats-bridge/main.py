#!/usr/bin/env python3
"""wger NATS Bridge — polls wger API and publishes health events to NATS.

Phase 4.3: Polls wger API v2 for workout completions, weight entries, measurements.
Phase 4.4: CHIT-signs all NATS publishes (advisory mode if CHIT_PASSPHRASE absent).

NATS subjects published:
  - health.metrics.updated.v1 (weight + measurements)
  - health.workout.completed.v1 (workout logs)
  - health.weekly.summary.v1 (aggregated weekly summary)

Runtime: Standalone sidecar alongside wger service. Shares pmoves_bus network.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import aiohttp
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _load_secret(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    file_path = os.environ.get(f"{key}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


def _resolve_nats_url() -> str:
    url = _load_secret("NATS_URL")
    if url:
        return url
    host = os.environ.get("NATS_HOST", "nats")
    port = os.environ.get("NATS_PORT", "4222")
    return f"nats://{host}:{port}"


def _redact_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return url.replace(parsed.netloc, netloc)
    except Exception:
        pass
    return url


def _chit_sign(payload: dict, passphrase: str) -> dict:
    """CHIT HMAC-SHA256 signing for NATS payloads."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(passphrase.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    payload["sig"] = {"alg": "HMAC-SHA256", "kid": "wger-nats-bridge", "hmac": sig}
    return payload


class WgerNatsBridge:
    def __init__(self):
        self.nats_url = _resolve_nats_url()
        self.wger_url = os.environ.get("WGER_API_URL", "http://wger:8000")
        self.wger_user = _load_secret("WGER_API_USER", "")
        self.wger_pass = _load_secret("WGER_API_PASSWORD", "")
        self.chit_passphrase = _load_secret("CHIT_PASSPHRASE")
        self.poll_interval = int(os.environ.get("WGER_POLL_INTERVAL", "60"))
        self.watermark_file = os.environ.get("WGER_WATERMARK_FILE", "/tmp/wger_watermark.json")
        self.watermark: dict[str, int] = {}
        self._load_watermark()
        self.nc: NATS | None = None

    def _load_watermark(self):
        try:
            with open(self.watermark_file) as f:
                self.watermark = json.load(f)
        except Exception:
            self.watermark = {}

    def _save_watermark(self):
        try:
            with open(self.watermark_file, "w") as f:
                json.dump(self.watermark, f)
        except Exception:
            pass

    def _api_headers(self):
        import base64
        creds = base64.b64encode(f"{self.wger_user}:{self.wger_pass}".encode()).decode()
        return {"Authorization": f"Basic {creds}"} if creds else {}

    async def _publish(self, subject: str, payload: dict):
        if not self.nc:
            logger.warning("NATS not connected — skipping publish to %s", subject)
            return
        if self.chit_passphrase:
            payload = _chit_sign(payload, self.chit_passphrase)
        else:
            logger.debug("CHIT_PASSPHRASE not set — publishing unsigned (advisory mode)")
        await self.nc.publish(subject, json.dumps(payload, default=str).encode())
        logger.info("Published to %s", subject)

    async def _poll_endpoint(self, session: aiohttp.ClientSession, path: str) -> list[dict]:
        url = f"{self.wger_url}/api/v2/{path}"
        try:
            async with session.get(url, headers=self._api_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning("wger API %s returned %d", path, resp.status)
                    return []
                data = await resp.json()
                return data.get("results", [])
        except Exception as e:
            logger.error("wger API error for %s: %s", path, type(e).__name__)
            return []

    async def _poll_and_publish(self, session: aiohttp.ClientSession):
        ts = datetime.now(timezone.utc).isoformat()

        # Poll workouts
        workouts = await self._poll_endpoint(session, "workoutlog")
        new_workouts = [w for w in workouts if w.get("id", 0) > self.watermark.get("workout", 0)]
        for w in new_workouts:
            await self._publish("health.workout.completed.v1", {
                "id": "health-workout-" + str(w.get("id")),
                "timestamp": w.get("date", ts),
                "source": {"agent": "wger-nats-bridge", "endpoint": "workoutlog"},
                "data": {"workout_id": w.get("id"), "date": w.get("date")},
            })
        if new_workouts:
            self.watermark["workout"] = max(w.get("id", 0) for w in new_workouts)

        # Poll weight entries
        weights = await self._poll_endpoint(session, "weightentry")
        new_weights = [w for w in weights if w.get("id", 0) > self.watermark.get("weight", 0)]
        if new_weights:
            await self._publish("health.metrics.updated.v1", {
                "id": "health-metrics-" + str(int(time.time())),
                "timestamp": ts,
                "namespace": "wger",
                "source": {"agent": "wger-nats-bridge", "type": "weightentry"},
                "metrics": [{"weight": w.get("weight"), "date": w.get("date")} for w in new_weights[-5:]],
            })
            self.watermark["weight"] = max(w.get("id", 0) for w in new_weights)

        # Poll measurements
        measurements = await self._poll_endpoint(session, "measurement")
        new_meas = [m for m in measurements if m.get("id", 0) > self.watermark.get("measurement", 0)]
        if new_meas:
            self.watermark["measurement"] = max(m.get("id", 0) for m in new_meas)

        self._save_watermark()

        if new_workouts or new_weights:
            logger.info("Poll: workouts=%d weights=%d measurements=%d", len(new_workouts), len(new_weights), len(new_meas))

    async def run(self):
        self.nc = NATS()
        try:
            await self.nc.connect(self.nats_url, connect_timeout=10)
            logger.info("Connected to NATS at %s", _redact_url(self.nats_url))
        except Exception as e:
            logger.error("Failed to connect to NATS: %s", type(e).__name__)
            return

        stop_event = asyncio.Event()
        def _signal_handler(*_):
            stop_event.set()
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        async with aiohttp.ClientSession() as session:
            logger.info("wger NATS bridge started (poll=%ds, chit=%s)", self.poll_interval, bool(self.chit_passphrase))
            while not stop_event.is_set():
                try:
                    await self._poll_and_publish(session)
                except Exception as e:
                    logger.error("Poll cycle error: %s", type(e).__name__)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass

        logger.info("Shutting down wger NATS bridge")
        await self.nc.drain()


if __name__ == "__main__":
    bridge = WgerNatsBridge()
    asyncio.run(bridge.run())
