"""Tests for register_append -- the sanctioned register write path.

The point of this tool is that an agent with no Write tool can still file a
row, and cannot file a bad one. Both halves are asserted: it must refuse a held
lane and an unenforceable claim, AND it must actually append a valid row. A
sanctioned path that only refuses is the deadlock it exists to prevent.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_append.py"
HELD = (
    "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
)


def _load():
    # REGISTERED IN sys.modules, which it was not before. `exec_module` alone
    # produces a working module for anything that resolves names through the
    # module object -- which is why this loader looked fine for 60-odd tests --
    # but pydantic resolves a model's type namespace through
    # `sys.modules[cls.__module__]`. With the module absent from sys.modules,
    # `Literal` and `Annotated` cannot be resolved and every model raises
    # "`RegisterRow` is not fully defined". The module under test was fine; the
    # loader was lying about how Python loads modules.
    spec = importlib.util.spec_from_file_location("register_append", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["register_append"] = module
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


# --------------------------------------------------------------------------
# Two defects found by driving `amend` against a copy of the LIVE register
# instead of a fixture. Both are the same shape as the bug this whole lane
# exists to remove -- a literal matched anywhere in the text, including inside
# prose that merely QUOTES the grammar -- and both were invisible to the tool's
# own purity check, because inserting in the wrong place is still an insertion.
#
# MEASURED before the fix, on a copy of the live register:
#
#     amend --owner 'B850-CLAUDE (Knuckles)' --branch chore/cli-prereq-preflight
#     -> EXIT=0 "amended line 2657 ... one row changed by insertion only"
#
# The row it amended has its own lane `feat/register-co-owner-attribution` and
# merely cites `chore/cli-prereq-preflight` inside a ``...`` example. The field
# went into the middle of the sentence "a `co-owners:` field", so the real field
# was never set and the tool reported success.
# --------------------------------------------------------------------------


def test_amend_is_not_aimed_by_a_branch_the_row_only_cites(tmp_path, monkeypatch):
    """A ``quoted example`` is documentation, not a claim on the lane."""
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    citing = (
        "- `2026-09-01T00:00:00Z` CLAIM `OWNER-NODE` branch: `feat/real-lane` "
        "\xb7 scope: **Deliverable:** a `co-owners:` field, e.g. "
        "``branch: `chore/quoted-lane` \xb7 **TTL n/a**``.\n"
    )
    register.write_text("# register\n" + citing, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    before = register.read_text(encoding="utf-8")

    assert m.main(["amend", "--owner", "OWNER-NODE",
                   "--branch", "chore/quoted-lane",
                   "--co-owner", "PROBE:note"]) == m.EXIT_REFUSED
    assert register.read_text(encoding="utf-8") == before, (
        "a cited branch aimed the amend at a row that does not hold that lane"
    )


def test_amend_picks_the_row_that_really_holds_the_lane(tmp_path, monkeypatch):
    """The A/B control: same citation present, plus the row that truly holds it."""
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    citing = (
        "- `2026-09-01T00:00:00Z` CLAIM `OWNER-NODE` branch: `feat/real-lane` "
        "\xb7 scope: e.g. ``branch: `chore/quoted-lane` \xb7 **TTL n/a**``.\n"
    )
    real = (
        "- `2026-09-01T00:00:00Z` CLAIM `OWNER-NODE` branch: `chore/quoted-lane` "
        "\xb7 scope: **the row that really holds it.**\n"
    )
    register.write_text("# register\n" + citing + real, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)

    assert m.main(["amend", "--owner", "OWNER-NODE",
                   "--branch", "chore/quoted-lane",
                   "--co-owner", "PROBE:note"]) == m.EXIT_OK
    rows = _rows(m)
    assert "co-owners:" not in rows[0], "amended the citing row"
    assert "co-owners: `PROBE` (note)" in rows[1]
    assert "``branch: `chore/quoted-lane`" in rows[0], "the citation was edited"


def test_amend_ignores_a_co_owners_mention_in_the_prose(tmp_path, monkeypatch):
    """The field goes in the header, never into a sentence that discusses it."""
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    row = (
        "- `2026-09-01T00:00:00Z` CLAIM `OWNER-NODE` branch: `feat/real-lane` "
        "\xb7 scope: **Deliverable:** a `co-owners:` field carrying IDs.\n"
    )
    register.write_text("# register\n" + row, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)

    assert m.main(["amend", "--owner", "OWNER-NODE",
                   "--branch", "feat/real-lane",
                   "--co-owner", "PROBE:note"]) == m.EXIT_OK
    amended = _rows(m)[0]
    header = amended[:amended.index("scope:")]
    assert "co-owners: `PROBE` (note)" in header, (
        "the field was inserted into the prose, not the header: " + amended
    )
    assert "**Deliverable:** a `co-owners:` field carrying IDs." in amended, (
        "the sentence discussing the field was rewritten"
    )


def test_a_row_whose_timestamp_is_not_an_iso_date_refuses_cleanly(
        tmp_path, monkeypatch):
    """`open_claims_in` accepts it, `_ledger_rows` does not -- say so, do not raise.

    The gap used to reach `before.index(row)` and throw. Exit 3 either way
    thanks to `_guarded`, but a sanctioned road that prints a traceback teaches
    the reader that the road is broken rather than that the input is.
    """
    m = _load()
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text(
        "# register\n- `t0` CLAIM `OWNER-NODE` branch: `feat/real-lane` "
        "\xb7 scope: **x.**\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    before = register.read_text(encoding="utf-8")

    assert m.main(["amend", "--owner", "OWNER-NODE",
                   "--branch", "feat/real-lane",
                   "--co-owner", "PROBE:note"]) == m.EXIT_UNMEASURED
    assert register.read_text(encoding="utf-8") == before


# --- the check and the append are ONE transaction ---------------------------
# THE GATE'S OWN FAILURE MODE, INSIDE THE TOOL BUILT TO CLOSE IT. Two filers
# read a free lane, both pass evaluate_claims(), and both append: one lane, two
# owners, produced by the sanctioned path under exactly the concurrent filing it
# exists to support. O_APPEND orders bytes; it does not order decisions.
#
# The window is forced open deliberately in these tests rather than hoped for.
# A race test that relies on timing passes on a fast box and reports nothing.


class _RaceGate:
    """The real gate, with the read/check/append window held open on request.

    Purely test-side: `_dispatch()` obtains the gate through `_load_gate()`, so
    the delay is injected by patching that lookup. No fault-injection seam is
    added to the shipped tool, which would be a second thing to get wrong.
    """

    def __init__(self, real, arrive):
        self._real = real
        self._arrive = arrive

    def __getattr__(self, name):
        return getattr(self._real, name)

    def evaluate_claims(self, proposed, existing):
        verdict = self._real.evaluate_claims(proposed, existing)
        self._arrive()          # after the read, before the append
        return verdict


def test_two_threads_racing_one_free_lane_cannot_both_land(mod, monkeypatch):
    """Both filers reach the decision point with the lane free. One row lands.

    Pre-fix this returns [EXIT_OK, EXIT_OK] and writes two rows for one lane.
    The barrier makes that deterministic: neither filer can append until both
    have read, which is the interleaving Codex described.

    Post-fix the second filer cannot even READ until the first has appended, so
    it waits, sees the row, and refuses. The barrier then times out, which is
    the positive evidence that the two transactions were serialized rather than
    merely lucky.
    """
    lane = "feat/free-lane-under-race"
    barrier = threading.Barrier(2)
    tripped = []

    def arrive():
        try:
            barrier.wait(timeout=2.0)
            tripped.append(True)
        except threading.BrokenBarrierError:
            pass    # serialized: the other filer never got here at the same time

    real = mod._load_gate()
    monkeypatch.setattr(mod, "_load_gate", lambda: _RaceGate(real, arrive))

    results = {}

    def file_row(owner):
        results[owner] = mod.main(
            ["claim", "--owner", owner, "--branch", lane, "--scope", "racing"])

    threads = [threading.Thread(target=file_row, args=(o,))
               for o in ("AGENT-B", "AGENT-C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
        assert not t.is_alive(), "a filer never returned -- the lock deadlocked"

    rows = [r for r in _rows(mod) if lane in r]
    assert len(rows) == 1, (
        f"one lane, {len(rows)} owners: {rows}. The check and the append are "
        "not one transaction."
    )
    assert sorted(results.values()) == [mod.EXIT_OK, mod.EXIT_REFUSED], (
        f"exactly one filer must be told no: {results}"
    )
    assert not tripped, (
        "both filers were inside the decision window at once, so the "
        "transactions were not serialized"
    )


_RACE_CHILD = r"""
import importlib.util, os, sys, time, pathlib
TOOL, REG, BARRIER, OWNER, LANE = sys.argv[1:6]
spec = importlib.util.spec_from_file_location("register_append", TOOL)
mod = importlib.util.module_from_spec(spec)
sys.modules["register_append"] = mod  # pydantic resolves types via sys.modules
spec.loader.exec_module(mod)
mod.REGISTER = pathlib.Path(REG)

