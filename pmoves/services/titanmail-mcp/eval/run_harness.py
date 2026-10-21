#!/usr/bin/env python3
"""TitanMail date-window + dedup smoke harness.

Offline (CI default, no network):
    python pmoves/services/titanmail-mcp/eval/run_harness.py

Against a live mailpit (seeds the fixture over SMTP, then queries the HTTP API).
This WRITES ~470 messages into that mailpit, tagged with a per-run X-Tags value so
queries are scoped to this run; mailpit's MP_MAX_MESSAGES (default 500) may prune
older messages in a shared dev inbox, so point it at a throwaway instance:
    python .../run_harness.py --transport mailpit --mailpit-url http://127.0.0.1:8025 \
        --seed-smtp 127.0.0.1:1025

Exit: 0 pass / 1 below target (date accuracy < 0.99 or dedup precision < 0.999)
      / 3 could-not-measure (e.g. mailpit unreachable). 3 is NOT a pass.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import smtplib
import sys
import time
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from titanmail.evalkit.fixture import build_fixture  # noqa: E402
from titanmail.evalkit.harness import (EXIT_COULD_NOT_MEASURE, build_queries, run,  # noqa: E402
                                       score_naive, summarize)
from titanmail.service import TitanMailService  # noqa: E402
from titanmail.timewindow import FrozenClock, load_tz  # noqa: E402
from titanmail.transports import InMemoryTransport, MailpitTransport, TransportError  # noqa: E402


def make_caller(transport_factory, now, via: str):
    cache: dict = {}

    async def call(tool: str, args: dict, server_tz: str):
        if server_tz not in cache:
            svc = TitanMailService(transport_factory(), clock=FrozenClock(now), tz=load_tz(server_tz))
            if via == "mcp":
                from titanmail.mcp_app import build_mcp
                cache[server_tz] = (svc, build_mcp(svc))
            else:
                cache[server_tz] = (svc, None)
        svc, mcp = cache[server_tz]
        if mcp is not None:
            from titanmail.mcp_app import payload_of
            return payload_of(await mcp.call_tool(tool, args))
        return await getattr(svc, tool)(**args)

    return call


def seed_mailpit(fx, smtp: str, run_tag: str) -> None:
    host, _, port = smtp.partition(":")
    with smtplib.SMTP(host, int(port or 1025), timeout=30) as s:
        for m in fx.messages:
            s.send_message(m.to_mime(run_tag), from_addr=m.from_addr, to_addrs=m.to)


async def main_async(ns) -> int:
    fx = build_fixture(seed=ns.seed)
    queries = build_queries(fx)
    if ns.transport == "memory":
        emails = fx.emails()
        factory = lambda: InMemoryTransport(emails)  # noqa: E731
    else:
        run_tag = ns.run_tag or f"titanmail-eval-{secrets.token_hex(4)}"
        if ns.seed_smtp:
            try:
                seed_mailpit(fx, ns.seed_smtp, run_tag)
            except OSError as exc:
                print(f"COULD-NOT-MEASURE: SMTP seed to {ns.seed_smtp} failed: {exc}", file=sys.stderr)
                return EXIT_COULD_NOT_MEASURE
            time.sleep(ns.settle_seconds)
        scope = f"tag:{run_tag}"
        factory = lambda: MailpitTransport(ns.mailpit_url, scope_query=scope)  # noqa: E731
        try:
            probe = await factory().search(  # reachability probe
                __import__("titanmail.timewindow", fromlist=["TimeWindow"]).TimeWindow(
                    fx.now.replace(year=2000), fx.now, "explicit"), "", 1)
            print(f"mailpit reachable; probe returned {len(probe)} message(s) for {scope}",
                  file=sys.stderr)
        except TransportError as exc:
            print(f"COULD-NOT-MEASURE: {exc}", file=sys.stderr)
            return EXIT_COULD_NOT_MEASURE

    call = make_caller(factory, fx.now, ns.via)
    score = await run(fx, queries, call)
    report = {
        "transport": ns.transport, "via": ns.via,
        "fixture": {"messages": len(fx.messages), "span_days": round(fx.span_days(), 1),
                    "true_duplicate_pairs": len(fx.true_duplicate_pairs()), "seed": fx.seed,
                    "frozen_now": fx.now.isoformat()},
        "query_set": summarize(queries),
        "score": score.to_dict(),
        "positive_control_naive_utc_day_filter_accuracy": round(score_naive(fx, queries), 4),
    }
    code = score.verdict()
    report["exit_code"] = code
    report["verdict"] = {0: "PASS", 1: "BELOW TARGET", 3: "COULD-NOT-MEASURE"}[code]
    text = json.dumps(report, indent=2, default=str)
    if ns.json:
        Path(ns.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transport", choices=["memory", "mailpit"], default="memory")
    ap.add_argument("--via", choices=["mcp", "service"], default="mcp",
                    help="mcp = through FastMCP.call_tool (default); service = core only")
    ap.add_argument("--mailpit-url", default=os.getenv("TITANMAIL_MAILPIT_URL", "http://127.0.0.1:8025"))
    ap.add_argument("--seed-smtp", default="", help="host:port -- seed the fixture over SMTP first")
    ap.add_argument("--run-tag", default="", help="X-Tags value scoping this run (default random)")
    ap.add_argument("--settle-seconds", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--json", default="", help="also write the report here")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
