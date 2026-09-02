"""Tests for register_append -- the sanctioned register write path.

The point of this tool is that an agent with no Write tool can still file a
row, and cannot file a bad one. Both halves are asserted: it must refuse a held
lane and an unenforceable claim, AND it must actually append a valid row. A
sanctioned path that only refuses is the deadlock it exists to prevent.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_append.py"
HELD = (
    "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("register_append", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod(tmp_path: Path, monkeypatch):
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text("# register\n" + HELD, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    return m


def _rows(mod) -> list[str]:
    return [l for l in mod.REGISTER.read_text(encoding="utf-8").split("\n")
            if l.startswith("- `")]


# --- it says no --------------------------------------------------------------

def test_refuses_a_lane_another_owner_holds(mod):
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/widget",
                   "--scope", "mine now"])
    assert rc == mod.EXIT_REFUSED
    assert len(_rows(mod)) == 1, "a refused claim must not be written"


def test_refuses_a_claim_that_names_no_branch(mod):
    """A claim with no lane is unenforceable -- the gate has nothing to compare.

    78 rows in the live register are already in that state, which is why this
    is refused at the door rather than accepted and reported later.
    """
    rc = mod.main(["claim", "--owner", "AGENT-B", "--scope", "vague"])
    assert rc == mod.EXIT_UNMEASURED
    assert len(_rows(mod)) == 1


def test_refuses_a_row_with_no_owner(mod):
    assert mod.main(["claim", "--branch", "feat/x", "--scope", "s"]) == mod.EXIT_UNMEASURED


def test_refuses_a_row_with_no_scope(mod):
    assert mod.main(["claim", "--owner", "A", "--branch", "feat/x",
                     "--scope", "   "]) == mod.EXIT_UNMEASURED


def test_refuses_an_unparseable_ttl(mod):
    assert mod.main(["claim", "--owner", "A", "--branch", "feat/x",
                     "--scope", "s", "--ttl", "soonish"]) == mod.EXIT_UNMEASURED


def test_a_gate_that_will_not_load_refuses_rather_than_appending(mod, monkeypatch):
    """Could-not-measure is not a pass, including when the checker is broken.

    Appending unchecked because the collision gate failed to import would make
    the tool a way to bypass the very check it exists to perform.
    """
    monkeypatch.setattr(mod, "_load_gate", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert mod.main(["claim", "--owner", "B", "--branch", "feat/free",
                     "--scope", "s"]) == mod.EXIT_UNMEASURED
    assert len(_rows(mod)) == 1


# --- it says yes -------------------------------------------------------------

def test_appends_a_free_lane_end_to_end(mod):
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free",
                   "--ttl", "72h", "--scope", "new work"])
    assert rc == mod.EXIT_OK
    rows = _rows(mod)
    assert len(rows) == 2
    assert "CLAIM `AGENT-B`" in rows[1]
    assert "branch: `feat/free`" in rows[1]
    assert "TTL 72h (expires" in rows[1]


def test_the_same_owner_may_hold_several_lanes(mod):
    """Re-claiming under your own identity is the routine case, not a clash."""
    mod.main(["claim", "--owner", "AGENT-A", "--branch", "feat/second",
              "--scope", "also mine"])
    assert len(_rows(mod)) == 2


def test_dry_run_checks_but_writes_nothing(mod):
    assert mod.main(["claim", "--owner", "B", "--branch", "feat/free",
                     "--scope", "s", "--dry-run"]) == mod.EXIT_OK
    assert len(_rows(mod)) == 1


# --- the timestamp invariant, at the source ----------------------------------

def test_the_timestamp_is_read_from_the_clock_not_rounded(mod):
    """41 of 404 live rows are postdated and 89% carry `:00` seconds, because
    they were typed. A generated stamp cannot be either."""
    before = datetime.now(timezone.utc).replace(microsecond=0)
    mod.main(["claim", "--owner", "B", "--branch", "feat/free", "--scope", "s"])
    after = datetime.now(timezone.utc)
    ts = re.search(r"`([0-9T:\-]+Z)`", _rows(mod)[1]).group(1)
    parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before - timedelta(seconds=1) <= parsed <= after


def test_the_ttl_expiry_is_derived_from_that_same_stamp(mod):
    row = mod.build_row("CLAIM", "B", "feat/x", "s", ttl="72h",
                        now=datetime(2026, 9, 2, 11, 0, 0, tzinfo=timezone.utc))
    assert "`2026-09-02T11:00:00Z`" in row
    assert "expires `2026-09-05T11:00:00Z`" in row


def test_co_owners_render_in_the_documented_grammar(mod):
    row = mod.build_row("RELEASE", "B850-CLAUDE (Knuckles)", "fix/x", "done",
                        co_owners=["4090-CLAUDE:filed the blocker", "Z890-CLAUDE"])
    assert "co-owners: `4090-CLAUDE` (filed the blocker), `Z890-CLAUDE`" in row


# --- append-only is a property of the syscall --------------------------------

def test_append_never_truncates(mod):
    original = mod.REGISTER.read_text(encoding="utf-8")
    mod.append_row("- `t` RELEASE `X` scope: y", mod.REGISTER)
    after = mod.REGISTER.read_text(encoding="utf-8")
    assert after.startswith(original), "existing bytes must survive verbatim"
    assert len(after) > len(original)


# --- docs mode: prose may move, rows may not ---------------------------------

DOC = "# register\n\n## Anchor Heading\n" + HELD


@pytest.fixture()
def docmod(tmp_path: Path, monkeypatch):
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text(DOC, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    return m


def test_docs_insert_is_pure_insertion(docmod):
    before = docmod.REGISTER.read_text(encoding="utf-8")
    rc = docmod.insert_docs("## Anchor Heading", "### New Section\n\nprose.\n\n")
    assert rc == docmod.EXIT_OK
    after = docmod.REGISTER.read_text(encoding="utf-8")
    assert "### New Section" in after
    assert docmod._ledger_rows(before) == docmod._ledger_rows(after)
    # every original byte survives, in order
    assert after.replace("### New Section\n\nprose.\n\n", "", 1) == before


def test_docs_insert_refuses_a_missing_anchor(docmod):
    assert docmod.insert_docs("## Nope", "x") == docmod.EXIT_UNMEASURED


def test_docs_insert_refuses_an_ambiguous_anchor(docmod):
    """Two matches means the insertion point is a guess, and a guess in a
    provenance file is not an operation this tool will perform."""
    docmod.REGISTER.write_text(DOC + "\n## Anchor Heading\n", encoding="utf-8")
    assert docmod.insert_docs("## Anchor Heading", "x") == docmod.EXIT_UNMEASURED


def test_docs_insert_refuses_text_that_would_add_a_row(docmod):
    """Prose mode must not become a second, unchecked way to file a claim."""
    rc = docmod.insert_docs(
        "## Anchor Heading",
        "- `2026-09-02T11:00:00Z` CLAIM `SNEAKY` branch: `feat/widget` · scope: x\n",
    )
    assert rc == docmod.EXIT_REFUSED
    assert "SNEAKY" not in docmod.REGISTER.read_text(encoding="utf-8")


# --- the merged gate contract -------------------------------------------------
#
# `evaluate_claims` returned `(collisions, unkeyed)` here and a four-category
# verdict on main. Called bare, the widened return raised
# `ValueError: too many values to unpack` -- an UNCAUGHT traceback, exit 1 --
# in the one tool the fleet has when the Bash path denies and there is no Write
# tool. Exit 1 in this tool's doctrine means "refused: the lane is held by
# another owner", so the crash was indistinguishable from a legitimate refusal
# by exit code alone: this fleet's signature defect, inside the tool built to
# prevent it.
#
# These run through main() -> _load_gate(), so they exercise the REAL hook
# module rather than a stub. That is deliberate: it is the property that would
# have caught the incompatible merge in CI instead of at a deadlock.

def test_the_verdict_object_carries_all_four_categories(mod):
    """A tuple return is what made the widening silent. Pin the shape."""
    gate = mod._load_gate()
    v = gate.evaluate_claims(
        "- `t` CLAIM `AGENT-B` branch: `feat/widget` · scope: **x.**",
        gate.open_claims_in(mod.REGISTER.read_text(encoding="utf-8")),
    )
    for field in ("collisions", "shared", "one_sided", "unkeyed",
                  "unreadable_co_owners"):
        assert hasattr(v, field), f"verdict lost {field}"
    assert v.collisions, "the held lane must still collide"


def test_open_claims_carry_participants_through_the_sanctioned_path(mod):
    """The 4-tuple `main` introduced must survive here, not just in the hook."""
    gate = mod._load_gate()
    claims = gate.open_claims_in(mod.REGISTER.read_text(encoding="utf-8"))
    entry = next(iter(claims.values()))[0]
    assert len(entry) == 4, f"open_claims_in arity drifted: {entry!r}"
    _lineno, _lanes, _as_written, participants = entry
    assert participants, "a row's participants must at least contain its owner"


def test_a_gate_crash_is_could_not_measure_never_a_refusal(mod, monkeypatch):
    """A crash must not be able to wear a refusal's exit code.

    3 says "I did not check this"; 1 says "another owner holds your lane". A
    reader who cannot tell them apart retries forever or gives up wrongly, and
    the whole reason this tool exists is that could-not-measure is not a pass.
    """
    class _Boom:
        def open_claims_in(self, _text):
            return {}

        def evaluate_claims(self, _row, _open):
            raise ValueError("too many values to unpack (expected 3)")

    monkeypatch.setattr(mod, "_load_gate", lambda: _Boom())
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/unheld",
                   "--scope", "new work"])
    assert rc == mod.EXIT_UNMEASURED, (
        f"a gate crash returned {rc}; 1 is 'the lane is held', not 'I crashed'"
    )
    assert len(_rows(mod)) == 1, "nothing may be written after a crash"


def test_the_top_level_guard_never_exits_one(mod, monkeypatch):
    monkeypatch.setattr(mod, "main",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert mod._guarded([]) == mod.EXIT_UNMEASURED


# --- the three-way verdict reaches the sanctioned path ------------------------

_RECIPROCATED = (
    "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` branch: `feat/widget` · "
    "co-owners: `AGENT-B` (ran the validation) · scope: **holding.**\n"
)


def test_a_reciprocated_share_is_appended_and_announced(mod, capsys):
    mod.REGISTER.write_text("# register\n" + _RECIPROCATED, encoding="utf-8")
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/widget",
                   "--scope", "sharing the lane"])
    assert rc == mod.EXIT_OK
    assert "SHARED LANE" in capsys.readouterr().err
    assert len(_rows(mod)) == 2


def test_a_unilateral_declaration_is_refused_until_it_is_acknowledged(mod, capsys):
    """The hook asks a human here. A CLI has nobody to ask, so it refuses.

    Without this the sanctioned path would be the ONE route on which the
    question is never put -- a gate that can be walked around by using the door
    it recommends.
    """
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/widget",
                   "--scope", "picking this up",
                   "--co-owner", "AGENT-A:I say we are sharing"])
    assert rc == mod.EXIT_REFUSED
    err = capsys.readouterr().err
    assert "UNILATERAL" in err
    assert "--i-have-coordinated" in err
    assert len(_rows(mod)) == 1, "a refused claim must not be written"

    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/widget",
                   "--scope", "picking this up",
                   "--co-owner", "AGENT-A:I say we are sharing",
                   "--i-have-coordinated"])
    assert rc == mod.EXIT_OK
    assert len(_rows(mod)) == 2


# --- amend: the next deadlock instance, closed --------------------------------
#
# #2858's co-owner workflow requires the INCUMBENT to add `co-owners:` to a row
# they already filed. That is an in-place edit of one line: `sed -i` and
# `perl -pi` on the register are refused by the gate, register-claim only
# appends, and register-docs refuses anything that changes a ledger row. The
# field that SUPPRESSES a collision had no sanctioned way to be set from a shell.

def test_amend_adds_co_owners_to_your_own_open_row(mod, capsys):
    rc = mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/widget",
                   "--co-owner", "AGENT-B:ran the validation"])
    assert rc == mod.EXIT_OK, capsys.readouterr().err
    rows = _rows(mod)
    assert len(rows) == 1, "an amend must not add a row"
    assert "co-owners: `AGENT-B` (ran the validation)" in rows[0]
    assert "feat/widget" in rows[0] and "holding this lane" in rows[0]


def test_the_amended_row_reciprocates_for_real(mod):
    """The point of the amend is that the GATE then allows the other node."""
    assert mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/widget",
                     "--co-owner", "AGENT-B"]) == mod.EXIT_OK
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/widget",
                   "--scope", "sharing the lane"])
    assert rc == mod.EXIT_OK, "the amend did not actually reciprocate"


def test_amend_refuses_a_row_you_did_not_file(mod, capsys):
    """Attribution and authority are different powers.

    You may declare who worked WITH you. You may not edit someone else's
    declaration of who worked with them.
    """
    rc = mod.main(["amend", "--owner", "AGENT-Z", "--branch", "feat/widget",
                   "--co-owner", "AGENT-Z"])
    assert rc == mod.EXIT_REFUSED
    assert "only amend a row you filed" in capsys.readouterr().err
    assert "AGENT-Z" not in _rows(mod)[0]


def test_amend_refuses_a_lane_you_have_no_open_row_for(mod):
    assert mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/other",
                     "--co-owner", "AGENT-B"]) == mod.EXIT_REFUSED


def test_amend_is_a_pure_insertion_into_exactly_one_row(mod):
    original = mod.REGISTER.read_text(encoding="utf-8")
    mod.REGISTER.write_text(
        original + "- `2026-01-02T00:00:00Z` CLAIM `AGENT-C` branch: "
                   "`feat/other` · scope: **untouched.**\n",
        encoding="utf-8")
    before = _rows(mod)
    assert mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/widget",
                     "--co-owner", "AGENT-B"]) == mod.EXIT_OK
    after = _rows(mod)
    assert len(before) == len(after) == 2
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [0], f"an amend touched {len(changed)} rows"
    inserted = " " + chr(183) + " co-owners: `AGENT-B`"
    assert after[0].replace(inserted, "", 1) == before[0], (
        "the amended row is not the original plus one insertion"
    )


def test_amend_extends_an_existing_co_owner_field(mod):
    mod.REGISTER.write_text("# register\n" + _RECIPROCATED, encoding="utf-8")
    assert mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/widget",
                     "--co-owner", "AGENT-D"]) == mod.EXIT_OK
    row = _rows(mod)[0]
    assert "`AGENT-D`" in row and "`AGENT-B`" in row, (
        "extending the field must not drop the incumbent declaration"
    )
    assert row.count("co-owners:") == 1


def test_amend_needs_a_branch_and_a_co_owner(mod):
    assert mod.main(["amend", "--owner", "AGENT-A", "--branch", "feat/widget"]) \
        == mod.EXIT_UNMEASURED
    assert mod.main(["amend", "--owner", "AGENT-A", "--co-owner", "X"]) \
        == mod.EXIT_UNMEASURED


def test_amend_handles_the_grammar_the_register_actually_uses(tmp_path, monkeypatch):
    """18 of 264 CLAIM rows carry ` \\xb7 scope:`. The first cut refused the other 246.

    `build_row` emits that separator, so a fixture built to the tool's own
    output passes while every hand-filed historical row -- which is exactly what
    an incumbent would need to amend -- returns "could not measure". Found by
    running the amend against a copy of the LIVE register instead of a fixture.
    """
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    bare = ("- `2026-06-11T21:30:00-04:00` CLAIM `COWORK-CLAUDE` scope: "
            "Scaffold the bridge. branch: `feat/hirag-mcp-bridge`\n")
    register.write_text("# register\n" + bare, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)

    assert m.main(["amend", "--owner", "COWORK-CLAUDE",
                   "--branch", "feat/hirag-mcp-bridge",
                   "--co-owner", "DEMO-PEER:reviewed"]) == m.EXIT_OK
    row = _rows(m)[0]
    assert "co-owners: `DEMO-PEER` (reviewed)" in row
    assert "scope: Scaffold the bridge." in row, "the scope must survive intact"
    assert len(_rows(m)) == 1


def test_amend_leaves_a_row_with_no_scope_field_valid(tmp_path, monkeypatch):
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text(
        "# register\n- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` branch: `feat/x`\n",
        encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    assert m.main(["amend", "--owner", "AGENT-A", "--branch", "feat/x",
                   "--co-owner", "AGENT-B"]) == m.EXIT_OK
    assert "co-owners: `AGENT-B`" in _rows(m)[0]
    assert len(_rows(m)) == 1
