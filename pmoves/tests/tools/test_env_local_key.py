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

import importlib.util
import io
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
# The real overlay's basename, used ONLY to name temp files and to ask git's
# ignore engine about names. Never joined to a real pmoves/ directory.
DEFAULT_NAME = ".env.local"

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


def _load_tool_module(path: Path = TOOL):
    """In-process import, for seams a subprocess cannot patch. Callers must
    always pass --file under tmp_path; the tool also refuses its default path
    while PYTEST_CURRENT_TEST is set."""
    spec = importlib.util.spec_from_file_location(f"env_local_key_{id(path)}", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_unset_absent_key_is_a_noop_without_backup_audit_or_echo(tmp_path):
    # P3: an all-caps VALUE pasted as KEY passes the key regex; if it matches
    # no line it must be neither echoed nor audited.
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "unset", "PASTED_VALUE_LOOKS_LIKE_A_KEY")
    assert proc.returncode == 0
    assert "result=noop" in proc.stdout and "<redacted: not present>" in proc.stdout
    assert_value_not_in_output(proc, "PASTED_VALUE_LOOKS_LIKE_A_KEY")
    assert f.read_bytes() == ORIGINAL
    assert _backups(tmp_path) == []
    assert _audit_rows(tmp_path) == []


def test_has_absent_key_is_redacted(tmp_path):
    _write(tmp_path)
    proc = _run(TOOL, tmp_path, "has", "PASTED_VALUE_LOOKS_LIKE_A_KEY")
    assert proc.returncode == 1 and "result=absent" in proc.stdout
    assert_value_not_in_output(proc, "PASTED_VALUE_LOOKS_LIKE_A_KEY")


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
    data = ORIGINAL + b"\nTARGET_KEY=second\n"
    f = _write(tmp_path, data)
    for args, stdin in ((("unset", "TARGET_KEY"), None), (("set", "TARGET_KEY"), SECRET)):
        proc = _run(TOOL, tmp_path, *args, stdin=stdin)
        assert proc.returncode == 1, (args, proc.stdout, proc.stderr)
        assert "defined 2 times" in proc.stderr
        assert f.read_bytes() == data
    assert _backups(tmp_path) == []
    assert _audit_rows(tmp_path) == []


@pytest.mark.parametrize("inert_line", [b"export TARGET_KEY=third\n",
                                        b"  TARGET_KEY=indented\n",
                                        b"\texport TARGET_KEY=both\n"])
def test_inert_forms_follow_the_loader_and_block_set_and_unset(tmp_path, inert_line):
    """P2c: with-env.sh loads only unindented `KEY=` lines. Inert forms are
    reported separately and make set/unset refuse (this REPLACES the old
    behaviour, which counted them as definitions and kept `export `)."""
    data = ORIGINAL + b"\n" + inert_line
    f = _write(tmp_path, data)
    has = _run(TOOL, tmp_path, "has", "TARGET_KEY")
    assert has.returncode == 0 and "count=1" in has.stdout and "inert=1" in has.stdout
    for args, stdin in ((("unset", "TARGET_KEY"), None), (("set", "TARGET_KEY"), SECRET)):
        proc = _run(TOOL, tmp_path, *args, stdin=stdin)
        assert proc.returncode == 1 and "inert form" in proc.stderr, proc.stderr
        assert f.read_bytes() == data
    assert _backups(tmp_path) == [] and _audit_rows(tmp_path) == []


def test_only_an_inert_form_reads_as_absent_but_is_named(tmp_path):
    f = _write(tmp_path, b"export ONLY_EXPORTED=x\nB=2\n")
    has = _run(TOOL, tmp_path, "has", "ONLY_EXPORTED")
    assert has.returncode == 1 and "result=absent" in has.stdout and "inert=1" in has.stdout
    proc = _run(TOOL, tmp_path, "set", "ONLY_EXPORTED", stdin=SECRET)
    assert proc.returncode == 1 and "inert form" in proc.stderr
    assert f.read_bytes() == b"export ONLY_EXPORTED=x\nB=2\n"


class _MustNotRead:
    def isatty(self):
        return False

    def read(self):
        raise AssertionError("the value was requested before the duplicate check")


def test_duplicates_are_refused_before_the_value_is_requested(tmp_path, capsys):
    mod = _load_tool_module()
    f = _write(tmp_path, ORIGINAL + b"\nTARGET_KEY=second\n")
    rc = mod.main(["--file", str(f), "--audit-log", str(tmp_path / "a.jsonl"),
                   "set", "TARGET_KEY"], stdin=_MustNotRead())
    assert rc == 1 and "defined 2 times" in capsys.readouterr().err


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


