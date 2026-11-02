"""Crash-safe backup for the mutation harnesses.

WHY THIS EXISTS
---------------
A mutation harness proves a fix by MUTATING a tracked source file in the live
tree, running the named test against the mutation, and restoring the file.
The restore lives in a ``finally``, so it runs when the test FAILS -- but a
KILLED process runs no ``finally``, and a kill is exactly what the repo's
pytest RATCHET does when a chunk of test files overruns its wall-clock
budget.

MEASURED on CI, 2026-11-02 (branch ``fix/carry-over-closure``, head
``346fa264a9a``): the merge gate's ``python-tests`` job runs
``pmoves/tools/pytest_ratchet.py``, which gives one chunk of test files a
budget and kills it when the budget is exceeded. The chunk holding the
encoding harness was killed MID-MUTATION, so
``pmoves/tools/windows_encoding_ratchet.py`` was left mutated on disk. The
chunk was then re-run one file at a time, and the sibling test that scans the
LIVE tree imported the MUTATED tool -- so the gate reported

    FAIL|tests.tools.test_windows_encoding_ratchet|test_the_live_tree_has_no_io_or_codecs_open_gap

a defect that did not exist. The sibling's own import happens at COLLECTION
time, which is why it was only ever wrong when a previous session had died
mid-mutation and left the tree dirty for the next one to inherit.

The harness's contract said the tree is restored when it FINISHES. It said
nothing about the tree when the harness is KILLED, and that was the clause
that was missing.

THE CONTRACT THIS MODULE PROVIDES
----------------------------------
The tree is trustworthy BETWEEN runs -- even when a harness was killed. The
harness writes the PRISTINE bytes to a backup BEFORE it mutates and removes
the backup when it has restored the tree. If the process dies in between, the
backup is still on disk, and the next session that collects tests in this
tree restores it BEFORE any test module is imported -- pytest imports every
conftest during collection, and collection happens before the first test
executes. So the pristine tool is what the sibling imports.

THE LOCK IS PER TARGET, NOT PER REPOSITORY
-------------------------------------------
The lock exists for one reason: a restore must not revert a mutation that a
LIVE harness is making right now. A repository-wide lock would make every
pytest session in the checkout wait for whichever harness happens to be
running -- and a mutation harness runs dozens of child pytest sessions, so
that wait would be paid dozens of times. A lock PER TARGET says exactly what
is needed: "this file is being mutated right now, leave it alone", and
nothing about the other files.

WHAT IS NOT CLAIMED
-------------------
A restore performed by a LATER session repairs the tree; it cannot un-run a
test that already failed against a mutated tree. That is why the allowance in
``pmoves/configs/pytest_ratchet/_slow_files.yaml`` is the PRIMARY fix -- it
stops the kill from happening -- and this module is the defence in depth
behind it.

THE BACKUP LIVES OUTSIDE THE REPOSITORY
----------------------------------------
The backup is written under the system temp directory, never inside the
working tree. A backup file inside the tree would be picked up by
``git add -A`` -- and a mutation harness holds the tree mutated by design, so
the tree is only trustworthy BETWEEN runs (see the lane's lesson 34). A
backup in the tree would also show up as an untracked file in every
``git status`` while a harness is running.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import quote, unquote

#: Suffix on a backup file's name. It marks the file as ours, so a stray file
#: in the backup directory is never mistaken for a backup.
_MARKER = ".mutation-backup"

#: Suffix on a lock file's name. Deliberately NOT a suffix of ``_MARKER``:
#: the restore globs for ``*_MARKER``, and a lock named ``<key>.mutation-
#: backup.lock`` would match that glob and be read as a backup.
_LOCK_MARKER = ".mutation-lock"

#: Root of the backup directory. Per-repository sub-directories live under it,
#: so two checkouts on one machine never see each other's backups.
_BACKUP_ROOT = Path(tempfile.gettempdir()) / "pmoves-mutation-backups"

#: How long a restore waits for a target's lock before giving up on it.
#: This is a PROBE, not a wait: a live harness holds the lock for the whole
#: of its mutation window, which is seconds, so a fraction of a second is
#: enough to see the contention. A target whose lock cannot be taken is
#: SKIPPED, never forced.
_RESTORE_LOCK_TIMEOUT_SECONDS = 0.5


def _repo_dir(repo_root: Path) -> Path:
    """The backup directory for one checkout.

    Keyed by the resolved checkout path, so two worktrees of the same repo --
    and the operator's primary checkout -- keep separate backups and cannot
    restore each other's files.
    """
    resolved = str(Path(repo_root).resolve())
    key = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return _BACKUP_ROOT / key


def _key_for(repo_root: Path, target: Path) -> str:
    """A reversible, file-name-safe key for one target.

    ``urllib.parse.quote`` with no safe characters encodes ``/`` as ``%2F``
    and ``:`` as ``%3A``, so the key is reversible with ``unquote`` and needs
    no side-car index. ``R-`` is a path relative to the checkout and ``A-`` is
    an absolute path outside it.
    """
    root = Path(repo_root).resolve()
    resolved = Path(target).resolve()
    try:
        return "R-" + quote(resolved.relative_to(root).as_posix(), safe="")
    except ValueError:
        # A target OUTSIDE the checkout. It still gets a backup, because the
        # contract is about the file being mutated, not about where it lives.
        return "A-" + quote(str(resolved), safe="")


def _target_from_key(repo_root: Path, key: str) -> Path:
    """The inverse of :func:`_key_for`.

    The prefix is read at a FIXED WIDTH -- one letter, one separator, then
    the payload -- rather than by hunting for the first hyphen. The payload
    is percent-encoded, and percent-encoding leaves ``-`` alone, so a path
    like ``pmoves/mk/yt-cookies.mk`` carries hyphens of its own. Hunting for
    a separator would have to know which one comes first; a fixed width does
    not have to know anything.
    """
    if len(key) < 3 or key[1] != "-":
        raise ValueError(f"not a backup key: {key!r}")
    kind, path = key[0], unquote(key[2:])
    return Path(repo_root) / path if kind == "R" else Path(path)


def backup_path(repo_root: Path, target: Path) -> Path:
    """Where the pristine bytes of ``target`` are kept while it is mutated."""
    return _repo_dir(repo_root) / (_key_for(repo_root, target) + _MARKER)


def lock_path(repo_root: Path, target: Path) -> Path:
    """The mutation lock for ONE target.

    A live harness holds this while it mutates that file; a restore takes it
    before it touches the file. The OS drops the lock when the holder dies,
    so a killed harness cannot wedge it forever -- and that is exactly the
    moment the restore is needed.
    """
    return _repo_dir(repo_root) / (_key_for(repo_root, target) + _LOCK_MARKER)


def write_backup(repo_root: Path, target: Path, data: bytes) -> Path:
    """Record ``target``'s pristine bytes BEFORE it is mutated.

    The bytes are the file's exact bytes, not its decoded text: a decoded
    comparison cannot tell LF from CRLF, because ``read_text`` translates
    them away.
    """
    path = backup_path(repo_root, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def clear_backup(repo_root: Path, target: Path) -> None:
    """Drop the backup for ``target`` -- called once the tree is restored."""
    backup_path(repo_root, target).unlink(missing_ok=True)


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 300.0) -> Iterator[None]:
    """A cross-process advisory lock, held for the duration of the block.

    The same two-layer shape the house's mutation harnesses already use: an
    OS-level advisory lock (``msvcrt.locking`` on Windows, ``fcntl.flock`` on
    POSIX) serialises separate PROCESSES, which an in-process lock cannot do.
    The OS drops the lock when the holder dies, so a crash cannot leave it
    held.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    acquired = False
    try:
        deadline = time.monotonic() + timeout
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
                time.sleep(0.05)
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


