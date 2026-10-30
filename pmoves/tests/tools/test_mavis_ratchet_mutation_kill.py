"""Mutation-kill harness: the mavis CLI ratchet must reject a broken launcher.

This is the PROVENANCE HARNESS for the defects found in the
``test_mavis_cli_timeout.py`` ratchet after it shipped in PR #3095.

It is a test (not a scratch script) because a ratchet that nobody re-runs
decays. Run it directly to see the mutation kill in action:

    python -m pytest pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py -v

It works by rewriting the code under test back to its ORIGINAL defective
form, re-running the module that owns the check, and asserting that the
module now FAILS. If the ratchet ever stops catching the defect, this
harness fails.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens inside the mutation lock, so a
failed run cannot leave the tree mutated.

Defects covered:

Defect A -- the version gate accepted stderr as a version string
    Original:  ``version = (proc.stdout or proc.stderr or "").strip()``
                ``assert version``
    A broken launcher (Node's "Cannot find module" banner on stderr, rc=1)
    satisfies that assertion, so the ratchet reported GREEN on a 100%
    broken CLI.

Defect B -- the upstream repo pin pointed at a 404
    ``MiniMaxInc/MiniMax-Code`` does not exist. The real upstream is
    ``MiniMax-AI/minimax-code``. With the wrong pin the fetch returned a
    JSON error object where a list was expected, so the matrix cross-check
    silently degraded to a permanent SKIP.

Defect C -- the matrix reader ignored ``exclude:``
    ``_extract_matrix_platforms`` parsed ``include:`` but never
    ``exclude:``, so a matrix that EXCLUDES a platform still reported it
    as covered upstream.

Defect D -- the POSIX lock path could block forever
    The Windows branch of the mutation lock honoured
    ``_LOCK_TIMEOUT_SECONDS``; the POSIX branch used a bare blocking
    ``flock`` that waited forever -- a stuck holder wedged the whole
    suite with no timeout and no diagnostic.

Defect E -- the clean-check read the target without the lock
    ``test_ratchet_file_is_left_clean_after_mutations`` read the
    ratchet file without taking the mutation lock, so it could observe
    the file mid-mutation (torn, partially-written bytes) -- the door
    left off the hinge.

Defect F -- the GitHub API host was matched by SUBSTRING
    ``"api.github.com" in url`` also accepts
    ``https://api.github.com.evil.example/`` and
    ``https://evil.example/?x=api.github.com``. The host is now compared
    EXACTLY, through the parsed hostname.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
------------------------------------------
Each mutation names the test that MUST fail for the mutation to count as
killed. The kill signal used to be "pytest exited non-zero and the word
'failed' appeared somewhere in the output" -- a signal that a collection
error, a timeout or an unrelated environment failure also satisfies. The
harness could therefore celebrate killing a mutation that was never even
exercised. Now the harness reads pytest's own short test summary and
requires the NAMED test to be in it.

The harness restores the file in a ``finally`` block, so a failed run
leaves the working tree clean, and the restore is asserted.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = Path(__file__).resolve()
TARGET = REPO_ROOT / "pmoves" / "tests" / "test_mavis_cli_timeout.py"

# The FIXED gate, verbatim from the repaired ratchet.
FIXED_GATE = '''    assert proc.returncode == 0, (
        f"mavis --version exited {proc.returncode} (expected 0). The CLI ran "
        f"but failed. stderr={proc.stderr!r} stdout={proc.stdout!r}. "
        f"Investigate the shim / daemon path before merging -- a non-zero "
        f"exit means the launcher is broken even though it did not hang."
    )
    version = (proc.stdout or "").strip()
    assert version, (
        f"mavis --version returned empty stdout (rc={proc.returncode}); CLI "
        f"ran without hanging but did not produce a version string. "
        f"stderr={proc.stderr!r}"
    )
    lowered = version.lower()
    for marker in ("error:", "cannot find module", "traceback", "not found"):
        assert marker not in lowered, (
            f"mavis --version stdout looks like an error banner, not a "
            f"version string: {version!r}. The ratchet must not accept "
            f"error prose as a version."
        )
'''

# The ORIGINAL gate, verbatim from PR #3095 (the defect that shipped).
ORIGINAL_GATE = '''    version = (proc.stdout or proc.stderr or "").strip()
    assert version, (
        f"mavis --version returned empty (rc={proc.returncode}); CLI ran "
        f"without hanging but did not produce a version string."
    )
'''

FIXED_UPSTREAM_PIN = '_UPSTREAM_REPO = "MiniMax-AI/minimax-code"'
ORIGINAL_UPSTREAM_PIN = '_UPSTREAM_REPO = "MiniMaxInc/MiniMax-Code"'

# The FIXED `exclude:` handling in the ratchet's matrix reader.
FIXED_EXCLUDE_HANDLING = '''def _apply_matrix_exclusions(
    combos: list[dict[str, object]],
    exclude_entries: list[object],
) -> list[dict[str, object]]:
    """Remove the combinations an ``exclude:`` entry matches.

    An ``exclude:`` entry that matches NOTHING is not an error: exclude
    can be broader than the matrix it filters (a shared exclude list
    naming platforms this job does not run). The entry is simply a
    filter, so an unmatched entry removes nothing.
    """
    for entry in exclude_entries:
        if not isinstance(entry, dict) or not entry:
            continue
        combos = [
            combo
            for combo in combos
            if not _combo_matches_exclude(combo, entry)
        ]
    return combos
'''

# The ORIGINAL `exclude:` handling: the list is accepted and then IGNORED.
ORIGINAL_EXCLUDE_HANDLING = '''def _apply_matrix_exclusions(
    combos: list[dict[str, object]],
    exclude_entries: list[object],
) -> list[dict[str, object]]:
    """Remove the combinations an ``exclude:`` entry matches.

    THE DEFECTIVE FORM (the defect this harness pins): the ``exclude:``
    list is parsed away and never applied, so every excluded combination
    is still reported as one the matrix runs.
    """
    return combos
'''

# The FIXED POSIX branch of the mutation lock: a NON-BLOCKING attempt, so
# the shared deadline loop can give up instead of waiting forever.
FIXED_POSIX_BRANCH = '''def _try_lock_posix(handle) -> bool:
    """Try to take the POSIX advisory lock WITHOUT blocking.

    The lock MUST be requested with ``LOCK_NB``: a bare blocking
    ``flock`` waits for the holder FOREVER, which wedges the whole test
    suite with no timeout and no diagnostic.
    """
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True
'''

# The ORIGINAL POSIX branch: a bare BLOCKING flock.
ORIGINAL_POSIX_BRANCH = '''def _try_lock_posix(handle) -> bool:
    """Try to take the POSIX advisory lock WITHOUT blocking.

    THE DEFECTIVE FORM (the defect this harness pins): a bare BLOCKING
    ``flock``. On a real POSIX host this waits for the holder forever --
    no timeout, no diagnostic, the suite wedges.
    """
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return True
'''

# The FIXED clean-check read: it takes the mutation lock.
FIXED_LOCKED_READ = '''def _read_ratchet_file_under_lock(lock_path: Path | None = None) -> str:
    """Read the tracked ratchet file WHILE HOLDING the mutation lock.

    Reading the target without the lock can observe the file MID-
    MUTATION -- torn, partially-written bytes -- and report a clean file
    that is not clean ("the door left off the hinge").
    """
    with _mutation_lock(lock_path):
        return TARGET.read_text(encoding="utf-8")
'''

# The ORIGINAL clean-check read: no lock at all.
UNLOCKED_READ = '''def _read_ratchet_file_under_lock(lock_path: Path | None = None) -> str:
    """Read the tracked ratchet file WHILE HOLDING the mutation lock.

    THE DEFECTIVE FORM (the defect this harness pins): the read happens
    WITHOUT the lock, so it can observe a torn, mid-mutation file.
    """
    return TARGET.read_text(encoding="utf-8")
'''

# The FIXED GitHub API host check: the HOSTNAME is compared exactly.
FIXED_API_HOST_MATCH = '''def _is_github_api_url(url: str) -> bool:
    """Whether ``url`` addresses the GitHub API host EXACTLY.

    A SUBSTRING test (``"api.github.com" in url``) is a loose host
    match: it also accepts

        https://api.github.com.evil.example/repos
        https://evil.example/?x=api.github.com

    -- neither of which is the host this ratchet talks to. The host is
    compared EXACTLY, through the parsed ``hostname``. The netloc is
    NOT compared: it carries userinfo and a port, so comparing it would
    reintroduce a different mismatch class (a real request to
    ``https://api.github.com:443/...`` would be rejected).

    A URL that is not an absolute, parseable URL is NOT the API host,
    and must not raise out of the caller.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    try:
        hostname = parsed.hostname
    except ValueError:
        return False
    return hostname == "api.github.com"
'''

# The ORIGINAL GitHub API host check: a loose SUBSTRING match, which
# also accepts "api.github.com.evil.example" and a query string that
# merely CONTAINS the API host.
ORIGINAL_API_HOST_MATCH = '''def _is_github_api_url(url: str) -> bool:
    """Whether ``url`` addresses the GitHub API host EXACTLY.

    THE DEFECTIVE FORM (the defect this harness pins): the host is
    matched as a SUBSTRING, so a look-alike host -- or the API host
    sitting inside a query string -- is accepted as the GitHub API.
    """
    return "api.github.com" in url
'''

# WHY THE MUTATE WINDOW IS LOCKED
# -------------------------------
# Both mutations rewrite the SAME tracked source file on disk and restore
# it in a ``finally``. Under pytest-xdist (or any parallel runner, or a
# Ctrl-C mid-write) the two interleave: one test reads the "original"
# while the other has it mutated, and the restore in ``finally`` can
# resurrect a mutated file. A mutation harness that itself has a race
# condition is a self-healing grenade.
#
# The lock is TWO layers on purpose. The ``threading.Lock`` serializes
# threads inside one pytest process; the advisory FILE lock serializes
# separate PROCESSES (xdist workers, two pytest invocations at once), which
# a ``threading.Lock`` cannot do. The file lock is released by the OS if a
# worker dies, so a crashed run cannot leave the lock held forever.
_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-mavis-ratchet-mutation.lock"
_LOCK_TIMEOUT_SECONDS = 300
# How long the deadline loop sleeps between attempts. Short enough that a
# timeout is felt quickly, long enough not to spin the CPU.
_LOCK_POLL_SECONDS = 0.2


class MutationLockTimeout(TimeoutError):
    """The mutation lock could not be taken within the deadline.

    A subclass of ``TimeoutError`` (and therefore of ``OSError``) so the
    failure reads as a timeout, and so the Windows and POSIX branches
    behave identically.
    """


def _holder_path(lock_path: Path) -> Path:
    """Where the current holder of ``lock_path`` records itself."""
    return lock_path.with_name(lock_path.name + ".holder")


def _write_holder_info(lock_path: Path) -> None:
    """Record WHO holds the lock, so a timeout can name the holder."""
    try:
        _holder_path(lock_path).write_text(
            f"pid={os.getpid()} host={socket.gethostname()} "
            f"thread={threading.get_ident()} since={int(time.time())}\n",
            encoding="utf-8",
        )
    except OSError:
        # The holder info is a DIAGNOSTIC, never a precondition: a host
        # with a read-only temp dir must still be able to take the lock.
        pass


def _read_holder_info(lock_path: Path) -> str:
    """Describe the recorded holder of ``lock_path``."""
    try:
        text = _holder_path(lock_path).read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return text or "unknown"


def _clear_holder_info(lock_path: Path) -> None:
    """Forget the recorded holder once the lock is released."""
    try:
        _holder_path(lock_path).unlink()
    except OSError:
        pass


def _open_lock_handle(lock_path: Path):
    """Open the lock file, making sure there is at least one byte to lock."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    # msvcrt.locking needs at least one byte to lock.
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    return handle


def _try_lock_windows(handle) -> bool:
    """Try to take the Windows byte-range lock WITHOUT blocking."""
    import msvcrt

    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return False
    return True


def _try_lock_posix(handle) -> bool:
    """Try to take the POSIX advisory lock WITHOUT blocking.

    The lock MUST be requested with ``LOCK_NB``: a bare blocking
    ``flock`` waits for the holder FOREVER, which wedges the whole test
    suite with no timeout and no diagnostic.
    """
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _try_lock_nonblocking(handle) -> bool:
    """Try the OS-appropriate NON-BLOCKING lock; False if it is held."""
    if os.name == "nt":
        return _try_lock_windows(handle)
    return _try_lock_posix(handle)


def _lock_file(
    handle,
    *,
    lock_path: Path | None = None,
    timeout_seconds: float | None = None,
    monotonic=None,
    sleep=None,
    attempt=None,
) -> None:
    """Take the exclusive advisory lock, with a HARD deadline.

    BOTH OS BRANCHES GO THROUGH THIS ONE LOOP. The Windows branch used
    to honour ``_LOCK_TIMEOUT_SECONDS`` while the POSIX branch used a
    bare blocking ``flock`` that waited forever: a stuck holder wedged
    the whole suite with no timeout and no diagnostic. The two branches
    are now behaviourally equivalent -- same timeout constant, same
    failure mode, same message shape.

    A timeout RAISES. It never "proceeds without the lock": proceeding
    without the lock defeats the whole point of the lock, which is to
    make the mutate -> run -> restore window exclusive.
    """
    path = _LOCK_PATH if lock_path is None else Path(lock_path)
    timeout = _LOCK_TIMEOUT_SECONDS if timeout_seconds is None else float(timeout_seconds)
    clock = time.monotonic if monotonic is None else monotonic
    nap = time.sleep if sleep is None else sleep
    try_lock = _try_lock_nonblocking if attempt is None else attempt
    deadline = clock() + timeout
    while True:
        if try_lock(handle):
            return
        if clock() >= deadline:
            raise MutationLockTimeout(
                f"could not acquire the mutation lock {path} within "
                f"{timeout:g}s (holder: {_read_holder_info(path)}). Another "
                f"pytest process or a stuck mutation run is holding it -- "
                f"kill the holder, or wait for it to release."
            )
        nap(_LOCK_POLL_SECONDS)


def _unlock_file(handle) -> None:
    """Release the advisory lock taken by ``_lock_file``."""
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _file_lock(
    lock_path: Path,
    *,
    timeout_seconds: float | None = None,
) -> Iterator[None]:
    """Hold the advisory file lock on ``lock_path`` for the window."""
    handle = _open_lock_handle(lock_path)
    try:
        _lock_file(handle, lock_path=lock_path, timeout_seconds=timeout_seconds)
        _write_holder_info(lock_path)
        try:
            yield
        finally:
            _unlock_file(handle)
            _clear_holder_info(lock_path)
    finally:
        handle.close()


@contextlib.contextmanager
def _mutation_lock(lock_path: Path | None = None) -> Iterator[None]:
    """Hold the mutate -> run -> restore window exclusively."""
    with _MUTATION_LOCK:
        with _file_lock(_LOCK_PATH if lock_path is None else Path(lock_path)):
            yield


def _read_ratchet_file_under_lock(lock_path: Path | None = None) -> str:
    """Read the tracked ratchet file WHILE HOLDING the mutation lock.

    Reading the target without the lock can observe the file MID-
    MUTATION -- torn, partially-written bytes -- and report a clean file
    that is not clean ("the door left off the hinge").
    """
    with _mutation_lock(lock_path):
        return TARGET.read_text(encoding="utf-8")


def _assert_ratchet_file_clean(content: str) -> None:
    """Assert the tracked ratchet file is in its fixed (unmutated) form.

    Named and importable so the check is stated ONCE: the pytest test
    below and any caller share this function rather than restating it.
    """
    assert FIXED_GATE in content, "the ratchet gate is not in its fixed form"
    assert FIXED_UPSTREAM_PIN in content, "the upstream pin is not the fixed one"


def _repo_relative(path: Path) -> str:
    """Path relative to the repo root, for a stable pytest invocation."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _run_pytest(module: Path, *, select: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a pytest module and capture the whole report.

    ``-rA`` makes pytest print the short test summary for EVERY test. That
    summary is the harness's evidence: it is what turns "the run was
    unhappy" into "THIS test failed".

    ``select`` is a pytest ``-k`` expression. The mutation cases use it
    to run ONLY the test the mutation is supposed to kill: the other
    tests are not evidence for this mutation, and running the whole
    module would pay for a live ``mavis --version`` on every mutation.
    """
    args = [
        sys.executable,
        "-m",
        "pytest",
        _repo_relative(module),
        "-rA",
        "--tb=short",
        "-q",
    ]
    if select:
        args += ["-k", select]
    return subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _failed_test_names(output: str) -> set[str]:
    """The names of the tests pytest reported as FAILED.

    WHY THE SUMMARY AND NOT A SUBSTRING
    ------------------------------------
    The kill signal used to be ``proc.returncode != 0 and "failed" in
    output``. A collection error caused by an unrelated import change, a
    timeout, or an environment failure all satisfy that signal too -- the
    substring check cannot tell "1 failed" from "failed to create
    endpoint". Reading pytest's own short test summary gives the NAME of
    the test that failed, which can only exist if that test actually ran
    and actually failed.
    """
    names: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("FAILED "):
            continue
        node = stripped[len("FAILED "):].split(" - ", 1)[0].strip()
        if "::" in node:
            names.add(node.rsplit("::", 1)[-1].strip())
    return names


def _load_ratchet_module():
    """Import the ratchet module FROM DISK, freshly.

    The harness INVOKES the ratchet's own assertion functions -- it
    never restates the check inline. Loading from disk (rather than
    importing once at module load) is what lets the harness call those
    functions against a MUTATED source.
    """
    spec = importlib.util.spec_from_file_location(
        "pmoves_mavis_ratchet_under_test", TARGET
    )
    assert spec is not None and spec.loader is not None, (
        f"could not load the ratchet module from {TARGET}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mutation_case(
    path: Path,
    old: str,
    new: str,
    *,
    select: str,
    expected_failing_test: str,
) -> tuple[bool, str]:
    """Apply a mutation, prove it kills, restore -- GREEN, RED, GREEN.

    THE THREE PHASES ARE THE CONTRACT:

    1. GREEN BEFORE -- the pristine source must pass the selected test.
    2. RED AFTER    -- the mutated source must fail the NAMED test.
    3. GREEN AFTER  -- the byte-exact restored source must pass again.

    ``expected_failing_test`` is the test that MUST fail for the mutation
    to count as killed. Anything else failing (a collection error, a
    timeout, an unrelated failure) does NOT count: the harness may only
    claim a kill it can point at.

    Returns (mutation_was_killed, combined_output).
    """
    with _mutation_lock():
        # The original BYTES are captured before the mutation and written
        # back verbatim: the restore must put the tracked file back exactly
        # as it was, not approximately.
        original_bytes = path.read_bytes()
        # The anchors are LF text while the file on disk may be CRLF, so
        # the replacement is computed on the newline-normalised text and
        # the restore uses the exact bytes.
        original_text = original_bytes.decode("utf-8").replace("\r\n", "\n")
        assert old in original_text, (
            f"mutation setup failed: anchor not found in {path.name}"
        )
        mutated_text = original_text.replace(old, new)
        assert mutated_text != original_text, (
            "mutation setup failed: replacement was a no-op"
        )

        # PHASE 1 -- GREEN BEFORE.
        before = _run_pytest(path, select=select)
        before_output = before.stdout + before.stderr
        assert before.returncode == 0 and not _failed_test_names(before_output), (
            "the pristine source was NOT green before the mutation -- a "
            f"mutation case may not start from a red baseline:\n{before_output}"
        )

        killed = False
        output = ""
        try:
            # PHASE 2 -- RED AFTER.
            path.write_text(mutated_text, encoding="utf-8", newline="\n")
            proc = _run_pytest(path, select=select)
            output = proc.stdout + proc.stderr
            killed = (
                proc.returncode != 0
                and expected_failing_test in _failed_test_names(output)
            )
        finally:
            # PHASE 3 -- RESTORE, byte-exact.
            path.write_bytes(original_bytes)
            restored = path.read_bytes()
            assert restored == original_bytes, (
                f"{path.name} was NOT restored to its pre-mutation bytes"
            )

        after = _run_pytest(path, select=select)
        after_output = after.stdout + after.stderr
        assert after.returncode == 0 and not _failed_test_names(after_output), (
            "the restored source was NOT green after the mutation -- the "
            f"restore must put the tree back exactly:\n{after_output}"
        )
        return killed, output


def test_mutation_original_version_gate_is_killed() -> None:
    """Restoring the original version gate MUST make the ratchet fail.

    The test that must fail is ``test_mutation_broken_shim_fails_ratchet``:
    it is the one that INVOKES the ratchet's own gate with a broken
    launcher, so when the gate is weakened back to the stderr fallback the
    broken launcher is accepted and that test fails. Naming the test keeps
    the kill honest.
    """
    killed, output = _mutation_case(
        TARGET,
        FIXED_GATE,
        ORIGINAL_GATE,
        select="test_mutation_broken_shim_fails_ratchet",
        expected_failing_test="test_mutation_broken_shim_fails_ratchet",
    )
    assert killed, (
        "the ratchet did NOT catch the original stderr-fallback defect -- "
        f"the gate was weakened again.\n{output}"
    )


def test_mutation_original_upstream_pin_is_killed() -> None:
    """Restoring the 404 upstream pin MUST make the ratchet fail.

    The test that must fail is ``test_mutation_wrong_upstream_repo_is_detectable``:
    it asserts the pin IS the repo that exists, so a 404 pin fails it
    directly. (The cross-check would merely degrade to a skip, which is a
    silent failure -- exactly what must not pass unnoticed.)
    """
    killed, output = _mutation_case(
        TARGET,
        FIXED_UPSTREAM_PIN,
        ORIGINAL_UPSTREAM_PIN,
        select="test_mutation_wrong_upstream_repo_is_detectable",
        expected_failing_test="test_mutation_wrong_upstream_repo_is_detectable",
    )
    assert killed, (
        "the ratchet did NOT catch the wrong upstream repo pin -- the "
        f"cross-check can silently skip again.\n{output}"
    )


def test_mutation_exclude_handling_is_killed() -> None:
    """Ignoring the matrix's ``exclude:`` list MUST make the ratchet fail.

    The matrix reader parsed ``include:`` but never ``exclude:``, so a
    matrix that EXCLUDES a platform still reported it as covered
    upstream -- the ratchet would announce "upstream covers Windows" for
    a matrix that never runs Windows.

    The harness INVOKES the ratchet's own assertion function
    (``_assert_matrix_platforms``) rather than restating the check
    inline: the green phase below is that function's own verdict.
    """
    ratchet = _load_ratchet_module()
    ratchet._assert_matrix_platforms(
        ratchet._SAMPLE_UPSTREAM_CI_WITH_EXCLUDE,
        ["macos", "ubuntu"],
        context="the matrix with an `exclude:` entry",
    )
    killed, output = _mutation_case(
        TARGET,
        FIXED_EXCLUDE_HANDLING,
        ORIGINAL_EXCLUDE_HANDLING,
        select="test_mutation_excluded_platform_is_not_covered",
        expected_failing_test="test_mutation_excluded_platform_is_not_covered",
    )
    assert killed, (
        "the ratchet did NOT catch the ignored `exclude:` list -- an "
        f"excluded platform is still reported as covered.\n{output}"
    )


class _FakeFcntl:
    """A stand-in for the POSIX ``fcntl`` module.

    ``flock`` is asked for a ``LOCK_EX | LOCK_NB`` attempt and the fake
    reports the lock as HELD by raising ``BlockingIOError`` -- exactly
    what the kernel does for a non-blocking attempt on a held lock.

    A BLOCKING attempt (no ``LOCK_NB``) would hang a real POSIX host
    forever, so the fake raises instead: the hang becomes an immediate,
    visible failure instead of a wedged suite.
    """

    LOCK_EX = 1
    LOCK_SH = 2
    LOCK_NB = 4
    LOCK_UN = 8

    def __init__(self) -> None:
        self.operations: list[int] = []

    def flock(self, fd: int, operation: int) -> None:
        self.operations.append(operation)
        if operation & self.LOCK_UN:
            return
        if operation & self.LOCK_NB:
            raise BlockingIOError("the lock is held by another process")
        raise AssertionError(
            "the POSIX branch requested a BLOCKING flock -- on a real host "
            "that waits for the holder forever, with no timeout"
        )


class _FakeClock:
    """A monotonic clock that only advances when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_posix_lock_path_times_out_and_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The POSIX lock path MUST time out and RAISE, never hang.

    The POSIX branch used a bare blocking ``flock``: it waited for the
    holder forever, with no timeout and no diagnostic, so a stuck holder
    wedged the whole suite. The fix puts the POSIX branch on the SAME
    deadline loop as the Windows branch.

    The fake ``fcntl`` reports the lock as HELD and the fake clock makes
    the deadline reachable without sleeping -- so this test cannot hang,
    and a restored BLOCKING flock fails loudly instead of wedging.
    """
    fake_fcntl = _FakeFcntl()
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)
    lock_path = tmp_path / "posix-probe.lock"
    _write_holder_info(lock_path)
    handle = _open_lock_handle(lock_path)
    clock = _FakeClock()
    try:
        with pytest.raises(MutationLockTimeout) as excinfo:
            _lock_file(
                handle,
                lock_path=lock_path,
                timeout_seconds=1.0,
                attempt=_try_lock_posix,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            )
    finally:
        handle.close()

    message = str(excinfo.value)
    assert str(lock_path) in message, (
        f"the timeout message does not name the lock file: {message!r}"
    )
    assert "1s" in message, (
        f"the timeout message does not name the timeout: {message!r}"
    )
    assert "pid=" in message, (
        f"the timeout message does not name the holder: {message!r}"
    )
    assert fake_fcntl.operations, "the POSIX branch never attempted the lock"
    assert all(op & fake_fcntl.LOCK_NB for op in fake_fcntl.operations), (
        "the POSIX branch requested a BLOCKING flock: "
        f"{fake_fcntl.operations!r}"
    )
    assert clock.now >= 1.0, "the deadline was never reached"


_HOLDER_SCRIPT = """
import importlib.util
import pathlib
import sys
import time

spec = importlib.util.spec_from_file_location("harness", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
lock_path = pathlib.Path(sys.argv[2])
handle = module._open_lock_handle(lock_path)
module._lock_file(handle, lock_path=lock_path, timeout_seconds=60)
print("LOCKED", flush=True)
time.sleep(120)
"""


def test_held_lock_makes_the_next_holder_time_out(tmp_path: Path) -> None:
    """A lock held by ANOTHER PROCESS must time out, not hang.

    This is the end-to-end proof on the real OS primitive: a child
    process holds the advisory lock, and the parent -- with a one second
    deadline -- must give up and RAISE.
    """
    lock_path = tmp_path / "held.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _HOLDER_SCRIPT,
            str(HARNESS),
            str(lock_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        line = holder.stdout.readline().strip()
        assert line == "LOCKED", (
            "the holder process never took the lock "
            f"(said {line!r}); stderr={holder.stderr.read() if holder.stderr else ''!r}"
        )
        handle = _open_lock_handle(lock_path)
        try:
            with pytest.raises(MutationLockTimeout):
                _lock_file(handle, lock_path=lock_path, timeout_seconds=1.0)
        finally:
            handle.close()
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            holder.kill()


def test_clean_check_is_serialized_against_concurrent_mutation(
    tmp_path: Path,
) -> None:
    """The clean-check must NOT read the target while a mutation holds the lock.

    The clean-check used to read the ratchet file WITHOUT the mutation
    lock, so it could observe the file mid-mutation -- torn,
    partially-written bytes -- and report a clean file that is not
    clean. The read must be serialized against every mutation.
    """
    lock_path = tmp_path / "clean-check.lock"
    started = threading.Event()
    finished = threading.Event()
    outcome: dict[str, object] = {}

    def reader() -> None:
        started.set()
        try:
            outcome["content"] = _read_ratchet_file_under_lock(lock_path)
        finally:
            finished.set()

    with _file_lock(lock_path):
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        assert started.wait(10), "the reader thread never started"
        assert not finished.wait(0.5), (
            "the clean-check read the target WITHOUT the mutation lock -- it "
            "can observe a torn, partially-written file mid-mutation (the "
            "door left off the hinge)"
        )
    thread.join(timeout=30)
    assert finished.is_set(), (
        "the clean-check never completed after the lock was released"
    )
    assert FIXED_GATE in str(outcome.get("content")), (
        "the clean-check did not read the ratchet file"
    )


def test_mutation_posix_blocking_flock_is_killed() -> None:
    """A BLOCKING ``flock`` in the POSIX branch MUST fail the harness.

    The mutation rewrites this harness' own POSIX branch back to the
    bare blocking form; the test that must fail is
    ``test_posix_lock_path_times_out_and_raises``, because a blocking
    flock cannot honour the deadline at all.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_POSIX_BRANCH,
        ORIGINAL_POSIX_BRANCH,
        select="test_posix_lock_path_times_out_and_raises",
        expected_failing_test="test_posix_lock_path_times_out_and_raises",
    )
    assert killed, (
        "the POSIX lock branch can block forever again -- a stuck holder "
        f"would wedge the suite with no timeout and no diagnostic.\n{output}"
    )


def test_mutation_unlocked_clean_check_is_killed() -> None:
    """Reading the clean-check WITHOUT the lock MUST fail the harness.

    The mutation rewrites this harness' own clean-check read back to the
    unlocked form; the test that must fail is
    ``test_clean_check_is_serialized_against_concurrent_mutation``.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_LOCKED_READ,
        UNLOCKED_READ,
        select="test_clean_check_is_serialized_against_concurrent_mutation",
        expected_failing_test="test_clean_check_is_serialized_against_concurrent_mutation",
    )
    assert killed, (
        "the clean-check can read the target without the lock again -- it "
        f"can observe a torn, mid-mutation file.\n{output}"
    )


def test_mutation_loose_api_host_match_is_killed() -> None:
    """A SUBSTRING host match MUST fail the harness.

    The ratchet's network test double matched the GitHub API host with
    ``"api.github.com" in url`` -- a loose host match that also accepts
    ``https://api.github.com.evil.example/`` and
    ``https://evil.example/?x=api.github.com``. The mutation rewrites the
    ratchet's host check back to that substring form; the test that must
    fail is ``test_mutation_github_api_host_match_is_exact``.

    The harness INVOKES the ratchet's own helper (``_is_github_api_url``)
    rather than restating the host check inline.
    """
    ratchet = _load_ratchet_module()
    assert ratchet._is_github_api_url("https://api.github.com/repos")
    assert not ratchet._is_github_api_url("https://api.github.com.evil.example/")
    killed, output = _mutation_case(
        TARGET,
        FIXED_API_HOST_MATCH,
        ORIGINAL_API_HOST_MATCH,
        select="test_mutation_github_api_host_match_is_exact",
        expected_failing_test="test_mutation_github_api_host_match_is_exact",
    )
    assert killed, (
        "the GitHub API host can be matched by substring again -- a "
        f"look-alike host would be treated as the API.\n{output}"
    )


def test_ratchet_file_is_left_clean_after_mutations() -> None:
    """The harness must not leave the ratchet file mutated.

    The read happens UNDER the mutation lock: without it, this check can
    observe the target mid-mutation and report a clean file that is not
    clean.
    """
    _assert_ratchet_file_clean(_read_ratchet_file_under_lock())


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(pytest.main([__file__, "-v"]))
