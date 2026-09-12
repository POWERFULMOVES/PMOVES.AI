#!/usr/bin/env python3
"""persona_consumption — CLI producer for persona.consumption.recorded.v1.

Logs a third-reference consumption event (human or agent) to the
persona-thirdref consumer over NATS. This is the agent-side logging
surface; the human side arrives via the Jellyfin playback path.

Usage:
  python3 -m pmoves.tools.persona_consumption \
      --agent crush-spark --kind youtube_video --item VIDEO_ID [--session SID]

  python3 -m pmoves.tools.persona_consumption \
      --user darkxside --kind beat --item "808 Low.m4a"

Env: NATS_URL (default nats://nats:pmoves@nats:4222). Events fail loudly —
a dropped consumption event is lost grounding signal, not a convenience.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys

SUBJECT = "persona.consumption.recorded.v1"


def build_event(args: argparse.Namespace) -> dict:
    event = {
        "consumer_kind": "agent" if args.agent else "human",
        "item_kind": args.kind,
        "item_id": args.item,
        "source": "cli",
        "timestamp": dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    if args.agent:
        event["agent_id"] = args.agent
    if args.user:
        event["user_id"] = args.user
    if args.session:
        event["session_id"] = args.session
    if args.domains:
        event["resonance_domains"] = [d.strip() for d in args.domains.split(",") if d.strip()]
    return event


async def publish(event: dict, url: str) -> None:
    from nats.aio.client import Client as NATS

    client = NATS()
    await client.connect(url, connect_timeout=5)
    await client.publish(SUBJECT, json.dumps(event).encode())
    await client.flush()
    await client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--agent", help="agent_id (agent-side consumption)")
    identity.add_argument("--user", help="user_id (human-side consumption)")
    parser.add_argument("--kind", required=True,
                        choices=["youtube_video", "beat", "generic"])
    parser.add_argument("--item", required=True, help="item identifier")
    parser.add_argument("--session", help="session grouping id")
    parser.add_argument("--domains", help="comma-separated domains (generic kind)")
    args = parser.parse_args(argv)

    event = build_event(args)
    try:
        asyncio.run(publish(event, os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")))
    except Exception as exc:  # noqa: BLE001 — surface, never swallow
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(event))
    return 0


if __name__ == "__main__":
    sys.exit(main())
