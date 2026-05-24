#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py==2.10.0"]
# ///
"""Persistent NATS inbox for node-bound agent coordination messages."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


DEFAULT_SUBJECTS = (
    "claw.task.assign.v1",
    "branch.>",
    "chit.>",
    "p7.>",
    "owner.presence.>",
)


async def _ignore_nats_error(exc: Exception) -> None:
    return None


def resolve_host_nats_url(url: str) -> str:
    if os.environ.get("PMOVES_NATS_NO_HOST_REWRITE", "").lower() in ("1", "true", "yes"):
        return url
    parts = urlsplit(url)
    userinfo = ""
    hostport = parts.netloc
    if "@" in hostport:
        userinfo, hostport = hostport.rsplit("@", 1)
        userinfo += "@"
    if hostport == "nats":
        hostport = "127.0.0.1"
    elif hostport.startswith("nats:"):
        hostport = "127.0.0.1:" + hostport.split(":", 1)[1]
    return urlunsplit((parts.scheme, userinfo + hostport, parts.path, parts.query, parts.fragment))


def parse_subjects(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_SUBJECTS)
    subjects = [part.strip() for part in value.split(",") if part.strip()]
    return subjects or list(DEFAULT_SUBJECTS)


def default_inbox_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "PMOVES" / "agent-inbox"
    root = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(root) / "pmoves" / "agent-inbox"


def inbox_path(agent_id: str, inbox_dir: str | None = None) -> Path:
    safe_agent = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in agent_id)
    root = Path(inbox_dir) if inbox_dir else default_inbox_dir()
    return root / f"{safe_agent}.jsonl"


def decode_payload(data: bytes) -> object:
    text = data.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def append_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


async def run_inbox(
    *,
    nats_url: str,
    agent_id: str,
    subjects: Iterable[str],
    output_path: Path,
    max_messages: int | None,
) -> int:
    try:
        import nats
    except ImportError:
        print("ERROR: nats-py is required. Install with: pip install nats-py", file=sys.stderr)
        return 2

    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    received = 0

    async def handler(msg) -> None:
        nonlocal received
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "subject": msg.subject,
            "reply": msg.reply or None,
            "payload": decode_payload(msg.data),
        }
        append_record(output_path, record)
        received += 1
        print(json.dumps({"received": received, "subject": msg.subject, "path": str(output_path)}))
        if max_messages is not None and received >= max_messages:
            stop_event.set()

    nc = await asyncio.wait_for(
        nats.connect(
            nats_url,
            name=f"pmoves-agent-inbox-{agent_id}",
            connect_timeout=5,
            allow_reconnect=False,
            error_cb=_ignore_nats_error,
        ),
        timeout=8,
    )
    try:
        for subject in subjects:
            await nc.subscribe(subject, cb=handler)
        await nc.flush(timeout=2)
        print(json.dumps({
            "status": "listening",
            "agent_id": agent_id,
            "subjects": list(subjects),
            "path": str(output_path),
        }))
        await stop_event.wait()
        await nc.flush(timeout=2)
        return 0
    finally:
        await nc.drain()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persist node-bound PMOVES NATS messages to a JSONL inbox.")
    parser.add_argument("--agent-id", default=os.environ.get("PMOVES_AGENT_ID", "5090-CODEX"))
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://nats:pmoves@127.0.0.1:4222"))
    parser.add_argument(
        "--subjects",
        default=os.environ.get("PMOVES_AGENT_INBOX_SUBJECTS"),
        help="Comma-separated NATS subjects. Defaults to task, branch, CHIT, P7, and owner-presence subjects.",
    )
    parser.add_argument("--inbox-dir", default=os.environ.get("PMOVES_AGENT_INBOX_DIR"))
    parser.add_argument("--max-messages", type=int, default=None, help="Exit after this many messages; useful for smoke tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    subjects = parse_subjects(args.subjects)
    path = inbox_path(args.agent_id, args.inbox_dir)
    try:
        return asyncio.run(
            run_inbox(
                nats_url=resolve_host_nats_url(args.nats_url),
                agent_id=args.agent_id,
                subjects=subjects,
                output_path=path,
                max_messages=args.max_messages,
            )
        )
    except Exception as exc:
        print(f"ERROR: NATS inbox failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
