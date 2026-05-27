#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py==2.10.0"]
# ///
"""One-shot: subscribe to a NATS subject, print first message, exit."""

from __future__ import annotations
import argparse
import asyncio
import json
import sys


async def receive_one(nats_url: str, subject: str, timeout: float) -> int:
    import nats

    received: list[dict] = []

    async def handler(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            data = msg.data.decode("utf-8", errors="replace")
        received.append(data)

    nc = await asyncio.wait_for(
        nats.connect(nats_url, name="pmoves-cap-verify", connect_timeout=5, allow_reconnect=False),
        timeout=8,
    )
    try:
        sub = await nc.subscribe(subject, cb=handler)
        print(f"subscribed: {subject}", flush=True)
        # Wait up to timeout for one message
        deadline = asyncio.get_event_loop().time() + timeout
        while not received and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.05)
        await sub.unsubscribe()
    finally:
        await nc.close()

    if received:
        print(json.dumps(received[0], indent=2))
        return 0
    print("TIMEOUT — no message received", file=sys.stderr)
    return 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subject", default="mesh.agent.4090.capabilities.v1")
    p.add_argument("--nats-url", default="nats://127.0.0.1:4223")
    p.add_argument("--timeout", type=float, default=5.0)
    args = p.parse_args()
    return asyncio.run(receive_one(args.nats_url, args.subject, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
