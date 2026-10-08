"""Who a RELEASE closes, per the accords: every PARTICIPANT of the named lane.

The keystone docs govern, not code comments. AGNOTE4482.md:1699: the ledger
is "an awareness surface, not a claim registry"; :1709-1713: "Shared lanes are
the point. Multiple idents may sign the same lane"; "Rows are reversible
adsorptions". KRISS_KROSS_ACCORD.md:12-16: one active owner per branch "unless
explicit overlay handoff is recorded" -- the release row is the register part
of that record (the trail entry and PR comment are not checked here).

So a RELEASE naming a lane closes the open rows on it of:
  * the signer (unchanged);
  * any owner whose row declares the signer in `co-owners:`;
  * the holder the release NAMES with `baton-from: <holder>`.
It is reversible: the holder re-CLAIMing supersedes it. register-status shows
every close filed under another identity ("released by X on behalf of owner
Y"); it shows, it does not block. There is no grant row, no operator set, no
origin/main check -- the owner-only pairing those guarded came in with #2858
(ad63bb8c5) and cited no accord.

KEPT from the earlier design: a malformed `baton-from:` row closes NOTHING
and is never read as the signer's own ordinary release; batons are read only
from real row heads outside fences; lanes come only from declared `branch:`
markers.

EVERY LANE-STATE ASSERTION GOES THROUGH `open_claims_in()`, the gate's own
authority, so the same assertions run unchanged against an earlier gate as a
behavioural failing-before control.
"""

from __future__ import annotations

import importlib.util
import json
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

HELD = (
    f"- `2026-09-20T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
    "· scope: **holding this lane.**\n"
    f"- `2026-09-20T00:05:00Z` CLAIM `{HOLDER}` branch: `fix/sprocket` "
    "· scope: **and this one.**\n"
    f"- `2026-09-20T00:10:00Z` CLAIM `{SIGNER}` branch: `chore/mine` "
    "· scope: **the signer's own lane.**\n"
)
SHARED = (f"- `2026-09-20T00:15:00Z` CLAIM `{HOLDER}` branch: `feat/shared` "
          f"· co-owners: `{SIGNER}` (reviewed) · scope: **shared.**\n")

BEFORE = {"crush": ["feat/widget", "fix/sprocket"], "b850-claude": ["chore/mine"]}


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


def _baton(lane: str, holder: str = HOLDER, **kw) -> str:
    return _release(f"branch: `{lane}` · baton-from: `{holder}`", **kw)


# ------------------------------------------------------ the five rules ------

def test_a_peer_release_with_baton_from_closes_the_holders_row(gate):
    assert _lanes(gate, HELD) == BEFORE
    assert _lanes(gate, HELD + _baton("feat/widget")) == {
        "crush": ["fix/sprocket"],          # the holder's OTHER lane stays held
        "b850-claude": ["chore/mine"],      # the signer's own lane is untouched
    }


def test_a_co_owners_plain_release_closes_the_shared_row(gate):
    named = _release("branch: `feat/shared`")
    assert _lanes(gate, HELD + SHARED)["crush"] == [
        "feat/shared", "feat/widget", "fix/sprocket"]
    assert _lanes(gate, HELD + SHARED + named) == BEFORE


def test_a_non_participant_release_without_baton_from_closes_nothing(gate):
    stranger = _release("branch: `feat/widget`", signer=OTHER)
    assert _lanes(gate, HELD + stranger) == BEFORE
    assert gate.peer_closes_in(HELD + stranger) == []


def test_a_holder_re_claim_supersedes_the_peer_release(gate):
    reclaim = (f"- `2026-10-02T00:00:00Z` CLAIM `{HOLDER}` branch: `feat/widget` "
               "· scope: **back, still working it.**\n")
    text = HELD + _baton("feat/widget") + reclaim
    assert _lanes(gate, text) == BEFORE
    [pc] = gate.peer_closes_in(text)
    assert pc.heard_from


