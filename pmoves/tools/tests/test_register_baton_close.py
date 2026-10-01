"""The BATON close: a peer passes or closes another AGInTZ's lane, with authority.

The AGInTZ are peers; a lane is a Known Road handed on like a relay baton, and
identity on a row is attribution, not territory. Until this, a RELEASE paired
only with the SIGNING owner's claims, so a lane whose holder had stopped
running could not be closed by anyone.

A baton row is a RELEASE carrying the holder (`baton-from:`) and the authority
(`ruling:` or `handoff:`). It closes the holder's rows on the named lanes and
nothing else. A malformed baton closes NOTHING -- it is never read as an
ordinary release of the signer's own lanes.

EVERY LANE-STATE ASSERTION GOES THROUGH `open_claims_in()`, the gate's own
authority, so the same assertions run unchanged against the pre-baton gate as
a behavioural failing-before control (the row stays open; no symbol is missing).
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
UNKNOWN = "NOBODY-XYZ (nowhere)"         # -> not in the vocabulary

HELD = (
    f"- `2026-09-20T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
    f"- `2026-09-20T00:05:00Z` CLAIM `{HOLDER}` branch: `fix/sprocket` "
    "· scope: **and this one.**\n"
    f"- `2026-09-20T00:10:00Z` CLAIM `{SIGNER}` branch: `chore/mine` "
    "· scope: **the signer's own lane.**\n"
)


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


def _release(fields: str, signer: str = SIGNER) -> str:
    return (f"- `2026-10-01T00:00:00Z` RELEASE `{signer}` {fields} "
            "· scope: **passing the baton.**\n")


BEFORE = {"crush": ["feat/widget", "fix/sprocket"], "b850-claude": ["chore/mine"]}


# --------------------------------------------------------------- the reader --

def test_baton_closes_only_the_named_lane_of_the_named_holder(gate):
    row = _release(f"branch: `feat/widget` · baton-from: `{HOLDER}` "
                   "· ruling: `operator 2026-10-01T12:00Z`")
    assert _lanes(gate, HELD) == BEFORE
    assert _lanes(gate, HELD + row) == {
        "crush": ["fix/sprocket"],          # the holder's OTHER lane stays held
        "b850-claude": ["chore/mine"],      # the signer's own lane is untouched
    }


def test_handoff_is_an_authority_too(gate):
    row = _release(f"branch: `fix/sprocket` · baton-from: `{HOLDER}` "
                   "· handoff: `PR #3240`")
    assert _lanes(gate, HELD + row)["crush"] == ["feat/widget"]


def test_baton_event_records_both_identities_and_the_authority(gate):
    row = _release(f"branch: `feat/widget` · baton-from: `{HOLDER}` "
                   "· ruling: `operator 2026-10-01`")
    [event] = gate.baton_events_in(HELD + row)
    assert (event.signer, event.holder, event.holder_key) == (SIGNER, HOLDER, "crush")
    assert event.authority == ("ruling", "operator 2026-10-01")
    assert event.closed == {"feat/widget"} and not event.problem


def test_baton_without_authority_closes_nothing_and_never_falls_back(gate):
    # No ruling/handoff. Read as an ordinary named release by the SIGNER it
    # would be harmless here -- so make the fallback visible: name the
    # signer's own lane. A fallback would close `chore/mine`.
    row = _release(f"branch: `chore/mine` · baton-from: `{HOLDER}`")
    assert _lanes(gate, HELD + row) == BEFORE
    [event] = gate.baton_events_in(HELD + row)
    assert "authority" in event.problem


def test_baton_from_an_unknown_owner_closes_nothing(gate):
    text = HELD + (f"- `2026-09-20T00:20:00Z` CLAIM `{UNKNOWN}` branch: `feat/ghost` "
                   "· scope: **an unregistered holder.**\n")
    row = _release(f"branch: `feat/ghost` · baton-from: `{UNKNOWN}` "
                   "· ruling: `operator 2026-10-01`")
    before = _lanes(gate, text)
    assert _lanes(gate, text + row) == before
    [event] = gate.baton_events_in(text + row)
    assert "not a registered identity" in event.problem


def test_baton_by_an_unknown_signer_closes_nothing(gate):
    row = _release(f"branch: `feat/widget` · baton-from: `{HOLDER}` "
                   "· ruling: `operator 2026-10-01`", signer=UNKNOWN)
    assert _lanes(gate, HELD + row) == BEFORE


def test_baton_naming_a_lane_the_holder_does_not_hold_is_a_noop_with_warning(gate):
    row = _release(f"branch: `chore/mine` · baton-from: `{HOLDER}` "
                   "· ruling: `operator 2026-10-01`")
    # `chore/mine` is the SIGNER's lane, not the holder's: nothing closes.
    assert _lanes(gate, HELD + row) == BEFORE
    [event] = gate.baton_events_in(HELD + row)
    assert not event.problem and not event.closed
    assert event.not_held == {"chore/mine"}
    assert "holds no open row" in event.warning


def test_baton_naming_no_lane_closes_nothing(gate):
    # A lane-less ordinary RELEASE closes EVERYTHING its signer holds. A
    # lane-less baton must not -- neither the holder's lanes nor the signer's.
    row = _release(f"baton-from: `{HOLDER}` · ruling: `operator 2026-10-01`")
    assert _lanes(gate, HELD + row) == BEFORE


def test_bare_release_by_a_co_owner_still_does_not_close(gate):
    text = (f"- `2026-09-20T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
            f"· co-owners: `{SIGNER}` (reviewed) · scope: **shared.**\n")
    bare = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` "
            "· scope: **co-owner, bare release.**\n")
    named = (f"- `2026-10-01T00:01:00Z` RELEASE `{SIGNER}` branch: `feat/widget` "
             "· scope: **co-owner, named release.**\n")
    assert _lanes(gate, text + bare + named) == {"crush": ["feat/widget"]}


def test_a_quoted_baton_field_is_a_mention_not_a_baton(gate):
    # Documentation of the grammar inside a ``...`` span. The row is an
    # ordinary named release by the signer and must behave exactly as one.
    row = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `chore/mine` "
           f"· scope: **the new field reads ``baton-from: `{HOLDER}` ``.**\n")
    assert _lanes(gate, HELD + row) == {"crush": ["feat/widget", "fix/sprocket"]}


def test_a_branch_shaped_ruling_ref_is_not_a_lane(gate):
    row = _release(f"branch: `feat/widget` · baton-from: `{HOLDER}` "
                   "· ruling: `docs/rulings-fix/sprocket`")
    assert _lanes(gate, HELD + row)["crush"] == ["fix/sprocket"]


def test_no_vocabulary_means_no_baton_not_an_ordinary_release(gate, monkeypatch):
    monkeypatch.setattr(gate, "_LINEAGE", None)
    monkeypatch.setattr(gate, "_FOLDER", None)
    row = _release(f"branch: `chore/mine` · baton-from: `{HOLDER}` "
                   "· ruling: `operator 2026-10-01`")
    text = HELD + row
    # Without the vocabulary owner strings are compared raw; the point is
    # only that the baton row transitions NOTHING.
    before = gate.open_claims_in(HELD)
    assert gate.open_claims_in(text) == before
    [event] = gate.baton_events_in(text)
    assert "vocabulary is unavailable" in event.problem


# --------------------------------------------------------------- the writer --

@pytest.fixture()
def mod(tmp_path: Path, monkeypatch):
    for var in ("REGISTER_BATON_FROM", "REGISTER_RULING", "REGISTER_HANDOFF",
                "REGISTER_OWNER", "REGISTER_BRANCH", "REGISTER_SCOPE",
                "REGISTER_SCOPE_FILE", "REGISTER_CO_OWNERS", "REGISTER_TTL"):
        monkeypatch.delenv(var, raising=False)
    m = _load(TOOL, "register_append_baton")
    register = tmp_path / "AGNOTE4482PHI.t1.md"
    register.write_text("# register\n" + HELD, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    return m


def _run(mod, *extra):
    return mod.main(["release", "--owner", SIGNER, "--scope", "passing the baton",
                     *extra])


def _text(mod) -> str:
    return mod.REGISTER.read_text(encoding="utf-8")


def test_write_road_files_a_baton_that_the_gate_reads(mod, gate, capsys):
    rc = _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER,
              "--ruling", "operator 2026-10-01T12:00Z")
    assert rc == 0
    last = _text(mod).rstrip("\n").split("\n")[-1]
    assert f"RELEASE `{SIGNER}`" in last and f"baton-from: `{HOLDER}`" in last
    assert "ruling: `operator 2026-10-01T12:00Z`" in last
    assert _lanes(gate, _text(mod))["crush"] == ["fix/sprocket"]
    assert "BATON" in capsys.readouterr().err


@pytest.mark.parametrize("extra, needle", [
    (("--branch", "feat/widget", "--baton-from", HOLDER), "authority"),
    (("--branch", "feat/widget", "--ruling", "operator"), "without --baton-from"),
    (("--branch", "feat/widget", "--baton-from", UNKNOWN, "--ruling", "op"),
     "not a registered identity"),
    (("--branch", "chore/mine", "--baton-from", SIGNER, "--ruling", "op"),
     "same identity"),
    (("--all-lanes", "--baton-from", HOLDER, "--ruling", "op"), "never bare"),
    (("--branch", "feat/widget", "--baton-from", HOLDER, "--ruling", "op",
      "--handoff", "PR #1"), "ONE authority"),
])
def test_write_road_refuses_a_malformed_baton(mod, capsys, extra, needle):
    before = _text(mod)
    assert _run(mod, *extra) == 3
    assert _text(mod) == before
    assert needle in capsys.readouterr().err


def test_write_road_refuses_a_baton_for_a_lane_the_holder_does_not_hold(mod, capsys):
    before = _text(mod)
    assert _run(mod, "--branch", "chore/mine", "--baton-from", HOLDER,
                "--ruling", "op") == 1
    assert _text(mod) == before
    err = capsys.readouterr().err
    assert "WARNING" in err and "holds no open row" in err


def test_write_road_refuses_a_scope_that_would_close_a_second_held_lane(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "feat/widget",
                   "--baton-from", HOLDER, "--ruling", "op",
                   "--scope", "done; see also `fix/sprocket`"])
    assert rc == 1 and _text(mod) == before
    assert "fix/sprocket" in capsys.readouterr().err


def test_plain_release_whose_scope_declares_a_baton_is_refused(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                   "--scope", f"baton-from: `{HOLDER}` ruling: `op`"])
    assert rc == 3 and _text(mod) == before
    assert "DECLARES a `baton-from:` field" in capsys.readouterr().err


def test_ordinary_release_is_unchanged(mod, gate):
    assert mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                     "--scope", "done"]) == 0
    assert _lanes(gate, _text(mod)) == {"crush": ["feat/widget", "fix/sprocket"]}


def test_baton_rows_round_trip_for_register_sync_reapply(mod):
    row = mod.build_row("RELEASE", SIGNER, "feat/widget", "passing", baton_from=HOLDER,
                        handoff="PR #3240")
    parsed = mod._parse_rendered(row.rstrip("\n"))
    assert parsed["baton_from"] == HOLDER and parsed["handoff"] == "PR #3240"
    assert mod._assert_round_trips(row.encode()) == parsed


def test_register_status_reports_a_baton_that_closed_nothing(tmp_path, capsys):
    status = _load(TOOL.with_name("register_status.py"), "register_status_baton")
    register = tmp_path / "register.md"
    register.write_text("# register\n" + HELD + _release(
        f"branch: `feat/widget` · baton-from: `{HOLDER}`"), encoding="utf-8")
    rc = status.main(["--register", str(register), "--now", "2026-10-01T00:00:00Z"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "BATON ROWS THAT DID NOT DO WHAT THEY SAID (1)" in out
    assert "closed NOTHING" in out and "authority" in out


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
