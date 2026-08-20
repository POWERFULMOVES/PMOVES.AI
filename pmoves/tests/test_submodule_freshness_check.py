"""
Tests for pmoves/tools/submodule_freshness_check.py

The freshness check walks every submodule, asks the remote
for the tracked branch's HEAD, and compares to the parent
gitlink. The tool is a thin wrapper over `git ls-remote` +
`git ls-files --stage` + `git merge-base`; the tests assert:

  1. .gitmodules parsing yields the expected schema
     (path, url, branch; branch defaults to "main")
  2. parent_gitlink() returns the right SHA from the index
  3. The SubmoduleFreshness dataclass has the right fields
  4. The summary aggregates counts by status correctly
  5. The CLI's --no-json path produces a human-readable line
  6. The CLI's --strict path exits non-zero when remote_ahead
  7. Diverged branches are flagged as "error" (not in_sync,
     not remote_ahead, not remote_behind)

No live git ls-remote calls in the test suite — the tests
work entirely on a mocked subprocess that returns canned
output for git invocations. The live behavior is exercised
manually + in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import submodule_freshness_check as sfc  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_gitmodules(tmp_path: Path) -> Path:
    """Write a synthetic .gitmodules to a tmp dir for parser tests."""
    g = tmp_path / ".gitmodules"
    g.write_text(
        "[submodule \"PMOVES-HiRAG\"]\n"
        "	path = PMOVES-HiRAG\n"
        "	url = https://github.com/POWERFULMOVES/PMOVES-HiRAG.git\n"
        "	branch = PMOVES.AI-Edition-Hardened\n"
        "[submodule \"pmoves-hirag-mcp\"]\n"
        "	path = pmoves-hirag-mcp\n"
        "	url = https://github.com/POWERFULMOVES/pmoves-hirag-mcp.git\n"
        "	branch = PMOVES.AI-Edition-Hardened\n"
        "[submodule \"PMOVES-skills\"]\n"
        "	path = skills/PMOVES-skills\n"
        "	url = https://github.com/POWERFULMOVES/PMOVES-skills.git\n"
        "	# no branch = → defaults to \"main\"\n",
        encoding="utf-8",
    )
    return g


@pytest.fixture
def sample_records() -> list[dict[str, str]]:
    return [
        {"name": "PMOVES-HiRAG", "path": "PMOVES-HiRAG", "url": "https://example/r1.git", "branch": "PMOVES.AI-Edition-Hardened"},
        {"name": "pmoves-hirag-mcp", "path": "pmoves-hirag-mcp", "url": "https://example/r2.git", "branch": "PMOVES.AI-Edition-Hardened"},
        {"name": "PMOVES-skills", "path": "skills/PMOVES-skills", "url": "https://example/r3.git", "branch": "main"},
    ]


# ============================================================================
# 1. .gitmodules parsing
# ============================================================================



# The pure-logic tests below build synthetic records for paths that do not exist
# on disk. `check_one` now also verifies the working tree is checked out, which
# would short-circuit every one of them. That precondition is not what they are
# testing, so it is satisfied by default here; the tests that DO exercise it
# restore the real implementation explicitly.
_REAL_WORKTREE_POPULATED = sfc.worktree_populated


@pytest.fixture(autouse=True)
def _assume_worktree_checked_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sfc, "worktree_populated", lambda path: True)


def test_parse_gitmodules_returns_records(monkeypatch: pytest.MonkeyPatch, sample_gitmodules: Path) -> None:
    """The parser produces one record per `[submodule ...]` block."""
    monkeypatch.setattr(sfc, "GITMODULES", sample_gitmodules)
    records = sfc.parse_gitmodules()
    assert len(records) == 3, f"expected 3 records, got {len(records)}: {records}"
    assert records[0]["path"] == "PMOVES-HiRAG"
    assert records[0]["url"] == "https://github.com/POWERFULMOVES/PMOVES-HiRAG.git"
    assert records[0]["branch"] == "PMOVES.AI-Edition-Hardened"


def test_parse_gitmodules_branch_defaults_to_main(monkeypatch: pytest.MonkeyPatch, sample_gitmodules: Path) -> None:
    """A submodule without an explicit `branch =` field defaults to "main"."""
    monkeypatch.setattr(sfc, "GITMODULES", sample_gitmodules)
    records = sfc.parse_gitmodules()
    skills = next(r for r in records if r["path"] == "skills/PMOVES-skills")
    assert skills["branch"] == "main", (
        f"PMOVES-skills has no branch = field; parser must default to 'main' (got {skills['branch']!r})"
    )


def test_parse_gitmodules_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A missing .gitmodules returns an empty list (not an exception)."""
    monkeypatch.setattr(sfc, "GITMODULES", tmp_path / "no-such-file")
    assert sfc.parse_gitmodules() == []


