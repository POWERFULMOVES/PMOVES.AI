#!/usr/bin/env python3
"""Subscribe to geometry.cgp.v1 and print any messages received."""
import asyncio
import os
import nats


async def main() -> None:
    """Connect to NATS and print CGP events for 8 seconds."""
    url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
    nc = await nats.connect(url)
    print(f"Connected to NATS: {url}")
    msgs = []

    async def handler(msg: "nats.aio.msg.Msg") -> None:
        msgs.append(msg)
        print(f"RECV: {msg.subject} ({len(msg.data)} bytes)")
        print(f"Preview: {msg.data[:300]!r}")

    await nc.subscribe("tokenism.geometry.event.v1", cb=handler)
    await nc.subscribe("geometry.cgp.v1", cb=handler)
    await nc.subscribe("geometry.>", cb=handler)
    await nc.subscribe("tokenism.>", cb=handler)
    print("Subscribed to tokenism.geometry.event.v1 + wildcards — waiting 10s")
    await asyncio.sleep(10)
    print(f"Total messages: {len(msgs)}")
    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
