"""The NOTE record type, and the bare-RELEASE trap it used to feed.

TWO DEFECTS THAT COMPOUNDED.

  1. `register_append.py` accepted `claim`, `release`, `docs`, `amend` -- and no
     way to record a FACT. The register has 5 hand-inserted `NOTE` rows that
     predate the tool, so the need was already demonstrated; the tool just had
     no door for it.
  2. A RELEASE naming no lane closes EVERY lane its owner holds. 142 rows in
     the live register use it that way, so the convention is real.

Together: filing a correction had to be filed as a `release`, and an
under-specified release closes everything. An agent adding a footnote under an
owner with open lanes would have closed all of them silently. Observed live;
harmless only because that owner's lanes were already closed. A hazard whose
harm depends on ordering is untriggered, not safe.

EVERY LANE-STATE ASSERTION HERE GOES THROUGH `open_claims_in()`, the gate's own
authority on what is open. A test that reimplements the parser proves the
reimplementation, not the register.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_append.py"
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"
LIVE_REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"

# Two lanes, one owner. The second is what a bare RELEASE used to take with it.
HELD = (
    "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
    "- `2026-01-01T00:05:00Z` CLAIM `AGENT-A` branch: `fix/sprocket` "
    "· scope: **and this one.**\n"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gate():
    return _load(HOOK, "claim_collision_pre")


@pytest.fixture()
def mod(tmp_path: Path, monkeypatch):
    m = _load(TOOL, "register_append")
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text("# register\n" + HELD, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    return m


def _open_lanes(gate, register: Path) -> dict:
    """Open lanes as the AUTHORITY sees them, keyed owner -> sorted lanes."""
    claims = gate.open_claims_in(register.read_text(encoding="utf-8"))
    return {
        owner: sorted(lane for _ln, lanes, _raw, _p in rows for lane in lanes)
        for owner, rows in claims.items()
    }


def _rows(register: Path) -> list[str]:
    return [l for l in register.read_text(encoding="utf-8").split("\n")
            if l.startswith("- `")]


# --- A. a NOTE records a fact and transitions nothing -------------------------

def test_a_note_closes_no_open_lane(mod, gate):
    before = _open_lanes(gate, mod.REGISTER)
    assert before == {"AGENT-A": ["feat/widget", "fix/sprocket"]}, before

    rc = mod.main(["note", "--owner", "AGENT-A",
                   "--scope", "the 2026-01-01 row cites the wrong PR number"])

    assert rc == mod.EXIT_OK
    assert len(_rows(mod.REGISTER)) == 3, "the note must actually be written"
    assert _open_lanes(gate, mod.REGISTER) == before, (
        "a NOTE changed the open lanes -- this is the trap")


def test_a_note_quoting_a_release_is_still_inert(gate):
    """The hazard in its purest form, testable WITHOUT the new CLI kind.

    These rows discuss claims and releases for a living. A note reading "the
    RELEASE `AGENT-A` on line 42 was mis-attributed" carries the exact byte
    sequence RELEASE_RE looks for, and a bare RELEASE closes everything its
    owner holds. Parsed as a real row, one footnote empties a node's workload.

    Written against `open_claims_in()` directly rather than through the tool, so
    it fails BEHAVIOURALLY on the pre-fix parser instead of dying on a missing
    CLI choice.
    """
    note = (
        "- `2026-01-02T00:00:00Z` NOTE `AUDITOR` scope: the RELEASE `AGENT-A` "
        "filed on 2026-01-01 names no lane, which is worth recording.\n"
    )
    lanes = {
        owner: sorted(l for _ln, ls, _r, _p in rows for l in ls)
        for owner, rows in gate.open_claims_in(HELD + note).items()
    }
    assert lanes == {"AGENT-A": ["feat/widget", "fix/sprocket"]}, (
        "a NOTE's prose was read as a real RELEASE and closed the lanes it "
        f"merely described: {lanes}")


def test_a_note_quoting_a_claim_grants_no_lane(gate):
    """The mirror: a note that quotes a CLAIM must not OPEN a lane either."""
    note = (
        "- `2026-01-02T00:00:00Z` NOTE `AUDITOR` scope: the CLAIM `SQUATTER` "
        "branch: `feat/widget` would collide if anyone filed it.\n"
    )
    owners = set(gate.open_claims_in(HELD + note))
    assert "SQUATTER" not in owners, (
        f"a NOTE's prose opened a lane for an owner who filed nothing: {owners}")


def test_a_note_that_would_move_lane_state_is_refused(mod, gate, monkeypatch):
    """Defence in depth, and it must be a REFUSAL, never a silent write.

    The parser skip is one guarantee. This is the other: the tool simulates the
    append and refuses if the open-lane map moved. Forced here by widening the
    inert set to nothing, which is the only way to reach the branch once the
    parser is correct -- and exactly the state a future edit to
    INERT_ROW_KINDS would produce.
    """
    monkeypatch.setattr(gate, "INERT_ROW_KINDS", frozenset())
    monkeypatch.setattr(mod, "_load_gate", lambda: gate)
    before = _open_lanes(gate, mod.REGISTER)

    rc = mod.main(["note", "--owner", "AUDITOR",
                   "--scope", "the RELEASE `AGENT-A` row is mis-attributed"])

    assert rc == mod.EXIT_REFUSED
    assert _open_lanes(gate, mod.REGISTER) == before
    assert len(_rows(mod.REGISTER)) == 2, "a refused note must not be written"


def test_a_note_needs_an_owner_and_a_scope(mod):
    assert mod.main(["note", "--scope", "s"]) == mod.EXIT_UNMEASURED
    assert mod.main(["note", "--owner", "A", "--scope", " "]) == mod.EXIT_UNMEASURED
    assert len(_rows(mod.REGISTER)) == 2


def test_a_note_takes_no_ttl(mod):
    """An expiring footnote would be read by the TTL sweep as an overdue claim."""
    rc = mod.main(["note", "--owner", "A", "--scope", "s", "--ttl", "72h"])
    assert rc == mod.EXIT_UNMEASURED
    assert len(_rows(mod.REGISTER)) == 2


def test_a_note_row_carries_the_historical_grammar(mod):
    """`- \\`<ts>\\` NOTE \\`<owner>\\` ... scope: ...` -- the shape the 5
    hand-written NOTE rows already use, so one parser reads both."""
    mod.main(["note", "--owner", "AGENT-A", "--scope", "recorded"])
    row = _rows(mod.REGISTER)[-1]
    assert re.match(
        r"^- `[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z` "
        r"NOTE `AGENT-A`.*scope: recorded$", row), row


# --- regression: the live register still parses the same ---------------------

@pytest.mark.skipif(not LIVE_REGISTER.is_file(), reason="no live register here")
def test_the_inert_skip_changes_no_lane_in_the_live_register(gate, monkeypatch):
    """Every historical row still parses, and none changes hands.

    Both sides come from the REAL `open_claims_in()`; the control is the same
    function with the inert set emptied, which is exactly the pre-change
    behaviour. Comparing against a reimplementation would prove the
    reimplementation.
    """
    text = LIVE_REGISTER.read_text(encoding="utf-8")
    after = gate.open_claims_in(text)
    monkeypatch.setattr(gate, "INERT_ROW_KINDS", frozenset())
    before = gate.open_claims_in(text)

    assert before, "the control read no open claims at all -- inputs are empty"
    assert after == before, (
        f"the inert skip moved lane state: {len(before)} owners before, "
        f"{len(after)} after")


@pytest.mark.skipif(not LIVE_REGISTER.is_file(), reason="no live register here")
def test_no_live_claim_or_release_row_is_classified_inert(gate):
    """The skip must not swallow a row that really does transition state."""
    swallowed = [
        (i, line[:90])
        for i, line in enumerate(LIVE_REGISTER.read_text(encoding="utf-8")
                                 .split("\n"), 1)
        if gate.is_inert_row(line)
        and gate.row_kind(line) not in gate.INERT_ROW_KINDS
    ]
    assert not swallowed, swallowed

    kinds = {gate.row_kind(line)
             for line in LIVE_REGISTER.read_text(encoding="utf-8").split("\n")}
    assert "CLAIM" in kinds and "RELEASE" in kinds and "NOTE" in kinds, (
        f"the row-kind parser stopped recognising the live grammar: "
        f"{sorted(k for k in kinds if k)}")