# ============================================================================
# 2. parent_gitlink()
# ============================================================================


def test_parent_gitlink_reads_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """parent_gitlink parses the SHA from `git ls-files --stage` output."""
    fake = subprocess.CompletedProcess(
        args=["git", "ls-files", "--stage", "PMOVES-HiRAG"],
        returncode=0,
        stdout="160000 e904b12a477ad670d5036e059912c2889c308926 0\tPMOVES-HiRAG\n",
        stderr="",
    )
    monkeypatch.setattr(sfc, "run_git", lambda *a, **kw: fake)
    sha = sfc.parent_gitlink("PMOVES-HiRAG")
    assert sha == "e904b12a477ad670d5036e059912c2889c308926", (
        f"parent_gitlink should parse the SHA from the 160000 stage line; got {sha!r}"
    )


def test_parent_gitlink_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """An uninitialized submodule path returns None (caller marks local_uninitialized)."""
    fake = subprocess.CompletedProcess(
        args=["git", "ls-files", "--stage", "nope"],
        returncode=0,
        stdout="",
        stderr="",
    )
    monkeypatch.setattr(sfc, "run_git", lambda *a, **kw: fake)
    assert sfc.parent_gitlink("nope") is None


# ============================================================================
# 3. SubmoduleFreshness dataclass
# ============================================================================


def test_submodule_freshness_defaults() -> None:
    """The dataclass has the documented fields with safe defaults."""
    f = sfc.SubmoduleFreshness(path="p", url="u", branch="b")
    assert f.path == "p"
    assert f.url == "u"
    assert f.branch == "b"
    assert f.parent_gitlink is None
    assert f.remote_head is None
    assert f.status == "pending"
    assert f.detail == ""


def test_submodule_freshness_status_values() -> None:
    """All status values are part of the documented set."""
    expected = {"in_sync", "remote_ahead", "remote_behind", "remote_missing",
                "local_uninitialized", "error", "pending"}
    actual = set()
    # Smoke-test each status by constructing a record.
    for status in expected:
        f = sfc.SubmoduleFreshness(path="p", url="u", branch="b", status=status)
        actual.add(f.status)
    assert actual == expected, f"missing statuses: {expected - actual}"


# ============================================================================
# 4. Summary aggregation
# ============================================================================


def test_run_check_summary_aggregates(sample_records: list[dict[str, str]]) -> None:
    """run_check builds a summary with the right counts by status."""
    # Build canned results instead of running real git calls.
    canned = [
        sfc.SubmoduleFreshness(path=sample_records[0]["path"], url=sample_records[0]["url"], branch=sample_records[0]["branch"], status="in_sync"),
        sfc.SubmoduleFreshness(path=sample_records[1]["path"], url=sample_records[1]["url"], branch=sample_records[1]["branch"], status="remote_ahead"),
        sfc.SubmoduleFreshness(path=sample_records[2]["path"], url=sample_records[2]["url"], branch=sample_records[2]["branch"], status="remote_ahead"),
    ]
    with mock.patch.object(sfc, "check_one", side_effect=canned):
        report = sfc.run_check(sample_records[:3], parallel=False)
    s = report.summary
    assert s["total"] == 3
    assert s["in_sync"] == 1
    assert s["remote_ahead"] == 2
    assert s["remote_behind"] == 0
    assert s["errors"] == 0


