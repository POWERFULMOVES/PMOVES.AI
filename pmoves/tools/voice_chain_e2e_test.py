#!/usr/bin/env python3
"""End-to-end voice chain verifier (Session 12 Lane 3).

Publishes a synthetic `agentzero.task.result.v1` message with `meta.voice_mode=true`
and waits for the voice-relay to transform and re-publish it on
`voice.agent.response.v1`. Reports timing (publish → republish latency) and
asserts the relay's payload transformation is correct.

This proves the voice chain works end-to-end through the bus layer:

    test publisher (this script)
         │
         ▼ agentzero.task.result.v1
         │
    voice-relay (port 8121)
         │
         ▼ voice.agent.response.v1
         │
    test subscriber (this script)

Prerequisites:
    - NATS broker running (default: nats://nats:pmoves@nats:4222)
    - voice-relay service running (port 8121, /healthz returns nats_connected=true)
    - Flute-Gateway is NOT required (this only tests the bus, not synthesis)

Usage:
    # Default (NATS + voice-relay running)
    python pmoves/tools/voice_chain_e2e_test.py

    # Custom NATS URL
    NATS_URL=nats://nats:pmoves@nats:4222 python pmoves/tools/voice_chain_e2e_test.py

    # Longer wait window (for slow runners)
    python pmoves/tools/voice_chain_e2e_test.py --wait 15

Exit codes:
    0  Success — relay observed and payload transformation verified
    1  Timeout — relay did not republish within the wait window
    2  Connection / setup error
    3  Payload validation failed (relay is alive but transformation is broken)
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any, Dict

try:
    import nats
except ImportError:
    print("ERROR: nats-py not installed. Install with: pip install nats-py", file=sys.stderr)
    sys.exit(2)


INPUT_SUBJECT = "agentzero.task.result.v1"
OUTPUT_SUBJECT = "voice.agent.response.v1"


def _build_synthetic_task(text: str, task_id: str) -> Dict[str, Any]:
    """Build a synthetic agent-zero task result with voice_mode enabled."""
    return {
        "task_id": task_id,
        "output": text,
        "meta": {
            "voice_mode": True,
            "platform": "voice-chain-e2e-test",
            "user_id": "voice-chain-test-user",
            "model": "claude-opus-4-6",
            "sources": ["voice_chain_e2e_test.py"],
        },
    }


def _validate_relay_payload(payload: Dict[str, Any], expected_text: str, expected_task_id: str) -> list[str]:
    """Return a list of validation errors (empty list = valid)."""
    errors: list[str] = []
    # voice-relay may wrap the payload in an envelope (services.common.events.envelope)
    # or publish bare — handle both shapes.
    inner = payload
    if "data" in payload and isinstance(payload.get("data"), dict):
        inner = payload["data"]

    if inner.get("response_text") != expected_text:
        errors.append(
            f"response_text mismatch: got {inner.get('response_text')!r}, "
            f"expected {expected_text!r}"
        )
    if inner.get("message_id") != expected_task_id:
        errors.append(
            f"message_id mismatch: got {inner.get('message_id')!r}, "
            f"expected {expected_task_id!r}"
        )
    if inner.get("platform") != "voice-chain-e2e-test":
        errors.append(f"platform mismatch: got {inner.get('platform')!r}")
    if inner.get("user_id") != "voice-chain-test-user":
        errors.append(f"user_id mismatch: got {inner.get('user_id')!r}")
    if not inner.get("timestamp"):
        errors.append("timestamp missing or empty")
    return errors


async def run_test(nats_url: str, wait_seconds: float, text: str) -> int:
    """Run the voice chain e2e test. Returns the exit code."""
    task_id = str(uuid.uuid4())
    received_event = asyncio.Event()
    received_payload: Dict[str, Any] = {}
    publish_ts: float | None = None
    receive_ts: float | None = None

    print(f"voice-chain-e2e: connecting to NATS at {nats_url}")
    try:
        nc = await nats.connect(nats_url, connect_timeout=5)
    except Exception as exc:
        print(f"ERROR: NATS connect failed: {exc}", file=sys.stderr)
        return 2

    print(f"voice-chain-e2e: connected — subscribing to {OUTPUT_SUBJECT}")

    async def output_handler(msg) -> None:
        nonlocal receive_ts
        receive_ts = time.monotonic()
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"WARN: failed to decode {OUTPUT_SUBJECT} payload: {exc}", file=sys.stderr)
            return

        # voice-relay may publish for OTHER tasks during this test — only react to ours
        inner = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(inner, dict):
            return
        if inner.get("message_id") != task_id:
            return  # not our message; ignore

        received_payload.update(data)
        received_event.set()

    sub = await nc.subscribe(OUTPUT_SUBJECT, cb=output_handler)
    # Tiny delay to ensure subscription is registered before publish
    await asyncio.sleep(0.1)

    print(f"voice-chain-e2e: publishing synthetic {INPUT_SUBJECT} with task_id={task_id}")
    payload = _build_synthetic_task(text, task_id)
    publish_ts = time.monotonic()
    await nc.publish(INPUT_SUBJECT, json.dumps(payload).encode("utf-8"))
    await nc.flush()

    print(f"voice-chain-e2e: waiting up to {wait_seconds}s for relay republish on {OUTPUT_SUBJECT}")
    try:
        await asyncio.wait_for(received_event.wait(), timeout=wait_seconds)
    except asyncio.TimeoutError:
        print(
            f"FAIL: voice-relay did not republish within {wait_seconds}s.\n"
            f"  Check: voice-relay is running (`make -C pmoves up-voice-relay` or similar)\n"
            f"  Check: voice-relay /healthz reports nats_connected=true\n"
            f"  Check: voice-relay subscribed to {INPUT_SUBJECT}",
            file=sys.stderr,
        )
        await sub.unsubscribe()
        await nc.close()
        return 1

    latency_ms = (receive_ts - publish_ts) * 1000.0 if publish_ts and receive_ts else -1.0
    print(f"voice-chain-e2e: received relay republish after {latency_ms:.1f}ms")

    errors = _validate_relay_payload(received_payload, text, task_id)
    if errors:
        print("FAIL: relay payload validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(f"  Full payload received: {json.dumps(received_payload, indent=2)}", file=sys.stderr)
        await sub.unsubscribe()
        await nc.close()
        return 3

    print("PASS: voice chain end-to-end verified")
    print(f"  task_id:        {task_id}")
    print(f"  text:           {text!r}")
    print(f"  publish→relay:  {latency_ms:.1f}ms")
    print(f"  payload shape:  {sorted(received_payload.keys())}")

    await sub.unsubscribe()
    await nc.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Voice chain end-to-end NATS verifier")
    parser.add_argument(
        "--nats-url",
        default=os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222"),
        help="NATS broker URL (default: nats://nats:pmoves@nats:4222 or $NATS_URL)",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=10.0,
        help="Seconds to wait for relay republish (default: 10)",
    )
    parser.add_argument(
        "--text",
        default="Voice chain end-to-end test",
        help="Text payload to send (default: 'Voice chain end-to-end test')",
    )
    args = parser.parse_args()

    return asyncio.run(run_test(args.nats_url, args.wait, args.text))


if __name__ == "__main__":
    sys.exit(main())
