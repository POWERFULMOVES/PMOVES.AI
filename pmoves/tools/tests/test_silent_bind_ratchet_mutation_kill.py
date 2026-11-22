# pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py
"""Mutation-kill harness: the silent-bind ratchet's rules must BITE when they
are put back.

THE DEFECT
----------
The house already owns a runtime auditor for this class
(``make -C pmoves net-reality`` -> ``pmoves/scripts/audit_network_reality.sh``),
but it needs a running Docker daemon, so it cannot run on a GitHub-hosted
runner. The static gate in ``pmoves/tools/silent_bind_ratchet.py`` is the
CI-side twin. A static gate has a failure mode a runtime one does not: it can
quietly stop DETECTING, and a gate that cannot detect is indistinguishable
from a clean tree. Every rule below is therefore pinned by a mutation that
must kill a NAMED test.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the same three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted. The pristine
bytes are written to a crash-safe backup BEFORE the mutation (see
``pmoves/tests/mutation_backup.py``), so a harness that is KILLED mid-mutation
cannot leave the tree dirty for the next session to inherit.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero" -- a collection error, a
timeout or an unrelated environment failure also satisfies that. The harness
reads pytest's own short test summary and requires the NAMED test to be IN
it. A harness may only claim a kill it can point at.

THE MUTATIONS
--------------
Each mutation removes or inverts ONE rule the gate depends on. The gate is
not allowed to become a gate that cannot fail.

  M1   the internal-only verdict is removed
  M2   canonical internality inheritance is removed (the split-overlay
       blind spot: the generated overlays reference pmoves_api without
       declaring it, and 34 of the 73 measured pairs live in those files)
  M3   the empty-network-set guard is removed (vacuous truth: `all()` over
       an empty set is True, so every service without a `networks:` key
       becomes a phantom gap)
  M4   an EXTERNAL network is treated as internal (its internality is not
       knowable from source, so claiming it either way is a guess)
  M5   the STALE baseline rule is removed (a recorded gap that no longer
       exists would live on forever)
  M6   the placeholder-reason rule is removed (a recorded gap must carry a
       REVIEWED reason, not "REVIEW THIS")
  M7   the instrument-error rule is removed (an unreadable compose file
       would be skipped instead of failing the gate closed)

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no gh. It mutates files in this repo and
restores them.
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
RATCHET = REPO_ROOT / "pmoves" / "tools" / "silent_bind_ratchet.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tools" / "tests" / "test_silent_bind_ratchet.py"

_PYTEST_TIMEOUT_SECONDS = 300.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-silent-bind-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    target: Path
    old: str
    new: str
    target_test: str
    rationale: str


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_internal_only_verdict_removed",
        target=RATCHET,
        old="""        if all(v is True for v in flags.values()):""",
        new="""        if False:""",
        target_test="test_internal_only_service_is_reported",
        rationale=(
            "This IS the gate. Without it the tool reports nothing at all, "
            "and the moby/moby#36174 class -- a published port that Docker "
            "stores and never activates -- becomes invisible to CI."
        ),
    ),
    Mutation(
        name="M2_canonical_inheritance_removed",
        target=RATCHET,
        old="""    return canon.get(net)""",
        new="""    return None""",
        target_test="test_canonical_inheritance_covers_the_split_overlay",
        rationale=(
            "The generated split overlays reference pmoves_api WITHOUT "
            "declaring it -- the networks block lives in the source "
            "monolith. Ten files in the scope re-declare the pmoves_* "
            "networks without an `internal:` key, so a resolver that reads "
            "only the scanned file's own networks block degrades them to "
            "UNKNOWN and is blind to 34 of the 73 measured gap pairs."
        ),
    ),
    Mutation(
        name="M3_empty_network_set_guard_removed",
        target=RATCHET,
        old="""            if default_internal is True:
                nets = ["default"]
            else:
                continue""",
        new="""            if default_internal is True:
                nets = ["default"]""",
        target_test="test_service_without_networks_key_is_not_a_gap",
        rationale=(
            "A service with no `networks:` key joins the file's DEFAULT "
            "network, which is a normal bridge -- so its port binds. "
            "`all()` over an EMPTY set is True, so without this guard the "
            "gate reports every such service as a gap: dozens of phantom "
            "defects that would bury the real ones."
        ),
    ),
    Mutation(
        name="M4_external_network_treated_as_internal",
        target=RATCHET,
        old="""        if spec.get("external"):
            return None
        if "internal" in spec:
            return bool(spec["internal"])""",
        new="""        if spec.get("external"):
            return True
        if "internal" in spec:
            return bool(spec["internal"])""",
        target_test="test_unknown_network_is_never_a_finding",
        rationale=(
            "An `external: true` network is adopted by compose, which does "
            "not own its `internal` flag -- so its internality is NOT "
            "knowable from source. pmoves_external and pmoves_db_egress are "
            "both external. Asserting either way is a guess, and a guess "
            "that manufactures findings is worse than an admission of "
            "ignorance."
        ),
    ),
    Mutation(
        name="M5_stale_baseline_rule_removed",
        target=RATCHET,
        old="""        if key not in measured:
            findings.append({
                "kind": STALE_GAP, "file": key[0], "service": key[1],""",
        new="""        if False:
            findings.append({
                "kind": STALE_GAP, "file": key[0], "service": key[1],""",
        target_test="test_stale_baseline_entry_fails",
        rationale=(
            "The baseline may only SHRINK. A recorded gap whose service was "
            "fixed must fail the gate until the record is removed, "
            "otherwise the baseline silently becomes a list of folklore "
            "about services that no longer exist."
        ),
    ),
    Mutation(
        name="M6_placeholder_reason_rule_removed",
        target=RATCHET,
        old="""        elif not reason.strip() or reason.strip() == PLACEHOLDER_REASON:""",
        new="""        elif False:""",
        target_test="test_placeholder_reason_fails",
        rationale=(
            "A recorded gap must carry a REVIEWED reason. 'REVIEW THIS' is "
            "the generator's placeholder, not a reason -- without this rule "
            "a baseline of placeholders reads exactly like a baseline of "
            "reviewed decisions."
        ),
    ),
    Mutation(
        name="M7_instrument_error_rule_removed",
        target=RATCHET,
        old="""    except Exception as exc:
        errors.append({"kind": INSTRUMENT_ERROR, "file": path.name, "detail": str(exc)})
        return gaps, errors""",
        new="""    except Exception:
        return gaps, errors""",
        target_test="test_unparseable_compose_file_fails_closed",
        rationale=(
            "A gate that cannot read its input must FAIL CLOSED. Swallowing "
            "the parse error makes an unreadable compose file look like a "
            "clean one -- and the gate's whole job is to report the one "
            "thing a clean file looks like."
        ),
    ),
]


def _run_pytest(node_id: str, timeout: float = _PYTEST_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    # NOTE: no `--timeout` flag here. That flag belongs to the
    # `pytest-timeout` PLUGIN, which is not installed in every CI
    # environment -- and a flag the plugin does not know makes pytest exit
    # 4 with "unrecognized arguments", which would make the harness report
    # a mutation kill for the WRONG reason (a collection failure, not a
    # red test). The outer `subprocess.run(timeout=...)` is the real guard:
    # a hung inner pytest raises TimeoutExpired and the harness FAILS.
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
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
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
            f"mutation {mutation.name}: anchor not found in {mutation.target.name}. "
            "The tool's source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original = mutation.target.read_text(encoding="utf-8")
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in {mutation.target.name} "
            "-- the tool source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name
        assert mutation.target_test in TEST_FILE.read_text(encoding="utf-8"), (
            f"mutation {mutation.name}: the named test {mutation.target_test} "
            "does not exist in the ratchet test file"
        )


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED -> GREEN, with a byte-exact restore."""
    node_id = f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"
    original = mutation.target.read_text(encoding="utf-8")
    original_bytes = mutation.target.read_bytes()

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH), mutation_backup.file_lock(
        mutation_backup.lock_path(REPO_ROOT, mutation.target)
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
        mutation_backup.write_backup(REPO_ROOT, mutation.target, original_bytes)
        try:
            mutation.target.write_text(mutated, encoding="utf-8", newline="")
            try:
                # 2. RED AFTER
                after = _run_pytest(node_id)
                assert after.returncode != 0, (
                    f"{mutation.name}: the mutated source still PASSES "
                    f"{mutation.target_test} -- the rule is not load-bearing"
                )
                assert _named_test_failed(after, mutation.target_test), (
                    f"{mutation.name}: pytest failed but did not name "
                    f"{mutation.target_test} as the failure\n"
                    f"{after.stdout[-4000:]}"
                )
            finally:
                # 3. RESTORE -- byte-exact, and asserted.
                mutation.target.write_bytes(original_bytes)
                assert mutation.target.read_bytes() == original_bytes
        finally:
            mutation_backup.clear_backup(REPO_ROOT, mutation.target)

    # 4. GREEN AFTER -- the restored source must pass again.
    after_restore = _run_pytest(node_id)
    assert after_restore.returncode == 0, (
        f"{mutation.name}: the restored source does not pass "
        f"{mutation.target_test}\n{after_restore.stdout[-4000:]}"
    )