# ============================================================================
# 5. CLI --no-json
# ============================================================================


def test_cli_no_json_human_summary(sample_records: list[dict[str, str]], capsys: pytest.CaptureFixture) -> None:
    """--no-json prints a human-readable summary, not JSON."""
    # The summary counts come from the canned results, not the record count.
    canned = [
        sfc.SubmoduleFreshness(path="PMOVES-HiRAG", url="u", branch="b", status="in_sync", detail="ok"),
        sfc.SubmoduleFreshness(path="pmoves-hirag-mcp", url="u", branch="b", status="remote_ahead", detail="needs update"),
        sfc.SubmoduleFreshness(path="PMOVES-skills", url="u", branch="b", status="in_sync", detail="ok"),
    ]
    with mock.patch.object(sfc, "parse_gitmodules", return_value=sample_records):
        with mock.patch.object(sfc, "check_one", side_effect=canned):
            rc = sfc.main(["--no-json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "in_sync=2" in captured.out, f"missing in_sync count in: {captured.out!r}"
    assert "remote_ahead=1" in captured.out
    assert "needs update" in captured.out, "remote_ahead details should appear in the human summary"


def test_cli_default_emits_json(sample_records: list[dict[str, str]], capsys: pytest.CaptureFixture) -> None:
    """Default (no --no-json) prints a JSON object with the right shape."""
    canned = [
        sfc.SubmoduleFreshness(path="PMOVES-HiRAG", url="u", branch="b", status="in_sync"),
        sfc.SubmoduleFreshness(path="pmoves-hirag-mcp", url="u", branch="b", status="in_sync"),
        sfc.SubmoduleFreshness(path="PMOVES-skills", url="u", branch="b", status="in_sync"),
    ]
    with mock.patch.object(sfc, "parse_gitmodules", return_value=sample_records):
        with mock.patch.object(sfc, "check_one", side_effect=canned):
            rc = sfc.main([])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "checked_at" in payload
    assert "summary" in payload
    assert "submodules" in payload
    assert payload["summary"]["in_sync"] == 3


# ============================================================================
# 6. CLI --strict
# ============================================================================


def test_cli_strict_exits_nonzero_on_remote_ahead(sample_records: list[dict[str, str]]) -> None:
    """--strict returns 1 when any submodule is remote_ahead."""
    canned = [
        sfc.SubmoduleFreshness(path="a", url="u", branch="b", status="in_sync"),
        sfc.SubmoduleFreshness(path="b", url="u", branch="b", status="remote_ahead"),
        sfc.SubmoduleFreshness(path="c", url="u", branch="b", status="in_sync"),
    ]
    with mock.patch.object(sfc, "parse_gitmodules", return_value=sample_records):
        with mock.patch.object(sfc, "check_one", side_effect=canned):
            rc = sfc.main(["--strict", "--no-json"])
    assert rc == 1, f"--strict with remote_ahead must exit 1, got {rc}"


def test_cli_strict_passes_when_all_in_sync(sample_records: list[dict[str, str]]) -> None:
    """--strict returns 0 when all submodules are in_sync."""
    canned = [
        sfc.SubmoduleFreshness(path="a", url="u", branch="b", status="in_sync"),
        sfc.SubmoduleFreshness(path="b", url="u", branch="b", status="in_sync"),
        sfc.SubmoduleFreshness(path="c", url="u", branch="b", status="in_sync"),
    ]
    with mock.patch.object(sfc, "parse_gitmodules", return_value=sample_records):
        with mock.patch.object(sfc, "check_one", side_effect=canned):
            rc = sfc.main(["--strict", "--no-json"])
    assert rc == 0


# ============================================================================
# 7. Diverged branches
# ============================================================================


def test_check_one_diverged_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two SHAs that are not ancestors of each other -> status: error."""
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111")
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222")
    monkeypatch.setattr(sfc, "_has_object", lambda _s, _c: True)
    # merge-base --is-ancestor returns 1 for "not an ancestor" in both directions.
    monkeypatch.setattr(sfc, "_is_ancestor", lambda _a, _b, _cwd: False)
    result = sfc.check_one(record)
    assert result.status == "error", f"diverged branches should be 'error', got {result.status}"
    assert "diverged" in result.detail, f"detail should mention divergence: {result.detail!r}"


def test_check_one_remote_ahead(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote is ahead of parent (parent is ancestor of remote)."""
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    parent = "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"
    remote = "cccc3333cccc3333cccc3333cccc3333cccc3333"
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: parent)
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: remote)
    monkeypatch.setattr(sfc, "_has_object", lambda _s, _c: True)
    # parent is ancestor of remote (remote ahead); remote is NOT ancestor of parent.
    def fake_is_ancestor(maybe_anc, desc, _cwd):
        return maybe_anc == parent and desc == remote
    monkeypatch.setattr(sfc, "_is_ancestor", fake_is_ancestor)
    monkeypatch.setattr(sfc, "_count_commits_between", lambda _a, _b, _cwd: 3)
    result = sfc.check_one(record)
    assert result.status == "remote_ahead", f"expected remote_ahead, got {result.status}: {result.detail}"
    assert "3 commit" in result.detail


