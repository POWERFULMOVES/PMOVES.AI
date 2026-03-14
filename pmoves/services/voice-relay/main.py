"""Voice Relay — NATS bridge from agentzero.task.result.v1 to voice.agent.response.v1.

Subscribes to Agent Zero task results, filters for voice-tagged tasks
(meta.voice_mode), transforms the payload to match the voice.agent.response.v1
schema, and republishes so voice_follow_agent and voice_follow_cast_agent
receive spoken responses.
"""

from contextlib import asynccontextmanager

import asyncio
import contextlib
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from nats.aio.client import Client as NATS
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
INPUT_SUBJECT = os.getenv("VOICE_RELAY_INPUT_SUBJECT", "agentzero.task.result.v1")
OUTPUT_SUBJECT = os.getenv("VOICE_RELAY_OUTPUT_SUBJECT", "voice.agent.response.v1")
PORT = int(os.getenv("PORT", "8121"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voice-relay")

# ---------------------------------------------------------------------------
# Prometheus Counters
# ---------------------------------------------------------------------------
RELAYED = Counter("voice_relay_messages_relayed_total", "Messages relayed to voice subject")
FILTERED = Counter("voice_relay_messages_filtered_total", "Messages filtered (no voice_mode)")
ERRORS = Counter("voice_relay_errors_total", "Errors during relay processing")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_nc: NATS | None = None
_nats_loop_task: asyncio.Task | None = None


def _extract_output_text(output) -> str:
    """Extract a string from the output field which may be str or dict."""
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        for key in ("text", "response_text", "content", "message"):
            val = output.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(output) if output else ""


async def _handle_message(msg) -> None:
    """Process an incoming agentzero.task.result.v1 message."""
    global _nc
    try:
        data = json.loads(msg.data.decode("utf-8"))
    except Exception:
        ERRORS.inc()
        return

    if not isinstance(data, dict):
        ERRORS.inc()
        return

    meta = data.get("meta") or {}
    if not meta.get("voice_mode"):
        FILTERED.inc()
        return

    output = data.get("output", "")
    response_text = _extract_output_text(output)
    if not response_text:
        FILTERED.inc()
        return

    voice_event = {
        "platform": meta.get("platform", "agent-zero"),
        "user_id": meta.get("user_id", "system"),
        "message_id": data.get("task_id", ""),
        "response_text": response_text,
        "model_used": meta.get("model"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": meta.get("sources", []),
        "meta": meta,
    }

    nc = _nc
    if nc and nc.is_connected:
        await nc.publish(OUTPUT_SUBJECT, json.dumps(voice_event).encode("utf-8"))
        RELAYED.inc()
        logger.info("relayed task_id=%s text=%s", data.get("task_id"), response_text[:80])
    else:
        ERRORS.inc()
        logger.warning("cannot publish — NATS not connected")


# ---------------------------------------------------------------------------
# NATS resilience loop (mirrors publisher-discord pattern)
# ---------------------------------------------------------------------------
async def _nats_resilience_loop() -> None:
    global _nc
    backoff = 1.0
    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        def _mark_lost(reason: str) -> None:
            global _nc
            if _nc is nc:
                _nc = None
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning("nats connection lost: %s", reason)

        async def _disconnected_cb():
            _mark_lost("disconnected")

        async def _closed_cb():
            _mark_lost("closed")

        try:
            logger.info("connecting to NATS %s (backoff=%.1fs)", NATS_URL, backoff)
            await nc.connect(
                servers=[NATS_URL],
                disconnected_cb=_disconnected_cb,
                closed_cb=_closed_cb,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("NATS connect failed: %s (retry in %.1fs)", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue

        _nc = nc
        backoff = 1.0
        logger.info("NATS connected — subscribing to %s", INPUT_SUBJECT)
        await nc.subscribe(INPUT_SUBJECT, cb=_handle_message)

        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await nc.close()
            if _nc is nc:
                _nc = None
            raise

        with contextlib.suppress(Exception):
            await nc.close()


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nats_loop_task
    _nats_loop_task = asyncio.create_task(_nats_resilience_loop())
    yield
    _nats_loop_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _nats_loop_task


app = FastAPI(title="voice-relay", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    nc = _nc
    return {
        "status": "ok" if nc and nc.is_connected else "degraded",
        "nats_connected": bool(nc and nc.is_connected),
        "input_subject": INPUT_SUBJECT,
        "output_subject": OUTPUT_SUBJECT,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from starlette.responses import Response

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
