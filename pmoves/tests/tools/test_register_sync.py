"""register-sync: the recovery road for a checkout whose register has uncommitted rows.

Every test builds a THROWAWAY git repository in tmp_path. Nothing here reads or
writes the real register -- the tool is pointed at the scratch repo with
`--repo`, and the target ref is a scratch branch (`upstream`) standing in for
origin/main.

Shape of the fixture repo, mirroring the 2026-09-28 stuck root checkout:

  main (HEAD)  base register
  upstream     base + rows main gained since: one byte-identical copy of a
               stale row (ON-MAIN) and two RE-FILED rows carrying
               `first filed at <ts>` markers
  working tree base + 2 stale rows that upstream re-filed + 1 row upstream
               has verbatim + 2 rows upstream knows nothing about (KEEP)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "register_append.py"
# Assembled, not literal: see test_claim_collision_substitution.py.
REG_REL = "pmoves/docs/AGENTS/" + "AGNOTE4482" + "PHI.t1.md"
OWNER = "B850-CLAUDE (Knuckles)"

BASE = (
    "# Claim register\n"
    "\n"
    "## Active Claim Register\n"
    "- `2026-09-26T21:42:45Z` RELEASE `B850-CLAUDE (Knuckles)` branch: `ci/old` · scope: done.\n"
)
STALE_A = ("- `2026-09-27T07:58:26Z` CLAIM `B850-CLAUDE (Knuckles)` branch: "
           "`infra/storage` · **TTL 72h** · scope: reconcile storage.\n")
STALE_B = ("- `2026-09-27T08:25:08Z` CLAIM `B850-CLAUDE (Knuckles)` branch: "
           "`ops/kvm-disk` · **TTL 48h** · scope: investigate disk.\n")
VERBATIM = ("- `2026-09-27T09:00:00Z` NOTE `B850-CLAUDE (Knuckles)` branch: "
            "`ops/kvm-disk` · scope: a fact main already carries.\n")
# KEEP rows are RENDERED by the tool's own `build_row`, and relative to NOW:
# reapply requires a renderer round-trip and a timestamp inside
# [held_at - 30d, held_at], so hand-built or fixed-date fixtures would rot.
def _render(kind, owner, branch, scope, ttl="", at=None, co_owners=None):
    return _TOOL.build_row(kind=kind, owner=owner, branch=branch, scope=scope,
                           ttl=ttl, co_owners=co_owners, now=at)


def _load_tool():
    spec = importlib.util.spec_from_file_location("register_append_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the tool's pydantic models resolve their
    # (postponed) annotations through sys.modules.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_TOOL = _load_tool()
T0 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=3)
TS_A = (T0).strftime("%Y-%m-%dT%H:%M:%SZ")
TS_B = (T0 + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
KEEP_A = _render("CLAIM", OWNER, "feat/crush-acp", "bridge.", "48h", T0)
KEEP_B = _render("RELEASE", OWNER, "feat/crush-acp", "delivered.", at=T0 + timedelta(hours=1))
REFILED_A = ("- `2026-09-27T19:53:41Z` CLAIM `B850-CLAUDE (Knuckles)` branch: "
             "`infra/storage` · **TTL 60h** · scope: RE-FILED from an uncommitted "
             "working tree: first filed at 2026-09-27T07:58:26Z by the register road.\n")
REFILED_B = ("- `2026-09-27T19:54:04Z` CLAIM `B850-CLAUDE (Knuckles)` branch: "
             "`ops/kvm-disk` · **TTL 36h** · scope: RE-FILED: first filed at "
             "`2026-09-27T08:25:08Z`.\n")
UPSTREAM = BASE + VERBATIM + REFILED_A + REFILED_B
STALE = STALE_A + STALE_B + VERBATIM
KEEP_ROWS = KEEP_A + KEEP_B


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True).stdout


def _make_repo(tmp_path: Path, ignore_sidecar: bool = True) -> Path:
    repo = tmp_path / "repo"
    (repo / "pmoves" / "docs" / "AGENTS").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / REG_REL).write_text(BASE, encoding="utf-8")
    if ignore_sidecar:
        (repo / "pmoves" / ".gitignore").write_text("data/register-sync/\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "upstream")
    (repo / REG_REL).write_text(UPSTREAM, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "upstream re-files")
    _git(repo, "checkout", "-q", "main")
    return repo


def _dirty(repo: Path, appended: str) -> Path:
    reg = repo / REG_REL
    with open(reg, "a", encoding="utf-8") as fh:
        fh.write(appended)
    return reg


def _sync(repo: Path, *args: str, env: dict | None = None):
    full_env = {k: v for k, v in os.environ.items() if not k.startswith("REGISTER_SYNC_")}
    full_env.update(env or {})
    return subprocess.run(
        [sys.executable, str(TOOL), "sync", "--repo", str(repo), "--ref", "upstream", *args],
        capture_output=True, text=True, env=full_env, timeout=120)


# --- classification ---------------------------------------------------------

def test_classifies_all_three_classes_and_dry_run_writes_nothing(tmp_path):
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE + "\n" + KEEP_ROWS)
    before = reg.read_bytes()

    r = _sync(repo)

    assert r.returncode == 0, r.stderr
    assert "INPUT     6 uncommitted line(s)" in r.stdout
    assert "1 ON-MAIN, 2 RE-FILED, 3 KEEP (of 6 input)" in r.stdout
    lines = {ln.split()[0] + " " + ln.split("`")[1]
             for ln in r.stdout.splitlines() if ln.startswith("  ")
             and "`" in ln}
    assert "RE-FILED 2026-09-27T07:58:26Z" in lines
    assert "RE-FILED 2026-09-27T08:25:08Z" in lines
    assert "ON-MAIN 2026-09-27T09:00:00Z" in lines
    assert f"KEEP {TS_A}" in lines
    assert f"KEEP {TS_B}" in lines
    # The blank line is not a ledger row: KEEP, never guessed about.
    assert r.stdout.count("\n  KEEP") == 3
    # The ref and its sha are stated, because the tool never fetches.
    sha = _git(repo, "rev-parse", "upstream").strip()
    assert f"upstream = {sha}" in r.stdout and "NOT fetched" in r.stdout
    assert "DRY RUN" in r.stdout
    assert reg.read_bytes() == before
    assert not (repo / "pmoves" / "data").exists()


def test_empty_input_is_distinguishable_from_an_empty_result(tmp_path):
    repo = _make_repo(tmp_path)
    r = _sync(repo)
    assert r.returncode == 0, r.stderr
    assert "INPUT     0 uncommitted line(s)" in r.stdout
    assert "the INPUT is empty" in r.stdout


@pytest.mark.parametrize("stale, why", [
    (STALE_A.replace("07:58:26Z", "07:58:27Z"), "marker timestamp differs by one second"),
    (STALE_A.replace("`B850-CLAUDE (Knuckles)`", "`4090-CLAUDE`"), "different owner"),
    (STALE_A.replace("`infra/storage`", "`infra/storage-2`"), "different branch"),
    (STALE_A.replace(" CLAIM ", " RELEASE "), "different kind"),
    (STALE_A.replace(" branch: `infra/storage`", ""), "no header branch"),
    (STALE_A.replace(" · scope:", " scope:"), "no ` · scope:` separator: header unreadable"),
])
def test_keep_is_never_dropped_on_a_near_miss(tmp_path, stale, why):
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, stale)
    r = _sync(repo, "--apply")
    assert r.returncode == 0, r.stderr
    assert "0 ON-MAIN, 0 RE-FILED, 1 KEEP" in r.stdout, why
    assert reg.read_bytes() == BASE.encode() + stale.encode(), why


# --- refusals ---------------------------------------------------------------

@pytest.mark.parametrize("mutate", [
    lambda text: text.replace("## Active Claim Register\n", ""),            # removed
    lambda text: text.replace("scope: done.", "scope: done!"),              # modified
])
def test_refuses_anything_but_a_pure_append(tmp_path, mutate):
    repo = _make_repo(tmp_path)
    reg = repo / REG_REL
    reg.write_text(mutate(BASE) + STALE + KEEP_ROWS, encoding="utf-8")
    before = reg.read_bytes()
    for extra in ((), ("--apply",)):
        r = _sync(repo, *extra)
        assert r.returncode == 3, (r.stdout, r.stderr)
        assert "removes or modifies" in r.stderr
        assert reg.read_bytes() == before
    assert not (repo / "pmoves" / "data").exists()


def test_refuses_when_the_sidecar_directory_is_not_ignored(tmp_path):
    repo = _make_repo(tmp_path, ignore_sidecar=False)
    reg = _dirty(repo, STALE + KEEP_ROWS)
    before = reg.read_bytes()
    r = _sync(repo, "--apply")
    assert r.returncode == 3, r.stdout
    assert "not gitignored" in r.stderr
    assert reg.read_bytes() == before


def test_refuses_on_a_concurrent_write(tmp_path, monkeypatch, capsys):
    """A row landing between classification and the write voids the plan."""
    tool = _load_tool()
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE + KEEP_ROWS)
    late = "- `2026-09-28T00:00:00Z` CLAIM `OTHER` branch: `x/y` · scope: late.\n"
    real_lock = tool.register_lock

    def racing_lock(target, timeout=None):
        with open(target, "a", encoding="utf-8") as fh:   # the other filer wins the race
            fh.write(late)
        return real_lock(target, timeout)

    monkeypatch.setattr(tool, "register_lock", racing_lock)
    with pytest.raises(tool.SyncRefused, match="concurrent"):
        tool.sync_register(repo, "upstream", apply=True, hold=False)
    # Nothing on the register moved and the late row survives. The refusal
    # happens under the lock BEFORE any sidecar is written, so none exists.
    assert reg.read_bytes() == (BASE + STALE + KEEP_ROWS + late).encode()
    assert not list((repo / "pmoves" / "data" / "register-sync").glob("*.keep.md"))


# --- apply / hold / reapply --------------------------------------------------

def test_apply_leaves_the_working_diff_equal_to_keep(tmp_path):
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE + KEEP_ROWS)

    r = _sync(repo, env={"REGISTER_SYNC_APPLY": "1"})     # the make target's door

    assert r.returncode == 0, r.stderr
    assert "adds 2 line(s) and removes 0; 3 dropped" in r.stdout
    assert reg.read_bytes() == (BASE + KEEP_ROWS).encode()
    added, removed, _ = _git(repo, "diff", "--numstat", "--", REG_REL).split("\t")
    assert (added, removed) == ("2", "0")
    side = repo / "pmoves" / "data" / "register-sync"
    keep = next(side.glob("*.keep.md"))
    dropped = next(side.glob("*.dropped.md"))
    assert keep.read_bytes() == KEEP_ROWS.encode()
    assert dropped.read_bytes() == STALE.encode()
    pre = next(side.glob("*.preimage.md"))
    assert pre.read_bytes() == (BASE + STALE + KEEP_ROWS).encode()   # full pre-image
    assert next(side.glob("*.manifest.json")).is_file()
    # The sidecars are invisible to git: only the register shows as modified.
    assert _git(repo, "status", "--porcelain").splitlines() == [f" M {REG_REL}"]


def test_hold_then_pull_then_reapply_round_trips_byte_exact(tmp_path):
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE + KEEP_ROWS)

    # A dirty register blocks the fast-forward -- the defect being recovered.
    blocked = subprocess.run(["git", "-C", str(repo), "merge", "--ff-only", "-q", "upstream"],
                             capture_output=True, text=True)
    assert blocked.returncode != 0

    r = _sync(repo, "--apply", "--hold")
    assert r.returncode == 0, r.stderr
    assert reg.read_bytes() == BASE.encode()
    assert _git(repo, "status", "--porcelain") == ""
    keep = next((repo / "pmoves" / "data" / "register-sync").glob("*.keep.md"))
    assert keep.read_bytes() == KEEP_ROWS.encode()

    _git(repo, "merge", "--ff-only", "-q", "upstream")         # the pull
    assert reg.read_bytes() == UPSTREAM.encode()

    dry = _sync(repo, "--reapply", str(keep))
    assert dry.returncode == 0 and "DRY RUN" in dry.stdout
    assert reg.read_bytes() == UPSTREAM.encode()

    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 0, r.stderr
    assert reg.read_bytes() == (UPSTREAM + KEEP_ROWS).encode()

    again = _sync(repo, "--reapply", str(keep), "--apply")    # idempotent
    assert again.returncode == 0 and "0 to append, 2 skipped" in again.stdout
    assert hashlib.sha256(reg.read_bytes()).digest() == hashlib.sha256(
        (UPSTREAM + KEEP_ROWS).encode()).digest()


def test_hold_and_reapply_together_is_refused(tmp_path):
    repo = _make_repo(tmp_path)
    r = _sync(repo, "--hold", "--reapply", str(tmp_path / "x.keep.md"))
    assert r.returncode == 3


# --- prevention: warn when an append lands where nobody will see it ----------

def _note_on(tmp_path, monkeypatch, capsys, checkout):
    tool = _load_tool()
    repo = _make_repo(tmp_path)
    if checkout:
        _git(repo, "checkout", "-q", *checkout)
    monkeypatch.setattr(tool, "REGISTER", repo / REG_REL)
    rc = tool.main(["note", "--owner", OWNER, "--scope", "a recorded fact"])
    err = capsys.readouterr().err
    assert rc == 0, err
    return err


def test_an_append_on_main_warns_that_the_row_is_invisible(tmp_path, monkeypatch, capsys):
    err = _note_on(tmp_path, monkeypatch, capsys, None)
    assert "WARNING" in err and "INVISIBLE fleet-wide" in err and "`main`" in err


def test_an_append_on_a_detached_head_warns(tmp_path, monkeypatch, capsys):
    err = _note_on(tmp_path, monkeypatch, capsys, ("--detach",))
    assert "WARNING" in err and "DETACHED HEAD" in err


def test_an_append_on_a_feature_branch_does_not_warn(tmp_path, monkeypatch, capsys):
    err = _note_on(tmp_path, monkeypatch, capsys, ("-b", "fix/something"))
    assert "WARNING" not in err


# --- [P1] REAPPLY is no weaker than register-claim ---------------------------

def _held_sidecar(tmp_path):
    """A repo after HOLD: register at HEAD, a genuine KEEP sidecar + manifest."""
    repo = _make_repo(tmp_path)
    _dirty(repo, STALE + KEEP_ROWS)
    r = _sync(repo, "--apply", "--hold")
    assert r.returncode == 0, r.stderr
    side = repo / "pmoves" / "data" / "register-sync"
    return repo, next(side.glob("*.keep.md"))


def _forge(keep: Path, rows: str) -> None:
    """Rewrite a sidecar AND its manifest consistently -- the strongest forger,
    so the row-level checks are tested on their own, not hidden behind the hash."""
    keep.write_bytes(rows.encode())
    man = keep.with_name(keep.name[: -len(".keep.md")] + ".manifest.json")
    meta = json.loads(man.read_text())
    meta["keep_sha256"] = hashlib.sha256(rows.encode()).hexdigest()
    man.write_text(json.dumps(meta))


def test_reapply_refuses_a_file_outside_the_sidecar_directory(tmp_path):
    repo, _keep = _held_sidecar(tmp_path)
    forged = tmp_path / "forged.keep.md"
    forged.write_text(KEEP_A)
    before = (repo / REG_REL).read_bytes()
    r = _sync(repo, "--reapply", str(forged), "--apply")
    assert r.returncode == 3 and "sidecar in" in r.stderr
    assert (repo / REG_REL).read_bytes() == before


def test_reapply_refuses_an_edited_sidecar(tmp_path):
    repo, keep = _held_sidecar(tmp_path)
    keep.write_bytes(keep.read_bytes() + KEEP_A.replace("bridge.", "bridge!").encode())
    before = (repo / REG_REL).read_bytes()
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 3 and "does not match its manifest" in r.stderr
    assert (repo / REG_REL).read_bytes() == before


def test_reapply_refuses_a_sidecar_with_no_manifest(tmp_path):
    repo, keep = _held_sidecar(tmp_path)
    planted = keep.with_name("planted.keep.md")
    planted.write_text(KEEP_A)
    r = _sync(repo, "--reapply", str(planted), "--apply")
    assert r.returncode == 3 and "manifest" in r.stderr


INTRUDER = _render("CLAIM", "INTRUDER", "fix/held", "take the lane.", "24h", T0)

@pytest.mark.parametrize("rows, rc, needle", [
    (INTRUDER, 1, "another owner"),
    (_render("RELEASE", "INTRUDER", "", "close everything.", at=T0), 3, "bare RELEASE"),
    (KEEP_A + "this line is prose, not a ledger row\n", 3, "not ledger rows"),
])
def test_reapply_refuses_the_forged_file_probe(tmp_path, rows, rc, needle):
    """The reviewer's probe, with a CONSISTENT manifest: intruder CLAIM on a held
    lane, a bare RELEASE, a non-row line. All-or-nothing: nothing appended."""
    repo, keep = _held_with(tmp_path, rows)   # HELD now holds `fix/held`
    reg = repo / REG_REL
    before = reg.read_bytes()
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == rc, (r.stdout, r.stderr)
    assert needle in r.stderr
    assert reg.read_bytes() == before


def test_reapply_skips_rows_main_re_filed_during_the_pull(tmp_path):
    repo, keep = _held_sidecar(tmp_path)
    reg = repo / REG_REL
    refile = ("- `2026-09-28T02:00:00Z` CLAIM `B850-CLAUDE (Knuckles)` branch: "
              "`feat/crush-acp` · **TTL 24h** · scope: RE-FILED: first filed at "
              f"{TS_A}.\n")
    _git(repo, "checkout", "-q", "upstream")
    with open(reg, "a", encoding="utf-8") as fh:
        fh.write(refile)
    _git(repo, "commit", "-q", "-am", "main re-files the crush lane")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "--ff-only", "-q", "upstream")
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 0, r.stderr
    assert "SKIP RE-FILED" in r.stdout and "1 to append, 1 skipped" in r.stdout
    assert reg.read_bytes() == (UPSTREAM + refile + KEEP_B).encode()


# --- [P2] a failure mid-apply is reported truthfully -------------------------

def test_a_failure_after_the_truncate_is_reported_as_partial(tmp_path, monkeypatch):
    tool = _load_tool()
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE + KEEP_ROWS)
    original = reg.read_bytes()

    def boom(register, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(tool, "_append_bytes", boom)
    with pytest.raises(tool.SyncRefused) as exc:
        tool.sync_register(repo, "upstream", apply=True, hold=False)
    msg = str(exc.value)
    assert "PARTIAL APPLY" in msg and "WAS modified" in msg and ".preimage.md" in msg
    assert reg.read_bytes() == BASE.encode()           # HEAD intact, not torn
    pre = next((repo / "pmoves" / "data" / "register-sync").glob("*.preimage.md"))
    assert pre.read_bytes() == original


# --- [P2] bytes, not text ----------------------------------------------------

def test_a_non_utf8_byte_in_a_keep_row_round_trips_byte_exact(tmp_path):
    repo = _make_repo(tmp_path)
    reg = repo / REG_REL
    odd = KEEP_A.encode().replace(b"bridge.", b"bridge \xff.")
    with open(reg, "ab") as fh:
        fh.write(STALE_A.encode() + odd)
    r = _sync(repo, "--apply")
    assert r.returncode == 0, r.stderr
    assert "0 ON-MAIN, 1 RE-FILED, 1 KEEP" in r.stdout
    assert reg.read_bytes() == BASE.encode() + odd


def test_a_line_separator_inside_a_scope_stays_one_row(tmp_path):
    repo = _make_repo(tmp_path)
    stale = STALE_A.replace("reconcile storage.", "reconcile storage.")
    _dirty(repo, stale)
    r = _sync(repo)
    assert r.returncode == 0, r.stderr
    assert "INPUT     1 uncommitted line(s)" in r.stdout
    assert "0 ON-MAIN, 1 RE-FILED, 0 KEEP (of 1 input)" in r.stdout


# --- [P3] -------------------------------------------------------------------

def test_a_staged_register_change_is_refused(tmp_path):
    repo = _make_repo(tmp_path)
    reg = _dirty(repo, STALE)
    _git(repo, "add", REG_REL)
    r = _sync(repo, "--apply")
    assert r.returncode == 3 and "INDEX differs from HEAD" in r.stderr
    assert reg.read_bytes() == (BASE + STALE).encode()


def test_a_missing_git_cannot_turn_a_written_row_into_a_failure(tmp_path, monkeypatch, capsys):
    tool = _load_tool()

    def no_git(*a, **k):
        raise FileNotFoundError(2, "No such file or directory: 'git'")

    monkeypatch.setattr(tool.subprocess, "run", no_git)
    tool._warn_if_invisible(tmp_path / "reg.md")        # must not raise
    assert "WAS appended" in capsys.readouterr().err


# --- round 2: handoff, forged-row shape, timestamp window, coordination -------

HELD_CLAIM = ("- `2026-09-28T00:10:00Z` CLAIM `HELD` branch: `fix/held` · "
              "scope: held lane.\n")


def _held_with(tmp_path, rows: str):
    """A held sidecar set rewritten CONSISTENTLY (keep, pre-image, manifest) to
    carry `rows`, with another owner (HELD) holding `fix/held` in the register."""
    repo, keep = _held_sidecar(tmp_path)
    stem = keep.name[: -len(".keep.md")]
    pre = keep.with_name(stem + ".preimage.md")
    pre.write_bytes(pre.read_bytes() + rows.encode())
    _forge(keep, rows)
    man = keep.with_name(stem + ".manifest.json")
    meta = json.loads(man.read_text())
    meta["preimage_sha256"] = hashlib.sha256(pre.read_bytes()).hexdigest()
    man.write_text(json.dumps(meta))
    _dirty(repo, HELD_CLAIM)
    return repo, keep


def test_a_handoff_held_across_the_pull_reapplies(tmp_path):
    rel = _render("RELEASE", "HELD", "fix/held", "handing off.", at=T0)
    nxt = _render("CLAIM", "NEXT", "fix/held", "taking over.", "24h", T0 + timedelta(minutes=1))
    repo, keep = _held_with(tmp_path, rel + nxt)
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert (repo / REG_REL).read_bytes().endswith((rel + nxt).encode())


def test_the_claim_alone_still_collides(tmp_path):
    nxt = _render("CLAIM", "NEXT", "fix/held", "taking over.", "24h", T0)
    repo, keep = _held_with(tmp_path, nxt)
    before = (repo / REG_REL).read_bytes()
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 1 and "held by `HELD`" in r.stderr
    assert (repo / REG_REL).read_bytes() == before


@pytest.mark.parametrize("rows, needle", [
    (_render("CLAIM", "X", "a/b", "backdated.", "99999h",
             datetime(2020, 1, 1, tzinfo=timezone.utc)), "outside the window"),
    (_render("CLAIM", "X", "a/b", "from the future.", "24h",
             datetime.now(timezone.utc) + timedelta(days=1)), "outside the window"),
    ("- `2026-09-28T00:00:00Z` CORRECTION `X` branch: `a/b` · scope: rewrite history.\n",
     "not reapplied"),
    ("- `2026-09-28T00:00:00Z` CLAIM `X` branch: `a/b` · **TTL 24h** · scope: hand-built.\n",
     "not a row the append roads render"),
])
def test_reapply_refuses_rows_the_append_roads_would_not_emit(tmp_path, rows, needle):
    repo, keep = _held_with(tmp_path, rows)
    before = (repo / REG_REL).read_bytes()
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 3, (r.stdout, r.stderr)
    assert needle in r.stderr
    assert (repo / REG_REL).read_bytes() == before


def test_a_row_missing_from_the_pre_image_is_refused(tmp_path):
    repo, keep = _held_sidecar(tmp_path)
    extra = _render("NOTE", OWNER, "", "not in the pre-image.", at=T0)
    _forge(keep, extra)                       # keep + manifest, pre-image untouched
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 3 and "not in the recorded pre-image" in r.stderr


def test_i_have_coordinated_passes_through_to_reapply(tmp_path):
    nxt = _render("CLAIM", "NEXT", "fix/held", "joining.", "24h", T0,
                  co_owners=["HELD:incumbent"])
    repo, keep = _held_with(tmp_path, nxt)
    r = _sync(repo, "--reapply", str(keep), "--apply")
    assert r.returncode == 1 and "--i-have-coordinated" in r.stderr, (r.stdout, r.stderr)
    r = _sync(repo, "--reapply", str(keep), "--apply", "--i-have-coordinated")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert (repo / REG_REL).read_bytes().endswith(nxt.encode())