def test_set_preserves_crlf(tmp_path):
    f = _write(tmp_path, b"WINDOWS_LINE=x\r\nB=2\n")
    proc = _run(TOOL, tmp_path, "set", "WINDOWS_LINE", stdin=SECRET)
    assert proc.returncode == 0
    assert f.read_bytes() == b"WINDOWS_LINE=" + SECRET.encode() + b"\r\nB=2\n"


def test_lines_split_on_newline_only(tmp_path):
    # bytes.splitlines() would split on \x0c / \x85 and act on a fragment.
    data = b"FORM=a\x0cb\x85c\nTARGET_KEY=v\x0bw\nZ=1\n"
    f = _write(tmp_path, data)
    assert _run(TOOL, tmp_path, "unset", "TARGET_KEY").returncode == 0
    assert f.read_bytes() == b"FORM=a\x0cb\x85c\nZ=1\n"


def test_identical_set_is_a_noop(tmp_path):
    f = _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin="old-value-xyz")
    assert proc.returncode == 0 and "result=noop" in proc.stdout and "changed=no" in proc.stdout
    assert f.read_bytes() == ORIGINAL
    assert _backups(tmp_path) == [] and _audit_rows(tmp_path) == []


@pytest.mark.parametrize("risky", ["${OTHER}", "$(id)", "a`id`b"])
def test_expandable_value_warns_without_echo(tmp_path, risky):
    _write(tmp_path)
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=risky)
    assert proc.returncode == 0 and "WARNING" in proc.stderr
    assert_value_not_in_output(proc, risky)


def test_non_utf8_value_is_could_not_measure(tmp_path):
    f = _write(tmp_path)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ENV_LOCAL_KEY_")}
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--file", str(f), "--audit-log",
         str(tmp_path / "audit" / "edits.jsonl"), "set", "TARGET_KEY"],
        input=b"\xff\xfe\xfd", capture_output=True, env={**env, "PYTHONIOENCODING": "utf-8"},
        timeout=30)
    assert proc.returncode == 3, proc.stderr
    assert b"not valid UTF-8" in proc.stderr and b"Traceback" not in proc.stderr
    assert f.read_bytes() == ORIGINAL


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


# ------------------------------------------------ P2a: audit must not fail quiet ---

@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_unwritable_audit_log_refuses_before_any_change(tmp_path, action, stdin):
    f = _write(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    try:
        proc = subprocess.run(
            [sys.executable, str(TOOL), "--file", str(f), "--audit-log",
             str(locked / "sub" / "edits.jsonl"), action, "TARGET_KEY"],
            input=stdin or "", capture_output=True, text=True, timeout=30)
    finally:
        locked.chmod(0o700)
    assert proc.returncode == 1 and "audit log not writable" in proc.stderr, proc.stderr
    assert f.read_bytes() == ORIGINAL
    assert _backups(tmp_path) == []


@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_audit_failure_after_write_is_applied_unaudited_not_could_not_measure(
        tmp_path, capsys, monkeypatch, action, stdin):
    mod = _load_tool_module()

    def boom(self, row):
        self.close()
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mod._AuditLog, "append", boom)
    f = _write(tmp_path)
    rc = mod.main(["--file", str(f), "--audit-log", str(tmp_path / "audit" / "e.jsonl"),
                   action, "TARGET_KEY"], stdin=io.StringIO(stdin or ""))
    out = capsys.readouterr()
    assert rc == 4
    assert "result=APPLIED-UNAUDITED" in out.out and "APPLIED-UNAUDITED" in out.err
    assert "could-not-measure" not in out.out + out.err
    assert f.read_bytes() != ORIGINAL          # the edit DID land
    assert len(_backups(tmp_path)) == 1
    assert SECRET not in out.out + out.err


@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_failure_after_write_and_audit_says_applied_not_nothing_changed(
        tmp_path, capsys, monkeypatch, action, stdin):
    """The fallback OSError handler must not say "nothing changed" once the
    edit has landed -- e.g. `_report` hitting a broken stdout pipe."""
    mod = _load_tool_module()
    real_report = mod._report

    def broken_pipe(**fields):
        if fields.get("result") == "done":
            raise BrokenPipeError(32, "Broken pipe")
        return real_report(**fields)

    monkeypatch.setattr(mod, "_report", broken_pipe)
    f = _write(tmp_path)
    rc = mod.main(["--file", str(f), "--audit-log", str(tmp_path / "audit" / "edits.jsonl"),
                   action, "TARGET_KEY"], stdin=io.StringIO(stdin or ""))
    err = capsys.readouterr().err
    assert rc == 4
    assert "result=APPLIED " in err and "audited=yes" in err and "BrokenPipeError" in err
    assert "nothing changed" not in err and "could-not-measure" not in err
    assert f.read_bytes() != ORIGINAL and len(_audit_rows(tmp_path)) == 1
    assert SECRET not in err