@pytest.mark.parametrize("case, row, needle", [
    ("no holder in backticks",
     _release("branch: `chore/mine` · baton-from: crush"), "names no holder"),
    ("two holders",
     _release(f"branch: `chore/mine` · baton-from: `{HOLDER}` · baton-from: `{OTHER}`"),
     "more than one"),
    ("no declared lane", _release(f"baton-from: `{HOLDER}`"), "declares no lane"),
    ("headless line",
     f"  RELEASE `{SIGNER}` branch: `chore/mine` · baton-from: `{HOLDER}`\n",
     "not a ledger RELEASE row"),
    ("a REVIEW quoting a release",
     f"- `2026-10-01T00:00:00Z` REVIEW `CODEX` scope: RELEASE `{SIGNER}` "
     f"branch: `chore/mine` · baton-from: `{HOLDER}`\n", "not a ledger RELEASE row"),
])
def test_a_malformed_baton_closes_nothing_never_the_signers_own(gate, case, row, needle):
    # Each row names the SIGNER's own lane `chore/mine` (or is lane-less), so a
    # fallback to an ordinary release by the signer would show as it closing.
    assert _lanes(gate, HELD + row) == BEFORE
    [event] = gate.baton_events_in(HELD + row)
    assert needle in event.problem and not event.closed


# --------------------------------- P2-1: a peer close needs a real row ------
# Delta review of #3242, P2-1. The co-owner close used to run through the
# legacy RELEASE reader, which matches `RELEASE <x>` anywhere on a line and
# reads lanes out of prose. Each shape below closed the PRIMARY owner's shared
# row. Now each closes nothing of anyone else's, while the signer's OWN rows
# keep the legacy reading exactly (here: the signer's own `feat/shared` row
# closes, as it always has).

OWN_SHARED = (f"- `2026-09-20T00:20:00Z` CLAIM `{SIGNER}` branch: `feat/shared` "
              "· scope: **my own row on the shared lane.**\n")
P2_1_REPROS = {
    "a REVIEW row quoting the co-owner's release":
        (f"- `2026-10-01T00:00:00Z` REVIEW `EM-FLASH (4090)` · scope: per RELEASE "
         f"`{SIGNER}` on `feat/shared`, the guard lands next\n"),
    "an indented example row":
        (f"- `2026-10-01T00:00:00Z` NOTE `CODEX` scope: grammar example:\n"
         f"  - `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch `feat/shared` "
         "· scope: example\n"),
    "a release whose prose mentions the lane":
        (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `fix/other-thing` "
         f"· scope: done; `{HOLDER}` keeps `feat/shared`\n"),
}


@pytest.mark.parametrize("case", sorted(P2_1_REPROS))
def test_p2_1_a_non_row_or_prose_lane_closes_no_other_owners_row(gate, case):
    text = HELD + SHARED + OWN_SHARED + P2_1_REPROS[case]
    assert "feat/shared" in _lanes(gate, text)["crush"]
    assert gate.peer_closes_in(text) == []


@pytest.mark.parametrize("case", sorted(P2_1_REPROS))
def test_p2_1_the_signers_own_legacy_reading_is_unchanged(gate, case):
    text = HELD + SHARED + OWN_SHARED + P2_1_REPROS[case]
    assert _lanes(gate, text)["b850-claude"] == ["chore/mine"]


def test_p2_1_the_same_release_on_a_real_row_does_close_the_shared_row(gate):
    # The positive control for the three repros: a real RELEASE row head that
    # DECLARES the lane closes the co-owned row.
    row = _release("branch: `feat/shared`")
    text = HELD + SHARED + OWN_SHARED + row
    assert "feat/shared" not in _lanes(gate, text)["crush"]
    [pc] = gate.peer_closes_in(text)
    assert (pc.owner_key, pc.via) == ("crush", "co-owner")


def test_co_owner_match_uses_the_vocabulary_fold(gate):
    # Documented choice (P3-3): a co-owner is matched by canonical identity,
    # the same fold that decides an owner's own rows. CRUSH-GLM52 and CRUSH
    # fold to `crush`, so a row declaring one is closable by the other.
    row = (f"- `2026-09-20T00:00:00Z` CLAIM `{SIGNER}` branch: `feat/fold` "
           "· co-owners: `CRUSH-GLM52 (Knuckles)` · scope: s\n")
    rel = _release("branch: `feat/fold`", signer="CRUSH")
    assert "b850-claude" not in _lanes(gate, row + rel)


# ---------------------------------------------------- reading the rows ------

