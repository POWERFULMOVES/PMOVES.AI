"""Tests for pmoves/tools/env_local_key.py and the env-local-* make targets.

TEMP FILES ONLY. Every invocation below passes --file/--audit-log (or the
ENV_LOCAL_KEY_FILE/_AUDIT overrides, for the make targets) pointing into
pytest's tmp_path. `_run` refuses to start the tool without them, so a future
edit cannot quietly aim a test at the node's real overlay file -- agents have
zero access to it and these tests must never be the exception.

The central claim of the tool is NEGATIVE ("never prints a value"), and a test
of a negative claim passes trivially if it is looking in the wrong place. So
the value-absence assertion is itself tested: the positive controls build
deliberately leaking variants of the tool and require the SAME assertion
helpers to fail against them.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[2]
TOOL = PMOVES / "tools" / "env_local_key.py"

SECRET = "S3cr3t-VALUE-9f2c-do-not-print"

ORIGINAL = (
    b"# node-local overlay (test fixture)\n"
    b"ALPHA=1\n"
    b"\n"
    b"  # an indented comment, kept byte-for-byte\n"
    b"TARGET_KEY=old-value-xyz\n"
    b"WINDOWS_LINE=crlf\r\n"
    b"UNICODE=caf\xc3\xa9\n"
    b"# TARGET_KEY=commented-out-does-not-count\n"
    b"OMEGA=last-no-newline"
)


# ---------------------------------------------------------------- helpers ---

def _run(tool: Path, tmp_path: Path, *args: str, stdin: str | None = None,
         target: Path | None = None) -> subprocess.CompletedProcess:
    target = target if target is not None else tmp_path / "overlay.txt"
    assert str(target).startswith(str(tmp_path)), "tests may only touch tmp_path"
    env = {k: v for k, v in os.environ.items()
           if k not in ("ENV_LOCAL_KEY_FILE", "ENV_LOCAL_KEY_AUDIT")}
    return subprocess.run(
        [sys.executable, str(tool), "--file", str(target),
         "--audit-log", str(tmp_path / "audit" / "edits.jsonl"), *args],
        input=stdin if stdin is not None else "", capture_output=True,
        text=True, env=env, cwd=str(tmp_path), timeout=30,
    )


def _write(tmp_path: Path, data: bytes = ORIGINAL, mode: int = 0o600) -> Path:
    p = tmp_path / "overlay.txt"
    p.write_bytes(data)
    os.chmod(p, mode)
    return p


def _backups(tmp_path: Path) -> list[Path]:
    return sorted(tmp_path.glob("overlay.txt.bak-*"))


def _audit_rows(tmp_path: Path) -> list[dict]:
    p = tmp_path / "audit" / "edits.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def assert_value_not_in_output(proc: subprocess.CompletedProcess, value: str) -> None:
    """The load-bearing negative assertion, shared with the positive controls."""
    assert value not in proc.stdout, "value leaked to stdout"
    assert value not in proc.stderr, "value leaked to stderr"


def assert_value_not_in_audit(tmp_path: Path, value: str) -> None:
    raw = (tmp_path / "audit" / "edits.jsonl").read_text()
    assert value not in raw, "value leaked into the audit log"


# ------------------------------------------------------------------ unset ---

def test_unset_removes_exactly_one_line_and_keeps_the_rest_byte_identical(tmp_path):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "unset", "TARGET_KEY")
    assert proc.returncode == 0, proc.stderr
    expected = ORIGINAL.replace(b"TARGET_KEY=old-value-xyz\n", b"", 1)
    assert f.read_bytes() == expected
    assert len(ORIGINAL.splitlines()) - len(f.read_bytes().splitlines()) == 1
    assert "result=done" in proc.stdout and "old_len=13" in proc.stdout
    assert_value_not_in_output(proc, "old-value-xyz")


def test_unset_absent_key_is_a_noop_without_backup(tmp_path):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "unset", "NOT_THERE")
    assert proc.returncode == 0
    assert "result=noop" in proc.stdout
    assert f.read_bytes() == ORIGINAL
    assert _backups(tmp_path) == []
    (row,) = _audit_rows(tmp_path)
    assert row["changed"] is False and row["line_existed"] is False


def test_unset_missing_file_is_could_not_measure(tmp_path):
    proc = _run(TOOL, tmp_path, "unset", "TARGET_KEY")
    assert proc.returncode == 3
    assert "could-not-measure" in proc.stderr


def test_commented_line_is_not_a_definition(tmp_path):
    _write(tmp_path)
    proc = _run(TOOL, tmp_path, "has", "TARGET_KEY")
    assert proc.returncode == 0 and "count=1" in proc.stdout


# ------------------------------------------------------ refusals (guards) ---

def test_duplicate_key_is_refused_with_count_and_nothing_changes(tmp_path):
    data = ORIGINAL + b"\nTARGET_KEY=second\nexport TARGET_KEY=third\n"
    f = _write(tmp_path, data)
    for args, stdin in ((("unset", "TARGET_KEY"), None), (("set", "TARGET_KEY"), SECRET)):
        proc = _run(TOOL, tmp_path, *args, stdin=stdin)
        assert proc.returncode == 1, (args, proc.stdout, proc.stderr)
        assert "appears 3 times" in proc.stderr
        assert f.read_bytes() == data
    assert _backups(tmp_path) == []
    assert _audit_rows(tmp_path) == []


@pytest.mark.parametrize("bad", [
    "lower", "1LEADING_DIGIT", "_LEADING_UNDERSCORE", "HAS-DASH", "HAS SPACE",
    "KEY=VALUE", "$(shell touch x)", "`id`", "KÉY", "",
])
def test_malformed_key_is_refused_and_not_echoed(tmp_path, bad):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "unset", bad)
    assert proc.returncode == 1
    assert "malformed-key" in proc.stderr
    if bad:
        # A mistyped value pasted into KEY= must not come back on screen.
        assert bad not in proc.stdout + proc.stderr
    assert f.read_bytes() == ORIGINAL
    assert _backups(tmp_path) == []


def test_value_cannot_travel_as_an_argument(tmp_path):
    _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", SECRET)
    assert proc.returncode == 2  # argparse usage error: set takes KEY only
    assert (tmp_path / "overlay.txt").read_bytes() == ORIGINAL


@pytest.mark.parametrize("stdin,reason", [("", "empty value"), ("\n", "empty value"),
                                          ("a\nb\n", "multi-line")])
def test_empty_or_multiline_value_is_refused(tmp_path, stdin, reason):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=stdin)
    assert proc.returncode == 1 and reason in proc.stderr
    assert f.read_bytes() == ORIGINAL


# -------------------------------------------------------------------- set ---

def test_set_replaces_existing_line_via_stdin_without_echo(tmp_path):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=SECRET + "\n")
    assert proc.returncode == 0, proc.stderr
    assert_value_not_in_output(proc, SECRET)
    assert f.read_bytes() == ORIGINAL.replace(
        b"TARGET_KEY=old-value-xyz\n", b"TARGET_KEY=" + SECRET.encode() + b"\n", 1)
    assert f"new_len={len(SECRET)}" in proc.stdout and "line_existed=yes" in proc.stdout


def test_set_appends_new_key_after_a_file_without_trailing_newline(tmp_path):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "NEW_KEY", stdin=SECRET)
    assert proc.returncode == 0, proc.stderr
    assert_value_not_in_output(proc, SECRET)
    assert f.read_bytes() == ORIGINAL + b"\nNEW_KEY=" + SECRET.encode() + b"\n"


def test_set_preserves_crlf_and_export_prefix(tmp_path):
    f = _write(tmp_path, b"export WINDOWS_LINE=x\r\nB=2\n")
    proc = _run(TOOL, tmp_path, "set", "WINDOWS_LINE", stdin=SECRET)
    assert proc.returncode == 0
    assert f.read_bytes() == b"export WINDOWS_LINE=" + SECRET.encode() + b"\r\nB=2\n"


def test_set_creates_missing_file_at_0600(tmp_path):
    proc = _run(TOOL, tmp_path, "set", "FRESH", stdin=SECRET)
    assert proc.returncode == 0
    f = tmp_path / "overlay.txt"
    assert f.read_bytes() == b"FRESH=" + SECRET.encode() + b"\n"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


# ------------------------------------------- backup, mode, atomicity, audit ---

@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_backup_is_0600_and_holds_the_original_bytes(tmp_path, action, stdin):
    _write(tmp_path, mode=0o644)  # backup must be 0600 even from a looser file
    proc = _run(TOOL, tmp_path, action, "TARGET_KEY", stdin=stdin)
    assert proc.returncode == 0
    (bak,) = _backups(tmp_path)
    assert stat.S_IMODE(bak.stat().st_mode) == 0o600
    assert bak.read_bytes() == ORIGINAL
    assert f"backup={bak.name}" in proc.stdout


@pytest.mark.parametrize("mode", [0o600, 0o640])
@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_file_mode_is_preserved(tmp_path, mode, action, stdin):
    f = _write(tmp_path, mode=mode)
    assert _run(TOOL, tmp_path, action, "TARGET_KEY", stdin=stdin).returncode == 0
    assert stat.S_IMODE(f.stat().st_mode) == mode


def test_no_temp_files_are_left_behind(tmp_path):
    _write(tmp_path)
    assert _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=SECRET).returncode == 0
    leftovers = [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert leftovers == []


def test_audit_rows_carry_lengths_and_never_the_value(tmp_path):
    _write(tmp_path)
    assert _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=SECRET).returncode == 0
    assert _run(TOOL, tmp_path, "unset", "TARGET_KEY").returncode == 0
    assert_value_not_in_audit(tmp_path, SECRET)
    assert_value_not_in_audit(tmp_path, "old-value-xyz")
    set_row, unset_row = _audit_rows(tmp_path)
    for row in (set_row, unset_row):
        assert {"ts", "host", "key", "action", "old_len", "new_len", "operator"} <= set(row)
        assert row["key"] == "TARGET_KEY"
    assert (set_row["action"], set_row["old_len"], set_row["new_len"]) == ("set", 13, len(SECRET))
    assert (unset_row["action"], unset_row["old_len"], unset_row["new_len"]) == (
        "unset", len(SECRET), None)
    audit = tmp_path / "audit" / "edits.jsonl"
    assert stat.S_IMODE(audit.stat().st_mode) == 0o600


# -------------------------------------------------------------------- has ---

def test_has_reports_presence_without_value(tmp_path):
    _write(tmp_path)
    present = _run(TOOL, tmp_path, "has", "TARGET_KEY")
    absent = _run(TOOL, tmp_path, "has", "NOPE")
    assert (present.returncode, absent.returncode) == (0, 1)
    assert "result=present" in present.stdout and "result=absent" in absent.stdout
    assert_value_not_in_output(present, "old-value-xyz")
    assert _audit_rows(tmp_path) == [] and _backups(tmp_path) == []


# ------------------------------------------------------- positive controls ---
# A deliberately LEAKING variant of the tool, built by source transform into
# tmp_path. The same assertion helpers used above must FAIL against it; if they
# pass, they are not looking where the value would appear.

def _leaky_variant(tmp_path: Path, needle: str, injection: str) -> Path:
    src = TOOL.read_text()
    assert needle in src, f"positive-control anchor missing from tool: {needle!r}"
    leaky = tmp_path / "leaky_env_local_key.py"
    leaky.write_text(src.replace(needle, needle + injection, 1))
    return leaky


def test_positive_control_stdout_assertion_catches_an_echoing_variant(tmp_path):
    leaky = _leaky_variant(
        tmp_path, "    value = _read_value(stdin, key)\n",
        "    print('debug value:', value.decode())\n")
    _write(tmp_path)
    proc = _run(leaky, tmp_path, "set", "TARGET_KEY", stdin=SECRET)
    assert proc.returncode == 0  # the leaky variant still "works"
    with pytest.raises(AssertionError, match="leaked to stdout"):
        assert_value_not_in_output(proc, SECRET)


def test_positive_control_stderr_assertion_catches_an_echoing_variant(tmp_path):
    leaky = _leaky_variant(
        tmp_path, "    value = _read_value(stdin, key)\n",
        "    print(value.decode(), file=sys.stderr)\n")
    _write(tmp_path)
    proc = _run(leaky, tmp_path, "set", "TARGET_KEY", stdin=SECRET)
    with pytest.raises(AssertionError, match="leaked to stderr"):
        assert_value_not_in_output(proc, SECRET)


def test_positive_control_audit_assertion_catches_a_value_in_the_row(tmp_path):
    leaky = _leaky_variant(
        tmp_path, '        "action": action,\n',
        '        "debug": globals().get("_LEAK", ""),\n')
    # Route the value into the row through a module global set in cmd_set.
    src = leaky.read_text().replace(
        "    value = _read_value(stdin, key)\n",
        "    value = _read_value(stdin, key)\n    globals()['_LEAK'] = value.decode()\n", 1)
    leaky.write_text(src)
    _write(tmp_path)
    assert _run(leaky, tmp_path, "set", "TARGET_KEY", stdin=SECRET).returncode == 0
    with pytest.raises(AssertionError, match="leaked into the audit log"):
        assert_value_not_in_audit(tmp_path, SECRET)


# ---------------------------------------------------------- make targets ---

needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")


def _make(tmp_path: Path, target: str, key: str, stdin: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ENV_LOCAL_KEY_FILE"] = str(tmp_path / "overlay.txt")
    env["ENV_LOCAL_KEY_AUDIT"] = str(tmp_path / "audit" / "edits.jsonl")
    env.pop("KEY", None)
    return subprocess.run(
        ["make", "-s", "-C", str(PMOVES), target, f"KEY={key}"],
        input=stdin, capture_output=True, text=True, env=env, timeout=60,
    )


@needs_make
def test_make_unset_and_set_round_trip_on_a_temp_file(tmp_path):
    f = _write(tmp_path)
    proc = _make(tmp_path, "env-local-set", "TARGET_KEY", stdin=SECRET + "\n")
    assert proc.returncode == 0, proc.stderr
    assert_value_not_in_output(proc, SECRET)
    assert str(f) in proc.stdout  # the resolved path is always shown
    proc = _make(tmp_path, "env-local-unset", "TARGET_KEY")
    assert proc.returncode == 0, proc.stderr
    assert f.read_bytes() == ORIGINAL.replace(b"TARGET_KEY=old-value-xyz\n", b"", 1)
    assert len(_backups(tmp_path)) == 2


@needs_make
@pytest.mark.parametrize("payload", ["$(shell touch {canary})", "`touch {canary}`",
                                     "$$(touch {canary})"])
def test_make_key_is_never_expanded_or_executed(tmp_path, payload):
    _write(tmp_path)
    canary = tmp_path / "CANARY"
    proc = _make(tmp_path, "env-local-has", payload.format(canary=canary))
    assert proc.returncode != 0
    assert not canary.exists(), f"KEY payload executed: {payload}"


@needs_make
def test_positive_control_unexport_key_is_load_bearing(tmp_path):
    """Without `unexport KEY`, make expands a command-line KEY while exporting
    it to the recipe environment -- so the canary test above must be able to
    see an execution. Built from a throwaway copy of the Makefile, never by
    editing the tracked one."""
    src = (PMOVES / "Makefile").read_text()
    assert "\nunexport KEY\n" in src, "unexport KEY directive missing"
    variant = tmp_path / "Makefile.no-unexport"
    variant.write_text(src.replace("\nunexport KEY\n", "\n", 1))
    _write(tmp_path)
    canary = tmp_path / "CANARY"
    env = dict(os.environ)
    env["ENV_LOCAL_KEY_FILE"] = str(tmp_path / "overlay.txt")
    env["ENV_LOCAL_KEY_AUDIT"] = str(tmp_path / "audit" / "edits.jsonl")
    subprocess.run(
        ["make", "-s", "-C", str(PMOVES), "-f", str(variant), "env-local-has",
         f"KEY=$(shell touch {canary})"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert canary.exists(), "control failed: the canary cannot detect make expansion"
