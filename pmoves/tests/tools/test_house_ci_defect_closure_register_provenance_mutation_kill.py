"""Mutation-kill harness: the register-provenance gate must BITE when the
release row's provenance is put back the way it was.

THE DEFECT CLASS
----------------
A register row is a claim filed to the next reader. This lane's RELEASE row
filed one that no reader could check: it cited a trail artifact that the
repository's ignore rules EXCLUDE, so the receipt did not exist for anyone
reading the tree the row was filed in, and it asserted that no signing key was
available without recording WHICH check was run.

A gate that reads the row can only be load-bearing if a plausible edit to the
row makes it fail. So this harness puts the defect back, four ways, and
requires the NAMED test to die each time.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine register must pass the selected test.
  2. RED AFTER    -- the mutated register must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored register must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
The house budget model charges a mutation-kill harness by its WALL CLOCK: a
file that costs more than ``FALLBACK_FILE_TIMEOUT`` (60s) is killed when the
ratchet isolates it, and a healthy-but-slow file is then reported as a broken
one (see ``pmoves/configs/pytest_ratchet/_slow_files.yaml``). Every phase here
spawns a full ``python -m pytest`` child, and one child startup is ~1.6s on
this host -- irreducible.

So the GREEN phases run ONCE for the whole session, over every target test:

  * GREEN BEFORE runs once, before any mutation, over ALL the target tests;
  * RED AFTER runs per mutation, over the ONE named test (this is the only
    phase that has to be per-mutation: the source under test differs);
  * GREEN AFTER runs once, after every mutation has been restored.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it. A harness may
only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below changes the ROW -- the document the gate reads -- and
never re-types the gate's own expression. A mutation that edited the gate
would prove nothing about the document it claims to check.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_house_ci_defect_closure_register_provenance_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
this lane's row in the AGNOTE register in this repo and restores it.
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

REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"

PROVENANCE_GATE = (
    REPO_ROOT
    / "pmoves"
    / "tests"
    / "tools"
    / "test_house_ci_defect_closure_register_provenance.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

# The SAME house-wide lock the taxonomy harness uses. Two harnesses that mutate
# files in this repo must not hold the tree at once -- a mutation harness
# leaves the tree MUTATED by design, so anything that reads the tree during
# that window reads the mutation.
_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-house-ci-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    old: str
    new: str
    target_test: str
    rationale: str
    target_file: Path
    test_file: Path


MUTATIONS: list[Mutation] = [
    # ------------------------------------------------------------------
    # The row's cited artifact -- put back on the GITIGNORED rolling log
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_cited_artifact_put_back_on_the_gitignored_rolling_log",
        old=(
            "trail_artifact: pmoves/docs/logs/"
            "graphiti_signed_house_ci_defect_closure_release_2026-11-06.json;"
        ),
        new=(
            "trail_artifact: pmoves/docs/logs/graphiti_signed_latest.json;"
        ),
        target_test="test_the_cited_artifact_is_not_gitignored",
        rationale=(
            "This is the EXACT defect that was found: the row's only "
            "provenance artifact was a local log the repository's ignore "
            "rules exclude, so a reader of the repository the row is filed in "
            "had nothing to verify. The rolling log is what sign_trail.py "
            "writes, so it is the path a later edit would naturally reach "
            "for -- which is exactly why the gate has to notice."
        ),
        target_file=REGISTER,
        test_file=PROVENANCE_GATE,
    ),
    # ------------------------------------------------------------------
    # The row's signature state -- put back to claiming a signature
    # ------------------------------------------------------------------
    Mutation(
        name="M2_the_row_claims_a_signature_the_artifact_does_not_carry",
        old="trail_signature_state: UNSIGNED;",
        new="trail_signature_state: SIGNED;",
        target_test=(
            "test_the_rows_signature_state_matches_the_artifacts_actual_state"
        ),
        rationale=(
            "The mirror of M1: the artifact is unsigned, and a row that says "
            "otherwise is a FALSE provenance claim -- the worst kind, because "
            "it reads as stronger than the truth. A gate that only checked "
            "'does the row mention a signature state' would pass this, so the "
            "gate compares the DECLARED state against the artifact's ACTUAL "
            "one -- the `sig` block the payload does or does not carry."
        ),
        target_file=REGISTER,
        test_file=PROVENANCE_GATE,
    ),
    # ------------------------------------------------------------------
    # The row's declared identity -- put back to a different agent
    # ------------------------------------------------------------------
    Mutation(
        name="M3_the_row_declares_an_agent_the_artifact_was_not_written_by",
        old="trail_agent_id: minimax;",
        new="trail_agent_id: not-minimax;",
        target_test=(
            "test_the_cited_artifacts_identity_and_timestamp_appear_in_the_row"
        ),
        rationale=(
            "The citation has to be to a SPECIFIC payload. 'minimax' appears "
            "in several places in this row, so a gate that checked for the "
            "substring would pass on the wrong one -- which is why the row "
            "states the identity as a `key: value` token and the gate "
            "compares the token against the artifact's agent_id."
        ),
        target_file=REGISTER,
        test_file=PROVENANCE_GATE,
    ),
    # ------------------------------------------------------------------
    # The row's key probe -- removed, so the row asserts instead of records
    # ------------------------------------------------------------------
    Mutation(
        name="M4_the_recorded_key_probe_removed",
        old="chit_key_probe:",
        new="chit_key_probe_removed:",
        target_test="test_the_row_records_the_chit_key_probe",
        rationale=(
            "Removing the recorded probe is what turns the row back into a "
            "claim about the WORLD -- 'there is no signing key here' -- "
            "rather than a record of a CHECK. The 2026-08-09 5090-CLAUDE row "
            "already ruled that this disclaimer class is 'a process gap, not "
            "a material gap', and instructed sessions to attempt sign-trail "
            "before writing it. The gate requires the probe to name all five "
            "resolver sources, so a probe of fewer cannot support the claim."
        ),
        target_file=REGISTER,
        test_file=PROVENANCE_GATE,
    ),
]


def _run_pytest(
    node_ids: list[str], timeout: float = _PYTEST_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *node_ids,
            "-q",
            "-p",
            "no:warnings",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def _node_id(mutation: Mutation) -> str:
    return f"{mutation.test_file.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"


_GREEN_BEFORE: list[subprocess.CompletedProcess] = []


def _green_before() -> list[subprocess.CompletedProcess]:
    """GREEN BEFORE, once for the whole session: the pristine register must
    pass EVERY target test."""
    if not _GREEN_BEFORE:
        node_ids = [_node_id(mutation) for mutation in MUTATIONS]
        _GREEN_BEFORE.append(_run_pytest(node_ids))
    return _GREEN_BEFORE


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
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.target_file.name}. The source changed -- update the "
            f"mutation.\n--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def _read_source(path: Path) -> tuple[str, bool]:
    """(text, uses_crlf) for a source file.

    The text is normalised to ``\\n`` so a mutation anchor is line-ending
    independent; the flag records the file's OWN convention so the restore can
    put it back exactly as it was.
    """
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def _write_source(path: Path, text: str, crlf: bool) -> None:
    """Write a source file back in its own line-ending convention."""
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def test_every_mutation_anchor_is_present() -> None:
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original, _crlf = _read_source(mutation.target_file)
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.target_file.name} -- the source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED, with a byte-exact restore. GREEN is batched (see the
    module docstring): it runs once before any mutation and once after the
    last restore, over every target test."""
    node_id = _node_id(mutation)
    target = mutation.target_file
    original, crlf = _read_source(target)
    original_bytes = target.read_bytes()

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH), mutation_backup.file_lock(
        mutation_backup.lock_path(REPO_ROOT, target)
    ):
        # 1. GREEN BEFORE (batched over every target test)
        before = _green_before()[0]
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine register does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        # The pristine bytes go on disk BEFORE the mutation, so a process that
        # is KILLED mid-mutation cannot leave the tree dirty for the next
        # session to inherit. See pmoves/tests/mutation_backup.py.
        mutation_backup.write_backup(REPO_ROOT, target, original_bytes)
        try:
            _write_source(target, mutated, crlf)

            # 2. RED AFTER -- the NAMED test must die
            after = _run_pytest([node_id])
            assert after.returncode != 0, (
                f"{mutation.name}: the mutation SURVIVED -- "
                f"{mutation.target_test} still passed\n{after.stdout[-4000:]}"
            )
            assert _named_test_failed(after, mutation.target_test), (
                f"{mutation.name}: pytest failed, but NOT the named test "
                f"{mutation.target_test}\n{after.stdout[-4000:]}\n{after.stderr[-2000:]}"
            )
        finally:
            # 3. restore -- byte-exact, line endings included
            _write_source(target, original, crlf)
            restored = target.read_bytes()
            assert restored == original_bytes, (
                f"{mutation.name}: the restore was not byte-exact"
            )
            # The backup is dropped only AFTER a byte-exact restore. If the
            # assert above fails, the backup is the only good copy of the
            # pristine source, and the next session must still be able to
            # restore it -- so it stays on disk.
            mutation_backup.clear_backup(REPO_ROOT, target)


def test_the_sources_are_intact_after_the_mutation_suite() -> None:
    """GREEN AFTER: after every mutation has been restored, every target test
    must pass again -- and the register must be byte-identical to the
    original."""
    row = REGISTER.read_text(encoding="utf-8")
    assert "trail_artifact: pmoves/docs/logs/graphiti_signed_latest.json;" not in row, (
        "the gitignored rolling log is cited again in the register"
    )
    assert (
        "trail_artifact: pmoves/docs/logs/"
        "graphiti_signed_house_ci_defect_closure_release_2026-11-06.json;" in row
    ), (
        "the tracked trail artifact citation is not intact after the mutation "
        "suite"
    )
    assert "trail_signature_state: SIGNED;" not in row, (
        "the row still claims a signature the artifact does not carry"
    )
    assert "chit_key_probe:" in row, (
        "the recorded key probe is not intact after the mutation suite"
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored register does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