def test_peer_close_says_who_released_it_on_whose_behalf(gate):
    [pc] = gate.peer_closes_in(HELD + _baton("feat/widget"))
    assert (pc.signer, pc.owner_key, pc.via, pc.lanes) == (
        SIGNER, "crush", "baton-from", {"feat/widget"})
    assert not pc.heard_from
    assert f"released by `{SIGNER}` on behalf of owner" in str(pc)
    assert "not heard from since" in str(pc)


def test_co_owner_close_is_recorded_as_such(gate):
    [pc] = gate.peer_closes_in(HELD + SHARED + _release("branch: `feat/shared`"))
    assert (pc.owner_key, pc.via) == ("crush", "co-owner")


def test_the_signers_own_release_is_not_a_peer_close(gate):
    assert gate.peer_closes_in(HELD + _release("branch: `chore/mine`")) == []


def test_a_bare_co_owner_release_reaches_no_one_elses_row(gate):
    bare = f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` · scope: **bare.**\n"
    assert _lanes(gate, HELD + SHARED + bare)["crush"] == [
        "feat/shared", "feat/widget", "fix/sprocket"]


def test_a_baton_closes_only_lanes_it_declares_not_lanes_its_prose_mentions(gate):
    row = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `feat/widget` "
           f"· baton-from: `{HOLDER}` · scope: done; `fix/sprocket` is next\n")
    assert _lanes(gate, HELD + row)["crush"] == ["fix/sprocket"]


def test_the_bare_word_branch_in_baton_prose_is_not_a_declaration(gate):
    row = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `feat/widget` "
           f"· baton-from: `{HOLDER}` · scope: keeping branch `fix/sprocket`\n")
    assert _lanes(gate, HELD + row)["crush"] == ["fix/sprocket"]


def test_a_fenced_baton_is_refused(gate):
    fenced = "```\n" + _baton("feat/widget") + "```\n"
    assert _lanes(gate, HELD + fenced) == BEFORE


def test_a_quoted_baton_field_is_a_mention_not_a_baton(gate):
    row = (f"- `2026-10-01T00:00:00Z` RELEASE `{SIGNER}` branch: `chore/mine` "
           f"· scope: **the new field reads ``baton-from: `{HOLDER}` ``.**\n")
    assert _lanes(gate, HELD + row) == {"crush": ["feat/widget", "fix/sprocket"]}


def test_baton_naming_a_lane_the_holder_no_longer_holds_is_a_noop(gate):
    gone = (f"- `2026-09-30T14:00:00Z` RELEASE `{HOLDER}` branch: `feat/widget` "
            "· scope: done\n")
    text = HELD + gone + _baton("feat/widget")
    assert _lanes(gate, text) == _lanes(gate, HELD + gone)
    [event] = gate.baton_events_in(text)
    assert not event.problem and event.not_held == {"feat/widget"}
    assert "holds no open row" in event.warning


def test_the_grant_machinery_is_gone(gate):
    for name in ("baton_operator_identities", "resolve_grant", "grant_problem",
                 "BATON_GRANT_RE", "BATON_TO_RE"):
        assert not hasattr(gate, name), name


# --------------------------------------------------------------- the writer --

@pytest.fixture()
def mod(tmp_path: Path, monkeypatch):
    for var in ("REGISTER_BATON_FROM", "REGISTER_BATON_TO", "REGISTER_GRANT",
                "REGISTER_OWNER", "REGISTER_BRANCH", "REGISTER_SCOPE",
                "REGISTER_SCOPE_FILE", "REGISTER_CO_OWNERS", "REGISTER_TTL"):
        monkeypatch.delenv(var, raising=False)
    m = _load(TOOL, "register_append_baton")
    register = tmp_path / "register.md"
    register.write_text("# register\n" + HELD + SHARED, encoding="utf-8")
    monkeypatch.setattr(m, "REGISTER", register)
    return m


def _run(mod, *extra, owner=SIGNER):
    return mod.main(["release", "--owner", owner, "--scope", "passing the baton",
                     *extra])


def _text(mod) -> str:
    return mod.REGISTER.read_text(encoding="utf-8")


def test_write_road_files_a_baton_that_the_gate_reads(mod, gate, capsys):
    assert _run(mod, "--branch", "feat/widget", "--baton-from", HOLDER) == 0
    last = _text(mod).rstrip("\n").split("\n")[-1]
    assert f"RELEASE `{SIGNER}`" in last and f"baton-from: `{HOLDER}`" in last
    assert "grant:" not in last
    assert _lanes(gate, _text(mod))["crush"] == ["feat/shared", "fix/sprocket"]
    assert "on behalf of `" in capsys.readouterr().err


