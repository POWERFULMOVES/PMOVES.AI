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

# M5 -- the Mavis SDK env strip is nested back inside the env.shared branch.
# The PowerShell twin used to run the strip unconditionally; the regression
# is putting it back where a missing env.shared disables it.
M5_OLD = """$mavis_helper = Join-Path $root 'pmoves\\\\scripts\\\\mavis_sdk_env.ps1'
if (Test-Path $mavis_helper) {{
    . $mavis_helper
    Strip-MavisSdkEnvFor -CliName '{tool.family}'
}} else {{
    Write-Warning "[{tool.launcher_basename}] mavis_sdk_env.ps1 not found at $mavis_helper -- Mavis SDK env may bleed into the launched session."
}}

if (Test-Path $envf) {{
    # Per-CLI blocklist (mirrors DEFAULT_BLOCKLIST_BY_TOOL in pmoves_launcher_generator.py).
    # These control the {tool.binary} SDK itself, not MCP creds -- sourcing them would
    # clobber session state or force API billing.
    $blocklist = @(
{blocklist_entries}
    ) -replace '\\\\*', '.*'"""
M5_NEW = """if (Test-Path $envf) {{
    $mavis_helper = Join-Path $root 'pmoves\\\\scripts\\\\mavis_sdk_env.ps1'
    if (Test-Path $mavis_helper) {{
        . $mavis_helper
        Strip-MavisSdkEnvFor -CliName '{tool.family}'
    }} else {{
        Write-Warning "[{tool.launcher_basename}] mavis_sdk_env.ps1 not found at $mavis_helper -- Mavis SDK env may bleed into the launched session."
    }}
    # Per-CLI blocklist (mirrors DEFAULT_BLOCKLIST_BY_TOOL in pmoves_launcher_generator.py).
    # These control the {tool.binary} SDK itself, not MCP creds -- sourcing them would
    # clobber session state or force API billing.
    $blocklist = @(
{blocklist_entries}
    ) -replace '\\\\*', '.*'"""

# M6 -- the MiniMax renderer drops an unrenderable transport instead of
# failing closed, so the rendered roster silently stops being the declared
# roster.
M6_OLD = """            raise MCPConfigError(
                f"server '{spec.key}' has unsupported transport "
                f"'{spec.transport}' for client 'minimax' -- refusing to "
                f"render a roster that is not the declared one."
            )"""
M6_NEW = "            continue  # MUTATED: the unrenderable server silently vanishes"

# M7 -- an explicitly supplied client profile is ignored for any client
# that has no registered profile of its own.
M7_OLD = """    path = profile_path or CLIENT_PROFILES.get(client)
    if path is None:
        return None"""
M7_NEW = """    if client not in CLIENT_PROFILES:
        return None
    path = profile_path or CLIENT_PROFILES.get(client)
    if path is None:
        return None"""

# M8 -- the emitted usage line names the doubled installer that has never
# existed.
M8_OLD = "#   {tool.install_basename}.sh && {tool.launcher_basename}         # rc function"
M8_NEW = (
    "#   install-{tool.name}-pmoves-command.sh && {tool.launcher_basename}"
    "         # rc function"
)

# M9 -- the roster is written with write_text() and chmod'd afterwards, so
# it spends a window world-readable. POSIX-only: Windows has no mode bits,
# so the mode assertion cannot run there at all.
M9_OLD = """    payload = json.dumps(final, indent=2) + "\\n"
    fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        # fdopen did not take ownership of the descriptor -- close it here
        # rather than leaking it.
        os.close(fd)
        raise
    with handle:
        handle.write(payload)"""
M9_NEW = """    payload = json.dumps(final, indent=2) + "\\n"
    output_path.write_text(payload, encoding="utf-8")  # MUTATED: wide open at birth"""


MUTATIONS = [
    (
        "M1",
        LAUNCHER_GEN,
        M1_OLD,
        M1_NEW,
        "test_minimax_launcher_invokes_the_roster_generator",
        False,
    ),
    (
        "M2",
        CONFIG_GEN,
        M2_OLD,
        M2_NEW,
        "test_minimax_roster_absolutizes_a_repo_relative_command",
        False,
    ),
    (
        "M3",
        CONFIG_GEN,
        M3_OLD,
        M3_NEW,
        "test_minimax_roster_absolutizes_repo_relative_stdio_paths",
        False,
    ),
    (
        "M4",
        CONFIG_GEN,
        M4_OLD,
        M4_NEW,
        "test_write_client_config_preserves_the_runtime_flags",
        False,
    ),
    (
        "M5",
        LAUNCHER_GEN,
        M5_OLD,
        M5_NEW,
        "test_the_powershell_sdk_strip_runs_outside_the_env_shared_branch",
        False,
    ),
    (
        "M6",
        CONFIG_GEN,
        M6_OLD,
        M6_NEW,
        "test_minimax_renderer_refuses_an_unsupported_transport",
        False,
    ),
    (
        "M7",
        CONFIG_GEN,
        M7_OLD,
        M7_NEW,
        "test_an_explicit_client_profile_is_honoured_for_any_client",
        False,
    ),
    (
        "M8",
        LAUNCHER_GEN,
        M8_OLD,
        M8_NEW,
        "test_every_launcher_names_an_installer_that_actually_exists",
        False,
    ),
    (
        "M9",
        CONFIG_GEN,
        M9_OLD,
        M9_NEW,
        "test_the_rendered_roster_is_created_owner_only",
        True,
    ),
]


@pytest.mark.parametrize(
    "label,target,old,new,killing_test,posix_only",
    MUTATIONS,
    ids=[m[0] for m in MUTATIONS],
)
def test_mutation_is_killed(label, target, old, new, killing_test, posix_only):
    """Break the fix on purpose; the named test must go RED."""
    if posix_only and os.name == "nt":
        pytest.skip(
            f"{label}: the mode assertion cannot run on Windows -- the "
            f"filesystem has no POSIX mode bits, so there is nothing to kill"
        )
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
