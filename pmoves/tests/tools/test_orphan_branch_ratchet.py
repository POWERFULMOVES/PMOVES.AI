"""Tests for the orphan-branch ratchet.

The defect under test is work stranded off `main` in a shape no other gate
sees: pushed commits no open PR carries that never reached main, and local
commits never pushed. The two cases that prompted it (origin/fix/consolidate-
archon and z890's feat/showtime-updater) both turned out, on triage, to have
LANDED -- one inside a squash of a different branch (PR #2275), one as a merged
PR's exact head with its remote deleted. Each has a fixture below that must NOT
be flagged.

The hard half of the problem is not finding commits that are absent from
`main` -- `git rev-list main..branch` does that -- it is NOT flagging the
hundreds of branches whose content did land, through a SQUASH merge, and whose
ancestry therefore lies. So most of these tests are negative controls:

  * squash-merged branch whose head IS the merged PR head      -> not flagged
  * commits already on main by patch (cherry-picked)           -> not flagged
  * branch with an OPEN PR (in flight, not stranded)           -> not flagged

and the positive controls name the branch and the exact count, because a
check that reports "some orphans exist" can go blind without anyone noticing.

Every fixture is a throwaway git repo under tmp_path with a bare `origin`, and
the PR lookup is stubbed with `--prs-json`. Nothing here reaches GitHub. The
one test that exercises the gh path points `--gh` at a binary that does not
exist and requires exit 3 -- could not measure is never a pass.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "orphan_branch_ratchet.py"

spec = importlib.util.spec_from_file_location("orphan_branch_ratchet", MODULE)
assert spec and spec.loader
obr = importlib.util.module_from_spec(spec)
sys.modules["orphan_branch_ratchet"] = obr
spec.loader.exec_module(obr)

# Real `git` is required: the fixtures ARE git repos. If it is missing the
# suite has measured nothing, which must not read as green.
assert subprocess.run(["git", "--version"], capture_output=True).returncode == 0


# --------------------------------------------------------------------------
# fixture helpers
# --------------------------------------------------------------------------

_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd: Path, *args: str, author: str | None = None) -> str:
    env = dict(_ENV)
    if author:
        env["GIT_AUTHOR_NAME"] = author
    out = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def commit(repo: Path, name: str, body: str, author: str | None = None) -> str:
    (repo / name).write_text(body, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"touch {name}", author=author)
    return git(repo, "rev-parse", "HEAD")


class Fixture:
    """A bare origin, a working clone, and a list of fake PRs."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.origin = tmp_path / "origin.git"
        self.work = tmp_path / "work"
        git(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(tmp_path, "clone", "-q", str(self.origin), str(self.work))
        git(self.work, "checkout", "-q", "-b", "main")
        commit(self.work, "README", "root\n")
        git(self.work, "push", "-q", "origin", "main")
        self.prs: list[dict] = []

    def branch(self, name: str, start: str = "main") -> None:
        git(self.work, "checkout", "-q", "-b", name, start)

    def push(self, name: str) -> None:
        git(self.work, "push", "-q", "origin", name)

    def pr(self, branch: str, head: str, state: str, number: int) -> None:
        self.prs.append(
            {
                "number": number,
                "state": state,
                "headRefName": branch,
                "headRefOid": head,
                "mergedAt": "2026-07-15T00:12:33Z" if state == "MERGED" else None,
                "closedAt": None if state == "OPEN" else "2026-07-15T00:12:33Z",
                "isCrossRepository": False,
            }
        )

    def squash_into_main(self, branch: str) -> None:
        git(self.work, "checkout", "-q", "main")
        git(self.work, "merge", "-q", "--squash", branch)
        git(self.work, "commit", "-q", "-m", f"squash {branch}")
        git(self.work, "push", "-q", "origin", "main")

    def prs_file(self) -> Path:
        path = self.tmp / "prs.json"
        path.write_text(json.dumps(self.prs), encoding="utf-8")
        return path

    def baseline(self, payload: dict | None = None) -> Path:
        path = self.tmp / "baseline.json"
        path.write_text(json.dumps(payload or {"remote": {}, "local": {}}), encoding="utf-8")
        return path


def run(capsys, fx: Fixture, mode: str, *extra: str) -> tuple[int, dict]:
    git(fx.work, "fetch", "-q", "origin")
    argv = [mode, "--repo", str(fx.work), "--json", "--prs-json", str(fx.prs_file())]
    if "--baseline" not in extra:
        argv += ["--baseline", str(fx.baseline())]
    if mode == "local" and "--node" not in extra:
        argv += ["--node", "testnode"]
    code = obr.main([*argv, *extra])
    return code, json.loads(capsys.readouterr().out)


def by_branch(out: dict) -> dict[str, dict]:
    return {f["branch"]: f for f in out["findings"]}


@pytest.fixture()
def fx(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path)


# --------------------------------------------------------------------------
# remote mode
# --------------------------------------------------------------------------


def test_post_merge_commits_are_flagged_with_count_authors_and_prs(capsys, fx):
    """Post-merge shape: PR merged, then more commits pushed that never landed."""
    fx.branch("fix/archon")
    commit(fx.work, "a1", "one\n")
    merged_head = commit(fx.work, "a2", "two\n")
    fx.push("fix/archon")
    fx.pr("fix/archon", merged_head, "MERGED", 2127)
    fx.squash_into_main("fix/archon")

    git(fx.work, "checkout", "-q", "fix/archon")
    commit(fx.work, "a3", "three\n", author="Agent Zero")
    closed_head = commit(fx.work, "a4", "four\n", author="Agent Zero")
    commit(fx.work, "a5", "five\n", author="Agent Zero")
    fx.push("fix/archon")
    fx.pr("fix/archon", closed_head, "CLOSED", 2208)

    code, out = run(capsys, fx, "remote")
    found = by_branch(out)

    assert code == 1
    assert found["fix/archon"]["count"] == 3, "exactly the commits after the merged head"
    assert found["fix/archon"]["kind"] == "POST_MERGE"
    assert found["fix/archon"]["authors"] == ["Agent Zero"]
    prs = {(p["number"], p["state"]) for p in found["fix/archon"]["prs"]}
    assert prs == {(2127, "MERGED"), (2208, "CLOSED")}
    assert found["fix/archon"]["recommendation"]
    assert found["fix/archon"]["status"] == "NEW"


def test_squash_merged_branch_whose_head_is_the_merged_pr_head_is_not_flagged(capsys, fx):
    """Ancestry lies after a squash merge: both commits are unreachable from
    main, yet the content landed. head == merged PR head means not an orphan."""
    fx.branch("feat/squashed")
    commit(fx.work, "s1", "one\n")
    head = commit(fx.work, "s2", "two\n")
    fx.push("feat/squashed")
    fx.pr("feat/squashed", head, "MERGED", 10)
    fx.squash_into_main("feat/squashed")

    # Sanity: ancestry really does say "2 commits not on main".
    git(fx.work, "fetch", "-q", "origin")
    assert git(fx.work, "rev-list", "--count", "origin/main..origin/feat/squashed") == "2"

    code, out = run(capsys, fx, "remote")
    assert "feat/squashed" not in by_branch(out)
    assert code == 0


def test_cherry_equivalent_commits_are_not_flagged(capsys, fx):
    """A commit whose patch is already on main (cherry-picked) is not stranded."""
    fx.branch("fix/picked")
    picked = commit(fx.work, "p1", "picked\n")
    fx.push("fix/picked")
    git(fx.work, "checkout", "-q", "main")
    git(fx.work, "cherry-pick", picked)
    git(fx.work, "push", "-q", "origin", "main")

    code, out = run(capsys, fx, "remote")
    assert "fix/picked" not in by_branch(out)
    assert code == 0


def test_branch_with_an_open_pr_is_in_flight_not_orphaned(capsys, fx):
    fx.branch("feat/open")
    head = commit(fx.work, "o1", "open\n")
    fx.push("feat/open")
    fx.pr("feat/open", head, "OPEN", 30)

    code, out = run(capsys, fx, "remote")
    assert "feat/open" not in by_branch(out)
    assert code == 0


def test_closed_unmerged_and_never_prd_branches_are_flagged(capsys, fx):
    fx.branch("feat/closed")
    head = commit(fx.work, "c1", "closed\n")
    fx.push("feat/closed")
    fx.pr("feat/closed", head, "CLOSED", 40)
    fx.branch("feat/nopr", "main")
    commit(fx.work, "n1", "nopr\n")
    fx.push("feat/nopr")

    code, out = run(capsys, fx, "remote")
    found = by_branch(out)
    assert code == 1
    assert found["feat/closed"]["kind"] == "CLOSED_UNMERGED"
    assert found["feat/nopr"]["kind"] == "NO_PR"


def test_branch_rebased_after_merge_counts_only_the_new_work(capsys, fx):
    """Rewritten-after-merge: the branch was force-pushed after its PR
    merged, so the merged head is NOT an ancestor of the branch any more. The
    rebased copies of already-merged commits are patch-equal to the merged
    head's history and must not be counted; only the genuinely new commit is."""
    fx.branch("fix/rewritten")
    commit(fx.work, "r1", "one\n")
    merged_head = commit(fx.work, "r2", "two\n")
    fx.push("fix/rewritten")
    fx.pr("fix/rewritten", merged_head, "MERGED", 80)
    fx.squash_into_main("fix/rewritten")
    # Rewrite: replay r1, r2 onto a new root commit on the branch, add r3.
    git(fx.work, "checkout", "-q", "-b", "tmp", "main~1")
    commit(fx.work, "unrelated", "x\n")
    git(fx.work, "cherry-pick", f"{merged_head}~1", merged_head)
    commit(fx.work, "r3", "new work\n")
    git(fx.work, "branch", "-f", "fix/rewritten", "tmp")
    git(fx.work, "push", "-q", "-f", "origin", "fix/rewritten")
    git(fx.work, "fetch", "-q", "origin")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", merged_head, "origin/fix/rewritten"],
        cwd=fx.work, capture_output=True,
    )
    assert ancestry.returncode == 1, "fixture must break ancestry, or it tests nothing"

    code, out = run(capsys, fx, "remote")
    found = by_branch(out)
    assert code == 1
    # r3 and "unrelated" are new; the replayed r1/r2 are not.
    assert found["fix/rewritten"]["count"] == 2


