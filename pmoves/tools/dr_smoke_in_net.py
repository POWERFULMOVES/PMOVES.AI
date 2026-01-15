from __future__ import annotations

import asyncio
import json
import os
import time
from nats.aio.client import Client as NATS

REQ = os.getenv("DR_REQ_SUBJ", "research.deepresearch.request.v1")
RES = os.getenv("DR_RES_SUBJ", "research.deepresearch.result.v1")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")


async def main() -> int:
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    corr = f"smoke-{int(time.time())}"
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict] = loop.create_future()

    async def cb(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        if isinstance(data, dict) and data.get("correlation_id") == corr and not fut.done():
            fut.set_result(data)

    sub = await nc.subscribe(RES, cb=cb)
    env = {
        "id": corr,
        "source": "deepresearch-smoke-in-net",
        "correlation_id": corr,
        "payload": {"query": "diag smoke", "mode": "local", "metadata": {"smoke": True}},
    }
    await nc.publish(REQ, json.dumps(env).encode("utf-8"))
    try:
        res = await asyncio.wait_for(fut, timeout=45.0)
        status = (res.get("payload") or {}).get("status", "unknown")
        print(f"✔ deepresearch-smoke-in-net: status={status}")
        code = 0
    except asyncio.TimeoutError:
        print("✖ deepresearch-smoke-in-net: timed out waiting for result")
        code = 2
    await sub.unsubscribe()
    await nc.drain()
    raise SystemExit(code)


if __name__ == "__main__":
    asyncio.run(main())