def test_write_road_co_owner_release_announces_the_shared_close(mod, gate, capsys):
    assert _run(mod, "--branch", "feat/shared") == 0
    assert _lanes(gate, _text(mod))["crush"] == ["feat/widget", "fix/sprocket"]
    assert "via co-owner" in capsys.readouterr().err


def test_write_road_reports_a_non_participant_release_that_closes_nothing(mod, gate, capsys):
    before = _lanes(gate, _text(mod))
    assert _run(mod, "--branch", "feat/widget", owner=OTHER) == 0
    assert _lanes(gate, _text(mod)) == before
    err = capsys.readouterr().err
    assert "closes nothing" in err and "BATON_FROM=" in err


@pytest.mark.parametrize("extra, needle, rc", [
    (("--branch", "chore/mine", "--baton-from", SIGNER), "same identity", 3),
    (("--all-lanes", "--baton-from", HOLDER), "never bare", 3),
    (("--branch", "feat/nobody-holds", "--baton-from", HOLDER), "holds no open row", 1),
    (("--branch", "feat/widget", "--grant", "2026-09-30T12:00:00Z"),
     "unrecognized arguments", 2),
])
def test_write_road_refuses_a_baton_that_would_not_do_what_it_says(mod, capsys, extra, needle, rc):
    before = _text(mod)
    try:
        got = _run(mod, *extra)
    except SystemExit as exc:  # argparse: the GRANT door is gone
        got = exc.code
    assert got == rc
    assert _text(mod) == before
    assert needle in capsys.readouterr().err


def test_write_road_refuses_a_scope_that_declares_a_second_held_lane(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "feat/widget",
                   "--baton-from", HOLDER,
                   "--scope", "done; also branch: `fix/sprocket`"])
    assert rc == 1 and _text(mod) == before
    assert "fix/sprocket" in capsys.readouterr().err


def test_plain_release_whose_scope_declares_a_baton_is_refused(mod, capsys):
    before = _text(mod)
    rc = mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                   "--scope", f"baton-from: `{HOLDER}`"])
    assert rc == 3 and _text(mod) == before
    assert "DECLARES a `baton-from:` field" in capsys.readouterr().err


def test_ordinary_release_is_unchanged(mod, gate):
    assert mod.main(["release", "--owner", SIGNER, "--branch", "chore/mine",
                     "--scope", "done"]) == 0
    assert _lanes(gate, _text(mod)) == {
        "crush": ["feat/shared", "feat/widget", "fix/sprocket"]}


def test_baton_rows_round_trip_for_register_sync_reapply(mod):
    row = mod.build_row("RELEASE", SIGNER, "feat/widget", "passing", baton_from=HOLDER)
    parsed = mod._parse_rendered(row.rstrip("\n"))
    assert mod._assert_round_trips(row.encode()) == parsed


# ------------------------------------------------------- register-status ----

def _status():
    return _load(TOOL.with_name("register_status.py"), "register_status_baton")


def _register(tmp_path, body: str) -> Path:
    register = tmp_path / "register.md"
    register.write_text("# register\n" + body, encoding="utf-8")
    return register