def test_merged_head_missing_from_object_store_is_could_not_measure(capsys, fx):
    """If we cannot see what merged, we cannot say what came after it."""
    fx.branch("fix/ghost")
    commit(fx.work, "g1", "one\n")
    fx.push("fix/ghost")
    fx.pr("fix/ghost", "d" * 40, "MERGED", 90)

    code, out = run(capsys, fx, "remote", "--no-fetch-pr-heads")
    assert code == 3
    assert [u["branch"] for u in out["unmeasured"]] == ["fix/ghost"]
    assert "fix/ghost" not in by_branch(out)


def test_commits_swallowed_by_another_branchs_squash_are_landed(capsys, fx):
    """The real consolidate-archon shape (corrected by triage 2026-10-07): its
    commits reached main inside PR #2275, a squash of a DIFFERENT branch. Its
    own PR closed unmerged, so neither `git cherry` nor PR-head matching can see
    that the content landed. The merge-tree content test must."""
    fx.branch("fix/swallowed")
    commit(fx.work, "w1", "one\n")
    head = commit(fx.work, "w2", "two\n")
    fx.push("fix/swallowed")
    fx.pr("fix/swallowed", head, "CLOSED", 2208)
    fx.branch("fix/carrier", "fix/swallowed")  # carries its commits, adds more, gets squashed
    carrier = commit(fx.work, "w3", "three\n")
    fx.push("fix/carrier")
    fx.pr("fix/carrier", carrier, "MERGED", 2275)
    fx.squash_into_main("fix/carrier")
    git(fx.work, "push", "-q", "origin", "--delete", "fix/carrier")

    # Sanity: cherry alone still calls both commits orphans.
    git(fx.work, "fetch", "-q", "--prune", "origin")
    plus = [ln for ln in git(fx.work, "cherry", "origin/main", "origin/fix/swallowed").splitlines()
            if ln.startswith("+")]
    assert len(plus) == 2, "fixture must defeat git cherry, or it tests nothing"

    code, out = run(capsys, fx, "remote")
    assert "fix/swallowed" not in by_branch(out)
    assert "fix/swallowed" not in [u["branch"] for u in out["uncertain"]]
    assert code == 0


