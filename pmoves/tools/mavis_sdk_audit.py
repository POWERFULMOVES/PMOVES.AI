"""mavis_sdk_audit.py - inspect the PMOVES_MAVIS_SDK_* audit log.

Lane C of the Mavis SDK env strip slice (per operator direction 2026-09-17):
the audit trail of Mavis SDK env-strip calls is durable JSONL on disk so
operators can re-inspect what bled into which session even after the shell
that did the stripping has exited.

The bash + PowerShell twins both append one JSONL line per
``mavis_sdk_strip_env_for`` / ``Strip-MavisSdkEnvFor`` call to the default
log path ``pmoves/data/chit/mavis_sdk_env.log`` (gitignored; override via
$PMOVES_MAVIS_SDK_LOG_PATH).  This script reads that file and prints the
entries - filterable by CLI / host / recent-N.  The format is intentionally
one JSON object per line (no encoding traps, easy to grep, easy to splice
into a downstream filter).

Line shape (per call):

    {"ts":"2026-09-22T16:53:54Z",
     "host":"POWERFULMOVES",
     "pid":12345,
     "cli":"claude",
     "stripped_count":5,
     "stripped_names":"ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ...",
     "all_consumed":false}

The ``all_consumed=true`` flag appears only for ``pmoves-mini`` (the '*'
wildcard consumes every Mavis SDK var instead of stripping).  Anything
else is a strip call - ``stripped_count`` is the number of vars caught.

Usage:

    # last 10 calls (default)
    python pmoves/tools/mavis_sdk_audit.py
    python pmoves/tools/mavis_sdk_audit.py --last 10
    # filter
    python pmoves/tools/mavis_sdk_audit.py --cli claude
    python pmoves/tools/mavis_sdk_audit.py --host POWERFULMOVES
    # last since a duration string ("30s", "5m", "2h", "1d")
    python pmoves/tools/mavis_sdk_audit.py --since 1h
    # explicit log path
    python pmoves/tools/mavis_sdk_audit.py --log /tmp/foo.log

Exit code:  0 on success (matches found or zero matches - the operator
checks the output, not the exit).  1 on usage / parse error.  2 on file
read error (no such log file = 2 with a clear message).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO_ROOT / "pmoves" / "data" / "chit" / "mavis_sdk_env.log"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {
    "ts", "host", "pid", "cli", "stripped_count", "stripped_names",
    "all_consumed",
}


@dataclass(frozen=True)
class AuditEntry:
    ts: datetime
    host: str
    pid: int
    cli: str
    stripped_count: int
    stripped_names: tuple[str, ...]
    all_consumed: bool
    raw: str

    @classmethod
    def from_jsonl_line(cls, line: str) -> "AuditEntry | None":
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        missing = _REQUIRED_KEYS - set(obj.keys())
        if missing:
            return None
        try:
            ts = _parse_ts(str(obj["ts"]))
            pid = int(obj["pid"])
            sc = int(obj["stripped_count"])
        except (ValueError, TypeError):
            return None
        names = tuple(s for s in str(obj["stripped_names"]).split() if s)
        return cls(
            ts=ts,
            host=str(obj["host"]),
            pid=pid,
            cli=str(obj["cli"]),
            stripped_count=sc,
            stripped_names=names,
            all_consumed=bool(obj["all_consumed"]),
            raw=line,
        )


# Accept both "2026-09-22T16:53:54Z" and "2026-09-22T16:53:54+00:00" -- the
# bash helper emits the "Z" form; downstream tooling may emit offsets.
def _parse_ts(s: str) -> datetime:
    if s.endswith("Z"):
        return datetime.fromisoformat(s[:-1] + "+00:00")
    if re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", s):
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            pass
    raise ValueError(f"unrecognised timestamp: {s!r}")


def parse_log(path: Path) -> list[AuditEntry]:
    """Read a JSONL audit log; skip malformed lines (don't error)."""
    if not path.is_file():
        raise FileNotFoundError(f"audit log not found: {path}")
    out: list[AuditEntry] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        entry = AuditEntry.from_jsonl_line(raw_line)
        if entry is not None:
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _parse_since(s: str) -> datetime:
    """Parse ``--since 30s | 5m | 2h | 1d`` to a UTC cutoff timestamp.

    Accepted units: ``s`` (seconds), ``m`` (minutes), ``h`` (hours),
    ``d`` (days).  No months/years because days is unambiguous and
    sufficient for "since this morning" use-cases.
    """
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        raise argparse.ArgumentTypeError(
            f"--since must be like 30s / 5m / 2h / 1d, got {s!r}"
        )
    n = int(m.group(1))
    unit = m.group(2)
    delta = {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[unit]
    return datetime.now(timezone.utc) - delta


def filter_entries(
    entries: Iterable[AuditEntry],
    *,
    cli: str | None,
    host: str | None,
    since: datetime | None,
) -> list[AuditEntry]:
    out = []
    for e in entries:
        if cli is not None and e.cli != cli:
            continue
        if host is not None and e.host != host:
            continue
        if since is not None and e.ts < since:
            continue
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def render_entry(e: AuditEntry) -> str:
    names = ", ".join(e.stripped_names) if e.stripped_names else "<none>"
    flag = " [ALL_CONSUMED]" if e.all_consumed else ""
    return (
        f"{e.ts.strftime('%Y-%m-%dT%H:%M:%SZ')}  "
        f"host={e.host}  pid={e.pid}  "
        f"cli={e.cli}{flag}  "
        f"stripped={e.stripped_count}  names=[{names}]"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mavis_sdk_audit",
        description="Inspect the PMOVES_MAVIS_SDK_* JSONL audit log.",
    )
    p.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG,
        help=f"path to the audit log (default: {DEFAULT_LOG})",
    )
    p.add_argument(
        "--last",
        type=int,
        default=10,
        help="print only the last N entries (default: 10)",
    )
    p.add_argument("--cli", help="filter by CLI name (e.g. claude, kilo)")
    p.add_argument("--host", help="filter by host name (e.g. POWERFULMOVES)")
    p.add_argument(
        "--since",
        type=_parse_since,
        help="only entries within the last duration (30s / 5m / 2h / 1d)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="ignore --last and print every matching entry",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="print entries as JSONL (machine-readable)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        entries = parse_log(args.log)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    matched = filter_entries(
        entries,
        cli=args.cli,
        host=args.host,
        since=args.since,
    )
    if not args.all:
        matched = matched[-args.last:] if args.last > 0 else []

    if args.json:
        for e in matched:
            sys.stdout.write(e.raw + "\n")
    else:
        if not matched:
            print("(no matching entries)")
            return 0
        for e in matched:
            print(render_entry(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
