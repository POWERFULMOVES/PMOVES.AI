"""Mutation-kill harness: the mavis CLI ratchet must reject a broken launcher.

This is the PROVENANCE HARNESS for the defects found in the
``test_mavis_cli_timeout.py`` ratchet after it shipped in PR #3095.

It is a test (not a scratch script) because a ratchet that nobody re-runs
decays. Run it directly to see the mutation kill in action:

    python -m pytest pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py -v

It works by rewriting the gate inside
``pmoves/tests/test_mavis_cli_timeout.py`` back to its ORIGINAL defective
form, re-running that module, and asserting that the module now FAILS.
If the ratchet ever stops catching the defect, this harness fails.

Two defects are covered:

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
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
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


def _lock_file(handle) -> None:
    """Take an exclusive advisory lock on an open file, across processes."""
    if os.name == "nt":
        import msvcrt

        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


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
def _mutation_lock() -> Iterator[None]:
    """Hold the mutate -> run -> restore window exclusively."""
    with _MUTATION_LOCK:
        _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        handle = open(_LOCK_PATH, "a+b")
        try:
            # msvcrt.locking needs at least one byte to lock.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            _lock_file(handle)
            try:
                yield
            finally:
                _unlock_file(handle)
        finally:
            handle.close()


def _run_module() -> subprocess.CompletedProcess[str]:
    """Run the ratchet module and capture the whole report.

    ``-rA`` makes pytest print the short test summary for EVERY test. That
    summary is the harness's evidence: it is what turns "the run was
    unhappy" into "THIS test failed".
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "pmoves/tests/test_mavis_cli_timeout.py",
            "-rA",
            "--tb=short",
            "-q",
        ],
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


def _mutate_and_run(old: str, new: str, expected_failing_test: str) -> tuple[bool, str]:
    """Apply a mutation, run the ratchet module, restore the file.

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
        original_bytes = TARGET.read_bytes()
        # The anchors are LF text while the file on disk may be CRLF, so
        # the replacement is computed on the newline-normalised text and
        # the restore uses the exact bytes.
        original_text = original_bytes.decode("utf-8").replace("\r\n", "\n")
        assert old in original_text, "mutation setup failed: anchor not found"
        mutated_text = original_text.replace(old, new)
        assert mutated_text != original_text, "mutation setup failed: replacement was a no-op"

        try:
            TARGET.write_text(mutated_text, encoding="utf-8")
            proc = _run_module()
            output = proc.stdout + proc.stderr
            killed = (
                proc.returncode != 0
                and expected_failing_test in _failed_test_names(output)
            )
            return killed, output
        finally:
            TARGET.write_bytes(original_bytes)
            restored = TARGET.read_bytes()
            assert restored == original_bytes, (
                "the ratchet file was NOT restored to its pre-mutation bytes"
            )


def test_mutation_original_version_gate_is_killed() -> None:
    """Restoring the original version gate MUST make the ratchet fail.

    The test that must fail is ``test_mutation_broken_shim_fails_ratchet``:
    it is the one that INVOKES the ratchet's own gate with a broken
    launcher, so when the gate is weakened back to the stderr fallback the
    broken launcher is accepted and that test fails. Naming the test keeps
    the kill honest.
    """
    killed, output = _mutate_and_run(
        FIXED_GATE,
        ORIGINAL_GATE,
        "test_mutation_broken_shim_fails_ratchet",
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
    killed, output = _mutate_and_run(
        FIXED_UPSTREAM_PIN,
        ORIGINAL_UPSTREAM_PIN,
        "test_mutation_wrong_upstream_repo_is_detectable",
    )
    assert killed, (
        "the ratchet did NOT catch the wrong upstream repo pin -- the "
        f"cross-check can silently skip again.\n{output}"
    )


def test_ratchet_file_is_left_clean_after_mutations() -> None:
    """The harness must not leave the ratchet file mutated."""
    content = TARGET.read_text(encoding="utf-8")
    assert FIXED_GATE in content, "the ratchet gate is not in its fixed form"
    assert FIXED_UPSTREAM_PIN in content, "the upstream pin is not the fixed one"


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(pytest.main([__file__, "-v"]))
