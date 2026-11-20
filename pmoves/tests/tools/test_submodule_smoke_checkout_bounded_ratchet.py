"""Ratchet: the Submodule Smoke Test must not clone the whole fleet.

THE DEFECT THIS GUARDS
-----------------------
``.github/workflows/submodule-smoke.yml`` used to check out with::

    submodules: recursive
    fetch-depth: 0

On a repo with 84 submodules that clones EVERY submodule at FULL history. The
job then dies inside "Checkout PR branch" with 30+ concurrent
``git-remote-https`` / ``git-submodule`` processes still running, when
``timeout-minutes: 45`` fires -- MEASURED on PR #3482 (the 13-gitlink
promotion lane): runs 44639462331 and 44649240426 both ran 45.6m and were
cancelled in that step, and the job never reached step 2.

The clone was pure waste. "Identify changed submodules" diffs the SUPERPROJECT
tree (``git diff base..head`` + ``git ls-tree``) and every step after it reads
only the CHANGED submodule paths. So the job cloned 84 repositories to use 13.

WHY THESE ASSERTIONS AND NOT OTHERS
------------------------------------
The interesting property is not "the word recursive is absent" -- it is that
the job clones a BOUNDED set of submodules, and that the superproject keeps
the history step 2 needs. A ratchet that only banned one string would be
satisfied by deleting the checkout entirely, which would break the job in a
different way. So each assertion below names a capability, and the mutation
harness proves each one BITES a NAMED test.

THE INVARIANTS
--------------
  1. The smoke job's checkout does NOT recursively clone submodules.
  2. There IS a step that initialises submodules, and it uses the CHANGED
     list -- not every path.
  3. The superproject checkout keeps ``fetch-depth: 0``, because step 2
     diffs against the base commit, which a shallow superproject lacks.
  4. The initialisation is depth-bounded, with a full-history fallback for a
     pin that is not the branch tip (a promotion lane pins arbitrary
     commits, and a shallow clone cannot fetch an unadvertised one).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "submodule-smoke.yml"

SMOKE_JOB = "smoke-test"


def _workflow() -> dict:
    with WORKFLOW.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _smoke_job() -> dict:
    jobs = _workflow().get("jobs") or {}
    assert SMOKE_JOB in jobs, (
        f"the workflow no longer has a {SMOKE_JOB!r} job -- jobs: {sorted(jobs)}"
    )
    return jobs[SMOKE_JOB]


def _steps() -> list[dict]:
    steps = _smoke_job().get("steps") or []
    assert steps, "the smoke job has no steps"
    return steps


def _checkout_step() -> dict:
    for step in _steps():
        uses = str(step.get("uses") or "")
        if uses.startswith("actions/checkout@"):
            return step
    raise AssertionError("the smoke job has no actions/checkout step")


def _init_step() -> dict:
    for step in _steps():
        name = str(step.get("name") or "")
        if "initialise" in name.lower() or "initialize" in name.lower():
            return step
    raise AssertionError("the smoke job has no submodule-initialisation step")


def _init_script() -> str:
    return str(_init_step().get("run") or "")


def test_the_smoke_job_does_not_check_out_every_submodule_recursively() -> None:
    """A recursive checkout clones all 84 submodules at full history."""
    with_block = _checkout_step().get("with") or {}
    assert str(with_block.get("submodules", "")).lower() != "recursive", (
        "the smoke job checks out with `submodules: recursive`, which clones "
        "every submodule in the repo at full history -- that is what blew the "
        "45-minute job timeout on PR #3482"
    )


def test_the_smoke_job_initialises_only_the_changed_submodules() -> None:
    """The initialisation must be driven by the changed list."""
    script = _init_script()
    assert "steps.changed.outputs.submodules" in script, (
        "the initialisation step does not use the changed-submodule list -- "
        "it must not initialise the whole fleet"
    )
    assert "git submodule update" in script, (
        "the initialisation step does not run `git submodule update`"
    )


def test_the_superproject_checkout_keeps_full_history_for_the_base_diff() -> None:
    """Step 2 diffs against the base commit, which a shallow clone lacks."""
    with_block = _checkout_step().get("with") or {}
    assert "fetch-depth" in with_block, (
        "the smoke job's checkout does not state a fetch-depth"
    )
    assert int(with_block["fetch-depth"]) == 0, (
        "the superproject checkout must keep fetch-depth: 0 -- "
        "'Identify changed submodules' diffs against the base commit"
    )


def test_the_submodule_init_is_depth_bounded_with_a_full_history_fallback() -> None:
    """A shallow clone cannot fetch a pin that is not the branch tip."""
    script = _init_script()
    assert "--depth 1" in script, (
        "the initialisation is not depth-bounded -- a full-history clone of "
        "every changed submodule is what exhausted the job budget"
    )
    assert "--force" in script, (
        "the initialisation has no full-history fallback -- a promotion lane "
        "pins arbitrary commits, and a shallow clone cannot fetch an "
        "unadvertised one"
    )
