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

Defect G -- the module LOAD ran WITHOUT the mutation lock
    ``_load_ratchet_module`` read the ratchet file and executed it
    without holding the lock. A load that landed while another case
    held the lock and had the file in its MUTATED state measured a
    DIFFERENT ratchet than the one it thought it was measuring -- the
    subject under test was swapped out from under the measurement. This
    is round-3 finding C one level earlier: there the VERIFICATION was
    unlocked, here it is the SUBJECT.

Defect H -- the pytest run had NO timeout, and it ran while holding the lock
    ``_run_pytest`` called ``subprocess.run`` with no ``timeout=``. It is
    invoked from inside the mutation lock, so a hung pytest -- a stuck
    child, a network-gated test waiting on a socket, a deadlock inside
    the child -- held the lock FOREVER and every other case in this file
    blocked behind it. Same defect class as lesson #19 ("a lock with a
    timeout on one platform and none on another is two different
    locks"): here the LOCK HOLDER is the one that can hang.

Defect I -- the deadline could be switched OFF by a typo
    ``_pytest_timeout_seconds`` guarded the override with
    ``value <= 0``. But ``float("nan")`` compares False against
    EVERYTHING, so ``PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT=nan`` sailed
    straight past the guard and BECAME the deadline -- and a ``nan``
    deadline never fires, so the run was unbounded. ``inf`` is the same
    hole with a slower fuse: the deadline becomes astronomically large,
    so the guarantee is gone. Both are ordinary float literals a typo
    can produce. The override may now only make the deadline SAFER:
    anything that is not a FINITE POSITIVE number falls back to the
    default.

Defect J -- the timeout could still hang on WINDOWS
    CPython's own timed-out ``subprocess.run`` path kills the DIRECT
    child and then, on WINDOWS, calls ``process.communicate()`` with NO
    timeout -- an unbounded read. A killed inner pytest can leave
    GRANDCHILDREN behind (this harness spawns nested pytest subprocesses
    BY DESIGN), and a surviving grandchild holds the stdout pipe open:
    the unbounded post-kill read blocks FOREVER, ``PytestRunTimeout``
    never raises, and the mutation lock is never released. The child is
    now started in its OWN process group, the whole TREE is killed on
    timeout, and the post-kill drain is BOUNDED.

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
import math
import os
import signal
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

# The FIXED module load: the whole read+exec happens UNDER the lock.
FIXED_LOCKED_MODULE_LOAD = '''    path = TARGET if target is None else Path(target)
    with _mutation_lock(lock_path):
        return _read_and_exec_ratchet_module(path)
'''

# The ORIGINAL module load: no lock at all around the read+exec.
UNLOCKED_MODULE_LOAD = '''    path = TARGET if target is None else Path(target)
    return _read_and_exec_ratchet_module(path)
'''

# The FIXED pytest run: a REAL deadline, the whole TREE killed on
# timeout, and a BOUNDED post-kill drain.
FIXED_PYTEST_RUN = '''    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            _pytest_timeout_message(timeout, args, select)
        ) from exc
'''

# The ORIGINAL pytest run: NO deadline, and no handling of a hang.
ORIGINAL_PYTEST_RUN = '''    try:
        stdout, stderr = process.communicate()
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            _pytest_timeout_message(timeout, args, select)
        ) from exc
'''

# The FIXED post-kill block: the child is killed as a TREE (not just the
# direct child), and the drain that follows is BOUNDED.
FIXED_POST_KILL = '''    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            _pytest_timeout_message(timeout, args, select)
        ) from exc
'''

# The ORIGINAL post-kill block: only the DIRECT child is killed. The
# grandchildren this harness spawns BY DESIGN survive, and one of them
# holding the stdout pipe open is enough to wedge the drain.
ORIGINAL_POST_KILL = '''    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            _pytest_timeout_message(timeout, args, select)
        ) from exc
'''

# The FIXED post-kill drain: the read of the child's pipes carries its
# OWN deadline, so a survivor that still holds the pipe open cannot
# wedge the read forever.
FIXED_DRAIN = '''    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stdout, stderr = "", ""
        _close_process_pipes(process)
    finally:
        try:
            process.wait(timeout=_TREE_KILL_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, OSError, AttributeError):
            pass
    return stdout or "", stderr or ""
'''

