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
        schemes = list(_re.finditer(r"(?<![A-Za-z0-9+.\-:/@%])[A-Za-z][A-Za-z0-9+.\-]*://", text))
        if not schemes:
            at = text.rfind("@")
            out = "***" + text[at:] if at >= 0 else text
        else:
            out = text[: schemes[0].start()]
            for i, m in enumerate(schemes):
                end = schemes[i + 1].start() if i + 1 < len(schemes) else len(text)
                seg = text[m.end():end]
                at = seg.rfind("@")
                out += m.group(0) + ("***" + seg[at:] if at >= 0 else seg)
        return _re.sub(
            r"(?i)([?&;](?:password|passwd|pass|pwd|secret|token|api_?key|access_token)=)[^&#\s]*",
            r"\1***",
            out,
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