def test_upstream_gone_branch_whose_tip_is_a_merged_pr_head_is_landed(capsys, fx):
    """The feat/showtime-updater shape (corrected by triage): it was PR #1905's
    head, squash-merged, remote branch deleted -> `[gone]`. Main has since
    moved over the same file, so the content test alone would say UNCERTAIN;
    the merged-PR-head match must settle it as landed first."""
    fx.branch("feat/updater")
    head = commit(fx.work, "README", "updater change\n")
    git(fx.work, "push", "-q", "-u", "origin", "feat/updater")
    fx.pr("feat/updater", head, "MERGED", 1905)
    fx.squash_into_main("feat/updater")
    git(fx.work, "push", "-q", "origin", "--delete", "feat/updater")
    git(fx.work, "fetch", "-q", "--prune", "origin")
    git(fx.work, "checkout", "-q", "main")
    commit(fx.work, "README", "main moved on\n")
    git(fx.work, "push", "-q", "origin", "main")
    assert ": gone]" in git(fx.work, "branch", "-vv", "--list", "feat/updater")

    code, out = run(capsys, fx, "local")
    assert "feat/updater" not in by_branch(out)
    assert "feat/updater" not in [u["branch"] for u in out["uncertain"]]
    assert code == 0


def test_conflicting_commit_is_uncertain_and_not_counted(capsys, fx):
    """Main moved over the same lines: the commit neither no-op-applies nor
    applies cleanly. Nothing is provable, so it is reported apart and the
    ratchet does not fail on it."""
    fx.branch("fix/conflicts")
    commit(fx.work, "README", "branch change\n")
    fx.push("fix/conflicts")
    git(fx.work, "checkout", "-q", "main")
    commit(fx.work, "README", "main change\n")
    git(fx.work, "push", "-q", "origin", "main")

    code, out = run(capsys, fx, "remote")
    assert "fix/conflicts" not in by_branch(out)
    unc = {u["branch"]: u for u in out["uncertain"]}
    assert unc["fix/conflicts"]["count"] == 1
    assert "triage" in unc["fix/conflicts"]["hint"]
    assert code == 0