real = mod._load_gate()

class Gate:
    def __getattr__(self, name):
        return getattr(real, name)
    def evaluate_claims(self, proposed, existing):
        v = real.evaluate_claims(proposed, existing)
        # Filesystem barrier: announce, then wait for the other process to have
        # read too. Both children are therefore holding a 'lane is free' verdict
        # at the same moment -- if the lock does not exist.
        with open(BARRIER, 'a') as fh:
            fh.write(str(os.getpid()) + '\n')
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if len(open(BARRIER).read().split()) >= 2:
                break
            time.sleep(0.02)
        return v

mod._load_gate = lambda: Gate()
sys.exit(mod.main(['claim', '--owner', OWNER, '--branch', LANE,
                   '--scope', 'racing across processes']))
"""


def test_two_PROCESSES_racing_one_free_lane_cannot_both_land(mod, tmp_path):
    """The same race between separate processes -- what the fleet actually does.

    The threaded test above proves the lock serializes two open file
    descriptions; only this one proves it serializes two `make register-claim`
    invocations, which is the case in the report.
    """
    lane = "feat/free-lane-cross-process"
    child = tmp_path / "race_child.py"
    child.write_text(_RACE_CHILD, encoding="utf-8")
    barrier = tmp_path / "barrier.txt"
    barrier.write_text("", encoding="utf-8")

    procs = [
        subprocess.Popen(
            [sys.executable, str(child), str(TOOL), str(mod.REGISTER),
             str(barrier), owner, lane],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for owner in ("AGENT-B", "AGENT-C")
    ]
    outs = [p.communicate(timeout=90) for p in procs]
    codes = [p.returncode for p in procs]

    rows = [r for r in _rows(mod) if lane in r]
    assert len(rows) == 1, (
        f"one lane, {len(rows)} owners across processes: {rows}\n"
        + "\n".join(o[1] for o in outs)
    )
    assert sorted(codes) == [mod.EXIT_OK, mod.EXIT_REFUSED], (
        f"exit codes {codes}\n" + "\n".join(o[1] for o in outs)
    )


def test_a_lock_this_tool_cannot_take_is_exit_3_and_never_exit_1(mod, monkeypatch):
    """A wedged holder must not be reported as 'another owner holds your lane'.

    Exit 1 is a fact about the register. If the transaction never ran, no such
    fact was established, and a filer who backs off on that reading has been
    misinformed by the only write path they have.
    """
    monkeypatch.setattr(mod, "LOCK_TIMEOUT_SECONDS", 0.2)
    before = mod.REGISTER.read_text(encoding="utf-8")
    with mod.register_lock(mod.REGISTER):
        rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/blocked",
                       "--scope", "cannot get in"])
    assert rc == mod.EXIT_UNMEASURED, f"a lock timeout must be 3, got {rc}"
    assert mod.REGISTER.read_text(encoding="utf-8") == before


def test_the_read_modify_write_roads_take_the_lock_too(mod, monkeypatch, tmp_path):
    """`docs` and `amend` rewrite the WHOLE file, so an unlocked append is LOST.

    Codex named only the append path. These two are worse in kind: the append
    race duplicates a row, while a read-modify-write racing an append DELETES
    one, silently, from a ledger whose whole contract is append-only. Both must
    contend for the same lock, which is what this asserts.
    """
    monkeypatch.setattr(mod, "LOCK_TIMEOUT_SECONDS", 0.2)
    prose = tmp_path / "block.md"
    prose.write_text("some prose\n", encoding="utf-8")
    before = mod.REGISTER.read_text(encoding="utf-8")

    with mod.register_lock(mod.REGISTER):
        docs_rc = mod.main(["docs", "--anchor", "# register",
                            "--text-file", str(prose)])
        amend_rc = mod.main(["amend", "--owner", "AGENT-A",
                             "--branch", "feat/widget", "--co-owner", "AGENT-B"])

    assert docs_rc == mod.EXIT_UNMEASURED, f"docs ignored the lock: {docs_rc}"
    assert amend_rc == mod.EXIT_UNMEASURED, f"amend ignored the lock: {amend_rc}"
    assert mod.REGISTER.read_text(encoding="utf-8") == before


# --- the make road: a field value must never become a shell word -------------

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"
REGISTER_TARGETS = ("register-claim", "register-release", "register-amend",
                    "register-docs")
# Everything a caller supplies as CONTENT. Not ARGS, which carries flags the
# caller wrote themselves and is expanded deliberately.
FIELD_VARS = ("OWNER", "BRANCH", "SCOPE", "TTL", "CO_OWNER", "ANCHOR", "TEXT_FILE")


def _register_recipe_lines():
    """The tab-indented recipe lines of the four register targets."""
    text = MAKEFILE.read_text(encoding="utf-8")
    out, current = [], None
    for line in text.split("\n"):
        if line.startswith("\t"):
            if current:
                out.append((current, line))
            continue
        name = line.split(":")[0].strip()
        current = name if name in REGISTER_TARGETS else None
    return out


def test_no_register_field_is_expanded_into_a_recipe_line():
    """A value interpolated into a recipe is handed to a SHELL before python.

    Measured at 776b429b9, when SCOPE already travelled by environment and only
    the emptiness guard still expanded it:

        make register-claim ... SCOPE='scope with `touch /tmp/MARK` inside'
        -> the recorded row was CORRECT, and /tmp/MARK was created

    A correct row is not the whole test; the command ran. 6 of 7 field/target
    combinations executed an embedded substitution, OWNER / BRANCH / TTL /
    ANCHOR having no environment door at all. The guards now test the exported
    variable, so no field is ever part of a command string.
    """
    offenders = []
    for target, line in _register_recipe_lines():
        for var in FIELD_VARS:
            if "$(%s)" % var in line or "$(or $(%s)" % var in line:
                offenders.append(f"{target}: {line.strip()}")
    assert not offenders, (
        "register field values expanded into a recipe -- a shell sees them "
        "before python does:\n  " + "\n  ".join(offenders)
    )


def test_the_register_targets_use_a_dependency_aware_interpreter():
    """`$(PYTHON)` honours no PEP 723 declaration.

    `register_append.py` imports the collision hook, which needs PyYAML to read
    the identity vocabulary. Without it the gate compares owner strings exactly
    -- and one identity in this register spells itself several ways, so a
    RELEASE stops closing the CLAIM it is closing.
    """
    bad = [f"{t}: {l.strip()}" for t, l in _register_recipe_lines()
           if "register_append.py" in l and "$(REGISTER_PYTHON)" not in l]
    assert not bad, (
        "the sanctioned path must run on an interpreter chosen for the gate's "
        "dependencies:\n  " + "\n  ".join(bad))


def test_the_tool_declares_its_own_pep723_dependency():
    """The hook's block does nothing for an interpreter chosen by THIS file.

    `uv run --script` reads the PEP 723 block of the script it is pointed at.
    Pointed at `register_append.py`, the hook's declaration is never consulted.
    """
    head = TOOL.read_text(encoding="utf-8").split('"""')[0]
    assert "# /// script" in head, "no PEP 723 block"
    assert "pyyaml" in head, f"PyYAML not declared:\n{head}"


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_a_substitution_in_a_field_value_is_not_executed_by_make(tmp_path):
    """The behavioural half of the static check above. Runs the real target.

    `--dry-run`, so nothing is written to any register; the marker file is the
    only evidence sought.
    """
    marker = tmp_path / "EXECUTED"
    payload = "scope with `touch %s` inside" % marker
    r = subprocess.run(
        ["make", "-C", str(MAKEFILE.parent), "register-claim",
         "OWNER=PROBE-NODE", "BRANCH=fix/probe-lane-not-real",
         "TTL=n/a", "SCOPE=" + payload, "ARGS=--dry-run"],
        capture_output=True, text=True, timeout=180)
    # ASSERTED FIRST, because a target that fell over would make the marker
    # check pass while proving nothing. The row must come out correct AND the
    # substitution must not have run -- the defect produced a correct row.
    assert r.returncode == 0, f"the target did not run:\n{r.stdout}\n{r.stderr}"
    assert payload in r.stdout, (
        f"the row does not carry the scope verbatim:\n{r.stdout}")
    assert not marker.exists(), (
        "make executed a command substitution embedded in SCOPE")


