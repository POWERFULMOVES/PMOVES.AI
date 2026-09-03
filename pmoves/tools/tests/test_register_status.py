"""Tests for register_status -- the sanctioned register READ path.

#2879 closed the shell write-hole on the register correctly and left no way to
ASK. Every sanctioned path its refusal named was a write, and `open_claims_in()`
-- the register's own authority on what is open -- sits inside an interpreter
the gate refuses. An agent could file a claim and could not check the lane.

Two things are pinned here and the second matters as much as the first:

  1. The read path answers, and its answer is the GATE'S answer -- asserted as
     set equality against `open_claims_in()`, not as matching totals. A second
     parser that happens to agree today is the defect; the register already has
     20 spellings of one owner from exactly that.
  2. The read path did not widen the write surface. A read target that quietly
     re-opens `python3 -c` is a regression wearing a feature's clothes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_status.py"
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"
REGISTER_NAME = "AGNOTE4482PHI.t1.md"

ALLOW, BLOCK = 0, 2
CLEAN, FINDINGS, UNMEASURED = 0, 1, 3

NOW = "2026-09-03T12:00:00Z"

# A register with one of every shape that decides an exit code.
FIXTURE = "".join([
    "# claim register\n",
    "\n",
    # live TTL, stated expiry -- the grammar build_row() emits
    "- `2026-09-03T09:00:00Z` CLAIM `AGENT-A` branch: `feat/live-lane` "
    "· **TTL 24h (expires `2026-09-04T09:00:00Z`)** · scope: still working.\n",
    # expired, stated expiry
    "- `2026-08-30T09:00:00Z` CLAIM `AGENT-B` branch: `feat/stale-lane` "
    "· **TTL 24h (expires `2026-08-31T09:00:00Z`)** · scope: went quiet.\n",
    # expired, DERIVED from the row's own timestamp -- the hand-written prose
    # form, 3 of 22 open claims on the live file
    "- `2026-08-29T09:00:00Z` CLAIM `AGENT-C` scope: prose row. "
    "Branch `feat/derived-lane`, TTL 72h.\n",
    # no TTL at all -- 15 of 22 on the live file
    "- `2026-08-01T09:00:00Z` CLAIM `AGENT-D` branch: `feat/no-ttl-lane` "
    "· scope: open forever.\n",
    # claimed then released: must NOT appear
    "- `2026-08-02T09:00:00Z` CLAIM `AGENT-E` branch: `feat/closed-lane` "
    "· scope: did the thing.\n",
    "- `2026-08-03T09:00:00Z` RELEASE `AGENT-E` scope: landed.\n",
])


def _load_gate():
    spec = importlib.util.spec_from_file_location("claim_collision_pre", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["claim_collision_pre"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def register(tmp_path: Path) -> Path:
    path = tmp_path / REGISTER_NAME
    path.write_text(FIXTURE, encoding="utf-8")
    return path


def run_status(register: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(TOOL), "--register", str(register), "--now", NOW,
         *args],
        capture_output=True, text=True,
    )


def run_hook(tmp_path: Path, command: str):
    """Drive the collision gate's Bash path, as an agent's tool call would."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(tmp_path),
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True,
    )


# --------------------------------------------------------------------------
# IT IS THE GATE'S ANSWER, NOT A SECOND OPINION
# --------------------------------------------------------------------------


def test_the_read_path_reports_exactly_what_the_gate_holds_open(register):
    """Set equality, not matching counts.

    Two totals can agree while the rows underneath disagree, and the row is
    what a claimant acts on. This asserts the identity, the line, the lanes
    and the participants of every open claim -- so a private reimplementation
    of any of them fails here rather than in front of whoever got told they
    were clear.
    """
    gate = _load_gate()
    expected = {
        (lineno, owner_key, tuple(sorted(lanes)), tuple(sorted(parts)))
        for owner_key, rows in gate.open_claims_in(
            register.read_text(encoding="utf-8")).items()
        for lineno, lanes, _as_written, parts in rows
    }
    result = run_status(register, "--json")
    payload = json.loads(result.stdout)
    got = {
        (c["line"], c["owner_key"], tuple(c["lanes"]), tuple(c["participants"]))
        for c in payload["open_claims"]
    }
    assert got == expected
    assert payload["counts"]["open"] == len(expected)


