"""Tests for github_pool_sync -- the 3-surface normalizer.

The founding case is PR #3025 (measured 2026-09-12): both review endpoints
returned EMPTY while an APPROVE and a post-merge REQUEST_CHANGES sat as
issue comments posted by github-actions[bot] on behalf of the kilocode
fleet-review lane. An agent greping reviews saw a confident zero. These
tests pin that the normalizer cannot be fooled the same way.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "github_pool_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("github_pool_sync", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _load()


PR = {"number": 3025, "title": "fix(compose): cross-overlay deps",
      "user": {"login": "POWERFULMOVES"}, "mergeable": True}


def _fleet_comment(verdict_text: str) -> dict:
    return {"user": {"login": "github-actions[bot]"},
            "created_at": "2026-09-11T07:51:23Z",
            "html_url": "https://example/c2",
            "body": "## Fleet review: kilocode\n...\n**3. VERDICT: "
                    + verdict_text + "**\n..."}


def test_the_3025_shape_fleet_request_changes_is_seen(mod):
    """Empty review endpoints + bot issue comment carrying REQUEST_CHANGES
    must surface as changes_requested=True -- the exact miss that founded
    this tool."""
    rec = mod.normalize_surfaces(PR, [], [], [_fleet_comment("REQUEST_CHANGES")])
    assert rec["signals"]["changes_requested"] is True
    assert rec["signals"]["fleet_reviews"] == 1
    assert "CHANGES_REQUESTED stands" in mod.triage(rec)


def test_fleet_approve_is_seen(mod):
    rec = mod.normalize_surfaces(PR, [], [], [_fleet_comment("APPROVE")])
    assert rec["signals"]["approved"] is True
    assert rec["signals"]["changes_requested"] is False


def test_bot_comment_without_marker_is_not_fleet(mod):
    rec = mod.normalize_surfaces(PR, [], [], [{
        "user": {"login": "github-actions[bot]"},
        "created_at": "t", "html_url": "u", "body": "## Docker Hardening"}])
    assert rec["signals"]["fleet_reviews"] == 0


def test_review_endpoint_state_still_counts(mod):
    rec = mod.normalize_surfaces(PR, [{
        "user": {"login": "x"}, "state": "CHANGES_REQUESTED",
        "submitted_at": "t", "html_url": "u"}], [], [])
    assert rec["signals"]["changes_requested"] is True


def test_no_signal_at_all_is_loud(mod):
    rec = mod.normalize_surfaces(PR, [], [], [])
    assert "NO SIGNAL AT ALL" in mod.triage(rec)


def test_both_verdicts_changes_wins(mod):
    """APPROVE then a later REQUEST_CHANGES: the pool must not average
    verdicts -- changes_requested stands."""
    rec = mod.normalize_surfaces(
        PR, [], [],
        [_fleet_comment("APPROVE"), _fleet_comment("REQUEST_CHANGES")])
    assert rec["signals"]["approved"] is True
    assert rec["signals"]["changes_requested"] is True


def test_surface_counts_reported_with_verdict(mod):
    """Denominators ride with every verdict (empty-is-not-evidence)."""
    rec = mod.normalize_surfaces(PR, [], [], [_fleet_comment("REQUEST_CHANGES")])
    assert rec["surfaces"] == {"reviews": 0, "inline": 0, "issue_comments": 1}
