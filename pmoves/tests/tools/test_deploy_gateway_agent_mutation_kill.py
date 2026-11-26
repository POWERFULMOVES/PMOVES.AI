"""Mutation-kill harness: the deploy-gateway-agent gates must BITE when the
defect is put back.

THE DEFECT CLASS
----------------
`deploy-gateway-agent.yml` had failed on EVERY push to main since 2026-09-28,
and the cause was three placeholder variables that had drifted out of the
workflow's hand-maintained mirror of `pmoves/docker-compose.yml`'s `:?`
guards. On top of that, the workflow's `paths:` filter lists the workflow
file ITSELF, so editing the deploy config re-triggered the live deploys.

That is a harder class to gate than application code, because a workflow file
is read by GitHub, not imported by Python -- so a test that re-implements the
workflow's logic in Python proves only that the author believed the logic.
The gates here therefore SLICE the real shell out of the workflow file and RUN
it, and this harness is what proves those slices are load-bearing.

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

    python -m pytest pmoves/tests/tools/test_deploy_gateway_agent_mutation_kill.py -v

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
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-gateway-agent.yml"

DEPLOY_ENV_TEST = (
    REPO_ROOT / "pmoves" / "tests" / "tools" / "test_deploy_gateway_agent_env.py"
)
DEPLOY_CHANGE_TEST = (
    REPO_ROOT / "pmoves" / "tests" / "tools" / "test_deploy_gateway_agent_change_gate.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-deploy-gateway-mutation.lock"


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
    # the placeholder mirror of docker-compose.yml's `:?` guards
    # ------------------------------------------------------------------
    Mutation(
        name="M1_supabase_jwt_secret_dropped_from_the_build_env",
        old="""          CHIT_PASSPHRASE: ci-build-placeholder
          SECRET_KEY: ci-build-placeholder
          SUPABASE_JWT_SECRET: ci-build-placeholder""",
        new="""          CHIT_PASSPHRASE: ci-build-placeholder
          SECRET_KEY: ci-build-placeholder""",
        target_test="test_every_compose_step_satisfies_every_required_guard",
        rationale=(
            "`docker compose` interpolates the WHOLE compose file before it "
            "acts on any service, so a `:?` guard owned by a service this "
            "workflow does not deploy still blocks the build. SUPABASE_JWT_"
            "SECRET belongs to a2ui-renderer. MEASURED 2026-11-05: its "
            "absence from every build/deploy/rollback block is the cause of "
            "every failed run since 2026-09-28."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_ENV_TEST,
    ),
    Mutation(
        name="M2_secret_key_dropped_from_the_deploy_env",
        old="""          CHIT_PASSPHRASE: ci-deploy-placeholder
          SECRET_KEY: ci-deploy-placeholder
          SUPABASE_JWT_SECRET: ci-deploy-placeholder""",
        new="""          CHIT_PASSPHRASE: ci-deploy-placeholder
          SUPABASE_JWT_SECRET: ci-deploy-placeholder""",
        target_test="test_every_compose_step_satisfies_every_required_guard",
        rationale=(
            "SECRET_KEY belongs to tokenism-simulator, and the placeholder "
            "list carried the near-miss SECRET_KEY_BASE instead -- which is "
            "why the drift survived a month of red runs unnoticed."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_ENV_TEST,
    ),
    Mutation(
        name="M3_chit_passphrase_dropped_from_the_rollback_env",
        old="""          CHIT_PASSPHRASE: ci-rollback-placeholder
          SECRET_KEY: ci-rollback-placeholder
          SUPABASE_JWT_SECRET: ci-rollback-placeholder""",
        new="""          SECRET_KEY: ci-rollback-placeholder
          SUPABASE_JWT_SECRET: ci-rollback-placeholder""",
        target_test="test_every_compose_step_satisfies_every_required_guard",
        rationale=(
            "CHIT_PASSPHRASE belongs to wger-nats-bridge. The rollback block "
            "carried the near-miss CHIT_PROD_PASSPHRASE instead, so a "
            "rollback could not parse the compose file either -- the safety "
            "net was as broken as the deploy it was meant to undo."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_ENV_TEST,
    ),
    # ------------------------------------------------------------------
    # the change-detection gate
    # ------------------------------------------------------------------
    Mutation(
        name="M4_the_changes_job_removed",
        old="""  changes:
    name: Detect deploy-relevant changes""",
        new="""  changes-removed:
    name: Detect deploy-relevant changes""",
        target_test="test_a_workflow_only_change_does_not_deploy",
        rationale=(
            "The `changes` job is the second layer that keeps the workflow's "
            "own path filter from deploying to the fleet. Without it, editing "
            "the workflow re-triggers the live deploys to ai-lab and the VPS."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_CHANGE_TEST,
    ),
    Mutation(
        name="M5_a_workflow_file_change_allowed_to_deploy",
        old="""          if printf '%s\\n' "$changed" | grep -Eq '^\\.github/workflows/deploy-gateway-agent\\.yml$'; then
            build=true
          fi""",
        new="""          if printf '%s\\n' "$changed" | grep -Eq '^\\.github/workflows/deploy-gateway-agent\\.yml$'; then
            build=true
            deploy=true
          fi""",
        target_test="test_a_workflow_only_change_does_not_deploy",
        rationale=(
            "This is the PRE-FIX behaviour, written out: a workflow-file "
            "change is deploy-relevant. It is how PR #3445's merge re-"
            "triggered a month-dead pipeline -- the operator's own note was "
            "that the merge 'did not cause it ... but it did re-trigger it'."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_CHANGE_TEST,
    ),
    Mutation(
        name="M6_the_vps_deploy_job_loses_its_gate",
        old="""    needs: [validate, changes]
    if: needs.validate.result == 'success' && needs.changes.outputs.deploy == 'true'""",
        new="""    needs: [validate, changes]""",
        target_test="test_every_job_that_consumes_the_detection_is_gated_on_it",
        rationale=(
            "A job that consumes the detection output but does not gate on it "
            "runs unconditionally -- which is exactly the behaviour the gate "
            "removes."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_CHANGE_TEST,
    ),
    Mutation(
        name="M7_the_explicit_dependency_success_clause_dropped",
        old="""    if: needs.validate.result == 'success' && needs.changes.outputs.build == 'true'""",
        new="""    if: needs.changes.outputs.build == 'true'""",
        target_test="test_a_gated_job_states_its_dependency_success_explicitly",
        rationale=(
            "GitHub applies the implicit `success()` ONLY when the condition "
            "names no status function. A job-level `if:` that reads "
            "`needs.changes.outputs.build` therefore runs even when `validate` "
            "FAILED. The dependency's result has to be stated out loud."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_CHANGE_TEST,
    ),
    Mutation(
        name="M8_the_rollback_gated_on_failure_again",
        old="""    if: needs.deploy-ai-lab.result == 'failure' || needs.deploy-ai-lab.result == 'cancelled'""",
        new="""    if: failure() || cancelled()""",
        target_test="test_a_rollback_is_gated_on_the_deploy_job_not_on_the_whole_chain",
        rationale=(
            "`failure()` is TRUE WHEN ANY ANCESTOR JOB FAILED. The `changes` "
            "job is an ancestor of the deploy jobs, so a fail-closed detection "
            "failure -- the exact case where NOTHING was deployed -- would "
            "make `failure()` true and ARM this rollback. Its steps then stop "
            "and remove the currently HEALTHY gateway-agent: the gate that "
            "refused to deploy would tear the service down instead. This is "
            "the finding the codex review bot raised on PR #3455."
        ),
        target_file=DEPLOY_WORKFLOW,
        test_file=DEPLOY_CHANGE_TEST,
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
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "  changes:\n    name: Detect deploy-relevant changes" in deploy
    assert "needs.changes.outputs.deploy == 'true'" in deploy
    assert "SUPABASE_JWT_SECRET: ci-build-placeholder" in deploy
    assert "needs.deploy-ai-lab.result == 'failure'" in deploy
    assert "needs.deploy-vps.result == 'failure'" in deploy

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
