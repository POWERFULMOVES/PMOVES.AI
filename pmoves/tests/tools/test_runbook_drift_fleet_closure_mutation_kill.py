"""Mutation-kill harness: every fix in the runbook-drift fleet-closure lane
must BITE when the defect is put back.

This is the PROVENANCE HARNESS for the five findings closed by the lane
behind ``scripts/runbook_drift.py`` (the zero-LLM drift auditor added by
PR #3375):

  F1  the drift auditor's file probe grepped CONTENT and called it a NAME
  F2  node-registry had no Dockerfile / compose entry / Make target, and its
      code defaults claimed port 8082 -- which media-audio already owns
  F3  six ``sync: true`` registry forks appeared in no workflow list, and two
      pipecat forks were in no registry at all
  F4  a module-scope POSIX-only ``os.*`` call broke collection on Windows
      (71 tests hidden), and ``env_local_key`` raised a raw traceback there
  F5  nothing rebuilt the fleet's images -- ``build-images.yml`` was
      ``workflow_dispatch:`` only, so flute-gateway went 65 days stale

It is a test (not a scratch script) because a harness that nobody re-runs
decays. Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_runbook_drift_fleet_closure_mutation_kill.py -v

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens inside the mutation lock, so a failed
run cannot leave the tree mutated.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
Each mutation names the test that MUST fail for the mutation to count as
killed. The kill signal is NOT "pytest exited non-zero and the word 'failed'
appeared somewhere in the output" -- a signal that a collection error, a
timeout or an unrelated environment failure also satisfies. The harness
reads pytest's own short test summary and requires the NAMED test to be in
it. A harness may only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
A test that exercises a pure helper is not a test of the call site. Each
mutation below rewrites the CALL the production path makes, not a
neighbouring condition:

  F1  the path branch's matcher goes back to the basename matcher
      (``_paths_ending`` -> ``_paths_named``) -- not a change to the
      branch's entry condition, which was tried first and SURVIVED (it
      never touched the path branch, so it never restored the defect).
  F2  the port the service is wired to goes back to the collider.
  F3  a fork goes back out of the workflow list the registry claims.
  F4  the descriptor-based chmod goes back to the unconditional
      ``os.fchmod`` the tool used before it learned to adapt.
  F5  the scheduled rebuild trigger goes back out of the workflow.

The harness restores the file in a ``finally`` block, so a failed run
leaves the working tree clean, and the restore is asserted.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[3]

# The mutated source files, one per finding.
DRIFT_AUDITOR = REPO_ROOT / "scripts" / "runbook_drift.py"
NODE_REGISTRY_API = REPO_ROOT / "pmoves" / "services" / "node_registry" / "api.py"
COMPOSE_FILE = REPO_ROOT / "pmoves" / "docker-compose.yml"
FORK_SYNC_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fork-sync.yml"
ENV_LOCAL_KEY = REPO_ROOT / "pmoves" / "tools" / "env_local_key.py"
BUILD_IMAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-images.yml"

# The test modules that carry each finding's assertions.
DRIFT_PROBE_TESTS = REPO_ROOT / "pmoves" / "tests" / "test_runbook_drift_probe.py"
NODE_REGISTRY_TESTS = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_node_registry_deployment.py"
FORK_REGISTRY_TESTS = REPO_ROOT / "pmoves" / "tools" / "tests" / "test_fork_registry_ratchet.py"
WINDOWS_POSIX_TESTS = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_windows_posix_ratchet.py"
IMAGE_STALENESS_TESTS = REPO_ROOT / "pmoves" / "tools" / "tests" / "test_image_staleness_ratchet.py"

# --------------------------------------------------------------------------
# F1 -- the drift auditor's path matcher
# --------------------------------------------------------------------------

# FIXED: a PATH claim is matched on the PATH, on a directory boundary.
F1_FIXED_PATH_MATCHER = "        hits = _paths_ending(paths, claim)"

# DEFECTIVE: the same claim matched on its BASENAME, so any of the 210
# unrelated `README.md` files in the tree satisfied it -- the same category
# error as the content grep, one layer down.
F1_DEFECTIVE_PATH_MATCHER = "        hits = _paths_named(paths, claim)"

# The test that MUST fail. It is the one that states the rule the defective
# matcher breaks: a path claim must not be satisfied by an unrelated file
# that happens to share its basename.
F1_KILLED_TEST = "test_a_path_claim_is_not_satisfied_by_an_unrelated_file_of_the_same_name"

# --------------------------------------------------------------------------
# F2 -- node-registry's port
# --------------------------------------------------------------------------

# FIXED: the service binds the port the catalog and the docs already named.
F2_FIXED_PORT = "        port: int = 8115,"

# DEFECTIVE: 8082, which `pmoves/docker-compose.yml` binds to media-audio.
F2_DEFECTIVE_PORT = "        port: int = 8082,"

# FIXED: the compose entry publishes the same port.
F2_FIXED_COMPOSE_BINDING = '    - "${NODE_REGISTRY_BIND:-0.0.0.0}:8115:8115"'

# DEFECTIVE: the compose entry claims media-audio's host port, so the two
# services cannot bind alongside each other.
F2_DEFECTIVE_COMPOSE_BINDING = '    - "${NODE_REGISTRY_BIND:-0.0.0.0}:8082:8082"'

# The test that MUST fail for EITHER revert. It asserts the source default
# AND the compose binding, so one named test covers both halves -- which is
# why the lane runs TWO mutations against it.
F2_KILLED_TEST = "test_node_registry_code_default_and_compose_binding_match_catalog_port"

# --------------------------------------------------------------------------
# F3 -- the fork registry's workflow coverage
# --------------------------------------------------------------------------

# FIXED: the fork the registry claims is in the workflow's FORKS list.
F3_FIXED_FORKS_ENTRY = "          pipecat-ai/pipecat-client-web-transports|Pmoves-pipecat-client-web-transports|\n"

# DEFECTIVE: the registry still claims `sync: true`, but the workflow no
# longer carries it -- so nothing rebuilds it, and nothing notices.
F3_DEFECTIVE_FORKS_ENTRY = ""

F3_KILLED_TEST = "test_every_sync_true_registry_fork_is_in_the_workflow_forks_block"

# --------------------------------------------------------------------------
# F4 -- the env_local_key tool's POSIX syscall
# --------------------------------------------------------------------------

# FIXED: the tool adapts -- POSIX keeps the descriptor-based fchmod (immune
# to a symlink swap), Windows falls back to the path-based chmod and says
# once that the POSIX guarantees do not apply there.
F4_FIXED_CHMOD = """    if hasattr(os, "fchmod"):
        os.fchmod(fd, mode)
    else:
        _warn_windows_semantics_once()
        os.chmod(path, mode)"""

# DEFECTIVE: the unconditional syscall the tool used before it learned to
# adapt. On Windows `os.fchmod` does not exist, so the tool raised a raw
# AttributeError traceback instead of its own `result=` line.
F4_DEFECTIVE_CHMOD = """    os.fchmod(fd, mode)"""

F4_KILLED_TEST = "test_env_local_key_never_emits_a_raw_traceback"

# --------------------------------------------------------------------------
# F5 -- the fleet image rebuild trigger
# --------------------------------------------------------------------------

# FIXED: the matrix is rebuilt on a cadence, not on a human's click.
F5_FIXED_SCHEDULE = "  schedule:\n    - cron: '23 4 * * *'\n"

# DEFECTIVE: the trigger is gone, so the matrix is `workflow_dispatch:`
# only again -- and flute-gateway goes stale on a human's schedule.
F5_DEFECTIVE_SCHEDULE = ""

F5_KILLED_TEST = "test_real_workflow_has_a_non_manual_trigger"


# --------------------------------------------------------------------------
# the mutation lock
# --------------------------------------------------------------------------
# WHY THE MUTATE WINDOW IS LOCKED
# -------------------------------
# Every mutation rewrites a tracked source file on disk and restores it in a
# ``finally``. Under pytest-xdist (or any parallel runner, or a Ctrl-C
# mid-write) two mutations interleave: one test reads the "original" while
# the other has it mutated, and the restore in ``finally`` can resurrect a
# mutated file. A mutation harness that itself has a race condition is a
# self-healing grenade.
#
# The lock is TWO layers on purpose. The ``threading.Lock`` serializes
# threads inside one pytest process; the advisory FILE lock serializes
# separate PROCESSES (xdist workers, two pytest invocations at once), which
# a ``threading.Lock`` cannot do. The file lock is released by the OS if a
# worker dies, so a crashed run cannot leave the lock held forever.
_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-drift-fleet-mutation.lock"
_LOCK_TIMEOUT_SECONDS = 300
_LOCK_POLL_SECONDS = 0.2

# The DEADLINE for ONE pytest run inside the mutation lock. This bounds how
# long a case may HOLD the lock, which is a different question from how long
# it may WAIT for it. The measured slowest legitimate single run here is a
# few seconds (a selected test in one module, including interpreter and
# pytest startup), so 300s cannot fire on a healthy run while still
# bounding a wedged one.
_PYTEST_TIMEOUT_SECONDS = 300.0

# The DEADLINE for the POST-KILL drain of a timed-out child, and for the
# final reap of the child. Both are bounded so that a kill that cannot
# complete cannot become the new hang.
_DRAIN_TIMEOUT_SECONDS = 10.0
_TREE_KILL_TIMEOUT_SECONDS = 30.0


class MutationLockTimeout(TimeoutError):
    """The mutation lock could not be taken within the deadline."""


class PytestRunTimeout(TimeoutError):
    """A pytest run inside the mutation lock exceeded its deadline."""


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

    The lock MUST be requested with ``LOCK_NB``: a bare blocking ``flock``
    waits for the holder FOREVER, which wedges the whole test suite with no
    timeout and no diagnostic.
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


def _lock_file(handle, *, lock_path: Path, timeout_seconds: float) -> None:
    """Take the exclusive advisory lock, with a HARD deadline.

    BOTH OS BRANCHES GO THROUGH THIS ONE LOOP. A lock with a timeout on one
    platform and none on another is two different locks; here the deadline
    is the same constant on both.

    A timeout RAISES. It never "proceeds without the lock": proceeding
    without the lock defeats the whole point of the lock, which is to make
    the mutate -> run -> restore window exclusive.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        if _try_lock_nonblocking(handle):
            return
        if time.monotonic() >= deadline:
            raise MutationLockTimeout(
                f"could not acquire the mutation lock {lock_path} within "
                f"{timeout_seconds:g}s. Another pytest process or a stuck "
                f"mutation run is holding it -- kill the holder, or wait for "
                f"it to release."
            )
        time.sleep(_LOCK_POLL_SECONDS)


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
def _file_lock(lock_path: Path, *, timeout_seconds: float) -> Iterator[None]:
    """Hold the advisory file lock on ``lock_path`` for the window."""
    handle = _open_lock_handle(lock_path)
    try:
        _lock_file(handle, lock_path=lock_path, timeout_seconds=timeout_seconds)
        try:
            yield
        finally:
            _unlock_file(handle)
    finally:
        handle.close()