def test_ancestry_runs_inside_the_submodule_not_the_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cwd is the whole defect, so assert it rather than the outcome.

    A submodule's commits live in its own object store. Running merge-base in
    the parent resolves neither SHA, both ancestry checks return non-zero, and
    every genuine update is classified as divergence -- the tool reports
    "reconcile manually" for everything and never once says remote_ahead, which
    is the state --strict exists to gate on.
    """
    record = {"name": "x", "path": "sub/x", "url": "u", "branch": "b"}
    parent = "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"
    remote = "cccc3333cccc3333cccc3333cccc3333cccc3333"
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: parent)
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: remote)
    monkeypatch.setattr(sfc, "_has_object", lambda _s, _c: True)

    seen: list = []
    def spy(maybe_anc, desc, cwd):
        seen.append(cwd)
        return maybe_anc == parent and desc == remote
    monkeypatch.setattr(sfc, "_is_ancestor", spy)
    monkeypatch.setattr(sfc, "_count_commits_between", lambda _a, _b, _cwd: 1)

    sfc.check_one(record)

    assert seen, "_is_ancestor was never called"
    for cwd in seen:
        assert Path(cwd) == sfc.REPO_ROOT / "sub/x", (
            f"ancestry ran in {cwd}, must run in the submodule "
            f"{sfc.REPO_ROOT / 'sub/x'}"
        )


def test_unmeasurable_is_not_reported_as_divergence(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ls-remote` returns a SHA without fetching the object it names.

    Ancestry against an object that is not present fails exactly like genuine
    divergence. Those are different findings -- one is "they diverged", the
    other is "I could not look" -- and collapsing them is how a tool reports a
    conclusion it never measured.
    """
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: "a" * 40)
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: "c" * 40)
    monkeypatch.setattr(sfc, "_has_object", lambda _s, _c: False)   # never resolvable
    monkeypatch.setattr(sfc, "_try_fetch", lambda _u, _b, _c: None)  # fetch cannot help
    called = []
    monkeypatch.setattr(sfc, "_is_ancestor", lambda *a: called.append(a) or False)

    result = sfc.check_one(record)

    assert result.status == "unknown", f"expected 'unknown', got {result.status}"
    assert "could not compare" in result.detail
    assert not called, "must not guess a relationship it cannot compute"