def test_a_released_lane_is_not_reported_open(register):
    payload = json.loads(run_status(register, "--json").stdout)
    lanes = {lane for c in payload["open_claims"] for lane in c["lanes"]}
    assert "feat/closed-lane" not in lanes
    assert "feat/live-lane" in lanes


# --------------------------------------------------------------------------
# THE QUESTION AN AGENT ACTUALLY HAS
# --------------------------------------------------------------------------


def test_a_held_lane_is_reported_held(register):
    r = run_status(register, "--branch", "feat/live-lane", "--owner", "AGENT-Z")
    assert r.returncode == FINDINGS, r.stdout + r.stderr
    assert "HELD by `AGENT-A`" in r.stdout
    assert "register-claim` would refuse" in r.stdout


def test_a_free_lane_is_reported_free(register):
    r = run_status(register, "--branch", "feat/nobody-here", "--owner", "AGENT-Z")
    assert r.returncode == CLEAN, r.stdout + r.stderr
    assert "FREE" in r.stdout


def test_a_lane_you_already_hold_is_not_reported_as_a_strangers(register):
    """The gate allows an owner to re-name their own lane and says nothing.

    A status report cannot inherit that silence: "free" would then mean both
    "nobody is on it" and "you are on it", and those lead to opposite actions.
    """
    r = run_status(register, "--branch", "feat/live-lane", "--owner", "AGENT-A")
    assert r.returncode == FINDINGS, r.stdout + r.stderr
    assert "HELD BY YOU" in r.stdout
    assert "HELD by" not in r.stdout


def test_a_reciprocated_share_reads_as_shared_not_as_held(tmp_path):
    """The incumbent declared the claimant, so the gate ALLOWS. So must this."""
    reg = tmp_path / REGISTER_NAME
    reg.write_text(
        "- `2026-09-01T09:00:00Z` CLAIM `AGENT-A` branch: `feat/shared-lane` "
        "· co-owners: `AGENT-B` (filed the blocker) · scope: together.\n",
        encoding="utf-8",
    )
    r = run_status(reg, "--branch", "feat/shared-lane", "--owner", "AGENT-B")
    assert r.returncode == CLEAN, r.stdout + r.stderr
    assert "SHARED with `AGENT-A`" in r.stdout


# --------------------------------------------------------------------------
# TTL -- THE HALF NOBODY WAS LOOKING AT
# --------------------------------------------------------------------------


def test_an_expired_unreleased_claim_is_a_finding_not_a_footnote(register):
    r = run_status(register)
    assert r.returncode == FINDINGS, r.stdout + r.stderr
    assert "EXPIRED AND NOT RELEASED (2)" in r.stdout
    assert "feat/stale-lane" in r.stdout


def test_an_expiry_is_derived_when_the_row_states_only_a_duration(register):
    """3 of 22 open claims on the live register are this shape.

    `TTL 72h` with no `expires` predates the sanctioned write path. Reading it
    as "no TTL" would silently exempt the oldest rows -- the ones most likely
    to be abandoned -- from the only check that can flag them.
    """
    payload = json.loads(run_status(register, "--json").stdout)
    derived = next(c for c in payload["open_claims"]
                   if "feat/derived-lane" in c["lanes"])
    assert derived["ttl"] == "72h"
    assert derived["expires"] == "2026-09-01T09:00:00Z"  # row ts + 72h
    assert derived["ttl_state"] == "expired"


def test_a_claim_without_a_ttl_is_counted_not_treated_as_a_finding(register):
    """81% of open claims carry no TTL. An exit code that is non-zero because
    of that is an exit code nobody reads, so it is surfaced as a count."""
    payload = json.loads(run_status(register, "--json").stdout)
    assert payload["counts"]["no_ttl"] == 1
    assert "WITHOUT A TTL: 1 of 4" in run_status(register).stdout


