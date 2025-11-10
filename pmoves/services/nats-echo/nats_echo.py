from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Optional

from nats.aio.client import Client as NATS


async def main() -> int:
    parser = argparse.ArgumentParser(description="NATS echo subscriber for DeepResearch subjects")
    parser.add_argument("--nats", default=os.getenv("NATS_URL", "nats://nats:4222"))
    parser.add_argument("--subject", default=os.getenv("NATS_ECHO_SUBJECT", "research.deepresearch.request.v1"))
    parser.add_argument("--once", action="store_true", help="exit after first message")
    args = parser.parse_args()

    # Normalize NATS URL list; avoid mixing ws:// and nats:// in the same pool.
    raw_arg = (args.nats or "").strip()
    env_url = (os.getenv("NATS_URL", "nats://nats:4222") or "nats://nats:4222").strip()
    raw = raw_arg or env_url
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not urls:
        urls = [os.getenv("NATS_URL", "nats://nats:4222") or "nats://nats:4222"]
    scheme = urls[0].split(":", 1)[0]
    urls = [u for u in urls if u.startswith(f"{scheme}:")]

    nc = NATS()
    # Retry a few times to give the broker time to come up
    last_err: Optional[Exception] = None
    print(f"nats-echo: urls={urls}")
    for attempt in range(10):
        print(f"nats-echo: connect attempt {attempt+1}/10")
        try:
            await nc.connect(servers=urls)
            last_err = None
            break
        except Exception as exc:  # pragma: no cover
            last_err = exc
            print(f"nats-echo: connect failed: {exc}")
            await asyncio.sleep(1.0)
    if last_err:
        raise last_err
    print(f"connected to {','.join(urls)}")

    fut: Optional[asyncio.Future] = None
    if args.once:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

    async def cb(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            data = msg.data.decode("utf-8", errors="ignore")
        print(f"[{msg.subject}] {data}")
        if fut and not fut.done():
            fut.set_result(True)

    sub = await nc.subscribe(args.subject, cb=cb)
    try:
        if fut:
            await asyncio.wait_for(fut, timeout=60)
        else:
            while True:
                await asyncio.sleep(3600)
    finally:
        await sub.unsubscribe()
        await nc.drain()
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except KeyboardInterrupt:
        rc = 130
    raise SystemExit(rc)
