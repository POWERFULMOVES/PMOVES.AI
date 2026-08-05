#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""
NATS JetStream stream validation — asserts the 9 expected PMOVES streams exist.

Lane 5 (2026-08-01): the slice 3 + slice 6 subject families
(comfy.collab.*, room.*, helpdesk.*) used to publish into the void because
no backing JetStream stream was declared. This validator is the CI-runnable
guard that catches the regression.

Usage:
    # From the make target (recommended)
    make nats-streams-validate

    # Or manually
    nats -s nats://nats:pmoves@nats:4222 stream ls -n > /tmp/streams.txt
    uv run --script validate_streams.py /tmp/streams.txt

    # Exit codes:
    #   0 — all 9 expected streams present (with their expected subject filters)
    #   1 — one or more streams missing or misconfigured
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

# Force UTF-8 stdout/stderr on Windows (cp1252 default can't encode the
# checkmark / X marks below). Per the Lane 3 lesson — pin encoding on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# (stream_name, subject_filter, retention) — keep in sync with init_streams.sh
EXPECTED_STREAMS: list[tuple[str, str, str]] = [
    # Name,               Subjects,                  Retention
    ("GEOMETRY_CGP", "geometry.>", "limits"),
    ("TOKENISM_ATTRIBUTION", "tokenism.>", "interest"),  # legacy — see migration note
    ("BOTZ_COORDINATION", "botz.>", "limits"),
    ("MESH_GPU", "mesh.gpu.>", "limits"),
    ("CONTENT_PROVENANCE", "content.>", "limits"),
    ("COMFY_COLLAB", "comfy.collab.>", "limits"),
    ("ROOMS", "room.>", "limits"),
    ("HELPDESK", "helpdesk.>", "limits"),
    ("ARCHON", "archon.>", "limits"),  # mint family (#2336) — added 2026-08-04
]

# Streams the validator does NOT require (control-plane / p7.* / voice.*) — present
# in the operator's deployment but maintained by other sidecars or out of scope.
ALLOWED_OPTIONAL: set[str] = set()


class StreamRow(NamedTuple):
    name: str
    subjects: str
    retention: str


def parse_streams_ls_output(text: str) -> list[StreamRow]:
    """Parse the `nats stream ls -n` output.

    Expected format (one line per stream):
        GEOMETRY_CGP         geometry.>                limits
    """
    rows: list[StreamRow] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("---") or "Streams" in line and "Subjects" in line:
            continue
        # The nats CLI uses whitespace padding; split on runs of whitespace.
        parts = re.split(r"\s+", line.strip(), maxsplit=2)
        if len(parts) < 3:
            continue
        name, subjects, retention = parts[0], parts[1], parts[2]
        # Subjects are space-comma-separated if there are multiple; we only
        # declare single-subject streams in init_streams.sh.
        rows.append(StreamRow(name=name, subjects=subjects, retention=retention))
    return rows


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("ERROR: usage: validate_streams.py <path-to-stream-ls-output>", file=sys.stderr)
        print(
            "  Capture output: nats -s nats://nats:pmoves@nats:4222 stream ls -n > streams.txt",
            file=sys.stderr,
        )
        return 1

    path = Path(argv[1])
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    actual = parse_streams_ls_output(text)
    actual_by_name = {r.name: r for r in actual}

    failures: list[str] = []

    for name, subjects, retention in EXPECTED_STREAMS:
        if name not in actual_by_name:
            failures.append(f"  - MISSING: {name} (expected subjects={subjects}, retention={retention})")
            continue
        row = actual_by_name[name]
        if row.subjects != subjects:
            failures.append(
                f"  - WRONG_SUBJECTS: {name} (expected {subjects!r}, got {row.subjects!r})"
            )
        if row.retention != retention:
            failures.append(
                f"  - WRONG_RETENTION: {name} (expected {retention!r}, got {row.retention!r})"
            )

    if failures:
        print(f"❌ NATS stream validation FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f)
        print(
            f"\n  Found {len(actual)} stream(s): {sorted(r.name for r in actual)}",
            file=sys.stderr,
        )
        print(
            "  Run `make nats-streams-init` to (idempotently) create the missing streams.",
            file=sys.stderr,
        )
        return 1

    print(f"✅ NATS stream validation PASSED — all {len(EXPECTED_STREAMS)} expected streams present.")
    for name, subjects, retention in EXPECTED_STREAMS:
        print(f"   ✓ {name:<24} {subjects:<22} {retention}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
