"""The BATON close: a peer passes or closes another AGInTZ's lane, with VERIFIED authority.

The AGInTZ are peers; a lane is a Known Road handed on like a relay baton, and
identity on a row is attribution, not territory. Until this, a RELEASE paired
only with the SIGNING owner's claims, so a lane whose holder had stopped
running could not be closed by anyone.

Two rows. The GRANT is a NOTE signed by an operator identity (or by the
holder) naming the lane, the holder and the receiver. The BATON is a RELEASE
by the receiver carrying `baton-from: <holder>` and citing the grant by its
timestamp (`ruling:` for an operator grant, `handoff:` for a holder grant).
The reader RESOLVES that reference; free text is not authority. A baton that
fails any check closes NOTHING -- it is never read as an ordinary release of
the signer's own lanes.

EVERY LANE-STATE ASSERTION GOES THROUGH `open_claims_in()`, the gate's own
authority, so the same assertions run unchanged against the pre-baton gate as
a behavioural failing-before control (the row stays open, or the base gate
closes the SIGNER's lane; no symbol is missing).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_append.py"
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"
LIVE_REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"

# Registered identities (pmoves/config/identity_vocabulary.yaml).
HOLDER = "CRUSH-GLM52 (Knuckles)"        # -> crush
SIGNER = "B850-CLAUDE (Knuckles)"        # -> b850-claude
OTHER = "B850-CLAUDE-FUNNEL (Knuckles)"  # -> b850-claude-funnel
OPERATOR = "DARKXSIDE"                   # -> darkxside (operator identity)
UNKNOWN = "NOBODY-XYZ (nowhere)"         # -> not in the vocabulary

HELD = (
    f"- `2026-09-20T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
    f"- `2026-09-20T00:05:00Z` CLAIM `{HOLDER}` branch: `fix/sprocket` "
    "· scope: **and this one.**\n"
    f"- `2026-09-20T00:10:00Z` CLAIM `{SIGNER}` branch: `chore/mine` "
    "· scope: **the signer's own lane.**\n"
)

RULING_TS = "2026-09-30T12:00:00Z"
HANDOFF_TS = "2026-09-30T13:00:00Z"
# An operator grant passing BOTH holder lanes to SIGNER, and a holder grant.
RULING = (f"- `{RULING_TS}` NOTE `{OPERATOR}` branch: `feat/widget` "
          f"· baton-from: `{HOLDER}` · baton-to: `{SIGNER}` "
          "· scope: ruling - also branch: `fix/sprocket`\n")
HANDOFF = (f"- `{HANDOFF_TS}` NOTE `{HOLDER}` branch: `fix/sprocket` "
           f"· baton-to: `{SIGNER}` · scope: handing this over\n")
GRANTED = HELD + RULING + HANDOFF


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gate():
    return _load(HOOK, "claim_collision_pre_baton")


def _lanes(gate, text: str) -> dict:
    return {
        owner: sorted(lane for _ln, lanes, _raw, _p in rows for lane in lanes)
        for owner, rows in gate.open_claims_in(text).items()
    }


def _release(fields: str, signer: str = SIGNER, ts: str = "2026-10-01T00:00:00Z") -> str:
    return (f"- `{ts}` RELEASE `{signer}` {fields} "
            "· scope: **passing the baton.**\n")


def _baton(lane: str, authority: str, holder: str = HOLDER, **kw) -> str:
    return _release(f"branch: `{lane}` · baton-from: `{holder}` · {authority}", **kw)


BEFORE = {"crush": ["feat/widget", "fix/sprocket"], "b850-claude": ["chore/mine"]}


# --------------------------------------------------------------- the reader --

def test_baton_under_an_operator_ruling_closes_only_the_named_lane(gate):
    row = _baton("feat/widget", f"ruling: `{RULING_TS}`")
    assert _lanes(gate, GRANTED) == BEFORE
    assert _lanes(gate, GRANTED + row) == {
        "crush": ["fix/sprocket"],          # the holder's OTHER lane stays held
        "b850-claude": ["chore/mine"],      # the signer's own lane is untouched
    }


def test_baton_under_the_holders_own_handoff(gate):
    row = _baton("fix/sprocket", f"handoff: `{HANDOFF_TS}`")
    assert _lanes(gate, GRANTED + row)["crush"] == ["feat/widget"]


def test_baton_event_records_both_identities_and_the_grant(gate):
    row = _baton("feat/widget", f"ruling: `{RULING_TS}`")
    [event] = gate.baton_events_in(GRANTED + row)
    assert (event.signer, event.holder, event.holder_key) == (SIGNER, HOLDER, "crush")
    assert event.authority == ("ruling", RULING_TS)
    assert event.grant_line == 4 and event.closed == {"feat/widget"}
    assert not event.problem


# The four refusals the reviewer named, plus the shape refusals. Each one
# names the SIGNER's own lane `chore/mine` too wherever the grammar allows, so
# a fallback to "ordinary release by the signer" would be visible as
# `chore/mine` closing.
REFUSED = {
    "free-text authority":
        (_baton("feat/widget", "ruling: `operator said so on 2026-10-01`"), "free text"),
    "dangling reference":
        (_baton("feat/widget", "ruling: `2026-09-30T23:59:59Z`"), "resolves to no"),
    "ruling from a non-operator":
        (_baton("fix/sprocket", f"ruling: `{HANDOFF_TS}`"), "not an operator"),
    "handoff from someone other than the holder":
        (_baton("feat/widget", f"handoff: `{RULING_TS}`"), "not by the holder"),
    "grant for a different lane":
        (_baton("chore/mine", f"handoff: `{HANDOFF_TS}`"), "does not name"),
    "grant to a different receiver":
        (_baton("feat/widget", f"ruling: `{RULING_TS}`", signer=OTHER), "not to this"),
    "grant for a different holder":
        (_baton("chore/mine", f"ruling: `{RULING_TS}`", holder=OTHER), "not of this"),
    "no authority at all":
        (_baton("chore/mine", "scope-less"), "no authority"),
    "unknown holder":
        (_baton("feat/widget", f"ruling: `{RULING_TS}`", holder=UNKNOWN),
         "not a registered identity"),
    "unknown signer":
        (_baton("feat/widget", f"ruling: `{RULING_TS}`", signer=UNKNOWN),
         "not a registered identity"),
    "no lane":
        (_release(f"baton-from: `{HOLDER}` · ruling: `{RULING_TS}`"), "names no lane"),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_a_baton_that_fails_any_check_closes_nothing(gate, case):
    row, _needle = REFUSED[case]
    assert _lanes(gate, GRANTED + row) == BEFORE


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_a_refused_baton_says_why(gate, case):
    row, needle = REFUSED[case]
    [event] = gate.baton_events_in(GRANTED + row)
    assert needle in event.problem and not event.closed


def test_a_grant_filed_after_the_baton_does_not_authorise_it(gate):
    row = _baton("feat/widget", f"ruling: `{RULING_TS}`")
    assert _lanes(gate, HELD + row + RULING) == {
        "crush": ["feat/widget", "fix/sprocket"], "b850-claude": ["chore/mine"]}
    [event] = gate.baton_events_in(HELD + row + RULING)
    assert "ABOVE it" in event.problem


def test_a_grant_stamped_after_the_baton_does_not_authorise_it(gate):
    late = RULING.replace(RULING_TS, "2026-10-02T00:00:00Z")
    row = _baton("feat/widget", "ruling: `2026-10-02T00:00:00Z`")
    assert _lanes(gate, HELD + late + row) == BEFORE
    [event] = gate.baton_events_in(HELD + late + row)
    assert "AFTER the baton" in event.problem


def test_two_grants_with_one_timestamp_are_ambiguous(gate):
    row = _baton("feat/widget", f"ruling: `{RULING_TS}`")
    assert _lanes(gate, GRANTED + RULING + row) == BEFORE
    [event] = gate.baton_events_in(GRANTED + RULING + row)
    assert "ambiguous" in event.problem


def test_a_claim_row_is_not_a_grant(gate):
    # Same timestamp as a CLAIM: only NOTE/HANDOFF rows can grant.
    row = _baton("feat/widget", "ruling: `2026-09-20T00:00:00Z`")
    assert _lanes(gate, GRANTED + row) == BEFORE


def test_baton_naming_a_granted_lane_the_holder_no_longer_holds_is_a_noop(gate):
    gone = (f"- `2026-09-30T14:00:00Z` RELEASE `{HOLDER}` branch: `feat/widget` "
            "· scope: done\n")
    row = _baton("feat/widget", f"ruling: `{RULING_TS}`")
    text = GRANTED + gone + row
    assert _lanes(gate, text) == _lanes(gate, GRANTED + gone)
    [event] = gate.baton_events_in(text)
    assert not event.problem and event.not_held == {"feat/widget"}
    assert "holds no open row" in event.warning


def test_bare_release_by_a_co_owner_still_does_not_close(gate):
    text = (f"- `2026-09-20T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
            f"· co-owners: `{SIGNER}` (reviewed) · scope: **shared.**\n")
    bare = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` "
            "· scope: **co-owner, bare release.**\n")
    named = (f"- `2026-10-01T00:01:00Z` RELEASE `{SIGNER}` branch: `feat/widget` "
             "· scope: **co-owner, named release.**\n")
    assert _lanes(gate, text + bare + named) == {"crush": ["feat/widget"]}


def test_a_quoted_baton_field_is_a_mention_not_a_baton(gate):
    row = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `chore/mine` "
           f"· scope: **the new field reads ``baton-from: `{HOLDER}` ``.**\n")
    assert _lanes(gate, HELD + row) == {"crush": ["feat/widget", "fix/sprocket"]}


def test_no_vocabulary_means_no_baton_not_an_ordinary_release(gate, monkeypatch):
    monkeypatch.setattr(gate, "_LINEAGE", None)
    monkeypatch.setattr(gate, "_FOLDER", None)
    row = _baton("chore/mine", f"ruling: `{RULING_TS}`")
    before = gate.open_claims_in(GRANTED)
    assert gate.open_claims_in(GRANTED + row) == before
    [event] = gate.baton_events_in(GRANTED + row)
    assert "vocabulary is unavailable" in event.problem


# --------------------------------------------------------------- the writer --

@pytest.fixture()
def mod(tmp_path: Path, monkeypatch):
    for var in ("REGISTER_BATON_FROM", "REGISTER_BATON_TO", "REGISTER_RULING",
                "REGISTER_HANDOFF", "REGISTER_OWNER", "REGISTER_BRANCH",
                "REGISTER_SCOPE", "REGISTER_SCOPE_FILE", "REGISTER_CO_OWNERS",
                "REGISTER_TTL"):
        monkeypatch.delenv(var, raising=False)
    m = _load(TOOL, "register_append_baton")
    register = tmp_path / "register.md"
    register.write_text("# register\n" + GRANTED, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    # "Committed" = on origin/main. Here: the grants are committed by default;
    # individual tests narrow it.
    # raising=False so this fixture also loads the PRE-baton tool, where the
    # symbol does not exist -- the failing-before control then reports the
    # writer's BEHAVIOUR rather than a fixture error.
    monkeypatch.setattr(m, "_committed_register_text",
                        lambda: "# register\n" + GRANTED, raising=False)
    return m


def _run(mod, *extra, owner=SIGNER):
    return mod.main(["release", "--owner", owner, "--scope", "passing the baton",
                     *extra])


def _text(mod) -> str:
    return mod.REGISTER.read_text(encoding="utf-8")


def test_write_road_files_a_baton_that_the_gate_reads(mod, gate, capsys):
    rc = _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER,
              "--ruling", RULING_TS)
    assert rc == 0
    last = _text(mod).rstrip("\n").split("\n")[-1]
    assert f"RELEASE `{SIGNER}`" in last and f"baton-from: `{HOLDER}`" in last
    assert f"ruling: `{RULING_TS}`" in last
    assert _lanes(gate, _text(mod))["crush"] == ["fix/sprocket"]
    assert "BATON" in capsys.readouterr().err


@pytest.mark.parametrize("extra, needle, owner", [
    (("--branch", "feat/widget", "--baton-from", HOLDER), "authority", SIGNER),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--ruling",
      "operator said so"), "free text", SIGNER),
    (("--branch", "feat/widget", "--ruling", RULING_TS), "without --baton-from", SIGNER),
    (("--branch", "feat/widget", "--baton-from", UNKNOWN, "--ruling", RULING_TS),
     "not a registered identity", SIGNER),
    (("--branch", "chore/mine", "--baton-from", SIGNER, "--ruling", RULING_TS),
     "same identity", SIGNER),
    (("--all-lanes", "--baton-from", HOLDER, "--ruling", RULING_TS), "never bare", SIGNER),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--ruling", RULING_TS,
      "--handoff", HANDOFF_TS), "ONE authority", SIGNER),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--ruling",
      "2026-09-30T23:59:59Z"), "resolves to no", SIGNER),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--ruling", RULING_TS),
     "not to this", OTHER),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--handoff", RULING_TS),
     "not by the holder", SIGNER),
])
def test_write_road_refuses_a_baton_it_cannot_verify(mod, capsys, extra, needle, owner):
    before = _text(mod)
    assert _run(mod, *extra, owner=owner) == 3
    assert _text(mod) == before
    assert needle in capsys.readouterr().err


def test_write_road_refuses_a_grant_that_is_not_committed(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "_committed_register_text", lambda: "# register\n" + HELD)
    before = _text(mod)
    assert _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER,
                "--ruling", RULING_TS) == 1
    assert _text(mod) == before
    assert "not on origin/main" in capsys.readouterr().err


def test_write_road_is_unmeasured_when_git_cannot_answer(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "_committed_register_text", lambda: None)
    assert _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER,
                "--ruling", RULING_TS) == 3
    assert "NOT MEASURED" in capsys.readouterr().err


def test_write_road_refuses_a_baton_for_a_lane_the_holder_no_longer_holds(mod, capsys):
    gone = (f"- `2026-09-30T14:00:00Z` RELEASE `{HOLDER}` branch: `feat/widget` "
            "· scope: done\n")
    mod.REGISTER.write_text(_text(mod) + gone, encoding="utf-8")
    before = _text(mod)
    assert _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER,
                "--ruling", RULING_TS) == 1
    assert _text(mod) == before
    err = capsys.readouterr().err
    assert "WARNING" in err and "holds no open row" in err


def test_write_road_refuses_a_scope_that_would_close_a_second_held_lane(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "feat/widget",
                   "--baton-from", HOLDER, "--ruling", RULING_TS,
                   "--scope", "done; see also `fix/sprocket`"])
    assert rc == 1 and _text(mod) == before
    assert "fix/sprocket" in capsys.readouterr().err


def test_plain_release_whose_scope_declares_a_baton_is_refused(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                   "--scope", f"baton-from: `{HOLDER}` ruling: `{RULING_TS}`"])
    assert rc == 3 and _text(mod) == before
    assert "DECLARES a `baton-from:` field" in capsys.readouterr().err


def test_ordinary_release_is_unchanged(mod, gate):
    assert mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                     "--scope", "done"]) == 0
    assert _lanes(gate, _text(mod)) == {"crush": ["feat/widget", "fix/sprocket"]}


def test_note_road_files_an_operator_grant_the_reader_honours(mod, gate):
    rc = mod.main(["note", "--owner", OPERATOR, "--branch", "fix/sprocket",
                   "--baton-from", HOLDER, "--baton-to", OTHER,
                   "--scope", "operator ruling: pass it on"])
    assert rc == 0
    grant = _text(mod).rstrip("\n").split("\n")[-1]
    assert f"NOTE `{OPERATOR}`" in grant and f"baton-to: `{OTHER}`" in grant
    ts = grant.split("`")[1]
    row = _baton("fix/sprocket", f"ruling: `{ts}`", signer=OTHER,
                 ts="2099-01-01T00:00:00Z")
    assert _lanes(gate, _text(mod) + row)["crush"] == ["feat/widget"]


@pytest.mark.parametrize("extra, needle, owner", [
    (("--branch", "fix/sprocket", "--baton-from", HOLDER, "--baton-to", OTHER),
     "neither the holder", SIGNER),
    (("--branch", "fix/sprocket", "--baton-to", UNKNOWN), "receiver", HOLDER),
    (("--baton-from", HOLDER, "--baton-to", OTHER), "--branch", OPERATOR),
    (("--branch", "fix/sprocket", "--baton-from", HOLDER), "--baton-to", OPERATOR),
    (("--branch", "fix/sprocket", "--baton-to", OTHER, "--ruling", RULING_TS),
     "belong on the baton RELEASE", HOLDER),
])
def test_note_road_refuses_a_grant_no_reader_would_honour(mod, capsys, extra, needle, owner):
    before = _text(mod)
    assert mod.main(["note", "--owner", owner, "--scope", "grant", *extra]) == 3
    assert _text(mod) == before
    assert needle in capsys.readouterr().err


def test_baton_rows_round_trip_for_register_sync_reapply(mod):
    for row in (
        mod.build_row("RELEASE", SIGNER, "feat/widget", "passing", baton_from=HOLDER,
                      handoff=HANDOFF_TS),
        mod.build_row("NOTE", OPERATOR, "feat/widget", "grant", baton_from=HOLDER,
                      baton_to=SIGNER),
    ):
        parsed = mod._parse_rendered(row.rstrip("\n"))
        assert mod._assert_round_trips(row.encode()) == parsed


def test_register_status_reports_a_baton_that_closed_nothing(tmp_path, capsys):
    status = _load(TOOL.with_name("register_status.py"), "register_status_baton")
    register = tmp_path / "register.md"
    register.write_text("# register\n" + GRANTED + _baton(
        "feat/widget", "ruling: `free text`"), encoding="utf-8")
    rc = status.main(["--register", str(register), "--now", "2026-10-01T00:00:00Z"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "BATON ROWS THAT DID NOT DO WHAT THEY SAID (1)" in out
    assert "closed NOTHING" in out and "free text" in out


# ---------------------------------------------------------- monotonicity ----

def test_live_register_carries_no_baton_rows_yet_so_pairing_is_unchanged(gate, tmp_path):
    """With no baton row in the register, the new pairing must equal the old.

    The old pairing is the base revision of the gate, read with `git show` --
    never by reverting the working tree. Skipped when git or the base ref is
    unavailable (a shallow CI clone), and says so.
    """
    text = LIVE_REGISTER.read_text(encoding="utf-8")
    events = gate.baton_events_in(text)
    if events:
        pytest.skip(f"{len(events)} baton row(s) present; monotonicity is "
                    "then asserted only for non-baton owners (see PR body)")
    try:
        base = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show",
             "origin/main:.claude/hooks/governance/claim-collision-pre.py"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"base gate unavailable via git show ({exc})")
    if "def baton_events_in" in base:
        pytest.skip("origin/main already carries the baton pairing")
    old_path = tmp_path / "claim_collision_pre_base.py"
    old_path.write_text(base, encoding="utf-8")
    old = _load(old_path, "claim_collision_pre_base")
    # The base gate locates the identity module relative to its own file,
    # which is now in tmp_path. Hand it the SAME vocabulary the new gate uses,
    # so the comparison isolates the pairing change and nothing else.
    old._LINEAGE = gate._load_lineage()
    assert old._LINEAGE is not None, "vocabulary unavailable: COULD-NOT-MEASURE"
    old_open, new_open = old.open_claims_in(text), gate.open_claims_in(text)
    rows = sum(1 for line in text.split("\n") if line.lstrip().startswith("- `"))
    print(f"monotonicity: {len(text.split(chr(10)))} lines, {rows} rows; "
          f"old open owners={len(old_open)} rows={sum(map(len, old_open.values()))}; "
          f"new open owners={len(new_open)} rows={sum(map(len, new_open.values()))}")
    assert old_open == new_open
