# pmoves/tools/tests/test_validate_fork_guards.py
"""Tests for the fork-guard gate.

The gate asserts one invariant: no job running on a self-hosted runner may be
reachable from a fork's pull request without a fork guard.

These tests exist because the gate's own failure mode would be silent. A check
that accepts everything looks exactly like a clean tree -- the difference is
only visible if something is deliberately made to fail. So every negative here
is a spelling that READS like a guard and is not, and the coverage test below
fails if a new guard spelling is added to the tool without a case proving it
actually passes.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "validate_fork_guards.py"
REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _run(workflows: dict[str, str]) -> subprocess.CompletedProcess:
    """Write a synthetic workflow directory and run the gate over it."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, body in workflows.items():
            (Path(tmp) / name).write_text(body, encoding="utf-8")
        return subprocess.run(
            [PYTHON, str(TOOL), "--workflows", tmp],
            capture_output=True, text=True,
        )


def _job(cond: str | None = None, runs_on: str = "[self-hosted, Linux]",
         on: str = "[pull_request]") -> str:
    if_line = f"    if: {cond}\n" if cond is not None else ""
    return (
        f"name: T\non: {on}\njobs:\n  j:\n"
        f"    runs-on: {runs_on}\n"
        f"{if_line}"
        f"    steps:\n      - run: echo hi\n"
    )


# --------------------------------------------------------------------------- #
# Guard spellings that MUST pass. Kept beside a coverage test so a spelling
# added to the tool without a case here fails the suite rather than shipping
# unexercised -- the failure mode that let a hand-written guard suite certify
# a class it never tested.
# --------------------------------------------------------------------------- #
SPELLINGS = {
    "full_name": "github.event.pull_request.head.repo.full_name == github.repository",
    "full_name_reversed": "github.repository == github.event.pull_request.head.repo.full_name",
    "repo_id": "github.event.pull_request.head.repo.id == github.repository_id",
    "repo_id_reversed": "github.repository_id == github.event.pull_request.head.repo.id",
    "fork_false": "github.event.pull_request.head.repo.fork == false",
    "fork_false_reversed": "false == github.event.pull_request.head.repo.fork",
    "fork_ne_true": "github.event.pull_request.head.repo.fork != true",
    # The ${{ }} form is mandatory here, not cosmetic: a bare leading `!` is a
    # YAML TAG indicator, so `if: !github...` makes the whole file unparseable.
    "fork_bang": "${{ !github.event.pull_request.head.repo.fork }}",
}


@pytest.mark.parametrize("name", sorted(SPELLINGS))
def test_each_recognised_guard_spelling_passes(name):
    r = _run({"w.yml": _job(SPELLINGS[name])})
    assert r.returncode == 0, f"{name!r} rejected:\n{r.stdout}{r.stderr}"


def test_every_guard_atom_in_the_tool_has_a_case_here():
    """Coverage: a new atom without a test is a spelling nobody proved works."""
    sys.path.insert(0, str(TOOL.parent))
    import validate_fork_guards as v

    # Normalise with the TOOL's own function, not a copy. A second normaliser
    # here could drift from the real one and certify a spelling the gate would
    # actually reject -- which is the duplication this whole gate exists to stop.
    exercised = [v._normalise(s) for s in SPELLINGS.values()]
    for pattern in v.GUARD_ATOMS:
        assert any(pattern.search(e) for e in exercised), (
            f"GUARD_ATOMS entry {pattern.pattern!r} is matched by no entry in "
            f"SPELLINGS — add one so the spelling is proven, not assumed"
        )


def test_event_name_exclusion_guards_when_it_covers_every_fork_trigger():
    body = _job("github.event_name != 'pull_request'", on="[push, pull_request]")
    assert _run({"w.yml": body}).returncode == 0


def test_guard_propagates_through_needs():
    body = (
        "name: T\non: [pull_request]\njobs:\n"
        "  gate:\n    runs-on: ubuntu-latest\n"
        f"    if: {SPELLINGS['full_name']}\n"
        "    steps:\n      - run: echo hi\n"
        "  sh:\n    needs: gate\n    runs-on: [self-hosted, Linux]\n"
        "    steps:\n      - run: echo hi\n"
    )
    assert _run({"w.yml": body}).returncode == 0


def test_job_not_triggered_by_pull_request_is_not_a_finding():
    body = _job(None, on="[push, workflow_dispatch]")
    r = _run({"w.yml": body})
    assert r.returncode == 0
    assert "NOT-REACHABLE" in r.stdout


def test_disabled_job_is_not_a_finding():
    assert _run({"w.yml": _job("false && github.event_name == 'push'")}).returncode == 0


# --------------------------------------------------------------------------- #
# Negatives: each of these READS like a guard, or hides behind a spelling the
# tool must not be fooled by.
# --------------------------------------------------------------------------- #
def test_unguarded_self_hosted_job_fails():
    r = _run({"w.yml": _job(None)})
    assert r.returncode == 1
    assert "UNGUARDED" in r.stdout