def test_an_unreadable_ttl_is_could_not_measure_and_outranks_findings(tmp_path):
    """3 beats 1. An expiry that could not be computed is not "not expired"."""
    reg = tmp_path / REGISTER_NAME
    reg.write_text(
        "- `2026-08-01T09:00:00Z` CLAIM `AGENT-A` branch: `feat/weird` "
        "· scope: TTL 3w and nobody parses weeks.\n"
        "- `2026-08-30T09:00:00Z` CLAIM `AGENT-B` branch: `feat/stale` "
        "· **TTL 24h (expires `2026-08-31T09:00:00Z`)** · scope: gone.\n",
        encoding="utf-8",
    )
    r = run_status(reg)
    assert r.returncode == UNMEASURED, r.stdout + r.stderr
    assert "TTL NOT MEASURED (1)" in r.stdout
    assert "EXPIRED AND NOT RELEASED (1)" in r.stdout, (
        "the expired row is still reported; 3 outranks 1, it does not hide it"
    )


def test_a_clean_register_exits_zero(tmp_path):
    reg = tmp_path / REGISTER_NAME
    reg.write_text(
        "- `2026-09-03T09:00:00Z` CLAIM `AGENT-A` branch: `feat/live` "
        "· **TTL 24h (expires `2026-09-04T09:00:00Z`)** · scope: working.\n",
        encoding="utf-8",
    )
    assert run_status(reg).returncode == CLEAN


# --------------------------------------------------------------------------
# READ-ONLY, ASSERTED RATHER THAN ASSUMED
# --------------------------------------------------------------------------


def test_the_register_is_byte_identical_after_every_mode(register):
    before = register.read_bytes()
    run_status(register)
    run_status(register, "--branch", "feat/live-lane", "--owner", "AGENT-A")
    run_status(register, "--json")
    assert register.read_bytes() == before


def test_the_probe_row_is_never_appended(register):
    """`probe_branch` renders a real CLAIM row to ask the gate. If that row
    ever reached the file, the read path would be filing claims."""
    run_status(register, "--branch", "feat/probe-target", "--owner", "AGENT-Z")
    text = register.read_text(encoding="utf-8")
    assert "feat/probe-target" not in text
    assert "register-status probe" not in text


# --------------------------------------------------------------------------
# THE TRAP: A READ PATH THE GATE ITSELF REFUSES IS NOT A PATH
# --------------------------------------------------------------------------


def test_the_gate_allows_the_sanctioned_read_target(tmp_path):
    """The tool exists to satisfy the hook; the hook must let it run."""
    reg = tmp_path / REGISTER_NAME
    reg.write_text(FIXTURE, encoding="utf-8")
    r = run_hook(tmp_path, f'make -C pmoves register-status ARGS="--register {reg}"')
    assert r.returncode == ALLOW, r.stderr


def test_the_gate_allows_the_read_tool_invoked_directly(tmp_path):
    reg = tmp_path / REGISTER_NAME
    reg.write_text(FIXTURE, encoding="utf-8")
    r = run_hook(tmp_path, f"python3 pmoves/tools/register_status.py --register {reg}")
    assert r.returncode == ALLOW, r.stderr


def test_naming_the_read_tool_does_not_launder_an_inline_interpreter(tmp_path):
    """The sanctioned-tool allowance must not become a password.

    `-c` alongside the tool name means the interpreter is running something
    else, and what it does to the register is not in the command string.
    """
    reg = tmp_path / REGISTER_NAME
    reg.write_text(FIXTURE, encoding="utf-8")
    r = run_hook(
        tmp_path,
        f"python3 pmoves/tools/register_status.py -c \"open('{reg}','w')\"",
    )
    assert r.returncode == BLOCK, r.stdout
    assert "NOT MEASURED" in r.stderr


def test_the_refusal_offers_the_read_path_not_only_write_paths(tmp_path):
    """The whole defect in one assertion.

    An agent running an interpreter against the register is nearly always
    ASKING something. Answering with three ways to write is a dead end.
    """
    reg = tmp_path / REGISTER_NAME
    reg.write_text(FIXTURE, encoding="utf-8")
    r = run_hook(tmp_path, f"uv run --with pyyaml python -c \"print('{reg}')\"")
    assert r.returncode == BLOCK
    assert "register-status" in r.stderr, (
        "the refusal names only write targets to someone trying to read"
    )
    assert "register-claim" in r.stderr, "the write path is still named too"


def test_the_read_tool_declares_pyyaml_for_uv_run():
    """Without it, `uv run --script` gets an interpreter with no vocabulary and
    the tool refuses to answer -- correct, but useless."""
    head = TOOL.read_text(encoding="utf-8")[:600]
    assert "# /// script" in head
    assert "pyyaml" in head
