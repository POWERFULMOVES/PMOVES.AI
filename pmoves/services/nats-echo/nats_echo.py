"""NATS echo subscriber — prints messages on a configurable subject."""
import asyncio
import os
import signal

import nats

try:
    from services.common.redact import redact_url
except ImportError:  # image ships without services/common; copy of services/common/redact.py
    import re as _re

    def redact_url(url):
        if url is None:
            return ""
        text = str(url)
        spans = []
        prev_at = -1
        for match in _re.finditer("@", text):
            at = match.start()
            scheme = text.find("://", prev_at + 1, at)
            if scheme >= 0:
                spans.append([scheme + 3, at])
            elif spans:
                spans[-1][1] = at
            else:
                spans.append([0, at])
            prev_at = at
        out = []
        pos = 0
        for start, end in spans:
            out.append(text[pos:start] + "***")
            pos = end
        out.append(text[pos:])
        return _re.sub(
            r"(?i)([?&;#][\w.\-]*(?:password|passwd|pwd|pass|secret|token|api[_\-]?key|auth|signature|sig)[\w.\-]*=)[^&#;\s]*",
            r"\1***",
            "".join(out),
        )


async def main(subject: str, url: str) -> None:
    nc = nats.NATS()
    await nc.connect(url)
    print(f"[nats-echo] connected to {redact_url(url)}, subscribing to '{subject}'", flush=True)

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
    url = os.environ.get("NATS_URL", "nats://nats:4222")
    try:
        asyncio.run(main(subject, url))
    except KeyboardInterrupt:
        pass