def test_repository_owner_is_not_a_guard():
    """Identical on a fork PR -- the BASE repo owns github.repository_owner."""
    r = _run({"w.yml": _job("github.repository_owner == 'POWERFULMOVES'")})
    assert r.returncode == 1


def test_actor_check_is_not_a_guard():
    """A different control, and useless against the real threat here: a TRUSTED
    maintainer labelling an untrusted fork PR."""
    r = _run({"w.yml": _job("github.actor == 'POWERFULMOVES'")})
    assert r.returncode == 1


def test_guard_under_a_top_level_or_is_not_a_guard():
    """`A || B` guards only if BOTH sides guard. A substring matcher passes this."""
    cond = (f"{SPELLINGS['full_name']} || "
            "contains(github.event.pull_request.labels.*.name, 'run-it')")
    assert _run({"w.yml": _job(cond)}).returncode == 1


def test_guard_beside_a_conjunct_still_guards():
    """`A && B` guards if EITHER conjunct does."""
    cond = f"needs.gate.outputs.go == 'true' && {SPELLINGS['full_name']}"
    assert _run({"w.yml": _job(cond)}).returncode == 0


def test_operator_inside_a_string_literal_does_not_split_the_expression():
    """`contains(x, 'a || b')` must not be read as a top-level disjunction."""
    cond = f"contains(github.head_ref, 'a || b') && {SPELLINGS['full_name']}"
    assert _run({"w.yml": _job(cond)}).returncode == 0


def test_always_breaks_guard_propagation_through_needs():
    """always() runs the job even when the guarded dependency was skipped."""
    body = (
        "name: T\non: [pull_request]\njobs:\n"
        "  gate:\n    runs-on: ubuntu-latest\n"
        f"    if: {SPELLINGS['full_name']}\n"
        "    steps:\n      - run: echo hi\n"
        "  sh:\n    needs: gate\n    if: always()\n"
        "    runs-on: [self-hosted, Linux]\n"
        "    steps:\n      - run: echo hi\n"
    )
    assert _run({"w.yml": body}).returncode == 1


def test_runs_on_as_a_bare_string_is_still_detected():
    assert _run({"w.yml": _job(None, runs_on="self-hosted")}).returncode == 1


def test_runs_on_group_mapping_is_still_detected():
    body = (
        "name: T\non: [pull_request]\njobs:\n  j:\n"
        "    runs-on:\n      group: fleet\n      labels: [self-hosted, Linux]\n"
        "    steps:\n      - run: echo hi\n"
    )
    assert _run({"w.yml": body}).returncode == 1


def test_pull_request_target_is_also_treated_as_fork_reachable():
    assert _run({"w.yml": _job(None, on="[pull_request_target]")}).returncode == 1


def test_reusable_workflow_called_from_a_pull_request_is_reachable():
    caller = (
        "name: Caller\non: [pull_request]\njobs:\n"
        "  call:\n    uses: ./.github/workflows/reusable.yml\n"
    )
    reusable = (
        "name: Reusable\non: [workflow_call]\njobs:\n"
        "  sh:\n    runs-on: [self-hosted, Linux]\n"
        "    steps:\n      - run: echo hi\n"
    )
    r = _run({"caller.yml": caller, "reusable.yml": reusable})
    assert r.returncode == 1
    assert "workflow_call" in r.stdout


def test_ubuntu_runner_is_out_of_scope():
    assert _run({"w.yml": _job(None, runs_on="ubuntu-latest")}).returncode == 3


# --------------------------------------------------------------------------- #
# could-not-measure is not a pass
# --------------------------------------------------------------------------- #
def test_empty_directory_reports_could_not_measure_not_success():
    """A zero-finding run over an empty tree must not read as a clean tree."""
    r = _run({})
    assert r.returncode == 3
    assert "COULD-NOT-MEASURE" in r.stderr


def test_missing_directory_reports_could_not_measure():
    r = subprocess.run(
        [PYTHON, str(TOOL), "--workflows", "/nonexistent/path/xyzzy"],
        capture_output=True, text=True,
    )
    assert r.returncode == 3


def test_unparseable_workflow_fails_rather_than_being_skipped():
    """A file the gate cannot read is a gap in coverage, not a pass."""
    r = _run({"good.yml": _job(SPELLINGS["full_name"]),
              "bad.yml": "name: T\n  this: is: not: valid: yaml\n:::\n"})
    assert r.returncode == 1
    assert "UNPARSEABLE" in r.stdout


# --------------------------------------------------------------------------- #
# The invariant itself, on the real tree. This is the regression net.
# --------------------------------------------------------------------------- #
def test_this_repository_satisfies_the_invariant():
    r = subprocess.run(
        [PYTHON, str(TOOL), "--workflows", str(REPO_ROOT / ".github" / "workflows")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        "a self-hosted job is reachable from a fork PR without a guard:\n"
        + r.stdout + r.stderr
    )
