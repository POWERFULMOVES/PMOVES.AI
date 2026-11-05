"""Mutation-kill harness: the house-CI defect gates must BITE when the defect
is put back.

THE DEFECT CLASS
----------------
This lane closed defects that lived in WORKFLOW FILES, not in application
code. That is a harder class to gate, because a workflow file is read by
GitHub, not imported by Python -- so a test that re-implements the workflow's
logic in Python proves only that the author believed the logic. The gates in
this lane therefore SLICE the real shell out of the workflow file and RUN it,
and this harness is what proves those slices are load-bearing.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
The house budget model charges a mutation-kill harness by its WALL CLOCK: a
file that costs more than ``FALLBACK_FILE_TIMEOUT`` (60s) is killed when the
ratchet isolates it, and a healthy-but-slow file is then reported as a broken
one (see ``pmoves/configs/pytest_ratchet/_slow_files.yaml``). Every phase
here spawns a full ``python -m pytest`` child, and one child startup is ~1.6s
on this host -- irreducible.

So the GREEN phases run ONCE for the whole session, over every target test,
instead of once per mutation:

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
Each mutation below rewrites the CALL the production path makes, or removes a
rule the production path relies on. None of them re-types the fix's own
expression: each one is a defect a reviewer could plausibly introduce, and
each is killed by a test that exercises the production path.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_house_ci_defect_closure_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
workflow files in this repo and restores them.
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
APPROVE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "app-pr-approve.yml"

APPROVE_TEST = (
    REPO_ROOT / "pmoves" / "tests" / "tools" / "test_app_pr_approve_guard.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

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
    # app-pr-approve.yml -- the verdict guard
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_verdict_comparison_reverted_to_the_uppercase_spelling",
        old="""            concl="$(printf '%s' "$raw" | tr '[:lower:]' '[:upper:]')\"""",
        new="""            concl="$raw\"""",
        target_test="test_the_guard_accepts_the_lowercase_verdicts_the_api_returns",
        rationale=(
            "This is the EXACT pre-fix defect. The REST check-runs API returns "
            "conclusions in LOWERCASE and the GraphQL rollup returns UPPERCASE, "
            "so the case statement matched nothing and every check fell "
            "through to the default branch: the guard printed 'BAD: "
            "merge-decision is success' for a GREEN check and then refused with "
            "'30 check(s) not green'. The workflow had never run before "
            "2026-11-02, so the defect was never observed."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
    ),
    Mutation(
        name="M2_the_cancelled_review_bot_tolerance_removed",
        old="""                case "$name" in
                  "kilo-review"|"Kilo Code Review"|"claude-review"|"Claude Code Review"|"Codex Review")
                    tolerated=$((tolerated+1)); echo "tolerated CANCELLED review-bot check: $name" ;;
                  *) bad=$((bad+1)); echo "BAD: $name is CANCELLED" ;;
                esac ;;""",
        new="""                bad=$((bad+1)); echo "BAD: $name is CANCELLED" ;;""",
        target_test="test_the_guard_still_tolerates_a_cancelled_review_bot",
        rationale=(
            "The review bots cancel on rerun BY DESIGN. A guard that refuses "
            "them makes every rerun unapprovable, which is how a safety "
            "mechanism gets disabled in practice: it is too strict, so people "
            "stop using it."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
    ),
    Mutation(
        name="M3_the_failed_check_branch_removed",
        old="""              *) bad=$((bad+1)); echo "BAD: $name is $raw" ;;""",
        new="""              *) : ;;""",
        target_test="test_the_guard_still_refuses_a_failed_check",
        rationale=(
            "A guard that accepts a FAILING check is not a guard. This is the "
            "one mutation that must never survive: it converts the approval "
            "workflow into an unconditional approval."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
    ),
    Mutation(
        name="M4_every_cancelled_check_tolerated",
        old="""                case "$name" in
                  "kilo-review"|"Kilo Code Review"|"claude-review"|"Claude Code Review"|"Codex Review")
                    tolerated=$((tolerated+1)); echo "tolerated CANCELLED review-bot check: $name" ;;
                  *) bad=$((bad+1)); echo "BAD: $name is CANCELLED" ;;
                esac ;;""",
        new="""                tolerated=$((tolerated+1)); echo "tolerated CANCELLED check: $name" ;;""",
        target_test="test_the_guard_still_refuses_a_cancelled_non_review_bot",
        rationale=(
            "The tolerance is a NAMED list, not a category. Widening it to "
            "every cancelled check means a cancelled REAL check -- a CI job "
            "that was killed -- reads as a review bot that was rerun."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
    ),
    Mutation(
        name="M5_the_empty_check_set_refusal_removed",
        old="""          [ -n "$checks" ] || refuse "no check runs at head $head - absence is not consent\"""",
        new="""          :""",
        target_test="test_the_guard_refuses_when_there_are_no_check_runs_at_head",
        rationale=(
            "Absence is not consent. The API answers an empty check-runs list "
            "for a head that has never been checked, and 'every check is "
            "green' is then vacuously true. Without this refusal the guard "
            "approves a head that nothing has ever examined."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
    ),
    Mutation(
        name="M6_the_app_token_moved_back_across_a_job_boundary",
        old="""          GH_TOKEN: ${{ steps.app-token.outputs.token }}""",
        new="""          GH_TOKEN: ${{ needs.mint.outputs.token }}""",
        target_test="test_the_app_token_is_minted_inline_in_the_approving_job",
        rationale=(
            "GitHub Actions SKIPS a job output whose value 'may contain "
            "secret', so a cross-job token arrives EMPTY. The mint job "
            "succeeds and the consumer runs with no credential -- the mint "
            "job's own log says it verbatim. MEASURED 2026-11-02 in PMOVES.AI "
            "PR #3445: the reusable workflow .github/workflows/_app-token.yml "
            "was consumed through needs.mint.outputs.token and its only "
            "cross-job consumer failed on 100% of runs."
        ),
        target_file=APPROVE_WORKFLOW,
        test_file=APPROVE_TEST,
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
    """GREEN BEFORE, once for the whole session: the pristine source must pass
    EVERY target test."""
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
            f"{mutation.name}: the pristine source does not pass "
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
    must pass again -- and the source must be byte-identical to the
    original."""
    approve = APPROVE_WORKFLOW.read_text(encoding="utf-8")
    assert "concl=\"$(printf '%s' \"$raw\" | tr '[:lower:]' '[:upper:]')\"" in approve
    assert "GH_TOKEN: ${{ steps.app-token.outputs.token }}" in approve
    assert '[ -n "$checks" ] || refuse "no check runs at head $head' in approve

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
