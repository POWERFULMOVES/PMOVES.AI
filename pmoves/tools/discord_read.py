#!/usr/bin/env python3
"""Fetch messages from a Discord channel via REST API.

Usage:
    python discord_read.py --channel 1394743475349622905 --limit 50
    python discord_read.py --channel 1394743475349622905 --limit 200 --output messages.json
    python discord_read.py --channel 1394743475349622905 --all --format human

Requires DISCORD_BOT_TOKEN env var (bot must have Read Message History + Message Content intent).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, AsyncIterator, Optional

import httpx

DISCORD_API = "https://discord.com/api/v10"
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")


def _headers() -> dict[str, str]:
    if not BOT_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bot {BOT_TOKEN}"}


async def fetch_messages(
    channel_id: str,
    limit: int = 100,
    before: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Fetch up to `limit` messages (max 100 per call) from a channel."""
    params: dict[str, Any] = {"limit": min(limit, 100)}
    if before:
        params["before"] = before

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=_headers(),
            params=params,
        )
        if r.status_code == 401:
            print("ERROR: Invalid or expired bot token", file=sys.stderr)
            sys.exit(1)
        if r.status_code == 403:
            print(f"ERROR: Bot lacks access to channel {channel_id}", file=sys.stderr)
            sys.exit(1)
        r.raise_for_status()
        return r.json()


async def fetch_paginated(
    channel_id: str,
    total: int,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Paginate through channel history, yielding batches of up to 100."""
    fetched = 0
    before: Optional[str] = None

    while fetched < total:
        batch_size = min(100, total - fetched)
        batch = await fetch_messages(channel_id, limit=batch_size, before=before)
        if not batch:
            break
        yield batch
        fetched += len(batch)
        before = batch[-1]["id"]
        if len(batch) < batch_size:
            break  # reached end of channel history


async def fetch_all(channel_id: str) -> AsyncIterator[list[dict[str, Any]]]:
    """Fetch entire channel history."""
    before: Optional[str] = None

    while True:
        batch = await fetch_messages(channel_id, limit=100, before=before)
        if not batch:
            break
        yield batch
        before = batch[-1]["id"]
        if len(batch) < 100:
            break


def format_human(messages: list[dict[str, Any]]) -> str:
    """Format messages as human-readable text."""
    lines = []
    for msg in messages:
        ts = msg.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("+00:00", "+00:00"))
            ts_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts_str = ts[:16] if ts else "unknown"
        author = msg.get("author", {}).get("username", "unknown")
        content = msg.get("content", "")
        attachments = msg.get("attachments", [])

        line = f"[{ts_str}] {author}: {content}"
        if attachments:
            att_urls = ", ".join(a.get("url", "") for a in attachments if a.get("url"))
            if att_urls:
                line += f"  [attachments: {att_urls}]"
        lines.append(line)
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Discord channel messages")
    parser.add_argument("--channel", "-c", required=True, help="Discord channel ID")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Number of messages (default 50)")
    parser.add_argument("--all", action="store_true", help="Fetch entire channel history")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--format", "-f", choices=["json", "human"], default="json", help="Output format")
    args = parser.parse_args()

    all_messages: list[dict[str, Any]] = []

    if args.all:
        print("Fetching entire channel history...", file=sys.stderr)
        async for batch in fetch_all(args.channel):
            all_messages.extend(batch)
            print(f"  fetched {len(all_messages)} messages...", file=sys.stderr)
    else:
        async for batch in fetch_paginated(args.channel, args.limit):
            all_messages.extend(batch)

    # Discord returns newest-first; reverse for chronological order
    all_messages.reverse()

    print(f"Total: {len(all_messages)} messages", file=sys.stderr)

    if args.format == "human":
        output = format_human(all_messages)
    else:
        output = json.dumps(all_messages, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
