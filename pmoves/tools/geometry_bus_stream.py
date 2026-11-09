#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["nats-py>=2.7"]
# ///
"""geometry_bus_stream.py — create/inspect the JetStream stream for the GEOMETRY BUS.

WHY THIS EXISTS
---------------
`beats_to_cgp.py` publishes with `nc.publish()` — CORE NATS, not JetStream. Without a
stream whose subject filter matches, a published CGP packet is delivered to whatever
happens to be subscribed at that instant and persists nowhere. That is why
`$JSZ` reported 0 messages on a bus whose catalogue declares dozens of subjects: not
"nothing publishes", but "nothing durable was ever configured to catch it".

A JetStream stream listening on the subject captures core-NATS publishes automatically,
so this needs no change to the producer.

Scope is deliberately ONE subject (geometry.cgp.v1). Widen when a second adapter lands
and its subject is known — a `geometry.>` catch-all would apply one retention policy to
subjects with very different volumes.

Usage:
    uv run pmoves/tools/geometry_bus_stream.py status
    uv run pmoves/tools/geometry_bus_stream.py create
    uv run pmoves/tools/geometry_bus_stream.py purge     # drop messages, keep the stream

NATS_URL comes from the environment. There is deliberately no credential-bearing
default — see the note in main().
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import nats
from nats.js.api import RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import NotFoundError

STREAM = "GEOMETRY_CGP"
SUBJECTS = ["geometry.cgp.v1"]

# Bounded on purpose. This is a liveness/observability stream, not an archive: old
# geometry packets have little value and an unbounded stream on a node with 173G free
# is a slow-motion disk incident.
MAX_AGE_SECONDS = 7 * 24 * 3600
MAX_MSGS = 100_000


CONNECT_TIMEOUT_S = 5


async def _connect():
    url = os.environ.get("NATS_URL")
    if not url:
        print(
            "NATS_URL is not set.\n"
            "  Deliberately no default: the previous default in beats_to_cgp.py embedded\n"
            "  credentials (nats://user:pass@host), which is exactly what the fleet rule\n"
            "  against hardcoded creds targets. Export NATS_URL instead.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Bounded connect, and NO reconnect retries. The fleet NATS_URL points at the
    # container DNS name (nats:4222), which does not resolve from the host — running
    # a host-side tool with it inherited from env.shared otherwise hangs forever
    # instead of telling you why. A diagnostic that hangs is worse than one that fails.
    # asyncio.wait_for, NOT just connect_timeout: nats-py's connect_timeout does not
    # bound DNS resolution. With an unresolvable host this raised socket.gaierror only
    # after ~60s of retries while connect_timeout=5 sat there looking authoritative.
    # Measured, not assumed.
    try:
        return await asyncio.wait_for(
            nats.connect(url, connect_timeout=CONNECT_TIMEOUT_S, max_reconnect_attempts=0),
            timeout=CONNECT_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — surface the cause, whatever it is
        host = url.split("@")[-1]
        print(
            f"could not reach NATS at {host} within {CONNECT_TIMEOUT_S}s: {exc}\n"
            f"  If this is a container DNS name (e.g. nats:4222) you are running on the\n"
            f"  host — use the published address instead, e.g. NATS_URL=nats://…@localhost:4222",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


async def cmd_status() -> int:
    nc = await _connect()
    js = nc.jetstream()
    try:
        info = await js.stream_info(STREAM)
        st = info.state
        print(f"  stream   : {STREAM}")
        print(f"  subjects : {', '.join(info.config.subjects)}")
        print(f"  messages : {st.messages}")
        print(f"  bytes    : {st.bytes}")
        print(f"  first/last seq: {st.first_seq}/{st.last_seq}")
        print(f"  consumers: {st.consumer_count}")
    except NotFoundError:
        print(f"  stream {STREAM} does NOT exist — core publishes to "
              f"{SUBJECTS[0]} persist nowhere")
        await nc.close()
        return 1
    await nc.close()
    return 0


async def cmd_create() -> int:
    nc = await _connect()
    js = nc.jetstream()
    cfg = StreamConfig(
        name=STREAM,
        subjects=SUBJECTS,
        storage=StorageType.FILE,
        retention=RetentionPolicy.LIMITS,
        max_age=MAX_AGE_SECONDS,
        max_msgs=MAX_MSGS,
    )
    try:
        info = await js.stream_info(STREAM)
        print(f"  stream {STREAM} already exists "
              f"(subjects: {', '.join(info.config.subjects)}) — no change")
    except NotFoundError:
        info = await js.add_stream(cfg)
        print(f"  created {STREAM} on {', '.join(info.config.subjects)} "
              f"(file storage, max_age={MAX_AGE_SECONDS}s, max_msgs={MAX_MSGS})")
    await nc.close()
    return 0


async def cmd_purge() -> int:
    nc = await _connect()
    js = nc.jetstream()
    await js.purge_stream(STREAM)
    print(f"  purged {STREAM}")
    await nc.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="GEOMETRY BUS JetStream stream management")
    ap.add_argument("command", choices=["status", "create", "purge"])
    args = ap.parse_args()
    return asyncio.run({"status": cmd_status, "create": cmd_create, "purge": cmd_purge}[args.command]())


if __name__ == "__main__":
    raise SystemExit(main())