# --- absorbed-expansion symptoms --------------------------------------------

def test_refuses_a_scope_with_an_empty_assignment(mod, capsys):
    """`NAME=` followed by whitespace is the swallowed-expansion signature.

    A double-quoted SCOPE='...' where the shell already expanded `${X}` to
    nothing arrives here as an empty assignment; once appended it is
    uncorrectable, so it is refused on content alone.
    """
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope", "the env had SUPABASE_ANON_KEY= and nothing else"])
    assert rc == mod.EXIT_REFUSED
    assert len(_rows(mod)) == 1, "a symptom-refused claim must not be written"
    err = capsys.readouterr().err
    assert "empty assignment" in err
    assert "--literal-assignments" in err, (
        "a refusal with no named override is a dead end, not a gate")


def test_literal_assignments_override_files_quoted_evidence(mod):
    """The one legitimate use: a row QUOTING empty assignments as evidence.

    A real live row reads 'env.tier-ui had empty SUPABASE_ANON_KEY= entries';
    a bare refusal would make that row unfileable forever.
    """
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope", "env.tier-ui had empty SUPABASE_ANON_KEY= entries",
                   "--literal-assignments"])
    assert rc == mod.EXIT_OK
    assert len(_rows(mod)) == 2
    assert "SUPABASE_ANON_KEY= entries" in _rows(mod)[-1]


