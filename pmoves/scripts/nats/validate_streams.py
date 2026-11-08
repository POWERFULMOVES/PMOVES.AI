#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""
NATS JetStream stream validation — asserts the 10 expected PMOVES streams exist.

Lane 5 (2026-08-01): the slice 3 + slice 6 subject families
(comfy.collab.*, room.*, helpdesk.*) used to publish into the void because
no backing JetStream stream was declared. This validator is the CI-runnable
guard that catches the regression.

THE INPUT CONTRACT (F5, 2026-10-31). This validator used to claim it read
`nats stream ls -n` -- a table of "NAME SUBJECTS RETENTION". The nats CLI
does NOT emit that: `stream ls -n` prints NAMES ONLY, and `stream ls` prints
Name / Description / Created / Messages / Size / Last Message -- there is no
Subjects column and no Retention column. The old parser was therefore
reading a line format the tool never produces, and the guard could not have
passed against a real server. It was a fiction.

The only output that carries BOTH subjects and retention is
`nats stream info <NAME> -j`:

    {"config": {"name": "COMPUTE",
                "subjects": ["mesh.node.announce.>", "compute.nodes.>"],
                "retention": "limits", ...}, ...}

So the contract is now the CONCATENATED JSON of one `stream info <NAME> -j`
per stream, in sequence. This file parses that with a `raw_decode` loop --
`json.loads` accepts exactly ONE object per document and would reject the
whole capture the moment a second stream was appended.

Subjects are compared as SETS: JetStream does not promise an order, and a
stream that carries the right two families in the other order is the same
stream.

Usage:
    # From the make target (recommended)
    make nats-streams-validate

    # Or manually
    for s in GEOMETRY_CGP COMPUTE; do
      nats -s "$NATS_URL" stream info "$s" -j
    done > streams.json
    uv run --script validate_streams.py streams.json

    # Exit codes:
    #   0 — all expected streams present (with their expected subjects + retention)
    #   1 — one or more streams missing or misconfigured
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple

# Force UTF-8 stdout/stderr on Windows (cp1252 default can't encode the
# checkmark / X marks below). Per the Lane 3 lesson — pin encoding on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class ExpectedStream(NamedTuple):
    """One stream the guard insists on, and the shape it must have."""

    name: str
    subjects: tuple[str, ...]
    retention: str


# Keep in sync with init_streams.sh.
EXPECTED_STREAMS: List[ExpectedStream] = [
    ExpectedStream("GEOMETRY_CGP", ("geometry.>",), "limits"),
    # `interest` is the LEGACY live state, deliberately asserted here: the
    # change to `limits` is documented in init_streams.sh (MIGRATION note) as
    # requiring a manual `stream rm` + re-init on every node that already has
    # the stream, because JetStream retention is immutable after creation.
    # Until that migration is done, `limits` would make this guard red on
    # every live server -- and a red guard stops being read.
    ExpectedStream("TOKENISM_ATTRIBUTION", ("tokenism.>",), "interest"),
    ExpectedStream("BOTZ_COORDINATION", ("botz.>",), "limits"),
    ExpectedStream("MESH_GPU", ("mesh.gpu.>",), "limits"),
    ExpectedStream("CONTENT_PROVENANCE", ("content.>",), "limits"),
    ExpectedStream("COMFY_COLLAB", ("comfy.collab.>",), "limits"),
    ExpectedStream("ROOMS", ("room.>",), "limits"),
    ExpectedStream("HELPDESK", ("helpdesk.>",), "limits"),
    ExpectedStream("ARCHON", ("archon.>",), "limits"),  # mint family (#2336) — 2026-08-04
    # The node registry's announcement plane. The registry subscribes to
    # `mesh.node.announce.>` with a JetStream durable consumer on the stream
    # named `COMPUTE`; before that stream existed the subscribe raised and
    # the registry silently fell back to core NATS, losing every
    # announcement published while it was down. TWO subject families, so the
    # comparison has to be a SET comparison. Keep in sync with
    # init_streams.sh (see PRE_RESTART_PREFLIGHT_2026-08-25.md row R8a).
    ExpectedStream(
        "COMPUTE",
        ("mesh.node.announce.>", "compute.nodes.>"),
        "limits",
    ),
]