def _union_register(fx: Fixture) -> None:
    """A merge=union file on main, like pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md."""
    git(fx.work, "checkout", "-q", "main")
    (fx.work / ".gitattributes").write_text("register.md merge=union\n", encoding="utf-8")
    (fx.work / "register.md").write_text("row A\n", encoding="utf-8")
    git(fx.work, "add", ".gitattributes", "register.md")
    git(fx.work, "commit", "-q", "-m", "register")
    git(fx.work, "push", "-q", "origin", "main")


def _append_row(fx: Fixture, branch: str, row: str) -> str:
    fx.branch(branch)
    with (fx.work / "register.md").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(row + "\n")
    git(fx.work, "commit", "-q", "-am", f"append {row}")
    fx.push(branch)
    return git(fx.work, "rev-parse", "HEAD")


def test_union_file_row_already_on_main_is_landed(capsys, fx):
    """Review P2 on #3306: merge=union makes merge-tree replay an
    already-landed register row "cleanly" by DUPLICATING it, so the tree
    differs and the commit read as an orphan (8 of 92 baselined commits)."""
    _union_register(fx)
    row_b = _append_row(fx, "docs/reg-landed", "row B")
    # Main gets row B too, through another PR, at a different position.
    git(fx.work, "checkout", "-q", "main")
    with (fx.work / "register.md").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("row C\nrow B\nrow D\n")  # B lands mid-run, with rows after it
    git(fx.work, "commit", "-q", "-am", "other PRs land C, B, D")
    git(fx.work, "push", "-q", "origin", "main")

    # Sanity: the raw replay really is clean AND tree-changing (the old bug).
    main_sha = git(fx.work, "rev-parse", "main")
    tree = git(fx.work, "merge-tree", "--write-tree", f"--merge-base={row_b}^", main_sha, row_b)
    assert tree != git(fx.work, "rev-parse", "main^{tree}"), "fixture must reproduce the duplicate"

    code, out = run(capsys, fx, "remote")
    assert "docs/reg-landed" not in by_branch(out)
    assert "docs/reg-landed" not in [u["branch"] for u in out["uncertain"]]
    assert code == 0


