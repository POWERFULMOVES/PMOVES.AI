import argparse
import asyncio
import json
import os
import signal
import sys
import time
from typing import Iterable, Optional

try:
    from nats.aio.client import Client as NATS
except ImportError as exc:  # pragma: no cover - missing optional dependency
    raise SystemExit(
        "nats-py is required for the realtime listener. Install with:\n"
        "  python -m pip install --user nats-py\n"
    ) from exc

DEFAULT_NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")


def _format_json(data: bytes, pretty: bool) -> str:
    text = data.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text.strip()
    return json.dumps(parsed, indent=2 if pretty else None, sort_keys=pretty)


async def _listen(
    url: str,
    subjects: Iterable[str],
    *,
    pretty: bool,
    max_messages: int,
) -> None:
    nc = NATS()
    await nc.connect(servers=[url], allow_reconnect=True)

    received = 0
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows (or embedded) may not support signal handlers in asyncio.
            pass

    async def _handler(msg) -> None:
        nonlocal received
        received += 1
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print()
        print(f"[{ts}] subject={msg.subject}")
        if msg.reply:
            print(f"  reply={msg.reply}")
        try:
            metadata = msg.metadata  # JetStream metadata (optional)
        except Exception:
            metadata = None
        if metadata:
            stream_seq = getattr(metadata.sequence, "stream", None)
            consumer_seq = getattr(metadata.sequence, "consumer", None)
            timestamp = getattr(metadata, "timestamp", None)
            meta_bits = []
            if metadata.stream:
                meta_bits.append(f"stream={metadata.stream}")
            if stream_seq is not None:
                meta_bits.append(f"seq={stream_seq}")
            if consumer_seq is not None:
                meta_bits.append(f"consumer_seq={consumer_seq}")
            if timestamp:
                meta_bits.append(f"ts={timestamp.isoformat()}")
            print("  " + " ".join(meta_bits))
        body = _format_json(msg.data, pretty)
        print(body)
        sys.stdout.flush()
        if max_messages and received >= max_messages:
            stop_event.set()

    for subject in subjects:
        await nc.subscribe(subject, cb=_handler)
        print(f"Subscribed to {subject} (url={url})")

    await stop_event.wait()
    await nc.drain()


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Listen to PMOVES NATS topics and pretty-print event envelopes."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_NATS_URL,
        help=f"NATS server URL (default: {DEFAULT_NATS_URL})",
    )
    parser.add_argument(
        "--topics",
        nargs="+",
        default=["content.published.v1"],
        help="One or more subjects to subscribe to.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Exit after receiving N messages (default: keep running).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print envelopes on a single line instead of pretty JSON.",
    )
    return parser.parse_args(argv)


async def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    await _listen(
        args.url,
        args.topics,
        pretty=not args.compact,
        max_messages=args.max,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
