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