def test_literal_assignments_does_not_waive_the_compose_chain(mod):
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope", "ran docker compose -f a.yml --env-file x "
                              "--env-file y up -d with FOO= empty too",
                   "--literal-assignments"])
    assert rc == mod.EXIT_REFUSED
    assert len(_rows(mod)) == 1


def test_refuses_a_compose_invocation_with_its_env_file_chain(mod, capsys):
    """A make variable expanded into a full compose command -- the other
    recorded incident, verbatim in shape."""
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope", "up-external runs docker compose --project-directory x "
                              "--env-file env.shared --env-file env.tier-agent up -d"])
    assert rc == mod.EXIT_REFUSED
    assert "--env-file" in capsys.readouterr().err
    assert len(_rows(mod)) == 1


def test_a_single_implausibly_long_token_is_refused(mod):
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope", "x " + "a" * (mod.LONG_TOKEN_LIMIT + 1)])
    assert rc == mod.EXIT_REFUSED
    assert len(_rows(mod)) == 1
    # The longest legitimate token in the live register (153 chars, a
    # signature string) must keep filing.
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/other-lane",
                   "--scope", "signed " + "S" * 153])
    assert rc == mod.EXIT_OK


def test_scope_file_content_is_validated_too(mod, tmp_path):
    """Validation runs on the RESOLVED prose, so --scope-file is not a bypass."""
    f = tmp_path / "scope.md"
    f.write_text("the env had TOKEN= missing", encoding="utf-8")
    rc = mod.main(["claim", "--owner", "AGENT-B", "--branch", "feat/free-lane",
                   "--scope-file", str(f)])
    assert rc == mod.EXIT_REFUSED
    assert len(_rows(mod)) == 1


