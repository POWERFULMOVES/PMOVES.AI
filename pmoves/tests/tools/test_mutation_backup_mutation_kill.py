"""Mutation-kill harness for the crash-safe mutation backup.

WHAT THIS PROVES
-----------------
The crash-safety fix has two halves, and this harness proves the SECOND one
bites: that ``pmoves/tests/mutation_backup.py`` really is what makes a
KILLED mutation harness survivable.

The kill signal is a TEST NAME, not a mood. "pytest exited non-zero" is also
satisfied by a collection error, a timeout or an unrelated environment
failure, so this harness reads pytest's own short summary and requires it to
name the target test -- the same discipline the lane's other harnesses use.

THE MUTATION
-------------
``restore_outstanding`` is short-circuited to return ``[]`` without restoring
anything. That is exactly what a repair that does not repair looks like: the
backup is still on disk, the tree is still mutated, and the conftest's
call to the helper does nothing.

The target test is the END-TO-END one -- it spawns a Python process that
imports ``pmoves/conftest.py``, which is what pytest imports during
collection -- so the child process picks up the MUTATED helper from disk and
the leftover mutation is never repaired. The named test must go red.

WHAT IS NOT PROVEN HERE
-----------------------
That the allowance in ``pmoves/configs/pytest_ratchet/_slow_files.yaml`` is
the right size. That is a measurement, recorded with its basis in the config
itself, and gated on SHAPE by pmoves/tests/tools/test_pytest_ratchet.py.

    python -m pytest pmoves/tests/tools/test_mutation_backup_mutation_kill.py -v
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from pmoves.tests import mutation_backup

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_mutation_backup.py"
TARGET = REPO_ROOT / "pmoves" / "tests" / "mutation_backup.py"
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-mutation-backup-mutation.lock"
_PYTEST_TIMEOUT_SECONDS = 300.0

#: A marker that must never survive a run. It is deliberately distinctive:
#: the helper's own PROSE contains the word "mutated", so a looser marker
#: would report a false leak on a perfectly clean file.
_MARKER = b"# PMOVES-MUTANT-MARKER"

# The mutate window is locked, so two harnesses cannot mutate the tree at
# once. The threading.Lock serialises threads inside one pytest process; the
# advisory FILE lock serialises separate PROCESSES, which a threading.Lock
# cannot do.
_MUTATION_LOCK = threading.Lock()


@dataclass(frozen=True)
class Mutation:
    """One anchor-to-anchor rewrite of the helper under test."""

    name: str
    path: Path
    old: str
    new: str
    target_test: str
    rationale: str


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_restore_short_circuited",
        path=TARGET,
        old="""    directory = _repo_dir(repo_root)
    if not directory.is_dir():
        return []""",
        new="""    directory = _repo_dir(repo_root)
    if not directory.is_dir():
        return []
    return []  # PMOVES-MUTANT-MARKER: the repair does not repair""",
        target_test=(
            "test_the_conftest_restores_a_leftover_mutation_at_collection"
        ),
        rationale=(
            "A restore that returns without restoring is the failure this "
            "whole module exists to prevent: the backup is on disk, the tree "
            "is still mutated, and the next session inherits the mutation."
        ),
    ),
]


def _read_source(path: Path) -> tuple[bytes, str]:
    """The file's exact bytes, plus its text with newlines normalised to LF.

    The BYTES are what the restore must reproduce EXACTLY: a decoded-text
    comparison cannot tell LF from CRLF, because `read_text` translates them
    away -- it certifies byte-exactness through a lens that blurs the very
    bytes it certifies.
    """
    raw = path.read_bytes()
    return raw, raw.decode("utf-8").replace("\r\n", "\n")