def test_union_file_genuinely_new_row_is_an_orphan(capsys, fx):
    _union_register(fx)
    _append_row(fx, "docs/reg-new", "row D")
    git(fx.work, "checkout", "-q", "main")
    with (fx.work / "register.md").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("row C\n")
    git(fx.work, "commit", "-q", "-am", "main moves on")
    git(fx.work, "push", "-q", "origin", "main")

    code, out = run(capsys, fx, "remote")
    assert by_branch(out)["docs/reg-new"]["count"] == 1
    assert code == 1


def test_exempt_branch_is_skipped(capsys, fx):
    fx.branch("integration/long-lived")
    commit(fx.work, "i1", "x\n")
    fx.push("integration/long-lived")
    base = fx.baseline({"_exempt": {"integration/long-lived": "PR base branch"},
                        "remote": {}, "local": {}})
    code, out = run(capsys, fx, "remote", "--baseline", str(base))
    assert "integration/long-lived" not in by_branch(out)
    assert code == 0


def test_exempt_entry_without_reason_fails(capsys, fx):
    base = fx.baseline({"_exempt": {"integration/long-lived": " "}, "remote": {}, "local": {}})
    code, out = run(capsys, fx, "remote", "--baseline", str(base))
    assert code == 1
    assert any("_exempt" in p for p in out["baseline_problems"])


def test_pr_list_at_limit_is_could_not_measure(capsys, fx, monkeypatch):
    """A truncated PR list makes merged branches look orphaned: exit 3."""
    real_run = obr.subprocess.run

    def fake_run(cmd, *a, **kw):
        if cmd[0] == "fake-gh":
            prs = [{"number": i, "state": "MERGED", "headRefName": f"b{i}", "headRefOid": "0" * 40,
                    "isCrossRepository": False} for i in range(2)]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(prs), "")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(obr, "PR_LIMIT", 2)
    monkeypatch.setattr(obr.subprocess, "run", fake_run)
    git(fx.work, "fetch", "-q", "origin")
    code = obr.main(["remote", "--repo", str(fx.work), "--baseline", str(fx.baseline()),
                     "--gh", "fake-gh"])
    assert code == 3
    assert "limit" in capsys.readouterr().err


