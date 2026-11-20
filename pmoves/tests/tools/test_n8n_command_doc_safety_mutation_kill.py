"""Mutation-kill harness: the /n8n command-doc ratchet must BITE.

The companion harness for
``pmoves/tests/tools/test_n8n_command_doc_safety_ratchet.py``.

THE KILL CONTRACT: GREEN, RED, GREEN
-------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine command files must pass the selected tests.
  2. RED AFTER    -- the mutated files must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored files must pass again.

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
  M1  the search term is pasted back into a raw query string;
  M2  the listing stops asking for the public API's page cap;
  M3  the activation is never undone;
  M4  the executions are no longer filtered by when they started;
  M5  the credential-bearing parameter values stop being redacted;
  M6  the command stops pointing at the installed node catalog.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_n8n_command_doc_safety_mutation_kill.py -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_ROOT = REPO_ROOT / "pmoves"
COMMAND_DIR = REPO_ROOT / ".claude" / "commands" / "n8n"

RATCHET = "tests/tools/test_n8n_command_doc_safety_ratchet.py"

RAW_QUERY_TEST = "test_no_command_interpolates_arguments_into_a_raw_url_query"
PAGING_TEST = "test_every_workflow_listing_pages_through_every_page"
RESTORE_TEST = "test_the_execute_command_restores_the_activation_state"
NOT_EXECUTION_TEST = "test_the_execute_command_does_not_present_activation_as_execution"
REDACTION_TEST = "test_the_nodes_command_redacts_credential_bearing_parameters"
CATALOG_TEST = "test_the_nodes_command_reads_the_installed_node_catalog"

ALL_TARGETS = [
    f"{RATCHET}::{RAW_QUERY_TEST}",
    f"{RATCHET}::{PAGING_TEST}",
    f"{RATCHET}::{RESTORE_TEST}",
    f"{RATCHET}::{NOT_EXECUTION_TEST}",
    f"{RATCHET}::{REDACTION_TEST}",
    f"{RATCHET}::{CATALOG_TEST}",
]

MUTABLE = ("execute.md", "nodes.md", "workflows.md", "suggest.md")


def _read(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
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

def _mutate_raw_query(texts: dict[str, str]) -> dict[str, str]:
    """M1: the search term goes back into a raw query string."""
    assert '--data-urlencode "name=$ARGUMENTS"' in texts["workflows.md"], (
        "mutation anchor not found"
    )
    texts["workflows.md"] = texts["workflows.md"].replace(
        '--data-urlencode "name=$ARGUMENTS"', "?name=$ARGUMENTS"
    )
    return texts


def _mutate_paging(texts: dict[str, str]) -> dict[str, str]:
    """M2: the listing stops asking for the public API's page cap."""
    assert "take=250" in texts["workflows.md"], "mutation anchor not found"
    texts["workflows.md"] = texts["workflows.md"].replace("take=250", "take=100")
    return texts


def _mutate_no_restore(texts: dict[str, str]) -> dict[str, str]:
    """M3: the activation is never undone."""
    assert "/deactivate" in texts["execute.md"], "mutation anchor not found"
    texts["execute.md"] = texts["execute.md"].replace("/deactivate", "/activate")
    return texts


def _mutate_no_start_filter(texts: dict[str, str]) -> dict[str, str]:
    """M4: the executions are no longer filtered by when they started."""
    assert "select(.startedAt > $since)" in texts["execute.md"], (
        "mutation anchor not found"
    )
    texts["execute.md"] = texts["execute.md"].replace(
        "select(.startedAt > $since)", "select(true)"
    )
    return texts


def _mutate_no_redaction(texts: dict[str, str]) -> dict[str, str]:
    """M5: the credential-bearing parameter values stop being redacted."""
    assert "***REDACTED***" in texts["nodes.md"], "mutation anchor not found"
    texts["nodes.md"] = texts["nodes.md"].replace("***REDACTED***", "value")
    return texts


def _mutate_no_catalog(texts: dict[str, str]) -> dict[str, str]:
    """M6: the command stops pointing at the installed node catalog."""
    assert "n8n-nodes-base" in texts["nodes.md"], "mutation anchor not found"
    texts["nodes.md"] = texts["nodes.md"].replace("n8n-nodes-base", "some-package")
    return texts


MUTATIONS = [
    ("M1_raw_query", _mutate_raw_query, RAW_QUERY_TEST),
    ("M2_paging", _mutate_paging, PAGING_TEST),
    ("M3_no_restore", _mutate_no_restore, RESTORE_TEST),
    ("M4_no_start_filter", _mutate_no_start_filter, NOT_EXECUTION_TEST),
    ("M5_no_redaction", _mutate_no_redaction, REDACTION_TEST),
    ("M6_no_catalog", _mutate_no_catalog, CATALOG_TEST),
]


# ── the harness ──────────────────────────────────────────────────────────────

def test_mutation_kills_are_proven() -> None:
    """Every mutation must turn the NAMED test RED, and the tree must restore."""
    original = {name: _read(COMMAND_DIR / name) for name in MUTABLE}

    # 1. GREEN BEFORE -- the pristine files pass every target.
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"pristine command files are not green before mutation:\n{out}"

    kills: list[str] = []
    try:
        for name, mutate, named_test in MUTATIONS:
            texts = mutate(dict(original))
            assert texts != original, f"{name} produced no mutation"
            for filename, text in texts.items():
                _write(COMMAND_DIR / filename, text)

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
        for filename, text in original.items():
            _write(COMMAND_DIR / filename, text)

    # 3. GREEN AFTER -- the byte-exact restore passes again.
    for filename, text in original.items():
        assert _read(COMMAND_DIR / filename) == text, (
            f"{filename} was not restored byte-exactly"
        )
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"restored command files are not green after mutation:\n{out}"

    assert len(kills) == len(MUTATIONS), f"expected {len(MUTATIONS)} kills, got {kills}"
    print("\nproven kills:")
    for k in kills:
        print(f"  {k}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