def test_positive_control_same_oserror_before_write_is_nothing_changed(
        tmp_path, capsys, monkeypatch):
    """The same OSError raised BEFORE the write must still read as
    could-not-measure: the applied flag, not the exception type, decides."""
    mod = _load_tool_module()

    def broken_backup(path, data):
        raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(mod, "_backup", broken_backup)
    f = _write(tmp_path)
    rc = mod.main(["--file", str(f), "--audit-log", str(tmp_path / "audit" / "edits.jsonl"),
                   "unset", "TARGET_KEY"])
    err = capsys.readouterr().err
    assert rc == 3 and "nothing changed" in err and "result=APPLIED" not in err
    assert f.read_bytes() == ORIGINAL


def test_lost_group_on_fchown_permission_error_warns_by_name(tmp_path, capsys, monkeypatch):
    mod = _load_tool_module()

    def denied(fd, uid, gid):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(mod.os, "fchown", denied)
    target = tmp_path / "overlay.txt"
    target.write_bytes(ORIGINAL)
    foreign_gid = os.getegid() + 1   # any gid other than ours
    mod._atomic_write(target, b"X=1\n", 0o600, (os.geteuid(), foreign_gid))
    err = capsys.readouterr().err
    assert "WARNING: could not preserve owner/group" in err
    try:
        import grp
        expected = grp.getgrgid(foreign_gid).gr_name
    except KeyError:
        expected = str(foreign_gid)
    assert f"group={expected}" in err
    assert target.read_bytes() == b"X=1\n"


# --------------------------------------------------- P2b: symlinks write through ---

@pytest.mark.parametrize("action,stdin", [("unset", None), ("set", SECRET)])
def test_symlink_is_written_through_to_its_target(tmp_path, action, stdin):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    target = real_dir / "overlay.txt"
    target.write_bytes(ORIGINAL)
    target.chmod(0o640)
    link = tmp_path / "overlay.txt"
    link.symlink_to(target)
    proc = _run(TOOL, tmp_path, action, "TARGET_KEY", stdin=stdin)
    assert proc.returncode == 0, proc.stderr
    assert link.is_symlink() and link.resolve() == target.resolve()
    assert target.read_bytes() != ORIGINAL
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert len(list(real_dir.glob("overlay.txt.bak-*"))) == 1   # next to the target
    assert _backups(tmp_path) == []
    assert f"file={target.resolve()}" in proc.stdout and f"via={link}" in proc.stdout


def test_dangling_symlink_is_refused(tmp_path):
    link = tmp_path / "overlay.txt"
    link.symlink_to(tmp_path / "missing-target")
    proc = _run(TOOL, tmp_path, "set", "TARGET_KEY", stdin=SECRET)
    assert proc.returncode == 1 and "dangling symlink" in proc.stderr
    assert not (tmp_path / "missing-target").exists() and link.is_symlink()


# ---------------------------------------- P2d/P3: default path, temp and ignore ---

def _fake_install(tmp_path: Path) -> tuple[Path, Path]:
    """A copy of the tool whose DEFAULT_FILE is a FAKE overlay in tmp_path."""
    tools = tmp_path / "pmoves" / "tools"
    tools.mkdir(parents=True)
    copy = tools / TOOL.name
    copy.write_text(TOOL.read_text())
    fake_default = tmp_path / "pmoves" / DEFAULT_NAME
    fake_default.write_bytes(ORIGINAL)
    return copy, fake_default


