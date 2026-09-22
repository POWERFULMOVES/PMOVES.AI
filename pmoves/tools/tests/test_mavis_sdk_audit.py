"""Tests for pmoves/tools/mavis_sdk_audit.py -- the PMOVES_MAVIS_SDK_* JSONL inspector.

Lane C of the Mavis SDK env strip slice: the file-backed audit log gets
inspected by `python pmoves/tools/mavis_sdk_audit.py [--cli X] [--host Y]
[--since 1h] [--last N] [--json]`.  These tests are split into two halves:

  * Unit tests that import `mavis_sdk_audit` as a library and exercise
    ``parse_log``, ``filter_entries``, ``_parse_since``, ``render_entry``,
    and the ``AuditEntry`` dataclass.  Hermetic -- no subprocess.
  * Subprocess tests that invoke the script via ``python -m`` (or
    ``python <script>``) and assert on stdout/stderr/exit code.

The fixture uses ``tmp_path`` to write a synthetic JSONL log; the parser's
tolerance for blank + malformed lines is part of the contract (operator
must be able to recover from a partial write without crashing).
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

# `pmoves.tools` is an import path under the workspace root (importable
# because the test harness is run from the repo root and `pmoves/` is a
# package).  We add the repo root to sys.path so the test module can be
# invoked both as `python -m unittest` AND as `python test_mavis_sdk_audit.py`.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pmoves.tools import mavis_sdk_audit as A  # noqa: E402
from pmoves.tools.mavis_sdk_audit import AuditEntry  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers (not part of the loader-exported unit-tests machinery).
# ---------------------------------------------------------------------------

def _write_lines(path: Path, lines: Iterable[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_entry(
    *,
    ts: str = "2026-09-22T12:00:00Z",
    host: str = "POWERFULMOVES",
    pid: int = 1234,
    cli: str = "claude",
    stripped_count: int = 2,
    stripped_names: str = "ANTHROPIC_MODEL MCP_TIMEOUT",
    all_consumed: bool = False,
) -> str:
    return json.dumps({
        "ts": ts,
        "host": host,
        "pid": pid,
        "cli": cli,
        "stripped_count": stripped_count,
        "stripped_names": stripped_names,
        "all_consumed": all_consumed,
    })


# ---------------------------------------------------------------------------
# Unit: AuditEntry parsing + tolerance.
# ---------------------------------------------------------------------------


class ParseLogToleranceTests(unittest.TestCase):
    """The parser skips blank lines and malformed JSON, never raises."""

    def test_parses_valid_lines(self) -> None:
        with __import__("tempfile").NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(_make_entry(cli="claude") + "\n")
            f.write(_make_entry(cli="kilo", ts="2026-09-22T12:01:00Z") + "\n")
            path = Path(f.name)
        try:
            entries = A.parse_log(path)
            self.assertEqual(len(entries), 2)
            self.assertEqual([e.cli for e in entries], ["claude", "kilo"])
        finally:
            path.unlink(missing_ok=True)

    def test_skips_blank_and_malformed(self) -> None:
        with __import__("tempfile").NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(_make_entry(cli="a") + "\n")
            f.write("\n")  # blank
            f.write("not json\n")  # malformed
            f.write(_make_entry(cli="b", ts="2026-09-22T12:02:00Z") + "\n")
            path = Path(f.name)
        try:
            entries = A.parse_log(path)
            self.assertEqual(len(entries), 2, "blank + malformed must be skipped, not raise")
            self.assertEqual([e.cli for e in entries], ["a", "b"])
        finally:
            path.unlink(missing_ok=True)

    def test_missing_required_keys_skipped(self) -> None:
        with __import__("tempfile").NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(_make_entry() + "\n")
            # entry missing "cli"
            f.write(json.dumps({"ts": "2026-09-22T12:01:00Z", "host": "x"}) + "\n")
            path = Path(f.name)
        try:
            entries = A.parse_log(path)
            self.assertEqual(len(entries), 1, "missing required keys = skip")
            self.assertEqual(entries[0].cli, "claude")
        finally:
            path.unlink(missing_ok=True)

    def test_missing_file_raises_filenotfound(self) -> None:
        with __import__("tempfile").TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                A.parse_log(Path(td) / "does-not-exist.jsonl")


# ---------------------------------------------------------------------------
# Unit: timestamps + since filter.
# ---------------------------------------------------------------------------


class TimestampAndSinceFilterTests(unittest.TestCase):
    """ISO-8601 with Z (bash emit) and +00:00 (downstream tooling emit) both parse."""

    def test_iso_z_suffix(self) -> None:
        dt = A._parse_ts("2026-09-22T12:00:00Z")
        self.assertEqual(dt, datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc))

    def test_iso_offset_suffix(self) -> None:
        dt = A._parse_ts("2026-09-22T12:00:00+00:00")
        self.assertEqual(dt, datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc))

    def test_invalid_timestamp_raises(self) -> None:
        with self.assertRaises(ValueError):
            A._parse_ts("yesterday")

    def test_since_duration_units(self) -> None:
        # All four accepted units (s/m/h/d) parse without error
        now = datetime.now(timezone.utc)
        for n, unit, expected_delta in [
            ("30", "s", timedelta(seconds=30)),
            ("5", "m", timedelta(minutes=5)),
            ("2", "h", timedelta(hours=2)),
            ("1", "d", timedelta(days=1)),
        ]:
            cutoff = A._parse_since(f"{n}{unit}")
            # cutoff should be approximately now - expected_delta
            delta = (now - cutoff) - expected_delta
            self.assertLess(abs(delta.total_seconds()), 2,
                            f"since {n}{unit} off by more than 2s: {delta}")

    def test_since_rejects_unknown_units(self) -> None:
        # argparse ArgumentTypeError is raised internally; the helper
        # raises it (caught by argparse).  We assert by direct call.
        with self.assertRaises(Exception):  # ArgumentTypeError or ValueError
            A._parse_since("5y")  # years not in the supported set

    def test_since_filter_excludes_old_entries(self) -> None:
        # Build entries spanning the past hour
        now = datetime.now(timezone.utc)
        entries = [
            AuditEntry(
                ts=now - timedelta(minutes=10),
                host="x", pid=1, cli="fresh", stripped_count=1,
                stripped_names=("FOO",), all_consumed=False, raw="",
            ),
            AuditEntry(
                ts=now - timedelta(hours=2),
                host="x", pid=2, cli="old", stripped_count=1,
                stripped_names=("BAR",), all_consumed=False, raw="",
            ),
        ]
        # Filter to "since 1h" -- the 2-hour-old entry must drop
        cutoff = now - timedelta(hours=1)
        kept = A.filter_entries(entries, cli=None, host=None, since=cutoff)
        self.assertEqual([e.cli for e in kept], ["fresh"])


# ---------------------------------------------------------------------------
# Unit: filter combinations.
# ---------------------------------------------------------------------------


class FilterTests(unittest.TestCase):
    """--cli / --host / --since combinators applied in order."""

    def setUp(self) -> None:
        now = datetime.now(timezone.utc)
        self.entries = [
            AuditEntry(ts=now - timedelta(minutes=5), host="node-a",
                       pid=1, cli="claude", stripped_count=1,
                       stripped_names=("X",), all_consumed=False, raw=""),
            AuditEntry(ts=now - timedelta(minutes=10), host="node-b",
                       pid=2, cli="kilo", stripped_count=2,
                       stripped_names=("Y", "Z"), all_consumed=False, raw=""),
            AuditEntry(ts=now - timedelta(minutes=15), host="node-a",
                       pid=3, cli="kilo", stripped_count=0,
                       stripped_names=(), all_consumed=True, raw=""),
        ]

    def test_cli_only(self) -> None:
        kept = A.filter_entries(self.entries, cli="kilo", host=None, since=None)
        self.assertEqual([e.cli for e in kept], ["kilo", "kilo"])

    def test_host_only(self) -> None:
        kept = A.filter_entries(self.entries, cli=None, host="node-b", since=None)
        self.assertEqual([e.host for e in kept], ["node-b"])

    def test_cli_and_host_intersect(self) -> None:
        kept = A.filter_entries(self.entries, cli="claude", host="node-a", since=None)
        self.assertEqual([e.cli for e in kept], ["claude"])

    def test_cli_and_host_disjoint(self) -> None:
        kept = A.filter_entries(self.entries, cli="claude", host="node-b", since=None)
        self.assertEqual(kept, [], "claude never on node-b")

    def test_all_consumed_flag_surfaces(self) -> None:
        kept = A.filter_entries(self.entries, cli="kilo", host="node-a", since=None)
        self.assertEqual([e.all_consumed for e in kept], [True])

    def test_render_entry_includes_all_consumed_marker(self) -> None:
        kept = A.filter_entries(self.entries, cli="kilo", host="node-a", since=None)
        rendered = A.render_entry(kept[0])
        self.assertIn("[ALL_CONSUMED]", rendered,
                      "render_entry must surface the all_consumed=true marker")


# ---------------------------------------------------------------------------
# Subprocess: end-to-end CLI invocation.
# ---------------------------------------------------------------------------


def _cli_path() -> Path:
    return REPO_ROOT / "pmoves" / "tools" / "mavis_sdk_audit.py"


@unittest.skipUnless(_cli_path().is_file(), "mavis_sdk_audit.py missing")
class CliInvocationTests(unittest.TestCase):
    """Invoke the inspector as a real subprocess and assert on stdout."""

    def setUp(self) -> None:
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.log = self.tmpdir / "audit.jsonl"
        _write_lines(self.log, [
            _make_entry(cli="claude", ts="2026-09-22T12:00:00Z"),
            _make_entry(cli="kilo", pid=1235, ts="2026-09-22T12:01:00Z"),
            _make_entry(cli="pmoves-mini", pid=1236, ts="2026-09-22T12:02:00Z",
                        stripped_count=0, stripped_names="<none>", all_consumed=True),
        ])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_cli_path()), "--log", str(self.log), *args],
            capture_output=True, text=True,
        )

    def test_cli_filter_excludes_other_clis(self) -> None:
        r = self._run("--cli", "claude", "--last", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("claude", r.stdout)
        self.assertNotIn("pmoves-mini", r.stdout)

    def test_all_lists_every_entry(self) -> None:
        r = self._run("--all", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        non_blank = [ln for ln in r.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(non_blank), 3)
        # Each output line must parse as JSON
        for ln in non_blank:
            json.loads(ln)

    def test_json_output_is_valid_jsonl(self) -> None:
        r = self._run("--cli", "kilo", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.strip()
        self.assertTrue(out, "--json output should not be empty")
        # Exactly one line (since --cli filter isolated kilo)
        self.assertEqual(len([ln for ln in out.splitlines() if ln.strip()]), 1)
        json.loads(out)  # parses as JSON

    def test_default_path_message_when_no_log(self) -> None:
        # Run against a path that does NOT exist. Exit code = 2, stderr
        # mentions the missing file. Operator can see the failure without
        # a confusing stack trace.
        r = subprocess.run(
            [sys.executable, str(_cli_path()),
             "--log", str(self.tmpdir / "missing.jsonl")],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 2, "missing log = exit code 2")
        self.assertIn("audit log not found", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