# The ORIGINAL post-kill drain: an UNBOUNDED read. This is the shape of
# CPython's own timed-out ``subprocess.run`` path on Windows, and it is
# what held the mutation lock forever.
ORIGINAL_DRAIN = '''    try:
        stdout, stderr = process.communicate()
    except subprocess.TimeoutExpired:
        stdout, stderr = "", ""
        _close_process_pipes(process)
    finally:
        try:
            process.wait(timeout=_TREE_KILL_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, OSError, AttributeError):
            pass
    return stdout or "", stderr or ""
'''

# The FIXED deadline validation: a deadline must be FINITE and POSITIVE.
FIXED_DEADLINE_VALIDATION = '''    if not math.isfinite(value) or value <= 0:
        return _DEFAULT_PYTEST_TIMEOUT_SECONDS
    return value
'''

# The ORIGINAL deadline validation: ``value <= 0`` alone. ``float("nan")``
# compares False against EVERYTHING, so a ``nan`` override became the
# deadline -- and a ``nan`` deadline never fires.
ORIGINAL_DEADLINE_VALIDATION = '''    if value <= 0:
        return _DEFAULT_PYTEST_TIMEOUT_SECONDS
    return value
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

# The DEADLINE for ONE pytest run inside the mutation lock.
#
# WHY A SEPARATE, LARGER DEADLINE THAN THE LOCK ACQUISITION TIMEOUT
# -------------------------------------------------------------------
# ``_LOCK_TIMEOUT_SECONDS`` bounds how long a case WAITS FOR the lock.
# This bounds how long a case may HOLD the lock. They are different
# questions, and the second one is the one that can wedge the suite:
# a pytest run that hangs holds the lock FOREVER unless the run itself
# has a deadline.
#
# The measured slowest legitimate single pytest run in this harness is
# ~1.6s (a selected test in the ratchet file, including interpreter and
# pytest startup). 300s is ~180x that, so it cannot fire on a healthy
# run, while still bounding a wedged one.
_DEFAULT_PYTEST_TIMEOUT_SECONDS = 300.0
# The override exists so the TIMEOUT PATH ITSELF can be exercised with a
# short deadline instead of waiting out the real one. Same pattern as the
# other gates in this lane (``PMOVES_MAVIS_MATRIX_CHECK``).
_PYTEST_TIMEOUT_ENV = "PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT"

# The DEADLINE for the POST-KILL drain of a timed-out child.
#
# After the child -- and the whole TREE it spawned -- is killed, the
# pipes are drained with a SECOND, SHORT deadline. A survivor that still
# holds the pipe open must not be able to wedge the read forever: the
# mutation lock is held until this returns, so an unbounded drain is the
# same defect as no deadline at all.
_DRAIN_TIMEOUT_SECONDS = 10.0

# The DEADLINE for the tree kill itself, and for the final reap of the
# child. Both are bounded so that a kill that cannot complete cannot
# become the new hang.
_TREE_KILL_TIMEOUT_SECONDS = 30.0


class MutationLockTimeout(TimeoutError):
    """The mutation lock could not be taken within the deadline.

    A subclass of ``TimeoutError`` (and therefore of ``OSError``) so the
    failure reads as a timeout, and so the Windows and POSIX branches
    behave identically.
    """


class PytestRunTimeout(TimeoutError):
    """A pytest run inside the mutation lock exceeded its deadline.

    A subclass of ``TimeoutError`` so it reads as a timeout and cannot be
    mistaken for an ordinary assertion failure: the run was killed, not
    judged.
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


def _validated_deadline(value: float) -> float:
    """Return ``value`` if it is a usable deadline, else the DEFAULT.

    A deadline must be FINITE and POSITIVE.

    WHY NON-FINITE MATTERS
    ---------------------
    ``float("nan")`` compares False against EVERYTHING, so a
    ``value <= 0`` guard lets it through -- and a ``nan`` deadline never
    fires, so the run it was supposed to bound is unbounded. ``inf`` is
    the same hole with a slower fuse: the deadline becomes
    astronomically large, so the guarantee is gone. Both are ordinary
    float literals a typo can produce, so both are REJECTED here.
    """
    if not math.isfinite(value) or value <= 0:
        return _DEFAULT_PYTEST_TIMEOUT_SECONDS
    return value


def _pytest_timeout_seconds() -> float:
    """The deadline for ONE pytest run, with the env override applied.

    The override (``PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT``) exists so the
    TIMEOUT PATH ITSELF can be tested with a short deadline instead of
    waiting out the real one.

    An unparseable, empty, non-positive or NON-FINITE override falls back
    to the DEFAULT rather than silently dropping the deadline: a
    deadline that can be switched off by a typo is the defect this
    fixes, not a fix.

    ``float(...)`` on a ``str`` raises ``ValueError`` and nothing else,
    so ``ValueError`` is the only reachable arm here.
    """
    raw = os.environ.get(_PYTEST_TIMEOUT_ENV)
    if raw is None:
        return _DEFAULT_PYTEST_TIMEOUT_SECONDS
    try:
        value = float(raw.strip())
    except ValueError:
        return _DEFAULT_PYTEST_TIMEOUT_SECONDS
    return _validated_deadline(value)


def _pytest_timeout_message(
    timeout: float,
    args: list[str],
    select: str | None,
) -> str:
    """The message a timed-out pytest run fails with.

    It names the DEADLINE, the TEST that was being run, and the fact that
    the mutation lock is being released -- a reader who hits this needs to
    know that the lock is NOT stuck, and that the mutated file is being
    restored.
    """
    return (
        f"the pytest run TIMED OUT after {timeout:g}s (deadline "
        f"{_PYTEST_TIMEOUT_ENV}={timeout:g}s): {args!r} select={select!r}. "
        f"The mutation lock is about to be RELEASED and the mutated file is "
        f"being restored. The child and the whole process TREE it spawned "
        f"were killed, and the pipes were drained with a BOUND "
        f"({_DRAIN_TIMEOUT_SECONDS:g}s), so a surviving grandchild cannot "
        f"wedge this read. A hung child process, a network-gated test "
        f"waiting on a socket, or a deadlock inside pytest holds the "
        f"mutation lock FOREVER without this deadline -- check for a stuck "
        f"child process."
    )


def _spawn_pytest_process(args: list[str]) -> subprocess.Popen[str]:
    """Start the pytest child in its OWN process group.

    The child is started in a NEW SESSION on POSIX and a NEW PROCESS
    GROUP on Windows. That is what makes the TREE killable: without it
    the child shares this process' group, so a timeout could only ever
    kill the DIRECT child -- leaving the grandchildren (this harness
    spawns nested pytest subprocesses BY DESIGN) alive and holding the
    stdout pipe open.
    """
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )


def _kill_direct_child(process) -> None:
    """Kill the DIRECT child, if it is still alive."""
    try:
        process.kill()
    except (OSError, AttributeError):
        pass


def _kill_process_tree(process) -> None:
    """Kill the child AND every descendant it left behind.

    KILLING ONLY THE DIRECT CHILD IS NOT ENOUGH. This harness spawns
    nested pytest subprocesses by design, so a killed child can leave
    GRANDCHILDREN behind, and a surviving grandchild keeps the stdout
    pipe open. The post-kill read then never sees EOF -- and on Windows
    CPython's own timed-out ``subprocess.run`` path performs exactly
    that UNBOUNDED read, so the mutation lock would be held FOREVER.

    POSIX kills the whole process GROUP (the child was started with
    ``start_new_session=True``, so it leads its own group). Windows
    kills the whole TREE with ``taskkill /T /F``.
    """
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=_TREE_KILL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        _kill_direct_child(process)
        return
    try:
        os.killpg(
            os.getpgid(process.pid),
            getattr(signal, "SIGKILL", signal.SIGTERM),
        )
    except (AttributeError, OSError, ValueError):
        _kill_direct_child(process)


def _close_process_pipes(process) -> None:
    """Close the child's pipes without waiting on whoever still holds them."""
    for stream in (
        getattr(process, "stdout", None),
        getattr(process, "stderr", None),
    ):
        if stream is None:
            continue
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _drain_process_output(process, timeout: float) -> tuple[str, str]:
    """Drain the child's pipes with a BOUND.

    The direct child is dead, but a SURVIVOR may still hold the pipe
    open. An unbounded read would then never return -- and the mutation
    lock is held until this returns, so an unbounded drain is the same
    defect as no deadline at all. The drain gives up instead of waiting.
    """
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stdout, stderr = "", ""
        _close_process_pipes(process)
    finally:
        try:
            process.wait(timeout=_TREE_KILL_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, OSError, AttributeError):
            pass
    return stdout or "", stderr or ""


def _run_pytest(
    module: Path,
    *,
    select: str | None = None,
    timeout_seconds: float | None = None,
    spawn=None,
) -> subprocess.CompletedProcess[str]:
    """Run a pytest module and capture the whole report.

    ``-rA`` makes pytest print the short test summary for EVERY test. That
    summary is the harness's evidence: it is what turns "the run was
    unhappy" into "THIS test failed".

    ``select`` is a pytest ``-k`` expression. The mutation cases use it
    to run ONLY the test the mutation is supposed to kill: the other
    tests are not evidence for this mutation, and running the whole
    module would pay for a live ``mavis --version`` on every mutation.

    ``spawn`` replaces the child-starting step. It exists so the timeout
    path can be exercised against a SIMULATED child (one whose pipe is
    held open by a survivor) without wedging the suite that runs the
    test.

    THE DEADLINE IS MANDATORY, NOT DECORATION
    -----------------------------------------
    This runs INSIDE the mutation lock. A pytest run that hangs -- a stuck
    child, a network-gated test waiting on a socket, a deadlock inside the
    child -- would hold the lock FOREVER, and every other case in this
    file would block behind it. That is the same defect class as the POSIX
    branch that used a bare blocking ``flock`` (lesson #19: a lock with a
    timeout on one platform and none on another is two different locks):
    here the LOCK HOLDER is the one that can hang.

    The deadline is overridable through ``PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT``
    so the timeout path can be exercised without waiting out the real
    deadline.

    AND THE DEADLINE MUST SURVIVE THE KILL
    --------------------------------------
    A deadline on the DIRECT child is not enough. CPython's own
    timed-out ``subprocess.run`` path kills the direct child and then,
    on WINDOWS, calls ``process.communicate()`` with NO timeout -- an
    UNBOUNDED read. A killed inner pytest can leave GRANDCHILDREN behind
    (this harness spawns nested pytest subprocesses by design), and a
    surviving grandchild holds the stdout pipe open: the read never
    returns, ``PytestRunTimeout`` never raises, and the mutation lock is
    held FOREVER. The child is therefore started in its OWN process
    group, the whole TREE is killed on timeout, and the post-kill drain
    is BOUNDED.
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
    timeout = (
        _pytest_timeout_seconds()
        if timeout_seconds is None
        else _validated_deadline(float(timeout_seconds))
    )
    process = (
        _spawn_pytest_process(args) if spawn is None else spawn(args)
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            _pytest_timeout_message(timeout, args, select)
        ) from exc
    return subprocess.CompletedProcess(
        args, process.returncode, stdout or "", stderr or ""
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


def _read_and_exec_ratchet_module(path: Path):
    """Read the module at ``path`` and execute it as a fresh module.

    This is the INNER half of the load: the READ of the bytes and the
    EXEC of what was read. It is called ONLY from
    ``_load_ratchet_module``, which holds the mutation lock across the
    whole call -- the read and the exec must not be separable, or a
    mutation can land between them.
    """
    spec = importlib.util.spec_from_file_location(
        "pmoves_mavis_ratchet_under_test", path
    )
    assert spec is not None and spec.loader is not None, (
        f"could not load the ratchet module from {path}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_ratchet_module(
    lock_path: Path | None = None,
    target: Path | None = None,
):
    """Import the ratchet module FROM DISK, freshly, UNDER the mutation lock.

    The harness INVOKES the ratchet's own assertion functions -- it
    never restates the check inline. Loading from disk (rather than
    importing once at module load) is what lets the harness call those
    functions against a MUTATED source.

    THE WHOLE READ+EXEC IS UNDER THE LOCK
    --------------------------------------
    The load is a READ of the target followed by an EXEC of what was
    read. Without the lock, a load that lands while another case holds
    the lock and has the file in its MUTATED state measures a DIFFERENT
    ratchet than the one it thinks it is measuring: the subject under
    test is swapped out from under the measurement. This is round-3
    finding C (the unlocked clean-check read) one level EARLIER -- there
    the verification was unlocked, here it is the subject.

    The lock is taken for the whole read+exec and RELEASED afterwards.
    """
    path = TARGET if target is None else Path(target)
    with _mutation_lock(lock_path):
        return _read_and_exec_ratchet_module(path)


def _mutation_case(
    path: Path,
    old: str,
    new: str,
    *,
    select: str,
    expected_failing_test: str,
    lock_path: Path | None = None,
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

    ``lock_path`` selects the advisory lock FILE. The default is the
    shared lock, so the cases in this file serialize against each other
    and against any other pytest process on this host. A case that needs
    its own lock file (because it runs inside a child pytest that must
    not contend for the shared one) passes one explicitly.

    Returns (mutation_was_killed, combined_output).
    """
    # The mutation lock is held through ALL THREE PHASES. The ``with``
    # statement is what guarantees it is RELEASED on every exit path --
    # including the one where a pytest run times out and raises. The
    # mutated file is restored by the ``finally`` INSIDE this block, so
    # the restore happens BEFORE the lock is released: no other case can
    # ever observe the file in its mutated state.
    with _mutation_lock(lock_path):
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


def test_module_load_is_serialized_against_concurrent_mutation(
    tmp_path: Path,
) -> None:
    """The module LOAD must not observe a file that is mid-mutation.

    ``_load_ratchet_module`` reads the ratchet file and executes it.
    Without the mutation lock, a load that lands while another case
    holds the lock and has the file in its MUTATED state measures a
    DIFFERENT ratchet than the one it thinks it is measuring -- the
    subject under test is swapped out from under the measurement.

    The proof is a CONCURRENT mutation: a second thread takes the
    mutation lock and puts a marker into the file, and the loader -- run
    from a third thread -- must NOT be able to finish while that
    mutation is in effect. It may only load once the mutation has been
    undone.
    """
    lock_path = tmp_path / "module-load.lock"
    target = tmp_path / "ratchet_under_test.py"
    pristine = 'MARKER = "pristine"\n'
    mutated = 'MARKER = "mutated"\n'
    target.write_text(pristine, encoding="utf-8")

    mutation_written = threading.Event()
    may_restore = threading.Event()
    load_finished = threading.Event()
    outcome: dict[str, object] = {}

    def mutator() -> None:
        with _mutation_lock(lock_path):
            target.write_text(mutated, encoding="utf-8")
            mutation_written.set()
            may_restore.wait(60)
            target.write_text(pristine, encoding="utf-8")

    def loader() -> None:
        if not mutation_written.wait(60):
            return
        module = _load_ratchet_module(lock_path, target)
        outcome["marker"] = getattr(module, "MARKER", None)
        load_finished.set()

    mutator_thread = threading.Thread(target=mutator, daemon=True)
    loader_thread = threading.Thread(target=loader, daemon=True)
    mutator_thread.start()
    loader_thread.start()
    try:
        assert mutation_written.wait(60), (
            "the mutator never put the file into its mutated state"
        )
        assert not load_finished.wait(2.0), (
            "the module load COMPLETED while another case held the mutation "
            "lock -- the loader measured a ratchet that was mid-mutation "
            "instead of the one it thinks it measured"
        )
    finally:
        may_restore.set()
        mutator_thread.join(timeout=60)
        loader_thread.join(timeout=60)

    assert load_finished.is_set(), (
        "the module load never completed after the mutation was restored"
    )
    assert outcome.get("marker") == "pristine", (
        "the loader observed the MUTATED bytes "
        f"({outcome.get('marker')!r}) -- the load is not serialized against "
        f"the mutation lock"
    )


def test_pytest_run_timeout_fires_and_releases_the_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pytest run that HANGS must time out, release the lock, restore.

    ``_run_pytest`` runs INSIDE the mutation lock. Without a deadline, a
    hung pytest -- a stuck child, a network-gated test, a deadlock --
    holds the lock FOREVER and every other case in this file blocks
    behind it. The lock HOLDER was the one that could hang.

    The deadline is exercised here with a SHORT override
    (``PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT``) so the test never waits out
    the real deadline, and against a module that really does hang, so
    the deadline is not a formality.

    After the timeout the lock must be acquirable again, and the
    mutated file must be back to its original bytes.
    """
    slow_module = tmp_path / "test_slow_ratchet.py"
    pristine = (
        "SLEEP_SECONDS = 0.0\n"
        "\n"
        "\n"
        "def test_slow() -> None:\n"
        "    import time\n"
        "\n"
        "    time.sleep(SLEEP_SECONDS)\n"
    )
    slow_module.write_text(pristine, encoding="utf-8")
    original_bytes = slow_module.read_bytes()

    # A SHORT deadline: long enough for a healthy pytest startup, far
    # shorter than the hang it has to catch.
    monkeypatch.setenv(_PYTEST_TIMEOUT_ENV, "8")
    lock_path = tmp_path / "pytest-timeout.lock"

    with pytest.raises(PytestRunTimeout) as excinfo:
        _mutation_case(
            slow_module,
            "SLEEP_SECONDS = 0.0",
            "SLEEP_SECONDS = 20.0",
            select="test_slow",
            expected_failing_test="test_slow",
            lock_path=lock_path,
        )

    message = str(excinfo.value)
    assert "8s" in message, (
        f"the timeout message does not name the timeout: {message!r}"
    )
    assert "test_slow" in message, (
        f"the timeout message does not name the test that was running: {message!r}"
    )
    assert "lock" in message.lower(), (
        f"the timeout message does not say the lock is being released: {message!r}"
    )

    # The lock must be acquirable again -- the timeout path may not leave
    # it held. The check runs in a THREAD: the in-process half of the
    # lock is a non-reentrant ``threading.Lock``, so a leak would
    # deadlock the main thread instead of failing.
    acquired = threading.Event()
    failure: dict[str, object] = {}

    def acquire() -> None:
        try:
            with _MUTATION_LOCK:
                with _file_lock(lock_path, timeout_seconds=10):
                    acquired.set()
        except BaseException as exc:  # pragma: no cover - diagnostic path
            failure["exc"] = exc

    thread = threading.Thread(target=acquire, daemon=True)
    thread.start()
    thread.join(timeout=30)
    assert acquired.is_set(), (
        "the mutation lock was NOT released after the pytest timeout "
        f"(failure={failure.get('exc')!r}) -- every other case in this "
        f"file would block behind it forever"
    )

    # The mutated file must NOT be left in place.
    assert slow_module.read_bytes() == original_bytes, (
        "the mutated file was left in place after the pytest timeout"
    )


def test_nonfinite_timeout_override_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``nan`` / ``inf`` override MUST fall back to the DEFAULT.

    ``float("nan")`` compares False against EVERYTHING, so the old
    ``value <= 0`` guard let a ``nan`` override through and it BECAME
    the deadline -- and a ``nan`` deadline never fires, so the run it
    was supposed to bound was unbounded and the mutation lock could be
    held forever. ``inf`` is the same hole with a slower fuse: the
    deadline becomes astronomically large, so the guarantee is gone.

    The override exists so the TIMEOUT PATH ITSELF can be exercised with
    a SHORT deadline. It must never be able to make the deadline
    WEAKER, so anything that is not a finite positive number falls back
    to the default.
    """
    monkeypatch.setenv(_PYTEST_TIMEOUT_ENV, "7.5")
    assert _pytest_timeout_seconds() == 7.5, (
        "a VALID override must still be honoured -- the fallback must not "
        "swallow the short deadline the timeout tests rely on"
    )
    for raw in ("nan", "NaN", "inf", "Infinity", "-inf", "-Infinity"):
        monkeypatch.setenv(_PYTEST_TIMEOUT_ENV, raw)
        effective = _pytest_timeout_seconds()
        assert math.isfinite(effective), (
            f"the timeout override {raw!r} produced a NON-FINITE deadline "
            f"({effective!r}) -- a nan/inf deadline never fires, so the "
            f"mutation lock can be held forever"
        )
        assert effective > 0, (
            f"the timeout override {raw!r} produced a non-positive deadline "
            f"({effective!r})"
        )
        assert effective == _DEFAULT_PYTEST_TIMEOUT_SECONDS, (
            f"the timeout override {raw!r} did NOT fall back to the default "
            f"({_DEFAULT_PYTEST_TIMEOUT_SECONDS!r}); it produced {effective!r}"
        )


class _FakeWedgedChild:
    """A child whose stdout pipe is still held open by a SURVIVOR.

    It simulates the Windows wedge exactly: the direct child is killed,
    but a grandchild still holds the stdout pipe open, so a read of that
    pipe never sees EOF.

    The fake NEVER blocks -- a wedge simulated in a test must not become
    a wedged suite:

    * a BOUNDED ``communicate`` (one that carries a timeout) raises
      ``TimeoutExpired``, the way a pipe held open by a survivor does;
    * an UNBOUNDED ``communicate`` raises ``AssertionError``, because
      that is the defect this harness pins: on a real host it would
      block forever, and here it fails at the moment it happens.
    """

    def __init__(self, args: list[str]) -> None:
        self.args = list(args)
        # A pid that cannot belong to a live process: the tree kill is
        # stubbed out in the test, and a stray real kill must be
        # impossible.
        self.pid = -1
        self.returncode: int | None = None
        self.stdout = None
        self.stderr = None
        self.bounded_calls = 0
        self.unbounded_calls = 0
        self.killed = False

    def communicate(self, input=None, timeout=None):  # noqa: A002
        if timeout is None:
            self.unbounded_calls += 1
            raise AssertionError(
                "the post-kill drain was UNBOUNDED -- a surviving pipe "
                "holder can wedge the read forever, and the mutation lock "
                "is held forever with it"
            )
        self.bounded_calls += 1
        raise subprocess.TimeoutExpired(self.args, timeout)

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None) -> int:
        return -9


def test_post_kill_drain_is_bounded_when_a_pipe_holder_survives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A surviving pipe holder MUST NOT be able to wedge the post-kill read.

    CPython's timed-out ``subprocess.run`` path kills the DIRECT child
    and then, on WINDOWS, calls ``process.communicate()`` with NO
    timeout. This harness spawns nested pytest subprocesses BY DESIGN, so
    a killed child can leave GRANDCHILDREN behind, and a surviving
    grandchild holds the stdout pipe open. The unbounded post-kill read
    then blocks FOREVER: ``PytestRunTimeout`` never raises, the mutation
    lock is never released, and every other case in this file blocks
    behind it.

    The fix kills the TREE and drains the pipes with a BOUND. The child
    here is a FAKE that simulates the wedged pipe (a bounded read times
    out, an unbounded read fails loudly instead of hanging), so this test
    can never wedge the suite that runs it.
    """
    fake = _FakeWedgedChild(["pytest", "simulated"])
    tree_kills: list[object] = []
    monkeypatch.setattr(
        sys.modules[__name__],
        "_kill_process_tree",
        lambda process: tree_kills.append(process),
    )
    # A SHORT deadline: the simulated child ignores it, but the message
    # contract must still name the deadline that was in force.
    monkeypatch.setenv(_PYTEST_TIMEOUT_ENV, "5")
    lock_path = tmp_path / "drain.lock"

    started = time.monotonic()
    with pytest.raises(PytestRunTimeout) as excinfo:
        with _mutation_lock(lock_path):
            _run_pytest(
                TARGET,
                select="test_never_runs",
                spawn=lambda args: fake,
            )
    elapsed = time.monotonic() - started

    assert fake.unbounded_calls == 0, (
        "the post-kill drain was called WITHOUT a timeout -- a surviving "
        "pipe holder can wedge the read forever, and the mutation lock is "
        "held forever with it"
    )
    assert fake.bounded_calls >= 2, (
        "both the timed-out run and the post-kill drain must be BOUNDED "
        f"(saw {fake.bounded_calls} bounded reads)"
    )
    assert tree_kills, (
        "the timed-out child was not killed as a TREE -- a killed direct "
        "child can leave grandchildren behind that still hold the pipe open"
    )
    assert elapsed < 60, (
        f"the bounded post-kill drain took {elapsed:.1f}s -- it is not "
        f"bounded"
    )

    message = str(excinfo.value)
    assert "5s" in message, (
        f"the timeout message does not name the timeout: {message!r}"
    )
    assert "lock" in message.lower(), (
        f"the timeout message does not say the lock is being released: {message!r}"
    )

    # The lock must be acquirable again -- the timeout path may not leave
    # it held. The check runs in a THREAD: the in-process half of the
    # lock is a non-reentrant ``threading.Lock``, so a leak would
    # deadlock the main thread instead of failing.
    acquired = threading.Event()
    failure: dict[str, object] = {}

    def acquire() -> None:
        try:
            with _MUTATION_LOCK:
                with _file_lock(lock_path, timeout_seconds=10):
                    acquired.set()
        except BaseException as exc:  # pragma: no cover - diagnostic path
            failure["exc"] = exc

    thread = threading.Thread(target=acquire, daemon=True)
    thread.start()
    thread.join(timeout=30)
    assert acquired.is_set(), (
        "the mutation lock was NOT released after the bounded post-kill "
        f"drain (failure={failure.get('exc')!r}) -- every other case in "
        f"this file would block behind it forever"
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


def test_mutation_unlocked_module_load_is_killed() -> None:
    """Loading the ratchet module WITHOUT the lock MUST fail the harness.

    The mutation rewrites this harness' own module load back to the
    unlocked form; the test that must fail is
    ``test_module_load_is_serialized_against_concurrent_mutation``,
    because an unlocked load measures a ratchet that is mid-mutation
    instead of the one it thinks it measured.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_LOCKED_MODULE_LOAD,
        UNLOCKED_MODULE_LOAD,
        select="test_module_load_is_serialized_against_concurrent_mutation",
        expected_failing_test="test_module_load_is_serialized_against_concurrent_mutation",
    )
    assert killed, (
        "the module load can run without the mutation lock again -- the "
        f"harness may measure a ratchet that is mid-mutation.\n{output}"
    )


def test_mutation_pytest_run_without_timeout_is_killed() -> None:
    """A pytest run with NO deadline MUST fail the harness.

    The mutation rewrites this harness' own pytest call back to the
    deadline-less form; the test that must fail is
    ``test_pytest_run_timeout_fires_and_releases_the_lock``, because a
    pytest run without a deadline can hold the mutation lock FOREVER --
    the lock HOLDER is the one that can hang.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_PYTEST_RUN,
        ORIGINAL_PYTEST_RUN,
        select="test_pytest_run_timeout_fires_and_releases_the_lock",
        expected_failing_test="test_pytest_run_timeout_fires_and_releases_the_lock",
    )
    assert killed, (
        "the pytest run can hang without a deadline again -- it holds the "
        f"mutation lock forever and blocks every other case.\n{output}"
    )


def test_mutation_nonfinite_timeout_override_is_killed() -> None:
    """A non-finite timeout override MUST fail the harness.

    The mutation rewrites this harness' own deadline validation back to
    the ``value <= 0``-only form, so ``float("nan")`` -- which compares
    False against EVERYTHING -- becomes the deadline again; the test that
    must fail is
    ``test_nonfinite_timeout_override_falls_back_to_default``.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_DEADLINE_VALIDATION,
        ORIGINAL_DEADLINE_VALIDATION,
        select="test_nonfinite_timeout_override_falls_back_to_default",
        expected_failing_test="test_nonfinite_timeout_override_falls_back_to_default",
    )
    assert killed, (
        "the timeout override can be switched OFF by a typo again -- a nan "
        "or inf override becomes the deadline, and a deadline that never "
        f"fires is no deadline at all.\n{output}"
    )


def test_mutation_unbounded_post_kill_drain_is_killed() -> None:
    """An UNBOUNDED post-kill drain MUST fail the harness.

    The mutation rewrites this harness' own post-kill drain back to the
    unbounded read -- the shape of CPython's timed-out ``subprocess.run``
    path on Windows; the test that must fail is
    ``test_post_kill_drain_is_bounded_when_a_pipe_holder_survives``.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_DRAIN,
        ORIGINAL_DRAIN,
        select="test_post_kill_drain_is_bounded_when_a_pipe_holder_survives",
        expected_failing_test="test_post_kill_drain_is_bounded_when_a_pipe_holder_survives",
    )
    assert killed, (
        "the post-kill drain can block forever again -- a surviving "
        "grandchild holds the pipe open, the read never returns, and the "
        f"mutation lock is never released.\n{output}"
    )


def test_mutation_direct_child_kill_is_killed() -> None:
    """Killing only the DIRECT child MUST fail the harness.

    The mutation rewrites this harness' own post-kill block back to a
    direct-child kill, so the grandchildren this harness spawns BY
    DESIGN survive; the test that must fail is
    ``test_post_kill_drain_is_bounded_when_a_pipe_holder_survives``.
    """
    killed, output = _mutation_case(
        HARNESS,
        FIXED_POST_KILL,
        ORIGINAL_POST_KILL,
        select="test_post_kill_drain_is_bounded_when_a_pipe_holder_survives",
        expected_failing_test="test_post_kill_drain_is_bounded_when_a_pipe_holder_survives",
    )
    assert killed, (
        "a timed-out child can be killed without its TREE again -- the "
        "grandchildren survive, one of them holds the stdout pipe open, "
        f"and the mutation lock is held forever.\n{output}"
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