def test_docs_block_with_a_symptom_is_refused(mod, tmp_path):
    """docs mode inserts prose into the register; the same expansion could
    arrive through REGISTER_TEXT_FILE, so it gets the same check."""
    register = mod.REGISTER
    anchor = "# register"
    f = tmp_path / "block.md"
    f.write_text("note: KEY= was empty in the env file\n", encoding="utf-8")
    rc = mod.main(["docs", "--anchor", anchor, "--text-file", str(f)])
    assert rc == mod.EXIT_REFUSED
    assert register.read_text(encoding="utf-8").count("KEY=") == 0


# Fixtures with EXPECTED verdicts, not two paths compared against each other.
#
# The previous version of this test evaluated `expansion_symptoms(text)` on one
# side and `RegisterProse(text=text)` on the other -- and the model called that
# same function, so both sides were one expression. It could not fail, in
# either direction, for any input. Pinning each path against a stated expected
# outcome is what makes a divergence visible.
PROSE_CASES = [
    ("clean scope with `backticks` and TTL=72h inside", False),
    ("swallowed TOKEN= expansion", True),
    ("docker compose --env-file a --env-file b up", True),
    ("token " + "a" * 301, True),
    ("a normal sentence about a lane that landed", False),
    ("quoting ``SUPABASE_ANON_KEY=`` as evidence", False),  # backticked span
]


