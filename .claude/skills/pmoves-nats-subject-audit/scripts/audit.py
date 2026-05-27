#!/usr/bin/env python3
"""pmoves-nats-subject-audit — diff declared vs live NATS subjects.

No third-party deps. Uses stdlib urllib + re + json.

Exit codes:
  0 — informational run completed (regardless of drift)
  2 — fatal error (cannot reach monitoring endpoint AND no docs)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTEXT_DIR = REPO_ROOT / ".claude" / "context"
DOC_FILES = [
    CONTEXT_DIR / "nats-subjects.md",
    CONTEXT_DIR / "geometry-nats-subjects.md",
]
NATS_MONITOR_URL = os.environ.get(
    "NATS_MONITOR_URL",
    "http://127.0.0.1:8222/jsz?streams=true&consumers=true",
)

# Subject pattern: lowercase, at least two dot-separated segments, alphanumeric + underscore.
SUBJECT_RE = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_*>]+)+)`")


def parse_declared() -> set[str]:
    declared: set[str] = set()
    for doc in DOC_FILES:
        if not doc.exists():
            print(f"WARN: missing doc {doc}", file=sys.stderr)
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        for match in SUBJECT_RE.findall(text):
            # Filter out obviously non-subject tokens (URLs, file paths).
            if "/" in match or match.endswith(".md") or match.endswith(".py"):
                continue
            declared.add(match)
    return declared


def fetch_live() -> set[str]:
    try:
        with urllib.request.urlopen(NATS_MONITOR_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"WARN: cannot reach NATS monitor at {NATS_MONITOR_URL}: {exc}", file=sys.stderr)
        return set()

    live: set[str] = set()
    # /jsz schema: account_details[].stream_detail[].config.subjects + consumer_detail[].config.filter_subject
    for account in data.get("account_details", []) or []:
        for stream in account.get("stream_detail", []) or []:
            cfg = stream.get("config", {}) or {}
            for subj in cfg.get("subjects", []) or []:
                live.add(subj)
            for consumer in stream.get("consumer_detail", []) or []:
                ccfg = consumer.get("config", {}) or {}
                fs = ccfg.get("filter_subject")
                if fs:
                    live.add(fs)
                for fs2 in ccfg.get("filter_subjects", []) or []:
                    live.add(fs2)
    return live


def is_match(declared: str, live: str) -> bool:
    """Account for wildcards on either side: `archon.mint.*.v1` matches `archon.mint.agent.v1`."""
    if declared == live:
        return True
    if "*" not in declared and "*" not in live and ">" not in declared and ">" not in live:
        return False
    pat = re.escape(declared).replace(r"\*", r"[^.]+").replace(r"\>", r".+")
    return re.fullmatch(pat, live) is not None or re.fullmatch(
        re.escape(live).replace(r"\*", r"[^.]+").replace(r"\>", r".+"),
        declared,
    ) is not None


def main() -> int:
    declared = parse_declared()
    live = fetch_live()

    if not declared and not live:
        print("ERROR: no declared subjects parsed AND no live subjects observed", file=sys.stderr)
        return 2

    # Bucket subjects accounting for wildcards.
    declared_live: list[str] = []
    declared_orphan: list[str] = []
    matched_live: set[str] = set()

    for d in sorted(declared):
        hits = [l for l in live if is_match(d, l)]
        if hits:
            declared_live.append(d)
            matched_live.update(hits)
        else:
            declared_orphan.append(d)

    live_unknown = sorted(live - matched_live)

    print("== declared-not-live (orphans) ==")
    if declared_orphan:
        for s in declared_orphan:
            print(f"- {s}")
    else:
        print("(none)")

    print("\n== live-not-declared (drift) ==")
    if live_unknown:
        for s in live_unknown:
            print(f"- {s}")
    else:
        print("(none)")

    print("\n== declared-and-live (ok) ==")
    if declared_live:
        for s in declared_live:
            print(f"- {s}")
    else:
        print("(none)")

    print(
        f"\nsummary: declared={len(declared)} live={len(live)} "
        f"orphans={len(declared_orphan)} drift={len(live_unknown)} ok={len(declared_live)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
