"""
Hand-written workflow-glue tests for .github/workflows/provider-verifier.yml.

Lesson #12/13 from the post-merge fix in PR #2569: workflow YAML
needs code review, not just unit tests. The Python unit tests cover
the helper module; these workflow-glue tests parse the YAML and
assert on the patterns that bind the workflow to the helper's actual
contract (CLI flags, exit codes, paths).

If a future edit changes the workflow in a way that breaks the
binding, these tests catch it before the next PR gets a silent
workflow failure.

Coverage target: 100% of the load-bearing patterns.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


# Repo root is two parents up from pmoves/tests/.
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "provider-verifier.yml"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def workflow() -> dict:
    """The provider-verifier workflow as a parsed dict."""
    if not WORKFLOW_PATH.exists():
        pytest.skip(f"workflow file not present at {WORKFLOW_PATH}")
    with WORKFLOW_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    """The raw workflow file as a string (for grep-style assertions)."""
    if not WORKFLOW_PATH.exists():
        pytest.skip(f"workflow file not present at {WORKFLOW_PATH}")
    return WORKFLOW_PATH.read_text(encoding="utf-8")


# ============================================================================
# Trigger configuration
# ============================================================================


def _triggers(workflow: dict) -> dict:
    """Get the trigger block. YAML 1.1 parses `on:` as Python `True`,
    so this normalizes the key access."""
    return workflow.get(True) or workflow.get("on") or {}


def test_workflow_triggers_on_pull_request(workflow: dict) -> None:
    """The workflow must run on PRs to main (the static gate's primary trigger)."""
    triggers = _triggers(workflow)
    assert "pull_request" in triggers, (
        "pull_request trigger missing — the static gate won't run on PRs"
    )
    pr = triggers["pull_request"]
    # The PR trigger should target main, not a feature branch.
    branches = pr.get("branches", [])
    assert "main" in branches, (
        f"pull_request.branches must include 'main'; got {branches}"
    )


def test_workflow_has_no_paths_filter(workflow: dict) -> None:
    """on.pull_request must NOT carry a paths: filter.

    This gate is intended to become a required status check, and GitHub is
    explicit: "If a workflow is skipped due to path filtering ... checks
    associated with that workflow will remain in a Pending state. A pull request
    that requires those checks to be successful will be blocked from merging."
    A skipped WORKFLOW never reports; a skipped JOB reports success. So the path
    decision belongs in the job, not the trigger -- see the two tests below,
    which assert the same coverage in its new home.
    """
    pr = _triggers(workflow)["pull_request"]
    assert "paths" not in (pr or {}), (
        "on.pull_request must not filter by paths: a required check that never "
        "reports blocks every PR that touches none of those paths. Move the "
        "condition into the job (steps.changed) instead."
    )


def test_job_condition_covers_submodule(workflow_text: str) -> None:
    """The job-level path condition must still cover the verifier submodule.

    Same guarantee the old paths: filter carried -- a PR adding a provider to the
    cascade touches the submodule and must run the gate -- asserted where the
    decision now lives.
    """
    assert "Pmoves-MiniMax-Provider-Verifier/*)" in workflow_text, (
        "the `changed` step's case must match Pmoves-MiniMax-Provider-Verifier/*"
    )


def test_job_condition_covers_helper(workflow_text: str) -> None:
    """The job-level path condition must still cover the gate helper."""
    assert "pmoves/tools/provider_verifier_gate.py)" in workflow_text, (
        "the `changed` step's case must match pmoves/tools/provider_verifier_gate.py"
    )


def test_working_steps_are_gated_on_the_condition(workflow_text: str) -> None:
    """The work must be conditional even though the job is not.

    If the steps ran unconditionally the gate would execute on every PR in the
    repo; if the JOB were conditional it would stop reporting. Both halves matter.
    """
    assert "steps.changed.outputs.relevant == 'true'" in workflow_text, (
        "the gate steps must be guarded by the computed condition"
    )


def test_workflow_supports_workflow_dispatch(workflow: dict) -> None:
    """workflow_dispatch must be present for manual full-conformance runs.

    The static gate is the PR-time check; the operator-triggered full
    run (with real API keys) is workflow_dispatch. Without dispatch
    the operator has no way to run the full verifier from CI.
    """
    assert "workflow_dispatch" in _triggers(workflow), (
        "workflow_dispatch trigger missing — operator can't run the "
        "full conformance check from CI"
    )


# ============================================================================
# Permissions + concurrency
# ============================================================================


def test_workflow_has_minimal_permissions(workflow: dict) -> None:
    """permissions must be {} at the workflow level (no scopes the workflow as a whole needs).

    A workflow that inherits the default GITHUB_TOKEN can do too
    much. The static gate doesn't need any token scope (it just
    reads files); the job-level override adds `issues: write` for
    the PR-comment step.
    """
    assert workflow.get("permissions") == {}, (
        f"workflow-level permissions should be {{}} for minimal scope; "
        f"got {workflow.get('permissions')}"
    )


def test_workflow_job_has_issues_write_for_comment_step(workflow: dict) -> None:
    """The static-gate job must declare issues: write (for the PR comment step).

    actions/github-script uses the default GITHUB_TOKEN scope. With
    workflow-level `permissions: {}` the token has no scopes, so
    the PR-comment step would fail with a permissions error. The
    job-level override is the minimum scope that lets the comment
    step post.
    """
    job = workflow["jobs"]["static-gate"]
    perms = job.get("permissions", {})
    assert perms.get("issues") == "write", (
        f"job-level permissions.issues must be 'write' for the PR-comment step; "
        f"got {perms}"
    )


def test_workflow_has_concurrency_block(workflow_text: str) -> None:
    """The workflow must declare concurrency to avoid parallel gate runs on the same PR.

    Two concurrent runs against the same PR double the gate's work
    and create ambiguous status checks. The block is required.
    """
    assert "concurrency:" in workflow_text, (
        "concurrency block missing — re-runs of the same PR will "
        "race the gate"
    )


# ============================================================================
# Job + step configuration
# ============================================================================


def test_workflow_has_static_gate_job(workflow: dict) -> None:
    """The workflow must have a 'static-gate' job (matches merge-gate reference)."""
    jobs = workflow.get("jobs", {})
    assert "static-gate" in jobs, (
        f"static-gate job missing — merge-gate won't see the status check; "
        f"jobs: {list(jobs.keys())}"
    )


def test_workflow_job_name_is_verifier_gate(workflow: dict) -> None:
    """The job's name must be 'verifier-gate' (the status check name).

    merge-gate.yml references the status check by its job name. If the
    job name changes, the merge-gate config goes stale and the gate
    doesn't block merge on FAIL.
    """
    job = workflow["jobs"]["static-gate"]
    assert job.get("name") == "verifier-gate", (
        f"job name is {job.get('name')!r}; expected 'verifier-gate' "
        "(this is the status check name consumed by merge-gate)"
    )


def test_workflow_checkout_pins_submodules_recursive(workflow_text: str) -> None:
    """The checkout step must use submodules: recursive.

    Pmoves-MiniMax-Provider-Verifier/ is a submodule. Without
    submodules: recursive, the verifier's directory is empty in
    the runner, and the gate fails on check #1 (verifier_submodule_present).
    """
    # Look for the checkout step with submodules: recursive.
    pattern = re.compile(
        r"uses:\s*actions/checkout@[^\n]*\s*\n\s*with:\s*\n\s*submodules:\s*recursive",
        re.MULTILINE,
    )
    assert pattern.search(workflow_text), (
        "checkout step must use 'submodules: recursive' so the "
        "Pmoves-MiniMax-Provider-Verifier/ submodule is on disk"
    )


def test_workflow_uses_pinned_checkout(workflow_text: str) -> None:
    """The checkout action must be pinned to a SHA (not a version tag).

    Tag-pinned actions can be re-pointed by their author. SHA-pinned
    actions can't. The other workflows in this repo follow the SHA
    convention; this one should too.
    """
    # Look for actions/checkout@<40-char hex>
    pattern = re.compile(r"uses:\s*actions/checkout@[a-f0-9]{40}")
    assert pattern.search(workflow_text), (
        "checkout action must be pinned to a 40-char SHA, not a version tag"
    )


# ============================================================================
# CLI invocation pattern
# ============================================================================


def test_workflow_invokes_helper_with_json_flag(workflow_text: str) -> None:
    """The run step must invoke the helper with --json (for the step summary)."""
    assert "provider_verifier_gate.py" in workflow_text, (
        "the helper module must be invoked by the workflow"
    )
    assert "--json" in workflow_text, (
        "--json flag must be passed so the step summary gets the "
        "structured verdict"
    )


def test_workflow_captures_exit_code_via_RC(workflow_text: str) -> None:
    """The run step must capture the helper's exit code (lesson #13).

    The post-merge fix in PR #2569 caught a class of bugs where
    a `set -e` plus a pipeline masked publisher failures. The
    provider-verifier gate uses the same pattern: `set +e ... ; RC=$? ... set -e`
    to capture BOTH the output and the exit code.
    """
    # Look for the explicit RC capture pattern.
    assert "RC=$?" in workflow_text, (
        "run step must capture exit code via RC=$? (lesson #13: "
        "set -e alone masks pipeline failures)"
    )
    assert "set +e" in workflow_text or "set +e " in workflow_text, (
        "run step must disable set -e around the helper invocation "
        "to capture both output and exit code"
    )


# ============================================================================
# End-to-end: workflow + helper agree on the contract
# ============================================================================


def test_workflow_helper_exit_code_round_trips(workflow_text: str) -> None:
    """The workflow's RC variable is used to exit with the helper's code.

    A workflow that ignores RC and exits 0 always silently swallows
    FAIL. The contract: when the helper exits 1, the workflow exits 1.
    """
    # Look for 'exit "$RC"' or 'exit $RC' in the run step.
    assert re.search(r"exit\s+\"\$\{?RC\}?\"", workflow_text), (
        "run step must propagate the helper's exit code via 'exit \"$RC\"' "
        "or 'exit $RC' — without this, the gate is silently a no-op on FAIL"
    )


# ============================================================================
# Cross-workflow contract: merge-gate consumes the verifier-gate status
# ============================================================================


MERGE_GATE_PATH = REPO_ROOT / ".github" / "workflows" / "merge-gate.yml"


@pytest.fixture(scope="module")
def merge_gate_text() -> str:
    """The merge-gate workflow as a string."""
    if not MERGE_GATE_PATH.exists():
        pytest.skip(f"merge-gate.yml not present at {MERGE_GATE_PATH}")
    return MERGE_GATE_PATH.read_text(encoding="utf-8")


def test_merge_gate_does_not_reference_verifier_gate(merge_gate_text: str) -> None:
    """merge-decision must NOT list verifier-gate in `needs`.

    `needs` resolves only job IDs declared in the SAME workflow. `verifier-gate`
    is the display name of the `static-gate` job in provider-verifier.yml, so
    naming it here makes merge-gate.yml invalid — and merge-decision is a
    REQUIRED check on main, so it would never report and every PR in the repo
    would block on a check that cannot run.

    This test previously asserted the opposite. It was written to match the
    implementation rather than the requirement, so it passed while locking the
    defect in place. Gating on the verifier is done by adding its check to
    branch protection's required list, which is an operator action and cannot
    be expressed through `needs`.
    """
    assert "verifier-gate" not in merge_gate_text, (
        "merge-gate.yml must not reference 'verifier-gate' — it is a job in a "
        "different workflow, and an unresolvable `needs` invalidates the whole "
        "workflow, taking the required merge-decision check down with it"
    )


def test_merge_decision_requires_success_not_merely_not_failure(merge_gate_text: str) -> None:
    """Every merge-decision dependency must be required to equal 'success'.

    needs.<job>.result is one of success | failure | cancelled | skipped.
    Testing only for == 'failure' lets cancelled and skipped through, so a run
    that never evaluated a gate reports PASSED (see #2622).
    """
    assert '!= "success"' in merge_gate_text, (
        "merge-decision must require each dependency to equal 'success', not "
        "merely reject 'failure'"
    )


def test_workflow_invokes_python_not_the_windows_launcher(workflow_text: str) -> None:
    """The gate step must invoke `python`, not `py`.

    The job is runs-on: ubuntu-latest and actions/setup-python exposes the
    selected interpreter as `python`. `py` is the Windows launcher and is not
    present on the Ubuntu runner: the step would exit 127, set verdict=FAIL,
    and block every PR matching the path filter without running a check.

    This test previously asserted `py`, justified as "the GitHub-bundled alias"
    that "the other workflows in this repo use". Both halves are false --
    measured across .github/workflows/: ZERO workflows invoke bare `py`, and 27
    use `python`/`python3`.
    """
    assert "python " + "pmoves/tools/provider_verifier_gate" in workflow_text, (
        "the gate step must invoke the helper via 'python'"
    )
    assert "$(py " + "pmoves/tools/provider_verifier_gate" not in workflow_text, (
        "'py' is the Windows launcher and does not exist on ubuntu-latest"
    )

def test_helper_supports_json_flag() -> None:
    """The helper must support --json (workflow depends on it).

    This is the tool-contract test: the workflow calls
    `py ... --json` and the helper must accept that flag. If a
    future helper refactor drops --json, the workflow's step
    summary becomes empty.
    """
    result = subprocess.run(
        [sys.executable, "-m", "tools.provider_verifier_gate", "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT / "pmoves",
        env={"PYTHONPATH": str(REPO_ROOT / "pmoves")},
    )
    assert "--json" in result.stdout, (
        f"helper --help must mention --json; got: {result.stdout!r}"
    )


def test_detection_runs_before_checkout(workflow: dict) -> None:
    """The applicability check must not sit behind a 9-minute checkout.

    `submodules: recursive` over this monorepo's 72 submodules measured 9m15s
    on run 32294521610, after which the detection step took 2s to conclude the
    PR was irrelevant and every working step skipped. As a REQUIRED check that
    cost is paid by every pull request in the repo, almost none of which touch
    the verifier surface.

    The detection step reads no working-tree state -- it asks the PR files API
    and names the repo via github.repository -- so it can and must run first.
    """
    steps = workflow["jobs"]["static-gate"]["steps"]
    names = [s.get("name", "") for s in steps]

    detect = next(i for i, n in enumerate(names) if "verifier surface" in n)
    checkout = next(i for i, n in enumerate(names) if "Checkout" in n)

    assert detect < checkout, (
        "the detection step must precede checkout; found detect at "
        f"{detect} and checkout at {checkout}"
    )
    # ...and the checkout itself must be conditional, or the cost is unchanged.
    assert steps[checkout].get("if") == "steps.changed.outputs.relevant == 'true'"
    # The detection step must NOT be conditional -- it is what decides.
    assert "if" not in steps[detect]