@contextlib.contextmanager
def _mutation_lock() -> Iterator[None]:
    """Hold the mutate -> run -> restore window exclusively."""
    with _MUTATION_LOCK:
        with _file_lock(_LOCK_PATH, timeout_seconds=_LOCK_TIMEOUT_SECONDS):
            yield


# --------------------------------------------------------------------------
# running pytest
# --------------------------------------------------------------------------
def _spawn_pytest_process(args: list[str]) -> subprocess.Popen[str]:
    """Start the pytest child in its OWN process group.

    The child is started in a NEW SESSION on POSIX and a NEW PROCESS GROUP
    on Windows. That is what makes the TREE killable: without it the child
    shares this process' group, so a timeout could only ever kill the
    DIRECT child -- leaving the grandchildren alive and holding the stdout
    pipe open.
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

    KILLING ONLY THE DIRECT CHILD IS NOT ENOUGH. A killed child can leave
    GRANDCHILDREN behind, and a surviving grandchild keeps the stdout pipe
    open. The post-kill read then never sees EOF -- and on Windows
    CPython's own timed-out ``subprocess.run`` path performs exactly that
    UNBOUNDED read, so the mutation lock would be held FOREVER.
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

    The direct child is dead, but a SURVIVOR may still hold the pipe open.
    An unbounded read would then never return -- and the mutation lock is
    held until this returns, so an unbounded drain is the same defect as no
    deadline at all. The drain gives up instead of waiting.
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


def _repo_relative(path: Path) -> str:
    """The path as pytest should see it, relative to the repo root."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _run_pytest(
    module: Path,
    *,
    select: str | None = None,
    timeout_seconds: float = _PYTEST_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run a pytest module and capture the whole report.

    ``-rA`` makes pytest print the short test summary for EVERY test. That
    summary is the harness's evidence: it is what turns "the run was
    unhappy" into "THIS test failed".

    ``select`` is a pytest ``-k`` expression. The mutation cases use it to
    run ONLY the test the mutation is supposed to kill: the other tests are
    not evidence for this mutation.

    THE DEADLINE IS MANDATORY, NOT DECORATION. This runs INSIDE the
    mutation lock. A pytest run that hangs would hold the lock FOREVER,
    and every other case in this file would block behind it.
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
    process = _spawn_pytest_process(args)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        stdout, stderr = _drain_process_output(process, _DRAIN_TIMEOUT_SECONDS)
        raise PytestRunTimeout(
            f"the pytest run {_repo_relative(module)} exceeded its "
            f"{timeout_seconds:g}s deadline (select={select!r}). The mutation "
            f"lock would otherwise be held forever."
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

    WHY THE PARAMETERIZATION SUFFIX IS STRIPPED
    -------------------------------------------
    A PARAMETRIZED test appears in the summary as
    ``test_foo[args1-a-value\\n]`` -- the node id carries the parameter
    id after a bracket. The name of the test is still ``test_foo``, and
    that is what a mutation names. Matching the raw node id against a
    bare name would make every parametrized case UNKILLABLE, which is
    worse than useless: a harness that cannot see a kill will report a
    live defect as a passing lane.

    Stripping the suffix is not a weakening. A parametrized test fails
    when AT LEAST ONE of its parameterizations fails, and pytest reports
    each failing parameterization separately, so the bare name is present
    exactly when the test failed.
    """
    names: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("FAILED "):
            continue
        node = stripped[len("FAILED "):].split(" - ", 1)[0].strip()
        if "::" in node:
            leaf = node.rsplit("::", 1)[-1].strip()
            names.add(leaf.split("[", 1)[0].strip())
    return names


# --------------------------------------------------------------------------
# the mutation case
# --------------------------------------------------------------------------
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
    # The mutation lock is held through ALL THREE PHASES. The ``with``
    # statement is what guarantees it is RELEASED on every exit path --
    # including the one where a pytest run times out and raises. The
    # mutated file is restored by the ``finally`` INSIDE this block, so
    # the restore happens BEFORE the lock is released: no other case can
    # ever observe the file in its mutated state.
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
        mutated_text = original_text.replace(old, new, 1)
        assert mutated_text != original_text, (
            "mutation setup failed: replacement was a no-op"
        )

        # PHASE 1 -- GREEN BEFORE.
        before = _run_pytest(_test_module_for(path), select=select)
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
            proc = _run_pytest(_test_module_for(path), select=select)
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

        after = _run_pytest(_test_module_for(path), select=select)
        after_output = after.stdout + after.stderr
        assert after.returncode == 0 and not _failed_test_names(after_output), (
            "the restored source was NOT green after the mutation -- the "
            f"restore must put the tree back exactly:\n{after_output}"
        )
        return killed, output


def _test_module_for(path: Path) -> Path:
    """The test module that carries the assertions for the mutated file."""
    mapping = {
        DRIFT_AUDITOR: DRIFT_PROBE_TESTS,
        NODE_REGISTRY_API: NODE_REGISTRY_TESTS,
        COMPOSE_FILE: NODE_REGISTRY_TESTS,
        FORK_SYNC_WORKFLOW: FORK_REGISTRY_TESTS,
        ENV_LOCAL_KEY: WINDOWS_POSIX_TESTS,
        BUILD_IMAGES_WORKFLOW: IMAGE_STALENESS_TESTS,
    }
    try:
        return mapping[path]
    except KeyError as exc:  # pragma: no cover -- a new case must be mapped
        raise AssertionError(
            f"no test module is mapped for {path} -- every mutated file must "
            f"have a named test that carries its assertions"
        ) from exc


# --------------------------------------------------------------------------
# the cases
# --------------------------------------------------------------------------
def test_mutation_the_drift_auditors_path_matcher_is_killed() -> None:
    """Matching a PATH claim on its BASENAME again MUST make the probe fail.

    The defect the probe shipped with was worse than a content grep: it
    answered "does this PATH exist" with "does any file with this NAME
    exist". ``PMOVES-Archon/README.md`` was satisfied by any of the 210
    unrelated ``README.md`` files in the tree -- the auditor citing an
    artefact the claim never named.

    The test that must fail is
    ``test_a_path_claim_is_not_satisfied_by_an_unrelated_file_of_the_same_name``:
    it states the rule the defective matcher breaks.
    """
    killed, output = _mutation_case(
        DRIFT_AUDITOR,
        F1_FIXED_PATH_MATCHER,
        F1_DEFECTIVE_PATH_MATCHER,
        select=F1_KILLED_TEST,
        expected_failing_test=F1_KILLED_TEST,
    )
    assert killed, (
        "the drift auditor did NOT catch the basename-matching path defect -- "
        f"the probe can cite an artefact the claim never named again.\n{output}"
    )


def test_mutation_node_registrys_colliding_port_is_killed() -> None:
    """Defaulting the service back to 8082 MUST make the deployment test fail.

    8082 is not a free port: ``pmoves/docker-compose.yml`` binds media-audio
    to host ``${MEDIA_AUDIO_PORT:-8082}:8082``. A node-registry that claimed
    the same host port could not bind alongside it.

    The test that must fail is
    ``test_node_registry_code_default_and_compose_binding_match_catalog_port``.
    """
    killed, output = _mutation_case(
        NODE_REGISTRY_API,
        F2_FIXED_PORT,
        F2_DEFECTIVE_PORT,
        select=F2_KILLED_TEST,
        expected_failing_test=F2_KILLED_TEST,
    )
    assert killed, (
        "the node-registry deployment test did NOT catch the colliding port -- "
        f"the service can claim media-audio's host port again.\n{output}"
    )


def test_mutation_node_registrys_colliding_compose_binding_is_killed() -> None:
    """Publishing media-audio's host port in compose MUST also be caught.

    The source default and the compose binding are TWO pieces of wiring, and
    a single mutation only proves one of them load-bearing. This case
    reverts the COMPOSE half -- the deployment wiring that did not exist at
    all before this lane -- and requires the same named test to fail.

    Without it, a test that asserted only the source default would pass
    while the compose entry quietly claimed 8082, and the two services
    would collide at bring-up.
    """
    killed, output = _mutation_case(
        COMPOSE_FILE,
        F2_FIXED_COMPOSE_BINDING,
        F2_DEFECTIVE_COMPOSE_BINDING,
        select=F2_KILLED_TEST,
        expected_failing_test=F2_KILLED_TEST,
    )
    assert killed, (
        "the node-registry deployment test did NOT catch the colliding "
        f"compose binding -- the service can claim media-audio's host port "
        f"again.\n{output}"
    )


def test_mutation_the_fork_sync_workflow_coverage_is_killed() -> None:
    """Dropping a claimed fork from the workflow MUST make the ratchet fail.

    A ``sync: true`` entry in the registry with nothing behind it is a
    claim, not a feature. The ratchet that cross-checks registry ->
    workflow is the only thing that can say so.

    The test that must fail is
    ``test_every_sync_true_registry_fork_is_in_the_workflow_forks_block``.
    """
    killed, output = _mutation_case(
        FORK_SYNC_WORKFLOW,
        F3_FIXED_FORKS_ENTRY,
        F3_DEFECTIVE_FORKS_ENTRY,
        select=F3_KILLED_TEST,
        expected_failing_test=F3_KILLED_TEST,
    )
    assert killed, (
        "the fork registry ratchet did NOT catch a claimed fork disappearing "
        f"from the workflow -- the gap is invisible again.\n{output}"
    )


def test_mutation_the_env_local_key_posix_syscall_is_killed() -> None:
    """Going back to the unconditional ``os.fchmod`` MUST make the test fail.

    ``os.fchmod`` does not exist on Windows, so the unconditional call made
    the operator's own tool raise a raw ``AttributeError`` traceback
    instead of its own ``result=`` line.

    The test that must fail is
    ``test_env_local_key_never_emits_a_raw_traceback``.
    """
    killed, output = _mutation_case(
        ENV_LOCAL_KEY,
        F4_FIXED_CHMOD,
        F4_DEFECTIVE_CHMOD,
        select=F4_KILLED_TEST,
        expected_failing_test=F4_KILLED_TEST,
    )
    assert killed, (
        "the Windows POSIX ratchet did NOT catch the unguarded fchmod -- the "
        f"tool can stack-trace on the operator's platform again.\n{output}"
    )


def test_mutation_the_image_rebuild_trigger_is_killed() -> None:
    """Removing the scheduled rebuild MUST make the ratchet fail.

    ``build-images.yml`` was ``workflow_dispatch:`` only, so nothing
    rebuilt the fleet and flute-gateway went 65 days stale. The ratchet
    exists so that removing the trigger is a red check, not a silent rot.

    The test that must fail is
    ``test_real_workflow_has_a_non_manual_trigger``.
    """
    killed, output = _mutation_case(
        BUILD_IMAGES_WORKFLOW,
        F5_FIXED_SCHEDULE,
        F5_DEFECTIVE_SCHEDULE,
        select=F5_KILLED_TEST,
        expected_failing_test=F5_KILLED_TEST,
    )
    assert killed, (
        "the image-staleness ratchet did NOT catch the missing rebuild "
        f"trigger -- the fleet can go stale on a human's schedule again.\n{output}"
    )
