#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py==2.10.0"]
# ///
"""Publish one PMOVES NATS message from the host."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import urlsplit, urlunsplit


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


async def publish(nats_url: str, subject: str, payload: str) -> int:
    import nats

    nc = await asyncio.wait_for(
        nats.connect(
            nats_url,
            name="pmoves-nats-pub",
            connect_timeout=5,
            allow_reconnect=False,
            error_cb=_ignore_nats_error,
        ),
        timeout=8,
    )
    try:
        await nc.publish(subject, payload.encode("utf-8"))
        await nc.flush(timeout=2)
    finally:
        await nc.close()
    print(f"published {len(payload)} bytes to {subject}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish a PMOVES NATS message.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://nats:pmoves@127.0.0.1:4222"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.subject.strip():
        print("ERROR: --subject must not be empty", file=sys.stderr)
        return 2
    try:
        return asyncio.run(publish(resolve_host_nats_url(args.nats_url), args.subject, args.payload))
    except Exception as exc:
        print(f"ERROR: NATS publish failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
