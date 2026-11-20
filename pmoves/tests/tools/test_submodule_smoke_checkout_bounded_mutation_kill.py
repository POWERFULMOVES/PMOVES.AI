"""Mutation-kill harness: the Submodule Smoke Test checkout ratchet must BITE.

The companion harness for
``pmoves/tests/tools/test_submodule_smoke_checkout_bounded_ratchet.py``.

THE KILL CONTRACT: GREEN, RED, GREEN
-------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine workflow must pass the selected tests.
  2. RED AFTER    -- the mutated workflow must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored workflow must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it.

THE MUTATIONS
-------------
  M1  the checkout goes back to `submodules: recursive` (the defect itself);
  M2  the initialisation stops using the changed-submodule list and
      initialises every submodule instead;
  M3  the superproject checkout drops to a shallow fetch, which would break
      the base-commit diff in step 2;
  M4  the initialisation loses its depth bound (full history for everything);
  M5  the full-history fallback is removed, so a pin that is not the branch
      tip can never be fetched.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_submodule_smoke_checkout_bounded_mutation_kill.py -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_ROOT = REPO_ROOT / "pmoves"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "submodule-smoke.yml"

RATCHET = "tests/tools/test_submodule_smoke_checkout_bounded_ratchet.py"

NO_RECURSIVE_TEST = "test_the_smoke_job_does_not_check_out_every_submodule_recursively"
ONLY_CHANGED_TEST = "test_the_smoke_job_initialises_only_the_changed_submodules"
FULL_HISTORY_TEST = "test_the_superproject_checkout_keeps_full_history_for_the_base_diff"
DEPTH_BOUNDED_TEST = "test_the_submodule_init_is_depth_bounded_with_a_full_history_fallback"

ALL_TARGETS = [
    f"{RATCHET}::{NO_RECURSIVE_TEST}",
    f"{RATCHET}::{ONLY_CHANGED_TEST}",
    f"{RATCHET}::{FULL_HISTORY_TEST}",
    f"{RATCHET}::{DEPTH_BOUNDED_TEST}",
]


def _read() -> str:
    with WORKFLOW.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(text: str) -> None:
    with WORKFLOW.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _run_pytest(nodes: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *nodes, "-q", "--tb=no", "-rf"],
        cwd=PMOVES_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _failed_tests(output: str) -> set[str]:
    """The node ids pytest itself reported as FAILED."""
    failed = set()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            node = line[len("FAILED "):].split(" - ")[0].strip()
            failed.add(node)
    return failed


# ── the mutations ────────────────────────────────────────────────────────────

def _mutate_recursive(text: str) -> str:
    """M1: the checkout clones the whole fleet again."""
    assert "submodules: false" in text, "mutation anchor not found"
    return text.replace("submodules: false", "submodules: recursive")


def _mutate_no_changed_list(text: str) -> str:
    """M2: the initialisation stops being driven by the changed list."""
    anchor = 'IFS=\',\' read -ra subs <<< "${{ steps.changed.outputs.submodules }}"'
    assert anchor in text, "mutation anchor not found"
    return text.replace(anchor, "subs=(.)")


def _mutate_shallow_superproject(text: str) -> str:
    """M3: the superproject goes shallow, so the base-commit diff breaks."""
    assert "fetch-depth: 0" in text, "mutation anchor not found"
    return text.replace("fetch-depth: 0", "fetch-depth: 1")


def _mutate_no_depth_bound(text: str) -> str:
    """M4: the initialisation is no longer depth-bounded."""
    assert "--depth 1" in text, "mutation anchor not found"
    return text.replace("--depth 1", "--depth 999999")


def _mutate_no_fallback(text: str) -> str:
    """M5: the full-history fallback is removed."""
    assert "--force" in text, "mutation anchor not found"
    return text.replace("--force", "--no-checkout")


MUTATIONS = [
    ("M1_recursive_checkout", _mutate_recursive, NO_RECURSIVE_TEST),
    ("M2_no_changed_list", _mutate_no_changed_list, ONLY_CHANGED_TEST),
    ("M3_shallow_superproject", _mutate_shallow_superproject, FULL_HISTORY_TEST),
    ("M4_no_depth_bound", _mutate_no_depth_bound, DEPTH_BOUNDED_TEST),
    ("M5_no_fallback", _mutate_no_fallback, DEPTH_BOUNDED_TEST),
]


# ── the harness ──────────────────────────────────────────────────────────────

def test_mutation_kills_are_proven() -> None:
    """Every mutation must turn the NAMED test RED, and the tree must restore."""
    original = _read()

    # 1. GREEN BEFORE -- the pristine workflow passes every target.
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"the pristine workflow is not green before mutation:\n{out}"

    kills: list[str] = []
    try:
        for name, mutate, named_test in MUTATIONS:
            mutated = mutate(original)
            assert mutated != original, f"{name} produced no mutation"
            _write(mutated)

            node = f"{RATCHET}::{named_test}"
            rc, out = _run_pytest([node])
            failed = _failed_tests(out)
            assert rc != 0, f"{name}: {named_test} still passed on the mutated tree:\n{out}"
            assert any(named_test in f for f in failed), (
                f"{name}: expected {named_test} in pytest's failure summary, "
                f"got {sorted(failed)}"
            )
            kills.append(f"{name} -> {named_test}")
    finally:
        _write(original)

    # 3. GREEN AFTER -- the byte-exact restore passes again.
    assert _read() == original, "the workflow was not restored byte-exactly"
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"the restored workflow is not green after mutation:\n{out}"

    assert len(kills) == len(MUTATIONS), f"expected {len(MUTATIONS)} kills, got {kills}"
    print("\nproven kills:")
    for k in kills:
        print(f"  {k}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