@pytest.mark.parametrize("text,should_reject", PROSE_CASES)
def test_the_model_rejects_exactly_the_stated_cases(mod, text, should_reject):
    """The typed surface, pinned against expected verdicts."""
    if mod.RegisterProse is None:
        pytest.skip("pydantic not importable in this interpreter")
    from pydantic import ValidationError
    try:
        mod.RegisterProse(text=text)
        rejected = False
    except ValidationError:
        rejected = True
    assert rejected is should_reject, text


@pytest.mark.parametrize("text,should_reject", PROSE_CASES)
def test_the_offline_fallback_rejects_exactly_the_same_cases(mod, text, should_reject):
    """The stdlib path, pinned against the SAME expected verdicts.

    Independently asserted rather than compared to the model, so if the two
    ever diverge the failure names which one moved.
    """
    assert bool(mod.expansion_symptoms(text)) is should_reject, text


def test_the_model_is_the_enforcement_not_a_mirror(mod):
    """assert_prose_clean must route through the model when it is importable.

    The structural assertion the old agreement test could not make: that the
    typed surface is on the enforcement path at all. Without this, the model
    could be deleted and every other test here would still pass.
    """
    if mod.RegisterProse is None:
        pytest.skip("pydantic not importable in this interpreter")
    calls = []
    original = mod.RegisterProse

    class Spy(original):  # type: ignore[misc,valid-type]
        def __init__(self, **kwargs):
            calls.append(kwargs)
            super().__init__(**kwargs)

    mod.RegisterProse = Spy
    try:
        mod.assert_prose_clean("a clean scope line")
    finally:
        mod.RegisterProse = original
    assert calls, (
        "assert_prose_clean() did not construct RegisterProse -- the model is "
        "decorative again and the stdlib copy is the real enforcement"
    )