def test_missing_merged_head_is_fetched_from_refs_pull_without_moving_refs(capsys, fx):
    """Force-pushed after merge: the merged head lives only at refs/pull/N/head.
    The tool fetches it (objects only) and measures, instead of exit 3."""
    other = fx.tmp / "other"
    git(fx.tmp, "clone", "-q", str(fx.origin), str(other))
    git(other, "checkout", "-q", "-b", "pr-head", "origin/main")
    merged_head = commit(other, "m1", "merged\n")
    git(other, "push", "-q", "origin", f"{merged_head}:refs/pull/95/head")
    fx.pr("fix/forced", merged_head, "MERGED", 95)

    fx.branch("fix/forced")
    commit(fx.work, "f1", "after\n")
    fx.push("fix/forced")
    git(fx.work, "fetch", "-q", "origin")
    assert subprocess.run(["git", "cat-file", "-e", f"{merged_head}^{{commit}}"],
                          cwd=fx.work, capture_output=True).returncode != 0
    before = git(fx.work, "for-each-ref", "--format=%(refname) %(objectname)")

    code = obr.main(["remote", "--repo", str(fx.work), "--json", "--prs-json", str(fx.prs_file()),
                     "--baseline", str(fx.baseline())])
    out = json.loads(capsys.readouterr().out)
    assert out["unmeasured"] == []
    assert by_branch(out)["fix/forced"]["kind"] == "POST_MERGE"
    assert code == 1
    assert git(fx.work, "for-each-ref", "--format=%(refname) %(objectname)") == before


def test_gh_unavailable_is_could_not_measure_not_a_pass(capsys, fx, tmp_path):
    """No --prs-json and a gh that does not exist: exit 3, never 0."""
    git(fx.work, "fetch", "-q", "origin")
    code = obr.main(
        [
            "remote",
            "--repo",
            str(fx.work),
            "--baseline",
            str(fx.baseline()),
            "--gh",
            str(tmp_path / "no-such-gh"),
        ]
    )
    assert code == 3
    assert "could not measure" in capsys.readouterr().err.lower()


def test_unreachable_remote_is_could_not_measure(capsys, fx):
    git(fx.work, "remote", "set-url", "origin", str(fx.tmp / "gone.git"))
    code = obr.main(
        ["remote", "--repo", str(fx.work), "--baseline", str(fx.baseline()),
         "--prs-json", str(fx.prs_file())]
    )
    assert code == 3


# --------------------------------------------------------------------------
# local mode
# --------------------------------------------------------------------------


def test_unpushed_local_branch_is_flagged(capsys, fx):
    """Local-only, never pushed: this disk holds the only copy."""
    fx.branch("feat/local-only")
    commit(fx.work, "l1", "one\n")
    commit(fx.work, "l2", "two\n")
    git(fx.work, "checkout", "-q", "main")

    code, out = run(capsys, fx, "local")
    found = by_branch(out)
    assert code == 1
    assert found["feat/local-only"]["count"] == 2
    assert found["feat/local-only"]["kind"] == "NO_UPSTREAM"


def test_local_commits_ahead_of_a_live_upstream_are_flagged(capsys, fx):
    fx.branch("feat/ahead")
    commit(fx.work, "h1", "pushed\n")
    git(fx.work, "push", "-q", "-u", "origin", "feat/ahead")
    fx.pr("feat/ahead", git(fx.work, "rev-parse", "HEAD"), "OPEN", 50)
    commit(fx.work, "h2", "unpushed\n")
    git(fx.work, "checkout", "-q", "main")

    code, out = run(capsys, fx, "local")
    found = by_branch(out)
    assert code == 1
    assert found["feat/ahead"]["count"] == 1, "only the unpushed commit"
    assert found["feat/ahead"]["kind"] == "AHEAD_OF_UPSTREAM"


def test_local_squash_merged_branch_with_upstream_gone_is_not_flagged(capsys, fx):
    """The common case on a long-lived node: PR squash-merged, remote branch
    deleted, local branch left behind. Its content is on main."""
    fx.branch("chore/done")
    head = commit(fx.work, "d1", "done\n")
    git(fx.work, "push", "-q", "-u", "origin", "chore/done")
    fx.pr("chore/done", head, "MERGED", 60)
    fx.squash_into_main("chore/done")
    git(fx.work, "push", "-q", "origin", "--delete", "chore/done")
    git(fx.work, "fetch", "-q", "--prune", "origin")

    code, out = run(capsys, fx, "local")
    assert "chore/done" not in by_branch(out)
    assert code == 0