def test_tool_refuses_its_default_path_under_pytest(tmp_path):
    copy, fake_default = _fake_install(tmp_path)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ENV_LOCAL_KEY_")}
    env["PYTEST_CURRENT_TEST"] = "guard-check"
    proc = subprocess.run([sys.executable, str(copy), "--audit-log",
                           str(tmp_path / "a.jsonl"), "unset", "TARGET_KEY"],
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 1 and "off limits under pytest" in proc.stderr
    assert fake_default.read_bytes() == ORIGINAL


def test_positive_control_default_path_guard_is_what_refused(tmp_path):
    """Same call without PYTEST_CURRENT_TEST acts on the (fake) default, so
    the refusal above came from the guard, not from something else."""
    copy, fake_default = _fake_install(tmp_path)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("ENV_LOCAL_KEY_") and k != "PYTEST_CURRENT_TEST"}
    proc = subprocess.run([sys.executable, str(copy), "--audit-log",
                           str(tmp_path / "a.jsonl"), "unset", "TARGET_KEY"],
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert fake_default.read_bytes() != ORIGINAL


def test_temp_file_is_named_to_match_the_env_ignore(tmp_path, monkeypatch):
    mod = _load_tool_module()
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(Path(src).name)
        return real_replace(src, dst)

    monkeypatch.setattr(mod.os, "replace", spy)
    target = tmp_path / DEFAULT_NAME   # a TEMP file that shares the real name
    target.write_bytes(ORIGINAL)
    mod._atomic_write(target, b"X=1\n", 0o600, None)
    assert seen and seen[0].startswith(DEFAULT_NAME + ".tmp-")


def test_backup_temp_and_audit_names_are_git_ignored():
    """Asks git's ignore engine about NAMES only (--no-index; the paths need
    not exist and nothing is opened)."""
    names = [f"pmoves/{DEFAULT_NAME}.bak-20260923T000000Z",
             f"pmoves/{DEFAULT_NAME}.bak-20260923T000000Z-1",
             f"pmoves/{DEFAULT_NAME}.tmp-abc123",
             "pmoves/data/audit/env_local_edits.jsonl"]
    repo = PMOVES.parent
    for name in names:
        proc = subprocess.run(["git", "-C", str(repo), "check-ignore", "--no-index", "-q", name],
                              capture_output=True, timeout=30)
        assert proc.returncode == 0, f"not git-ignored: {name}"


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

def _is_gnu_make() -> bool:
    if shutil.which("make") is None:
        return False
    out = subprocess.run(["make", "--version"], capture_output=True, text=True).stdout
    return out.startswith("GNU Make")


needs_make = pytest.mark.skipif(not _is_gnu_make(), reason="GNU make not installed")


def test_unexport_key_precedes_every_include_and_shell_call():
    """P1 (#3164 review): on make >= 4.4, `$(shell ...)` also receives exported
    variables, so any parse-time $(shell) or include read BEFORE `unexport
    KEY` can execute a command-line KEY payload. CI runs make 4.3 and cannot
    observe that, so the ordering is asserted structurally instead."""
    lines = (PMOVES / "Makefile").read_text().splitlines()
    code = [(i, ln) for i, ln in enumerate(lines) if not ln.lstrip().startswith("#")]
    unexport = [i for i, ln in code if ln.strip() == "unexport KEY"]
    assert len(unexport) == 1, f"expected exactly one `unexport KEY`, found {len(unexport)}"
    risky = [i for i, ln in code
             if ln.lstrip().startswith(("include ", "-include ", "sinclude "))
             or "$(shell" in ln]
    assert risky, "structural check found no include/$(shell) lines -- parser is broken"
    assert unexport[0] < min(risky), (
        f"`unexport KEY` at line {unexport[0] + 1} comes after line {min(risky) + 1}: "
        f"{lines[min(risky)].strip()!r}")


def test_positive_control_structural_check_catches_an_end_of_file_unexport(tmp_path):
    """The ordering assertion must fail on the layout the review rejected."""
    src = (PMOVES / "Makefile").read_text().replace("\nunexport KEY\n", "\n", 1)
    variant = src + "\nunexport KEY\n"
    lines = variant.splitlines()
    code = [(i, ln) for i, ln in enumerate(lines) if not ln.lstrip().startswith("#")]
    unexport = [i for i, ln in code if ln.strip() == "unexport KEY"]
    risky = [i for i, ln in code
             if ln.lstrip().startswith(("include ", "-include ", "sinclude "))
             or "$(shell" in ln]
    assert unexport and risky and unexport[0] > min(risky)


def _make(tmp_path: Path, target: str, key: str, stdin: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ENV_LOCAL_KEY_FILE"] = str(tmp_path / "overlay.txt")
    env["ENV_LOCAL_KEY_AUDIT"] = str(tmp_path / "audit" / "edits.jsonl")
    env.pop("KEY", None)
    # P2d HARD PRE-RUN GUARD: the make targets pass no --file, so the ONLY
    # thing between this test and the real overlay is the override. Resolve
    # what the tool will act on and refuse to invoke make unless it is ours.
    tmp_root = Path(os.path.realpath(tmp_path))
    for var in ("ENV_LOCAL_KEY_FILE", "ENV_LOCAL_KEY_AUDIT"):
        acted_on = Path(os.path.realpath(env[var]))
        assert tmp_root in acted_on.parents, f"{var} escapes tmp_path: {acted_on}"
    assert env.get("PYTEST_CURRENT_TEST"), "tool-side default-path guard would be off"
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
