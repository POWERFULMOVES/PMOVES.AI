"""The crash-safe backup that lets a KILLED mutation harness leave the tree clean.

WHY THIS IS GATED
------------------
The tree is the thing every one of these tests is about, so the tests are
about the TREE, not about the helper's return values: a file that was
mutated is restored, a file that was not mutated is left alone, a checkout's
backups are not another checkout's backups, and the restore is SKIPPED while
a live harness owns the tree.

The end-to-end test drives the REAL path -- a Python process that imports
``pmoves/conftest.py``, which is what pytest imports during collection -- so
it exercises the wiring rather than re-typing it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from pmoves.tests import mutation_backup

REPO_ROOT = Path(__file__).resolve().parents[3]


def _backup_dir(repo_root: Path) -> Path:
    return mutation_backup._repo_dir(repo_root)


def test_the_backup_lives_outside_the_checkout(tmp_path):
    """A backup inside the tree would be picked up by `git add -A` -- and a
    mutation harness holds the tree mutated by design, so the tree is only
    trustworthy BETWEEN runs."""
    tool = tmp_path / "tool.py"
    tool.write_bytes(b"pristine")
    path = mutation_backup.write_backup(REPO_ROOT, tool, b"pristine")
    try:
        assert path.is_file()
        assert REPO_ROOT not in path.parents
        assert path.is_relative_to(_backup_dir(REPO_ROOT))
    finally:
        mutation_backup.clear_backup(REPO_ROOT, tool)


def test_a_mutated_file_is_restored_from_its_backup(tmp_path):
    """The whole point: a file left mutated by a killed harness comes back."""
    tool = tmp_path / "tool.py"
    tool.write_bytes(b"pristine bytes")
    mutation_backup.write_backup(REPO_ROOT, tool, b"pristine bytes")
    tool.write_bytes(b"MUTATED")
    restored = mutation_backup.restore_outstanding(REPO_ROOT)
    try:
        assert str(tool) in restored
        assert tool.read_bytes() == b"pristine bytes"
    finally:
        mutation_backup.clear_backup(REPO_ROOT, tool)


def test_the_restore_is_idempotent_and_leaves_an_untouched_file_alone(tmp_path):
    """A second restore finds nothing to do, and a file that was never
    mutated is not rewritten."""
    tool = tmp_path / "tool.py"
    tool.write_bytes(b"pristine bytes")
    mutation_backup.write_backup(REPO_ROOT, tool, b"pristine bytes")
    tool.write_bytes(b"MUTATED")
    first = mutation_backup.restore_outstanding(REPO_ROOT)
    second = mutation_backup.restore_outstanding(REPO_ROOT)
    try:
        assert first == [str(tool)]
        assert second == []
        assert tool.read_bytes() == b"pristine bytes"
    finally:
        mutation_backup.clear_backup(REPO_ROOT, tool)


def test_two_checkouts_keep_separate_backups(tmp_path):
    """The operator's primary checkout and a lane worktree are different
    trees; one must never restore the other's files."""
    other_root = tmp_path / "other-checkout"
    (other_root / "pmoves" / "tools").mkdir(parents=True)
    tool = other_root / "pmoves" / "tools" / "tool.py"
    tool.write_bytes(b"pristine bytes")
    mutation_backup.write_backup(other_root, tool, b"pristine bytes")
    tool.write_bytes(b"MUTATED")
    try:
        # This checkout's restore must not see the other checkout's backup.
        assert mutation_backup.restore_outstanding(REPO_ROOT) == []
        assert tool.read_bytes() == b"MUTATED"
        # The other checkout's restore does.
        assert str(tool) in mutation_backup.restore_outstanding(other_root)
        assert tool.read_bytes() == b"pristine bytes"
    finally:
        mutation_backup.clear_backup(other_root, tool)


def test_the_restore_is_skipped_while_a_live_harness_owns_the_lock(tmp_path, monkeypatch):
    """A live harness owns the tree while it mutates. A restore that cannot
    take the lock must leave the tree alone, not revert a mutation in flight.
    """
    tool = tmp_path / "tool.py"
    tool.write_bytes(b"pristine bytes")
    mutation_backup.write_backup(REPO_ROOT, tool, b"pristine bytes")
    tool.write_bytes(b"MUTATED")
    monkeypatch.setattr(mutation_backup, "_RESTORE_LOCK_TIMEOUT_SECONDS", 0.5)
    try:
        with mutation_backup.file_lock(
            mutation_backup.lock_path(REPO_ROOT, tool), timeout=1
        ):
            assert mutation_backup.restore_outstanding(REPO_ROOT) == []
        assert tool.read_bytes() == b"MUTATED"
    finally:
        mutation_backup.clear_backup(REPO_ROOT, tool)


def test_the_conftest_restores_a_leftover_mutation_at_collection(tmp_path):
    """END TO END, through the real wiring.

    pytest imports every conftest during COLLECTION, and collection happens
    before the first test executes -- so a repair in ``pmoves/conftest.py``
    runs before any test module can import a mutated source file. This test
    drives that path for real: a Python process that imports the conftest,
    exactly as pytest does.
    """
    tool = tmp_path / "tool.py"
    tool.write_bytes(b"pristine bytes")
    mutation_backup.write_backup(REPO_ROOT, tool, b"pristine bytes")
    tool.write_bytes(b"MUTATED")
    try:
        # The environment is INHERITED, not minimised: `pmoves/__init__.py`
        # imports `pmoves.services` at package-import time, and a stripped
        # environment changes what that import chain does on this host.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-c", "import pmoves.conftest"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert tool.read_bytes() == b"pristine bytes"
    finally:
        mutation_backup.clear_backup(REPO_ROOT, tool)