def test_local_mode_never_modifies_branches(capsys, fx):
    fx.branch("feat/keep")
    commit(fx.work, "k1", "keep\n")
    git(fx.work, "checkout", "-q", "main")
    git(fx.work, "fetch", "-q", "origin")
    before = git(fx.work, "for-each-ref", "--format=%(refname) %(objectname)")
    common = ["--repo", str(fx.work), "--json", "--prs-json", str(fx.prs_file()),
              "--baseline", str(fx.baseline())]
    obr.main(["local", "--node", "testnode", *common])
    obr.main(["remote", *common])
    capsys.readouterr()
    assert git(fx.work, "for-each-ref", "--format=%(refname) %(objectname)") == before


# --------------------------------------------------------------------------
# baseline ratchet
# --------------------------------------------------------------------------


def _post_merge(fx: Fixture, extra: int) -> None:
    fx.branch("fix/stranded")
    head = commit(fx.work, "m1", "merged\n")
    fx.push("fix/stranded")
    fx.pr("fix/stranded", head, "MERGED", 70)
    fx.squash_into_main("fix/stranded")
    git(fx.work, "checkout", "-q", "fix/stranded")
    for i in range(extra):
        commit(fx.work, f"x{i}", f"{i}\n")
    fx.push("fix/stranded")


def _baselined(fx: Fixture, count: int, reason: str = "known: triage pending") -> Path:
    return fx.baseline(
        {"remote": {"fix/stranded": {"count": count, "kind": "POST_MERGE", "reason": reason}},
         "local": {}}
    )


def test_baselined_orphan_at_its_count_passes(capsys, fx):
    _post_merge(fx, 2)
    code, out = run(capsys, fx, "remote", "--baseline", str(_baselined(fx, 2)))
    assert code == 0
    assert by_branch(out)["fix/stranded"]["status"] == "BASELINED"


def test_baseline_growth_fails(capsys, fx):
    _post_merge(fx, 3)
    code, out = run(capsys, fx, "remote", "--baseline", str(_baselined(fx, 2)))
    assert code == 1
    assert by_branch(out)["fix/stranded"]["status"] == "GROWTH"


def test_baseline_shrink_passes_and_says_to_lower_it(capsys, fx):
    _post_merge(fx, 1)
    code, out = run(capsys, fx, "remote", "--baseline", str(_baselined(fx, 2)))
    assert code == 0
    assert by_branch(out)["fix/stranded"]["status"] == "SHRUNK"


def test_vanished_baseline_entry_passes_but_is_flagged_stale(capsys, fx):
    code, out = run(capsys, fx, "remote", "--baseline", str(_baselined(fx, 2)))
    assert code == 0
    assert out["stale"] == ["fix/stranded"]


def test_baseline_entry_without_a_reason_fails(capsys, fx):
    _post_merge(fx, 2)
    code, out = run(capsys, fx, "remote", "--baseline", str(_baselined(fx, 2, reason="")))
    assert code == 1
    assert out["baseline_problems"]


def test_write_baseline_keeps_reasons_and_leaves_new_entries_unreasoned(capsys, fx):
    _post_merge(fx, 2)
    fx.branch("feat/nopr2", "main")
    commit(fx.work, "z1", "z\n")
    fx.push("feat/nopr2")
    path = _baselined(fx, 2, reason="kept reason")
    code, _ = run(capsys, fx, "remote", "--baseline", str(path), "--write-baseline")
    assert code == 0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["remote"]["fix/stranded"]["reason"] == "kept reason"
    assert data["remote"]["feat/nopr2"]["reason"] == ""
    # ...and that unreasoned entry fails the next run until someone writes why.
    code, _ = run(capsys, fx, "remote", "--baseline", str(path))
    assert code == 1