def test_register_status_shows_a_peer_close_and_does_not_block(tmp_path, capsys):
    reg = _register(tmp_path, HELD + _baton("feat/widget"))
    rc = _status().main(["--register", str(reg), "--now", "2026-10-01T01:00:00Z"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "CLOSED ON BEHALF OF A PEER (1)" in out
    assert f"released by `{SIGNER}` on behalf of owner `{HOLDER}`" in out


def test_register_status_listing_drops_a_close_once_the_owner_is_heard_from(tmp_path, capsys):
    back = (f"- `2026-10-02T00:00:00Z` NOTE `{HOLDER}` scope: seen it\n")
    reg = _register(tmp_path, HELD + _baton("feat/widget") + back)
    assert _status().main(["--register", str(reg), "--now", "2026-10-02T01:00:00Z"]) == 0
    assert "CLOSED ON BEHALF" not in capsys.readouterr().out


def test_register_status_reports_a_malformed_baton(tmp_path, capsys):
    reg = _register(tmp_path, HELD + _release(f"baton-from: `{HOLDER}`"))
    rc = _status().main(["--register", str(reg), "--now", "2026-10-01T00:00:00Z"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "BATON ROWS THAT DID NOT DO WHAT THEY SAID (1)" in out
    assert "closed NOTHING" in out and "declares no lane" in out


def test_register_status_branch_probe_free_lane_with_a_noop_baton_exits_0(tmp_path, capsys):
    # Delta review of #3242, P3-1: a no-op baton is REPORTED in the BRANCH=
    # probe but must not change the lane's verdict. FREE is exit 0.
    reg = _register(tmp_path, HELD + _baton("fix/free"))
    rc = _status().main(["--register", str(reg), "--branch", "fix/free",
                         "--owner", "CODEX", "--now", "2026-10-01T01:00:00Z"])
    out = capsys.readouterr().out
    assert "FREE" in out and "no-op for that lane" in out
    assert rc == 0


def test_register_status_json_carries_batons_and_peer_closes(tmp_path, capsys):
    reg = _register(tmp_path, HELD + _baton("feat/widget"))
    rc = _status().main(["--register", str(reg), "--now", "2026-10-01T01:00:00Z",
                         "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["exit_code"] == 0
    [baton] = payload["batons"]
    assert baton["closed"] == ["feat/widget"] and not baton["problem"]
    [pc] = payload["peer_closes"]
    assert (pc["released_by"], pc["owner"], pc["via"]) == (SIGNER, HOLDER, "baton-from")
    assert pc["owner_heard_from_since"] is False


# ---------------------------------------------------------- monotonicity ----

def test_live_register_every_state_change_is_a_participant_close(gate, tmp_path):
    """Against the pre-rework pairing, every row whose open/closed state changes
    must be one the new rule closed on behalf of a peer -- nothing else moves.

    The old pairing is origin/main's gate, read with `git show` -- never by
    reverting the working tree. Skipped (COULD-NOT-MEASURE) when git or the base
    ref is unavailable, and says so. The exact list for the PR is printed.
    """
    text = LIVE_REGISTER.read_text(encoding="utf-8")
    try:
        base = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show",
             "origin/main:.claude/hooks/governance/claim-collision-pre.py"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"base gate unavailable via git show ({exc})")
    if "def peer_closes_in" in base:
        pytest.skip("origin/main already carries participant pairing")
    old_path = tmp_path / "claim_collision_pre_base.py"
    old_path.write_text(base, encoding="utf-8")
    old = _load(old_path, "claim_collision_pre_base")
    # The base gate locates the identity module relative to its own file,
    # which is now in tmp_path. Hand it the SAME vocabulary the new gate uses.
    old._LINEAGE = gate._load_lineage()
    assert old._LINEAGE is not None, "vocabulary unavailable: COULD-NOT-MEASURE"

    def rows(open_claims):
        return {(o, ln): frozenset(lanes) for o, rs in open_claims.items()
                for ln, lanes, _r, _p in rs}

    old_rows, new_rows = rows(old.open_claims_in(text)), rows(gate.open_claims_in(text))
    changed = {k for k in set(old_rows) | set(new_rows)
               if old_rows.get(k) != new_rows.get(k)}
    explained = {(pc.owner_key, pc.claim_line) for pc in gate.peer_closes_in(text)}
    print(f"monotonicity: {len(text.split(chr(10)))} lines; old open rows="
          f"{len(old_rows)} new open rows={len(new_rows)}; changed={sorted(changed)}")
    assert not (set(new_rows) - set(old_rows)), "the new rule must never OPEN a row"
    assert changed <= explained


def test_an_off_home_session_may_take_the_baton_from_its_home_session(gate):
    """#3313: `B850-CLAUDE (spark)` and `B850-CLAUDE` (home, Knuckles) are two
    sessions of one identity, so a baton between them is a real handoff, not
    "closing your own lane". Home spellings are still one session."""
    ra = _load(TOOL, "register_append_baton_node")
    assert ra.baton_refusal(gate, "B850-CLAUDE (spark)", "B850-CLAUDE") == ""
    assert "same identity" in ra.baton_refusal(gate, "B850-CLAUDE (Opus 5)", "B850-CLAUDE")
