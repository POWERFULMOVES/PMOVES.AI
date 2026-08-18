"""pmoves/tools/branch_protection_publisher.py

The drift publisher. Wraps the branch_protection.drift_check() output
and publishes one message per non-compliant repo to
pmoves.branch_protection.drift.v1 (NATS). The orchestrator (from the
harness v0 slice) can consume the drift and dispatch a remediation
session.

The publisher follows the same Protocol shape as orchestrator.Publisher
so the test surface is uniform and the real pmoves-nats-mcp wire-up
later just drops in.

Two entry points:

    publish_drift_report(report, publisher) -> int
        Publishes one message per non-compliant repo. Returns the
        number of messages published (0 if everything is in sync).

    publish_drift_for_org(org, publisher, spec) -> int
        High-level helper: runs drift_check(org) + publishes. Returns
        the number of messages published.

CLI:

    python -m pmoves.tools.branch_protection_publisher \\
        --org POWERFULMOVES \\
        --spec pmoves/configs/branch_protection/pmoves_standard.json

Exit code:
    0 = drift published (or zero drift, nothing to publish)
    1 = CLI error (bad spec, no publisher, etc.)
    2 = drift detected but publish failed

NATS subject:

    pmoves.branch_protection.drift.v1 - registered in
    .claude/context/nats-subjects.md. Payload is a single repo's
    drift (the per-repo shape from AuditResult.to_dict()), wrapped
    in a `drift.v1` envelope so subscribers can filter by source.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Protocol

from pmoves.tools.branch_protection import (
    DEFAULT_SPEC_PATH,
    DriftReport,
    audit,
    drift_check,
    load_spec,
)


# --- NATS subject (registered in .claude/context/nats-subjects.md) ---

SUBJECT_DRIFT = "pmoves.branch_protection.drift.v1"


# --- Publisher protocol (matches orchestrator.Publisher) ---


class Publisher(Protocol):
    """Anything that can publish a (subject, payload) message.

    Real implementation wraps pmoves-nats-mcp (the PMOVES-built NATS
    server) or nats-py. Tests use MockPublisher that records what
    was published without actually sending anything.
    """

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        ...


class MockPublisher:
    """In-memory Publisher for tests + dry-run. Records everything."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.fail_next: bool = False  # set to True to test the failure path

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated NATS publish failure")
        self.published.append((subject, payload))


class FilePublisher:
    """JSONL file publisher. Useful for testing without NATS, and as
    a fallback when pmoves-nats-mcp is not reachable. Writes one
    JSON object per line to the given path (or stdout if None).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self.lines: list[str] = []
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Truncate the file on open so re-runs don't accumulate.
            path.write_text("")

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"subject": subject, "payload": payload})
        if self.path is None:
            print(line)
        else:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        self.lines.append(line)


# --- Envelope shape ---


def _envelope(repo_result: dict[str, Any]) -> dict[str, Any]:
    """Wrap a per-repo audit dict in the `drift.v1` envelope.

    The envelope adds a `source` (the publisher's identity) and a
    `published_at` timestamp so subscribers can filter by source +
    order by time. The original audit shape is preserved under
    `audit` for backwards compatibility.
    """
    return {
        "envelope": "drift.v1",
        "source": "pmoves.branch_protection",
        "published_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "audit": repo_result,
    }


# --- Public API ---


def publish_drift_report(
    report: DriftReport,
    publisher: Publisher,
    subject: str = SUBJECT_DRIFT,
) -> int:
    """Publish one drift message per non-compliant repo.

    Returns the number of messages published (0 if everything is
    in sync). Raises RuntimeError if any publish fails.
    """
    published = 0
    for repo_result in report.repos:
        # Only publish non-compliant repos. Compliant repos are silent
        # (publishing every audit would flood the subject).
        if repo_result.is_compliant:
            continue
        publisher.publish(subject, _envelope(repo_result.to_dict()))
        published += 1
    return published


def publish_drift_for_org(
    org: str = "POWERFULMOVES",
    publisher: Optional[Publisher] = None,
    spec: Optional[dict[str, Any]] = None,
    spec_path: Optional[Path] = None,
) -> int:
    """Run drift_check(org) + publish the drift.

    Convenience entry point that the workflow + the Mavis cron both
    call. `publisher` defaults to a MockPublisher (for tests); in
    production the workflow passes a NatsPublisher built on top of
    pmoves-nats-mcp.
    """
    publisher = publisher or MockPublisher()
    if spec is None:
        spec = load_spec(spec_path or DEFAULT_SPEC_PATH)
    report = drift_check(org, spec=spec)
    return publish_drift_report(report, publisher)


# --- CLI ---


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="branch_protection_publisher",
        description=(
            "PMOVES branch protection drift publisher. "
            "Runs drift_check on the named org and publishes the "
            "non-compliant repos to pmoves.branch_protection.drift.v1."
        ),
    )
    p.add_argument(
        "--org",
        default="POWERFULMOVES",
        help="GitHub org to audit (default: %(default)s)",
    )
    p.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="path to pmoves_standard.json (default: %(default)s)",
    )
    p.add_argument(
        "--sink",
        choices=["mock", "file", "nats"],
        default="file",
        help=(
            "publisher sink: file (JSONL to stdout) | mock (in-memory) | "
            "nats (via pmoves-nats-mcp; requires the MCP to be live)"
        ),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="file sink: path to write JSONL (default: stdout)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.sink == "file":
        publisher: Publisher = FilePublisher(args.out)
    elif args.sink == "mock":
        publisher = MockPublisher()
    else:  # nats
        try:
            from pmoves_nats_mcp import NatsPublisher  # type: ignore
        except ImportError as e:
            print(f"nats sink requires pmoves-nats-mcp: {e}", file=sys.stderr)
            return 1
        publisher = NatsPublisher()
    try:
        count = publish_drift_for_org(args.org, publisher, spec_path=args.spec)
    except Exception as e:
        print(f"drift publish failed: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"org": args.org, "published": count, "subject": SUBJECT_DRIFT}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
