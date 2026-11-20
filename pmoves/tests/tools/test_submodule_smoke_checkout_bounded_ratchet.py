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
  5. The initialisation is NOT ``--recursive``. ``Pmoves-cipher`` carries a
     NESTED submodule (``packages/byterover-packages``) whose URL is an SSH
     path to a THIRD-PARTY repo the runner has no key for, and which this
     job does not need -- MEASURED: with ``--recursive`` the init loop dies
     with "Failed to clone 'packages/byterover-packages' a second time,
     aborting".
  6. The full-history fallback CLEANS the partial module state before it
     retries. A failed shallow clone leaves ``.git/modules/<path>``
     half-built; retrying without removing it fails IDENTICALLY -- MEASURED:
     the first attempt died with "fatal: Needed a single revision" followed
     by "fatal: Unable to find current revision in submodule path
     'PMOVES-Wealth'", and the retry produced the same two lines.
  7. The changed-submodule detection reads the two TREES, not the diff.
     ``git diff`` honours the ``ignore`` setting in ``.gitmodules``, and this
     repo sets ``ignore = all`` for PMOVES-OpenRoom and PMOVES-registry --
     MEASURED on PR #3482: the diff listed 11 of the 13 promoted
     submodules, and the gate reported those 11.
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


def _detect_step() -> dict:
    for step in _steps():
        name = str(step.get("name") or "")
        if "identify" in name.lower() and "submodule" in name.lower():
            return step
    raise AssertionError("the smoke job has no changed-submodule detection step")


def _detect_script() -> str:
    """The detection step's script, with COMMENT-ONLY lines removed.

    The step's own comment explains the defect and quotes
    ``git diff --name-only`` by name; a substring assertion over the raw
    text would fail on the comment that documents the invariant.
    """
    return _strip_comments(str(_detect_step().get("run") or ""))


def _detect_script_raw() -> str:
    """The detection step's script verbatim, comments included."""
    return str(_detect_step().get("run") or "")


def _strip_comments(script: str) -> str:
    """Drop comment-only lines.

    The prose around these steps explains WHY each invariant holds, and that
    prose quotes the very strings the assertions forbid -- "NOT --recursive",
    "`git diff --name-only`". A substring assertion over the raw text would
    therefore fail on the comment that documents the invariant. Only
    comment-only lines are removed; nothing else about the script is
    rewritten.
    """
    code = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    return "\n".join(code)


def _init_script() -> str:
    """The init step's script, with COMMENT-ONLY lines removed."""
    return _strip_comments(str(_init_step().get("run") or ""))


def _init_script_raw() -> str:
    """The init step's script verbatim, comments included."""
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


def test_the_submodule_init_is_not_recursive() -> None:
    """``--recursive`` drags in a nested third-party submodule we cannot fetch.

    ``Pmoves-cipher`` pins ``packages/byterover-packages``, whose URL is
    ``git@github.com:campfirein/byterover-packages.git`` -- an SSH path to a
    THIRD-PARTY repository the self-hosted runner has no key for. The job
    verifies the changed submodule's OWN tree and then runs the SUPERPROJECT's
    ``make smoke test``; the nested package is never read.

    MEASURED locally against a faithful superproject carrying the 13 real
    pins: with ``--recursive``, the init loop aborts at ``Pmoves-cipher``
    with "Failed to clone 'packages/byterover-packages' a second time,
    aborting"; without it, 12 of 13 submodules initialise and the 13th
    succeeds on the full-history fallback.
    """
    script = _init_script()
    assert "--recursive" not in script, (
        "the initialisation step uses `--recursive`, which pulls in nested "
        "third-party submodules (Pmoves-cipher -> packages/byterover-packages, "
        "an SSH URL to a third-party repo the runner has no key for) and "
        "aborts the whole init loop"
    )


def test_the_full_history_fallback_cleans_the_partial_module_state() -> None:
    """The retry must not inherit the failed shallow clone's half-built state.

    A failed ``git submodule update --init --depth 1`` leaves
    ``.git/modules/<path>`` populated. Retrying the full-history fetch
    without removing it produces the SAME failure -- MEASURED on
    ``PMOVES-Wealth``: "fatal: Needed a single revision" then "fatal: Unable
    to find current revision in submodule path 'PMOVES-Wealth'", on the
    first attempt and again on the retry.

    So the fallback must deinitialise the module and remove its module
    directory BEFORE retrying, and the cleanup must come BEFORE the retry --
    a cleanup that runs afterwards is a cleanup that never runs.
    """
    script = _init_script()
    deinit = "git submodule deinit -f"
    purge = 'rm -rf ".git/modules/'
    retry = "git submodule update --init --force"

    assert deinit in script, (
        "the full-history fallback does not deinitialise the failed module -- "
        "the retry inherits the partial state and fails identically"
    )
    assert purge in script, (
        "the full-history fallback does not remove the half-built module "
        "directory under .git/modules -- the retry inherits the partial "
        "state and fails identically"
    )
    assert retry in script, (
        "the full-history fallback does not retry the submodule update"
    )
    assert script.index(deinit) < script.index(retry), (
        "the partial-state cleanup runs AFTER the retry -- a cleanup that "
        "runs afterwards is a cleanup that never runs"
    )
    assert script.index(purge) < script.index(retry), (
        "the .git/modules cleanup runs AFTER the retry -- a cleanup that runs "
        "afterwards is a cleanup that never runs"
    )


def test_the_changed_submodule_detection_reads_both_trees_not_the_diff() -> None:
    """The gate must SEE every gitlink the PR changed.

    ``git diff`` honours the ``ignore`` setting in ``.gitmodules``, and this
    repo sets ``ignore = all`` for PMOVES-OpenRoom and PMOVES-registry.
    MEASURED on PR #3482: ``git diff --name-only base..head`` listed only
    ELEVEN of the THIRTEEN promoted submodules -- the two ``ignore = all``
    paths were invisible -- and the job's own "Post results as PR comment"
    step reported those eleven. The gate would have verified 11 of its 13
    inputs and reported success: a FAIL-OPEN gate.

    ``git ls-tree`` is the authoritative read: no ``.gitmodules`` setting and
    no diff-side configuration can hide a path from it. And a gitlink is
    "changed" only when its SHA differs BETWEEN THE TWO TREES, so both trees
    must be read.
    """
    script = _detect_script()
    assert "git diff --name-only" not in script, (
        "the changed-submodule detection uses `git diff --name-only`, which "
        "honours the `ignore` setting in .gitmodules -- MEASURED on PR #3482 "
        "that listed 11 of the 13 promoted submodules and silently skipped "
        "PMOVES-OpenRoom and PMOVES-registry, which .gitmodules marks "
        "`ignore = all`"
    )
    assert script.count("git ls-tree") >= 2, (
        "the detection does not read BOTH trees -- a gitlink counts as changed "
        "only when its SHA differs between base and head, so one tree is not "
        "enough"
    )
    assert '"$base_sha"' in script and '"$head_sha"' in script, (
        "the detection does not read both the base and the head tree"
    )