def _write_source(path: Path, text: str, newline: str) -> None:
    """Write LF-normalised `text` using the file's OWN newline convention."""
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def _run_pytest(
    node_id: str, timeout: float = _PYTEST_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess:
    # NOTE: no `--timeout` flag. That flag belongs to the `pytest-timeout`
    # PLUGIN, which is not installed in every CI environment -- and a flag
    # the plugin does not know makes pytest exit 4 with "unrecognized
    # arguments". The outer `subprocess.run(timeout=...)` is the real guard.
    return subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "-p", "no:warnings"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def _named_test_failed(proc: subprocess.CompletedProcess, test_name: str) -> bool:
    """True only if pytest's own short summary names THIS test as failed.

    A collection error, a timeout, or an unrelated failure also makes pytest
    exit non-zero; none of those is a kill.
    """
    for line in proc.stdout.splitlines():
        if line.startswith("FAILED ") and test_name in line:
            return True
    for line in proc.stderr.splitlines():
        if line.startswith("FAILED ") and test_name in line:
            return True
    return False


@contextlib.contextmanager
def _file_lock(path: Path):
    """Cross-process lock so two harnesses cannot mutate the tree at once."""
    handle = path.open("a+", encoding="utf-8")
    acquired = False
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(0.2)
        if not acquired:
            raise TimeoutError(f"could not acquire {path}")
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _apply_mutation(mutation: Mutation, original: str) -> str:
    """Return the mutated source, or raise if the anchor does not match.

    A mutation whose anchor has drifted must FAIL LOUDLY. Silently mutating
    nothing would produce a green harness that proves nothing.
    """
    if mutation.old not in original:
        raise AssertionError(
            f"mutation {mutation.name}: anchor not found in {mutation.path.name}. "
            "The source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original = mutation.path.read_text(encoding="utf-8")
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.path.name} -- the source drifted"
        )


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED -> GREEN, with a byte-exact restore."""
    node_id = (
        f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"
    )
    target = mutation.path
    original_bytes, original = _read_source(target)
    newline = "\r\n" if b"\r\n" in original_bytes else "\n"

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH), mutation_backup.file_lock(
        mutation_backup.lock_path(REPO_ROOT, target)
    ):
        # 1. GREEN BEFORE
        before = _run_pytest(node_id)
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        # The pristine bytes go on disk BEFORE the mutation, so a process
        # that is KILLED mid-mutation cannot leave the tree dirty for the
        # next session to inherit. See pmoves/tests/mutation_backup.py.
        mutation_backup.write_backup(REPO_ROOT, target, original_bytes)
        try:
            _write_source(target, mutated, newline)

            # 2. RED AFTER -- the NAMED test must die
            after = _run_pytest(node_id)
            assert after.returncode != 0, (
                f"{mutation.name}: the mutation SURVIVED -- "
                f"{mutation.target_test} still passed\n{after.stdout[-4000:]}"
            )
            assert _named_test_failed(after, mutation.target_test), (
                f"{mutation.name}: pytest failed, but NOT the named test "
                f"{mutation.target_test}\n{after.stdout[-4000:]}\n{after.stderr[-2000:]}"
            )
        finally:
            # 3. GREEN AFTER -- byte-exact restore
            target.write_bytes(original_bytes)
            restored = target.read_bytes()
            assert restored == original_bytes, (
                f"{mutation.name}: the restore was not byte-exact"
            )
            # The backup is dropped only AFTER a byte-exact restore. If the
            # assert above fails, the backup is the only good copy of the
            # pristine source, and the next session must still be able to
            # restore it -- so it stays on disk.
            mutation_backup.clear_backup(REPO_ROOT, target)

        after_restore = _run_pytest(node_id)
        assert after_restore.returncode == 0, (
            f"{mutation.name}: the restored source does not pass "
            f"{mutation.target_test}\n{after_restore.stdout[-4000:]}"
        )


def test_the_helper_source_is_intact_after_the_mutation_suite():
    """The suite must not leave the helper mutated."""
    for mutation in MUTATIONS:
        original, _text = _read_source(mutation.path)
        assert _MARKER not in original, (
            f"{mutation.path.name} still carries a mutation marker"
        )