def restore_outstanding(repo_root: Path) -> list[str]:
    """Restore every target whose backup is still on disk.

    Returns the paths that were actually restored, so the caller can report
    them. A backup whose target already matches is simply removed: the
    restore is idempotent, and a leftover backup is not itself a defect.

    A target whose LOCK is held is SKIPPED and its backup is LEFT ALONE: a
    live harness owns that file right now and will restore it itself. The
    next session tries again.
    """
    directory = _repo_dir(repo_root)
    if not directory.is_dir():
        return []
    restored: list[str] = []
    for backup in sorted(directory.glob(f"*{_MARKER}")):
        key = backup.name[: -len(_MARKER)]
        target = _target_from_key(repo_root, key)
        lock = directory / (key + _LOCK_MARKER)
        try:
            with file_lock(lock, timeout=_RESTORE_LOCK_TIMEOUT_SECONDS):
                restored.extend(_restore_one(backup, target))
        except TimeoutError:
            # A live harness owns this file. Leave its backup where it is.
            continue
    return restored


def _restore_one(backup: Path, target: Path) -> list[str]:
    """Restore one target from its backup. The caller holds its lock.

    The backup is removed ONLY when the tree is actually back to its pristine
    state: either the restore happened, or the target already held the
    pristine bytes. If the target cannot be read or does not exist, the
    backup is LEFT ALONE -- it is the only copy of the pristine source, and
    destroying it while the tree stays mutated turns a recoverable crash into
    an unrecoverable one.
    """
    try:
        pristine = backup.read_bytes()
    except OSError:
        # An unreadable backup is left in place rather than deleted: the
        # tree may still hold a mutation, and the next session must try
        # again. Silently dropping it would lose the only copy.
        return []
    if not target.is_file():
        # The target is gone. The backup may be the only copy of it, so it
        # stays until a session can put it back.
        return []
    if target.read_bytes() == pristine:
        # Already pristine: the restore happened, or never needed to.
        backup.unlink(missing_ok=True)
        return []
    target.write_bytes(pristine)
    backup.unlink(missing_ok=True)
    return [str(target)]
