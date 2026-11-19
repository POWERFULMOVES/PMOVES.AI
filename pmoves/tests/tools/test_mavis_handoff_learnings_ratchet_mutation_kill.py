"""Mutation-kill harness: the LEARNINGS ratchet must BITE when the document is
put back the way it was.

THE DEFECT CLASS
----------------
``pmoves/docs/AGENTS/mavis_inter_agent_handoff_LEARNINGS.md`` documents the
Mavis inter-agent handoff harness. For a while the file on ``main`` described
the PRE-operator-review design: it said KVM rode ``pmoves.bpm.phase.v1`` with a
``phase: kvm-focus`` discriminator, and it described the ``known_targets``
derivation only vaguely. The orchestrator on ``main`` implements the
POST-review design. A gate that reads the document can only be load-bearing if
a plausible edit to the document makes it fail -- so this harness puts the
stale wording back, six ways, and requires the NAMED gate test to die each
time.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine document must pass the selected test.
  2. RED AFTER    -- the mutated document must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored document must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
The house budget model charges a mutation-kill harness by its WALL CLOCK: a
file that costs more than ``FALLBACK_FILE_TIMEOUT`` (60s) is killed when the
ratchet isolates it, and a healthy-but-slow file is then reported as a broken
one (see ``pmoves/configs/pytest_ratchet/_slow_files.yaml``). Every phase here
spawns a full ``python -m pytest`` child, and one child startup is ~1.7s on
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

A MUTATION MUST REVERT THE DOCUMENT, NEVER THE GATE
----------------------------------------------------
Each mutation below changes the LEARNINGS FILE -- the document the gate reads
-- and never re-types the gate's own expression. A mutation that edited the
gate would prove nothing about the document it claims to check.

THE MUTATIONS
-------------
M1  the KVM subject the document names is changed          -> kills
    test_the_learnings_names_the_kvm_subject_the_orchestrator_publishes_on
M2  the phase-discriminator design is selected again         -> kills
    test_the_learnings_does_not_pick_the_phase_discriminator_design
M3  the known_targets derivation is put back to the vague    -> kills
    wording                                               -> kills
    test_the_learnings_agrees_with_the_orchestrator_on_how_known_targets_is_derived
M4  the envelope's target_alias is put back to the alias    -> kills
    test_the_learnings_agrees_with_the_orchestrator_on_the_wire_target
M5  a rejected placeholder is dropped from the list         -> kills
    test_the_learnings_placeholder_set_matches_the_orchestrators_non_actionable_nodes
M6  a named regression test that does not exist is named    -> kills
    test_the_learnings_named_tests_exist_in_the_repo

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_mavis_handoff_learnings_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
this lane's LEARNINGS file in this repo and restores it.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pmoves.tests import mutation_backup  # noqa: E402

LEARNINGS = (
    REPO_ROOT
    / "pmoves"
    / "docs"
    / "AGENTS"
    / "mavis_inter_agent_handoff_LEARNINGS.md"
)

GATE = (
    REPO_ROOT
    / "pmoves"
    / "tests"
    / "tools"
    / "test_mavis_handoff_learnings_ratchet.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

# The SAME house-wide lock the register-provenance harness uses. Two harnesses
# that mutate files in this repo must not hold the tree at once -- a mutation
# harness leaves the tree MUTATED by design, so anything that reads the tree
# during that window reads the mutation.
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
    # M1 -- the KVM subject the document names
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_document_names_a_kvm_subject_the_orchestrator_does_not_use",
        old="pmoves.kvm.focus.v1",
        new="pmoves.kvm.focus.v2",
        target_test=(
            "test_the_learnings_names_the_kvm_subject_the_orchestrator_publishes_on"
        ),
        rationale=(
            "The subject name is the single most load-bearing string in the "
            "document: a consumer that subscribes on the subject the document "
            "names, rather than the one the code publishes, waits forever for "
            "an event that is never sent. The gate derives the expected "
            "subject from pmoves/tools/orchestrator.py, so renaming it in the "
            "document is exactly the drift the gate exists to catch."
        ),
        target_file=LEARNINGS,
        test_file=GATE,
    ),
    # ------------------------------------------------------------------
    # M2 -- the phase-discriminator design, selected again
    # ------------------------------------------------------------------
    Mutation(
        name="M2_the_phase_discriminator_design_is_selected_again",
        old=(
            "**The principle: \"A discriminator field does not make an "
            "incompatible\npayload compatible; it just moves the breakage "
            "into the consumer.\"**"
        ),
        new=(
            "Picked (B) because the KVM controller (a separate service) can\n"
            "reuse the existing phase-event subscriber, and the discriminator\n"
            "in the payload is the contract:\n"
            "\n"
            "- **(B) Reuse `pmoves.bpm.phase.v1`** with a `phase: kvm-focus`"
        ),
        rationale=(
            "The exact wording that was on main before the operator review: "
            "option (B) selected, the KVM focus event riding the BPM phase "
            "stream under a discriminator. This is the claim the whole "
            "operator-review rewrite exists to retract, so it is the most "
            "plausible edit to the document -- and if the gate still passed "
            "with it, the gate would be measuring nothing."
        ),
        target_test=(
            "test_the_learnings_does_not_pick_the_phase_discriminator_design"
        ),
        target_file=LEARNINGS,
        test_file=GATE,
    ),
    # ------------------------------------------------------------------
    # M3 -- the known_targets derivation, back to the vague wording
    # ------------------------------------------------------------------
    Mutation(
        name="M3_the_known_targets_derivation_is_put_back_to_the_vague_wording",
        old=(
            "edit. The fix: derive `known_targets` from "
            "`dataclasses.fields(self.bootstrap.routing)`\n"
            "plus a built-in floor. Adding a routing entry to the CGP now\n"
            "auto-widens the dispatch surface with zero orchestrator code.\n"
            "\n"
            "**Important sub-lesson from the operator review:** \"Enumerate the\n"
            "Routing dataclass's FIELDS rather than a literal tuple\" \u2014 i.e.\n"
            "`for f in dataclasses.fields(routing): if getattr(routing, f.name, "
            "None):`\n"
        ),
        new=(
            "edit. The fix: derive `known_targets` from `self.bootstrap.routing`\n"
            "plus a built-in floor. Adding a routing entry to the CGP now\n"
            "auto-widens the dispatch surface with zero orchestrator code.\n"
            "\n"
            "**Corollaries:** the built-in set is a FLOOR, not a CEILING.\n"
        ),
        rationale=(
            "The wording that was on main before the operator review: "
            "'derive known_targets from self.bootstrap.routing'. It is vague "
            "rather than false, which is what makes it dangerous -- a reader "
            "cannot tell whether the peers are enumerated from the dataclass's "
            "FIELDS or from a literal tuple, and only the latter breaks the "
            "docstring's promise. The gate parses the known_targets property "
            "body, so the document has to name dataclasses.fields."
        ),
        target_test=(
            "test_the_learnings_agrees_with_the_orchestrator_on_how_known_targets_is_derived"
        ),
        target_file=LEARNINGS,
        test_file=GATE,
    ),
    # ------------------------------------------------------------------
    # M4 -- the envelope's target_alias, put back to the alias
    # ------------------------------------------------------------------
    Mutation(
        name="M4_the_envelope_is_documented_without_the_target_alias",
        old=(
            "The fix: the envelope now carries `target: \"hermes-3\"` (the\n"
            "configured target from `routing.hermes.target`) AND `target_alias:\n"
            "\"hermes\"` (the routing key) for producer-side correlation. The\n"
        ),
        new=(
            "The fix: the envelope now carries `target: \"hermes\"` (the\n"
            "configured target from `routing.hermes.target`) for producer-side\n"
            "correlation. The\n"
        ),
        rationale=(
            "The alias/target split is the P1 the operator review caught: an "
            "envelope carrying the alias never matches the consumer, and the "
            "handoff sits pending forever with no error message. A document "
            "that names the alias where the code names the configured target "
            "is the drift that cost a whole handoff. The gate derives the "
            "configured target from the LIVE routing block."
        ),
        target_test=(
            "test_the_learnings_agrees_with_the_orchestrator_on_the_wire_target"
        ),
        target_file=LEARNINGS,
        test_file=GATE,
    ),
    # ------------------------------------------------------------------
    # M5 -- a rejected placeholder is dropped from the list
    # ------------------------------------------------------------------
    Mutation(
        name="M5_a_rejected_placeholder_is_dropped_from_the_documented_list",
        old="rejects `tbd/todo/none/n/a/-` alongside",
        new="rejects `tbd` alongside",
        rationale=(
            "The orchestrator refuses a documented set of placeholder node "
            "names. If the document narrows that set, a reader believes "
            "'todo' is a switchable machine and the KVM controller is asked "
            "to focus a keyboard on a node named todo. The gate parses "
            "_NON_ACTIONABLE_NODES out of the orchestrator source and requires "
            "the document to list the same set."
        ),
        target_test=(
            "test_the_learnings_placeholder_set_matches_the_orchestrators_non_actionable_nodes"
        ),
        target_file=LEARNINGS,
        test_file=GATE,
    ),
    # ------------------------------------------------------------------
    # M6 -- a named regression test that does not exist
    # ------------------------------------------------------------------
    Mutation(
        name="M6_the_document_names_a_regression_test_that_does_not_exist",
        old="test_routing_for_returns_a_copy_not_a_reference",
        new="test_routing_for_returns_the_live_reference",
        rationale=(
            "This is the exact falsehood that was on main: Lesson 3 named "
            "`test_routing_for_returns_a_copy_not_a_reference` as its "
            "regression check, and the file that used to hold it "
            "(pmoves/tests/test_orchestrator_kvm.py) had been deleted as "
            "stale. The document pointed at a guard that was not there. The "
            "gate resolves every test name the document cites against the "
            "repo's own test trees."
        ),
        target_test="test_the_learnings_named_tests_exist_in_the_repo",
        target_file=LEARNINGS,
        test_file=GATE,
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
    """GREEN BEFORE, once for the whole session: the pristine document must
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
            f"{mutation.name}: the pristine LEARNINGS does not pass "
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
    must pass again -- and the LEARNINGS file must be byte-identical to the
    original."""
    text = LEARNINGS.read_text(encoding="utf-8")
    assert "pmoves.kvm.focus.v2" not in text, (
        "the mutated KVM subject is still in the LEARNINGS file"
    )
    assert "pmoves.kvm.focus.v1" in text, (
        "the real KVM subject is not intact after the mutation suite"
    )
    assert "Picked (B)" not in text, (
        "the phase-discriminator design is still selected in the LEARNINGS file"
    )
    assert "dataclasses.fields" in text, (
        "the known_targets derivation is not intact after the mutation suite"
    )
    assert "`target_alias:\n\"hermes\"`" in text, (
        "the target_alias claim is not intact after the mutation suite"
    )
    assert "rejects `tbd/todo/none/n/a/-` alongside" in text, (
        "the rejected-placeholder list is not intact after the mutation suite"
    )
    assert "test_routing_for_returns_a_copy_not_a_reference" in text, (
        "the named regression test is not intact after the mutation suite"
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored LEARNINGS does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
