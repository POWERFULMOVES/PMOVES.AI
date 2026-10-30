#!/usr/bin/env python3
# test_minimax_roster_provisioning_mutation_kill.py
# ============================================================================
# Mutation-kill harness for the MiniMax MCP roster provisioning slice.
#
# WHAT THIS PROVES. A test suite that passes proves nothing on its own --
# it proves that the tests agree with the code. This harness proves the
# tests would NOTICE if the code regressed: for each defect this slice
# fixed, it breaks the fix on purpose and asserts that a named test goes
# RED.
#
# THE RULE (learned the hard way in the test-gap ratchet slice): the
# harness must MUTATE THE PRODUCTION CODE and run the real test file. It
# must never restate the assertion it expects to fail. A harness that
# re-implements the check proves only that the harness agrees with itself.
#
# THE MUTATIONS. Each one is a SINGLE, SURGICAL change to the shipped
# source -- the smallest edit that reintroduces the exact defect the
# corresponding review finding named:
#
#   M1  the roster block is never turned on
#       -> the launcher goes back to sourcing env.shared and exec'ing the
#          binary, so a fresh host never gets the seven-server roster.
#   M2  the repo-relative `command` is not absolutized
#   M3  the repo-relative `args` are not absolutized
#       -> `uv --directory ./pmoves-nats-mcp` is resolved against the
#          caller's cwd, so the NATS server cannot start from outside the
#          repo.
#   M4  the runtime-managed restore is not WIRED into the write path
#       -> the helper still exists and still works, but nothing calls it,
#          so a regeneration resets `configured` / `builtin`.
#
# Run:
#   python -m pytest pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py -v
# ============================================================================

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = "pmoves/tests/test_minimax_mcp_roster_provisioning.py"

LAUNCHER_GEN = REPO_ROOT / "pmoves" / "tools" / "pmoves_launcher_generator.py"
CONFIG_GEN = REPO_ROOT / "pmoves" / "tools" / "mcp_config_generator.py"


def _run_pytest(node_id: str) -> subprocess.CompletedProcess:
    """Run one test from the real test file in a child interpreter."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", f"{TEST_FILE}::{node_id}", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _apply_mutation(target: Path, old: str, new: str) -> bytes:
    """Mutate *target* in place, returning the original bytes for restore."""
    original = target.read_bytes()
    text = original.decode("utf-8")
    assert old in text, (
        f"mutation anchor not found in {target.name}; the harness is stale "
        f"and would silently pass. Anchor was:\n{old}"
    )
    assert text.count(old) == 1, (
        f"mutation anchor is not unique in {target.name} "
        f"(found {text.count(old)} times) -- it would mutate more than intended"
    )
    target.write_text(text.replace(old, new), encoding="utf-8")
    return original


def _restore(target: Path, original: bytes) -> None:
    target.write_bytes(original)
    assert target.read_bytes() == original, f"failed to restore {target.name}"


# ---------------------------------------------------------------------------
# The mutations
# ---------------------------------------------------------------------------

M1_OLD = '''ROSTER_CLIENT_BY_FAMILY: dict[str, tuple[str, str]] = {
    # family -> (mcp_config_generator client name, --endpoint mode)
    "minimax": ("minimax", "local"),
}'''
M1_NEW = '''ROSTER_CLIENT_BY_FAMILY: dict[str, tuple[str, str]] = {
    # family -> (mcp_config_generator client name, --endpoint mode)
}'''

M2_OLD = '            entry["command"] = _abs_repo_relative(command, root)'
M2_NEW = '            entry["command"] = command'

M3_OLD = '            abs_args = [_abs_repo_relative(a, root) for a in args]'
M3_NEW = '            abs_args = list(args)'

M4_OLD = '            final = _restore_minimax_runtime_managed(existing, final)'
M4_NEW = '            pass  # MUTATED: the restore is implemented but never called'


MUTATIONS = [
    (
        "M1",
        LAUNCHER_GEN,
        M1_OLD,
        M1_NEW,
        "test_minimax_launcher_invokes_the_roster_generator",
    ),
    (
        "M2",
        CONFIG_GEN,
        M2_OLD,
        M2_NEW,
        "test_minimax_roster_absolutizes_a_repo_relative_command",
    ),
    (
        "M3",
        CONFIG_GEN,
        M3_OLD,
        M3_NEW,
        "test_minimax_roster_absolutizes_repo_relative_stdio_paths",
    ),
    (
        "M4",
        CONFIG_GEN,
        M4_OLD,
        M4_NEW,
        "test_write_client_config_preserves_the_runtime_flags",
    ),
]


@pytest.mark.parametrize(
    "label,target,old,new,killing_test",
    MUTATIONS,
    ids=[m[0] for m in MUTATIONS],
)
def test_mutation_is_killed(label, target, old, new, killing_test, tmp_path):
    """Break the fix on purpose; the named test must go RED."""
    original = _apply_mutation(target, old, new)
    try:
        mutated = _run_pytest(killing_test)
    finally:
        _restore(target, original)

    assert mutated.returncode != 0, (
        f"{label}: the mutation was NOT killed -- {killing_test} still passed "
        f"with the defect reintroduced.\nSTDOUT:\n{mutated.stdout}"
    )

    # And the suite is green again once the fix is restored -- a test that
    # fails for an unrelated reason would "kill" every mutation.
    restored = _run_pytest(killing_test)
    assert restored.returncode == 0, (
        f"{label}: the test does not pass with the fix restored, so its "
        f"failure above proves nothing.\nSTDOUT:\n{restored.stdout}"
    )


def test_the_whole_suite_is_green_before_any_mutation():
    """Baseline: the suite the mutations are measured against is green.

    Without this, a suite that is red for an unrelated reason would make
    every mutation look "killed".
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, (
        f"the provisioning suite is not green BEFORE any mutation:\n{proc.stdout}"
    )