def test_check_one_in_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parent SHA == remote HEAD → in_sync."""
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    same = "deadbeef" + "f" * 32
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: same)
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: same)
    result = sfc.check_one(record)
    assert result.status == "in_sync"


def test_check_one_local_uninitialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """parent_gitlink returns None → local_uninitialized."""
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: None)
    result = sfc.check_one(record)
    assert result.status == "local_uninitialized"


def test_check_one_remote_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """remote_head returns None (branch not on remote) → remote_missing."""
    record = {"name": "x", "path": "x", "url": "u", "branch": "b"}
    monkeypatch.setattr(sfc, "parent_gitlink", lambda _p: "a" * 40)
    monkeypatch.setattr(sfc, "remote_head", lambda _u, _b: None)
    result = sfc.check_one(record)
    assert result.status == "remote_missing", f"expected remote_missing, got {result.status}: {result.detail}"
    assert "could not resolve" in result.detail


# ── uninitialized worktrees (2026-08-20) ────────────────────────────────────
#
# 13 of 71 submodules were uninitialized on B850 and this tool exited 0. Two
# independent reasons:
#
#   1. `local_uninitialized` was never counted in the summary, so the buckets
#      silently summed to 58 against total=71.
#   2. The status only fired when the parent GITLINK was missing from the index.
#      All 13 had a perfectly good gitlink and an EMPTY directory, which the
#      tool classified as healthy.
#
# PMOVES-MiniMax-MCP was one of them, which is why .claude/mcp.json registers
# MiniMax from PyPI rather than the submodule.

SOURCE = (sfc.REPO_ROOT / "pmoves" / "tools" / "submodule_freshness_check.py").read_text(
    encoding="utf-8"
)


def test_worktree_populated_requires_a_dotgit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`git` marks a submodule initialized by placing a .git file/dir inside it —
    the same signal `git submodule status` uses for its '-' marker."""
    monkeypatch.setattr(sfc, "worktree_populated", _REAL_WORKTREE_POPULATED)
    monkeypatch.setattr(sfc, "REPO_ROOT", tmp_path)
    (tmp_path / "empty-sub").mkdir()
    assert sfc.worktree_populated("empty-sub") is False
    assert sfc.worktree_populated("never-created") is False


def test_worktree_populated_true_when_checked_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards the positive case: if this returned False for a real checkout the
    gate would fail every run and get reverted."""
    monkeypatch.setattr(sfc, "worktree_populated", _REAL_WORKTREE_POPULATED)
    monkeypatch.setattr(sfc, "REPO_ROOT", tmp_path)
    sub = tmp_path / "real-sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/real-sub\n", encoding="utf-8")
    assert sfc.worktree_populated("real-sub") is True


def test_populated_gitlink_with_empty_tree_is_uninitialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact shape of all 13: a valid gitlink over an empty directory."""
    monkeypatch.setattr(sfc, "worktree_populated", _REAL_WORKTREE_POPULATED)
    monkeypatch.setattr(sfc, "REPO_ROOT", tmp_path)
    (tmp_path / "sub").mkdir()
    monkeypatch.setattr(sfc, "parent_gitlink", lambda path: "d1ac7f063d20e70015ed6732664049ae4ba9d74e")
    result = sfc.check_one({"path": "sub", "url": "https://example/sub.git", "branch": "main"})
    assert result.status == "local_uninitialized"
    assert "not checked out" in result.detail
    assert "git submodule update --init" in result.detail


def test_summary_counts_local_uninitialized() -> None:
    """The counter whose absence hid all 13."""
    assert 'r.status == "local_uninitialized"' in SOURCE
    assert '"local_uninitialized": sum(' in SOURCE


def test_summary_has_a_bucket_for_every_status() -> None:
    """The instrument checks itself. Adding a status without a counter shrinks
    the buckets against `total` — exactly how this went unnoticed."""
    for status in ("in_sync", "remote_ahead", "remote_behind",
                   "remote_missing", "local_uninitialized"):
        assert f'r.status == "{status}"' in SOURCE, f"{status} has no counter"
    assert 'r.status in ("error",)' in SOURCE
    assert "does not account for every submodule" in SOURCE, "no bucket-sum invariant"


def test_uninitialized_fails_without_needing_strict() -> None:
    """An uninitialized tree is not a freshness signal like remote_ahead — it
    means the code the gitlink points at is absent. It must fail on its own."""
    gate = SOURCE[SOURCE.index('if report.summary["local_uninitialized"]'):]
    before_return = gate.split("return 1")[0]
    assert "args.strict" not in before_return


def test_override_is_explicit_and_documented() -> None:
    assert "--allow-uninitialized" in SOURCE
    assert "deliberate partial checkout" in SOURCE
