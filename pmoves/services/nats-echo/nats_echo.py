"""NATS echo subscriber — prints messages on a configurable subject."""
import asyncio
import os
import signal
import sys

import nats


async def main(subject: str, url: str) -> None:
    nc = nats.NATS()
    await nc.connect(url)
    print(f"[nats-echo] connected to {url}, subscribing to '{subject}'", flush=True)

    async def handler(msg):
        print(
            f"[nats-echo] subject={msg.subject} reply={msg.reply} "
            f"data={msg.data.decode(errors='replace')}",
            flush=True,
        )

    await nc.subscribe(subject, cb=handler)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
    except NotImplementedError:
        pass  # Windows — rely on KeyboardInterrupt
    try:
        await stop.wait()
    except asyncio.CancelledError:
        pass
    await nc.drain()


if __name__ == "__main__":
    subject = os.environ.get("NATS_ECHO_SUBJECT", ">")
    url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
    try:
        asyncio.run(main(subject, url))
    except KeyboardInterrupt:
        pass
