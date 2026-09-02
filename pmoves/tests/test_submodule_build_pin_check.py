"""Tests for pmoves/tools/submodule_build_pin_check.py

The defect this gate exists to stop is invisible to CI by construction: a
submodule WORKTREE drifted off the recorded gitlink is node-local state. A
fresh clone is always correct, so nothing in the repo and nothing in a
pipeline can see it. On B850 that let cipher's MCP transport answer

    HTTP 400  InternalServerError: stream is not readable

for two weeks while `main` carried the fix, because the build road's
`build.context` is the worktree and docker reads files, not gitlinks.

So these tests build REAL git repositories with a real gitlink and drift them
on purpose. Mocking `git` here would test the mock, not the property.

The property that must never regress: a submodule the check could not read is
NOT reported as clean. Every "could not measure" case exits 3, and 3 wins over
any number of clean siblings.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import submodule_build_pin_check as sbpc  # noqa: E402


def _git(*args: str, cwd: Path) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        # A developer's own global config must not decide whether this passes.
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
    }
    out = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        check=True, env=env,
    )
    return out.stdout.strip()


@pytest.fixture
def superproject(tmp_path: Path) -> tuple[Path, str]:
    """A superproject with one real submodule, pinned at its second commit.

    Returns (superproject_path, first_commit_sha) — the sha is what the drift
    tests check the worktree back to.
    """
    sub = tmp_path / "sub-origin"
    sub.mkdir()
    _git("init", "-q", "-b", "main", cwd=sub)
    (sub / "f.txt").write_text("one\n")
    _git("add", "f.txt", cwd=sub)
    _git("commit", "-qm", "one", cwd=sub)
    first = _git("rev-parse", "HEAD", cwd=sub)
    (sub / "f.txt").write_text("two\n")
    _git("commit", "-qam", "two", cwd=sub)

    top = tmp_path / "top"
    top.mkdir()
    _git("init", "-q", "-b", "main", cwd=top)
    (top / "README").write_text("x\n")
    _git("add", "README", cwd=top)
    _git("commit", "-qm", "init", cwd=top)
    _git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
         str(sub), "Pmoves-cipher", cwd=top)
    _git("commit", "-qm", "add submodule", cwd=top)

    return top, first


def _run(cwd: Path, *paths: str) -> tuple[int, list[dict]]:
    """Invoke the check with cwd set — the tool anchors on CWD by design."""
    prev = Path.cwd()
    os.chdir(cwd)
    try:
        # REPO_ROOT is resolved at import time; re-resolve for this cwd.
        sbpc.REPO_ROOT = sbpc._repo_root()
        return sbpc.check(list(paths))
    finally:
        os.chdir(prev)


def test_synced_worktree_is_clean(superproject):
    top, _ = superproject
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 0
    assert findings[0]["status"] == "clean"
    assert findings[0]["gitlink"] == findings[0]["worktree"]


def test_drifted_worktree_is_reported(superproject):
    """The exact B850 shape: worktree behind the pin, nothing else wrong."""
    top, first = superproject
    _git("checkout", "-q", first, cwd=top / "Pmoves-cipher")
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 1
    assert findings[0]["status"] == "drift"
    assert findings[0]["gitlink"] != findings[0]["worktree"]


def test_drift_is_detected_when_worktree_is_AHEAD_too(superproject):
    """Ahead is drift as well.

    An unpushed local commit is the friendlier-looking case and exactly as
    unreproducible: the image would carry a commit that exists on one disk.
    """
    top, _first = superproject
    subdir = top / "Pmoves-cipher"
    (subdir / "f.txt").write_text("three\n")
    _git("commit", "-qam", "three", cwd=subdir)
    code, _ = _run(top, "Pmoves-cipher")
    assert code == 1


def test_uninitialized_submodule_is_unmeasured_not_clean(superproject):
    """The whole point of the exit-3 lane.

    An empty submodule directory reads as "no drift found" to any check that
    only compares what it managed to read.
    """
    top, _ = superproject
    subdir = top / "Pmoves-cipher"
    (subdir / ".git").unlink()
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 3
    assert findings[0]["status"] == "unmeasured"


def test_path_that_is_not_a_gitlink_is_unmeasured(superproject):
    """A typo'd or renamed path must not silently pass."""
    top, _ = superproject
    code, findings = _run(top, "README")
    assert code == 3
    assert findings[0]["status"] == "unmeasured"


def test_unmeasured_beats_clean_siblings(superproject):
    """3 takes precedence. One readable submodule cannot vouch for another."""
    top, _ = superproject
    code, findings = _run(top, "Pmoves-cipher", "README")
    assert code == 3
    assert {f["status"] for f in findings} == {"clean", "unmeasured"}


def test_outside_a_git_tree_returns_none_rather_than_guessing(tmp_path: Path):
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert sbpc._repo_root() is None
    finally:
        os.chdir(prev)
