from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any, Dict

try:
    from nats.aio.client import Client as NATS
except Exception as exc:  # pragma: no cover
    print("nats-py is required: pip install nats-py", file=sys.stderr)
    raise


REQUEST_SUBJECT = "research.deepresearch.request.v1"
RESULT_SUBJECT = "research.deepresearch.result.v1"


def _make_envelope(query: str, *, mode: str = "standard") -> Dict[str, Any]:
    evt_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())
    body: Dict[str, Any] = {
        "id": evt_id,
        "source": "deepresearch-smoke",
        "correlation_id": corr_id,
        "payload": {
            "query": query,
            "mode": mode,
            "metadata": {"smoke": True},
        },
    }
    return body


async def main() -> int:
    parser = argparse.ArgumentParser(description="DeepResearch NATS smoke")
    parser.add_argument("--query", default="What changed in PMOVES today?", help="research query")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for a result")
    parser.add_argument("--nats", default=os.getenv("NATS_URL", "nats://nats:4222"), help="NATS URL")
    args = parser.parse_args()

    nc = NATS()
    await nc.connect(servers=[args.nats])

    envelope = _make_envelope(args.query)
    corr_id = envelope["correlation_id"]

    fut: asyncio.Future[Dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def cb(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        if isinstance(data, dict) and data.get("correlation_id") == corr_id:
            if not fut.done():
                fut.set_result(data)

    sub = await nc.subscribe(RESULT_SUBJECT, cb=cb)

    await nc.publish(REQUEST_SUBJECT, json.dumps(envelope).encode("utf-8"))

    started = time.time()
    try:
        result = await asyncio.wait_for(fut, timeout=args.timeout)
    except asyncio.TimeoutError:
        await sub.unsubscribe()
        await nc.drain()
        print("✖ deepresearch-smoke: timed out waiting for result", file=sys.stderr)
        return 2

    await sub.unsubscribe()
    await nc.drain()

    payload = result.get("payload") or {}
    status = payload.get("status") or "unknown"
    duration_ms = payload.get("duration_ms")
    took = (time.time() - started) * 1000.0
    print(
        f"✔ deepresearch-smoke: result status={status} duration_ms={duration_ms} (waited {took:.0f}ms)"
    )
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)