# Streams the validator does NOT require (control-plane / p7.* / voice.*) — present
# in the operator's deployment but maintained by other sidecars or out of scope.
ALLOWED_OPTIONAL: set[str] = set()


class StreamRow(NamedTuple):
    """What the server reported about one stream."""

    name: str
    subjects: tuple[str, ...]
    retention: str


def parse_stream_info_json(text: str) -> List[StreamRow]:
    """Parse the concatenated JSON of `nats stream info <NAME> -j` captures.

    The capture is a SEQUENCE of JSON objects, one per stream, in the order
    the loop produced them -- not a JSON array and not one document. So the
    decoder is driven by `raw_decode`, which returns the end offset of the
    object it just read and can be pointed at the next one.

    A stream that does not exist contributes NO object: `stream info` exits
    non-zero and writes nothing to stdout (the error goes to stderr). Such a
    stream is therefore simply absent from the result, and the caller reports
    it MISSING.
    """
    decoder = json.JSONDecoder()
    rows: List[StreamRow] = []
    index = 0
    length = len(text)

    while index < length:
        # Skip the whitespace between two objects.
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        if text[index] != "{":
            snippet = text[index : index + 80].splitlines()[:1]
            raise ValueError(
                "expected a JSON object at offset "
                f"{index}, got {snippet!r}. The capture must be the "
                "concatenated output of `nats stream info <NAME> -j`."
            )
        try:
            payload, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"could not parse the JSON object at offset {index}: {exc}"
            ) from exc
        config = payload.get("config") or {}
        name = config.get("name")
        if not name:
            raise ValueError(
                "a captured stream object has no config.name: "
                f"{json.dumps(payload)[:200]}"
            )
        subjects = tuple(config.get("subjects") or ())
        retention = config.get("retention") or ""
        rows.append(StreamRow(name=name, subjects=subjects, retention=retention))

    return rows


def rows_by_name(rows: List[StreamRow]) -> Dict[str, StreamRow]:
    """Index the reported rows by stream name (last report wins)."""
    return {row.name: row for row in rows}


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(
            "ERROR: usage: validate_streams.py <path-to-stream-info-json>",
            file=sys.stderr,
        )
        print(
            "  Capture output: for s in $(nats -s \"$NATS_URL\" stream ls -n); "
            "do nats -s \"$NATS_URL\" stream info \"$s\" -j; done > streams.json",
            file=sys.stderr,
        )
        return 1

    path = Path(argv[1])
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        actual = parse_stream_info_json(text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    actual_by_name = rows_by_name(actual)

    failures: List[str] = []

    for expected in EXPECTED_STREAMS:
        name = expected.name
        if name not in actual_by_name:
            failures.append(
                f"  - MISSING: {name} "
                f"(expected subjects={list(expected.subjects)}, "
                f"retention={expected.retention})"
            )
            continue
        row = actual_by_name[name]
        # SET comparison: JetStream does not promise an order, and a stream
        # carrying the right families in the other order is the same stream.
        if set(row.subjects) != set(expected.subjects):
            failures.append(
                f"  - WRONG_SUBJECTS: {name} "
                f"(expected {sorted(expected.subjects)!r}, got {sorted(row.subjects)!r})"
            )
        if row.retention != expected.retention:
            failures.append(
                f"  - WRONG_RETENTION: {name} "
                f"(expected {expected.retention!r}, got {row.retention!r})"
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

    print(
        f"✅ NATS stream validation PASSED — all {len(EXPECTED_STREAMS)} "
        "expected streams present."
    )
    for expected in EXPECTED_STREAMS:
        subjects = ",".join(expected.subjects)
        print(f"   ✓ {expected.name:<24} {subjects:<38} {expected.retention}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
