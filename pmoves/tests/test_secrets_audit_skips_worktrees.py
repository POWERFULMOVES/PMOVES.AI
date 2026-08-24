"""The secrets audit must not walk linked-worktree repo copies.

Behavioural test: it builds a real directory tree and calls candidate_files(),
rather than restating the exclusion expression. A test that re-implemented the
`parts` check would keep passing if the real check were deleted.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOL = _REPO_ROOT / "pmoves" / "tools" / "secrets_hardening_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("secrets_hardening_audit", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["secrets_hardening_audit"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit(tmp_path, monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    return module


def _touch(root: Path, rel: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "worktree_rel",
    [
        # The layout actually in use — 190 repo copies live here, and it was the
        # one the exclusion missed.
        ".worktrees/some-branch/pmoves/tools/thing.py",
        # The layout the original exclusion covered.
        ".claude/worktrees/other-branch/pmoves/tools/thing.py",
    ],
)
def test_worktree_copies_are_not_audited(audit, tmp_path, worktree_rel):
    owned = _touch(tmp_path, "pmoves/tools/thing.py")
    copy = _touch(tmp_path, worktree_rel)

    found = set(audit.candidate_files())

    assert owned in found, "the checkout's own file must still be audited"
    assert copy not in found, (
        f"{worktree_rel} is a linked-worktree repo copy; auditing it double-counts "
        "every finding and buries the real ones"
    )


def test_a_normal_path_containing_worktree_like_names_is_still_audited(audit, tmp_path):
    """The exclusion must not become a blind spot for genuinely-owned files."""
    # `.claude` and `worktrees` present but NOT adjacent in that order.
    owned = _touch(tmp_path, "pmoves/worktrees/docs/.claude/notes.md")
    found = set(audit.candidate_files())
    assert owned in found