def test_the_waiver_is_a_field_on_the_model(mod):
    """`literal_assignments` waives the assignment symptom and nothing else."""
    if mod.RegisterProse is None:
        pytest.skip("pydantic not importable in this interpreter")
    from pydantic import ValidationError
    mod.RegisterProse(text="quoted SUPABASE_ANON_KEY= entries",
                      literal_assignments=True)
    with pytest.raises(ValidationError):
        mod.RegisterProse(text="docker compose --env-file a --env-file b up",
                          literal_assignments=True)


def test_usage_lines_name_the_single_quote_reason():
    """The static half of the invocation-boundary fix: the usage line must say
    WHY single quotes, not merely show them."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    claim_block = makefile.split("register-claim:", 1)[1].split("register-release:", 1)[0]
    assert "LOAD-BEARING" in claim_block
    assert "uncorrectable" in claim_block
    assert "--scope-file" in claim_block
    release_block = makefile.split("register-release:", 1)[1].split("register-amend:", 1)[0]
    assert "single-quote SCOPE" in release_block


# --- the row model: damage made unrepresentable, not detected afterwards -----
#
# `expansion_symptoms()` inspects a value AFTER it has been built. These pin
# the other half: a field that cannot legally appear in a ledger row is refused
# by the type before `build_row` renders anything.

def test_a_row_cannot_be_filed_under_an_unparsed_verb(mod):
    """`kind` was any string, and only CLAIM/RELEASE/UPDATE are ever read.

    A typo appended cleanly and was then invisible to `register_status`,
    `identity_lineage` and the collision gate alike -- a row that exists in the
    file and not in the ledger.
    """
    with pytest.raises(ValueError) as exc:
        mod.build_row("CLIAM", "B850-CLAUDE (Knuckles)", "fix/x", "typo verb")
    assert "CLAIM" in str(exc.value)


@pytest.mark.parametrize("field,value", [
    ("owner", "B850\x1b[0m-CLAUDE"),      # ESC: pasted terminal colour codes
    ("branch", "fix/x\nplus a second line"),
    ("scope", "up on \x00.0.0.0:4482"),   # the exact corruption 8b040956e fixed
])
def test_no_field_may_carry_a_control_character(mod, field, value):
    """The register carries 21 of these already, from pasted terminal output.

    A row is one line of text; a newline in a field silently forges a second
    row, and a NUL makes the whole file read as binary to grep and to GitHub.
    """
    kwargs = dict(kind="CLAIM", owner="B850-CLAUDE (Knuckles)",
                  branch="fix/x", scope="clean")
    kwargs[field] = value
    with pytest.raises(ValueError) as exc:
        mod.build_row(**kwargs)
    assert "control character" in str(exc.value)


def test_an_unparseable_ttl_is_refused_before_the_row_is_built(mod):
    """`_ttl_delta` raised -- but only after the row string was assembled."""
    with pytest.raises(ValueError):
        mod.build_row("CLAIM", "B850-CLAUDE (Knuckles)", "fix/x", "s",
                      ttl="72 hours")


def test_the_row_grammar_is_unchanged_by_the_model(mod):
    """The model validates and normalises; it must not alter the rendering."""
    row = mod.build_row("CLAIM", "B850-CLAUDE (Knuckles)", "fix/x", "some scope",
                        ttl="72h",
                        now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert row.startswith("- `2026-01-01T00:00:00Z` CLAIM `B850-CLAUDE (Knuckles)`")
    assert "branch: `fix/x`" in row
    assert "**TTL 72h (expires `2026-01-04T00:00:00Z`)**" in row
    assert row.endswith("· scope: some scope\n")
