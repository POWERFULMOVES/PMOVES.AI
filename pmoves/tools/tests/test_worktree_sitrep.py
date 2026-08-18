"""Regression net for worktree_sitrep's classifier.

Every case builds a REAL git repo in a temp dir and runs classify() against it.
Reasoning from the source is what produced the bugs these tests pin: the first
revision of this tool reported `clean` for an unreadable worktree, for an
untracked-only worktree, and for a staged `git rm` — three separate ways for the
"authoritative" gate to pass on something that was not clean.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "worktree_sitrep.py"


def _load():
    spec = importlib.util.spec_from_file_location("worktree_sitrep", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["worktree_sitrep"] = mod
    spec.loader.exec_module(mod)
    return mod


ws = _load()


def _run(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, check=False)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _run(["init", "-q"], r)
    _run(["config", "user.email", "t@t"], r)
    _run(["config", "user.name", "t"], r)
    (r / "keep.py").write_text("x\n", encoding="utf-8")
    (r / "old.py").write_text("y\n", encoding="utf-8")
    _run(["add", "-A"], r)
    _run(["commit", "-qm", "init"], r)
    return r


def test_clean_repo_is_clean(repo: Path):
    assert ws.classify(repo, set())["state"] == "clean"


def test_unreadable_worktree_is_unknown_not_clean(tmp_path: Path):
    """A non-git directory cannot be verified. It must NOT read as clean.

    The first revision collapsed every git failure into "" and fell through to
    clean, so an unreadable or timed-out worktree PASSED the strict gate.
    """
    d = tmp_path / "notarepo"
    d.mkdir()
    info = ws.classify(d, set())
    assert info["state"] == "unknown", info
    assert info["note"], "an unverifiable worktree must say why"


def test_missing_directory_is_missing(tmp_path: Path):
    assert ws.classify(tmp_path / "nope", set())["state"] == "missing"


def test_staged_deletion_is_dirty_not_husk(repo: Path):
    """`git rm` stages a deletion (D ). An emptied directory leaves the index
    alone ( D). Treating both as husks let real staged deletions pass strict."""
    _run(["rm", "-q", "old.py"], repo)
    info = ws.classify(repo, set())
    assert info["state"] == "dirty", info
    assert info["staged"] == 1
    assert info["worktree_deleted"] == 0


def test_emptied_directory_is_husk(repo: Path):
    for f in repo.glob("*.py"):
        f.unlink()
    info = ws.classify(repo, set())
    assert info["state"] == "husk", info
    assert info["worktree_deleted"] == 2
    assert info["staged"] == 0


def test_untracked_only_is_reported_not_silently_clean(repo: Path):
    (repo / "scratch.txt").write_text("z", encoding="utf-8")
    info = ws.classify(repo, set())
    assert info["state"] == "untracked-only", info
    assert info["untracked"] == 1


def test_untracked_is_not_counted_as_submodule_drift(repo: Path):
    """The first revision derived drift by subtracting two status calls, so an
    untracked file in a repo with ZERO submodules reported submodule_drift=1."""
    (repo / "scratch.txt").write_text("z", encoding="utf-8")
    assert ws.classify(repo, set())["submodule_drift"] == 0


def test_modified_tracked_file_is_dirty(repo: Path):
    (repo / "keep.py").write_text("changed\n", encoding="utf-8")
    info = ws.classify(repo, set())
    assert info["state"] == "dirty"
    assert info["modified"] == 1


def test_git_helper_returns_none_on_failure_not_empty_string(tmp_path: Path):
    """None (could not measure) must stay distinguishable from "" (measured,
    empty). Conflating them is the root of the clean-on-failure bug."""
    assert ws._git(["status", "--porcelain"], cwd=tmp_path) is None
