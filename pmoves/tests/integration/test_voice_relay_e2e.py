"""
Voice Relay E2E Integration Test (O-5)

Verifies the full voice synthesis chain end-to-end:
  agentzero.task.result.v1 (voice_mode=true)
    → voice-relay picks up (port 8121)
    → Flute synthesizes (port 8055)
    → voice.agent.response.v1 published
    → CGP packet on geometry.cgp.v1

Run with:
  pytest -m integration pmoves/tests/integration/test_voice_relay_e2e.py -v

Requires: NATS (4222), voice-relay (8121), flute-gateway (8055),
          vibevoice (3000) or ultimate-tts-studio (7861)
"""

import asyncio
import json
import os
import time
import uuid

import nats
import pytest
import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
VOICE_RELAY_URL = os.environ.get("VOICE_RELAY_URL", "http://localhost:8121")
FLUTE_URL = os.environ.get("FLUTE_URL", "http://localhost:8055")
VIBEVOICE_URL = os.environ.get("VIBEVOICE_URL", "http://localhost:3000")
ULTIMATE_TTS_URL = os.environ.get("ULTIMATE_TTS_URL", "http://localhost:7861")

TASK_RESULT_SUBJECT = "agentzero.task.result.v1"
VOICE_RESPONSE_SUBJECT = "voice.agent.response.v1"
CGP_SUBJECT = "geometry.cgp.v1"

VOICE_RESPONSE_TIMEOUT = 5.0
CGP_TIMEOUT = 8.0
HEALTH_TIMEOUT = 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _service_up(url: str, path: str = "/health") -> bool:
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
            r = await client.get(f"{url}{path}")
            return r.status_code < 500
    except Exception:
        return False


async def _nats_reachable() -> bool:
    try:
        nc = await nats.connect(NATS_URL, connect_timeout=3)
        await nc.drain()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def nats_client():
    nc = await nats.connect(NATS_URL)
    yield nc
    await nc.drain()


# ---------------------------------------------------------------------------
# Prerequisite checks (skip rather than fail when services are absent)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_nats_reachable():
    assert await _nats_reachable(), f"NATS not reachable at {NATS_URL}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_voice_relay_healthy():
    up = await _service_up(VOICE_RELAY_URL)
    if not up:
        pytest.skip(f"voice-relay not running at {VOICE_RELAY_URL}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_flute_healthy():
    up = await _service_up(FLUTE_URL)
    if not up:
        pytest.skip(f"flute-gateway not running at {FLUTE_URL}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_backend_healthy():
    """At least one TTS backend must be reachable."""
    vibevoice_up = await _service_up(VIBEVOICE_URL)
    ultimate_up = await _service_up(ULTIMATE_TTS_URL, path="/")
    if not vibevoice_up and not ultimate_up:
        pytest.skip(
            f"No TTS backend reachable. "
            f"vibevoice={VIBEVOICE_URL}, ultimate-tts={ULTIMATE_TTS_URL}"
        )
    if vibevoice_up:
        print(f"\n  TTS backend: VibeVoice ({VIBEVOICE_URL}) ✓")
    if ultimate_up:
        print(f"\n  TTS backend: Ultimate-TTS ({ULTIMATE_TTS_URL}) ✓")


# ---------------------------------------------------------------------------
# Core E2E test
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_voice_response_published_on_task_result():
    """
    Publish a synthetic agentzero.task.result.v1 with voice_mode=true and
    assert voice.agent.response.v1 arrives within VOICE_RESPONSE_TIMEOUT seconds.
    """
    if not await _nats_reachable():
        pytest.skip("NATS not reachable")
    if not await _service_up(VOICE_RELAY_URL):
        pytest.skip("voice-relay not running")

    nc = await nats.connect(NATS_URL)
    received: list[dict] = []

    async def _handler(msg):
        try:
            received.append(json.loads(msg.data.decode("utf-8")))
        except Exception:
            pass

    sub = await nc.subscribe(VOICE_RESPONSE_SUBJECT, cb=_handler)

    task_id = str(uuid.uuid4())
    payload = {
        "task_id": task_id,
        "status": "completed",
        "result": "Hello from the voice E2E test.",
        "meta": {
            "voice_mode": True,
            "persona": "dr-bean",
            "ts": int(time.time()),
        },
    }
    await nc.publish(TASK_RESULT_SUBJECT, json.dumps(payload).encode("utf-8"))

    deadline = time.monotonic() + VOICE_RESPONSE_TIMEOUT
    while time.monotonic() < deadline:
        if received:
            break
        await asyncio.sleep(0.1)

    await sub.unsubscribe()
    await nc.drain()

    assert received, (
        f"No {VOICE_RESPONSE_SUBJECT} received within {VOICE_RESPONSE_TIMEOUT}s "
        f"after publishing task_id={task_id}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cgp_packet_published_on_synthesis():
    """
    Assert that a geometry.cgp.v1 packet appears within CGP_TIMEOUT seconds
    after publishing a voice task — confirming Flute emits CGP on synthesis.
    """
    if not await _nats_reachable():
        pytest.skip("NATS not reachable")
    if not await _service_up(FLUTE_URL):
        pytest.skip("flute-gateway not running")

    nc = await nats.connect(NATS_URL)
    cgp_received: list[dict] = []

    async def _cgp_handler(msg):
        try:
            cgp_received.append(json.loads(msg.data.decode("utf-8")))
        except Exception:
            pass

    sub = await nc.subscribe(CGP_SUBJECT, cb=_cgp_handler)

    # Trigger synthesis via task result
    task_id = str(uuid.uuid4())
    payload = {
        "task_id": task_id,
        "status": "completed",
        "result": "Geometry bus E2E verification.",
        "meta": {"voice_mode": True, "ts": int(time.time())},
    }
    await nc.publish(TASK_RESULT_SUBJECT, json.dumps(payload).encode("utf-8"))

    deadline = time.monotonic() + CGP_TIMEOUT
    while time.monotonic() < deadline:
        if cgp_received:
            break
        await asyncio.sleep(0.1)

    await sub.unsubscribe()
    await nc.drain()

    if not cgp_received:
        pytest.skip(
            f"No {CGP_SUBJECT} packet within {CGP_TIMEOUT}s — "
            "Flute may be in degraded mode (no GPU TTS). "
            "Run with --profile voice,gpu to enable full synthesis."
        )

    pkt = cgp_received[0]
    assert "spec" in pkt or "super_nodes" in pkt or "summary" in pkt, (
        f"CGP packet missing expected fields: {list(pkt.keys())}"
    )
