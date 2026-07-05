"""Unit tests for the §9.4 GitHub Actions shim (.github/scripts/branch_trail_ci.py).

Tests the pure-function event parser in isolation — does not touch NATS
or any external service.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load the shim by path since `.github/scripts/` is not a Python package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SHIM_PATH = _REPO_ROOT / ".github" / "scripts" / "branch_trail_ci.py"


def _load_shim():
    spec = importlib.util.spec_from_file_location("branch_trail_ci", _SHIM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def shim():
    return _load_shim()


REPO = "POWERFULMOVES/PMOVES.AI"


class TestPushEvent:
    def test_push_to_new_branch_emits_create(self, shim):
        result = shim.parse_github_event(
            event_name="push",
            event_data={
                "before": "0" * 40,
                "after": "deadbeef" * 5,
                "head_commit": {"author": {"name": "DARKXSIDE"}},
            },
            ref="refs/heads/feat/9-4-e2e",
            sha="deadbeef" * 5,
            repository=REPO,
        )
        assert result is not None
        assert result["event"] == "create"
        assert result["branch"] == "feat/9-4-e2e"
        assert result["committer"] == "DARKXSIDE"

    def test_push_to_existing_branch_skips(self, shim):
        result = shim.parse_github_event(
            event_name="push",
            event_data={"before": "abc123", "after": "def456"},
            ref="refs/heads/feat/foo",
            sha="def456",
            repository=REPO,
        )
        assert result is None

    def test_push_to_main_skips_even_if_new(self, shim):
        result = shim.parse_github_event(
            event_name="push",
            event_data={"before": "0" * 40},
            ref="refs/heads/main",
            sha="abc",
            repository=REPO,
        )
        assert result is None

    def test_push_falls_back_to_pusher_when_no_author(self, shim):
        result = shim.parse_github_event(
            event_name="push",
            event_data={
                "before": "0" * 40,
                "pusher": {"name": "darkxside-fallback"},
            },
            ref="refs/heads/feat/x",
            sha="aaa",
            repository=REPO,
        )
        assert result is not None
        assert result["committer"] == "darkxside-fallback"


class TestPullRequestEvent:
    def test_opened_emits_link_pr(self, shim):
        result = shim.parse_github_event(
            event_name="pull_request",
            event_data={
                "action": "opened",
                "pull_request": {
                    "number": 1462,
                    "head": {"ref": "feat/9-4-e2e", "sha": "cafebabe" * 5},
                    "user": {"login": "DARKXSIDE"},
                },
            },
            ref="refs/pull/1462/merge",
            sha="cafebabe" * 5,
            repository=REPO,
        )
        assert result is not None
        assert result["event"] == "link_pr"
        assert result["branch"] == "feat/9-4-e2e"
        assert result["pr_url"] == "https://github.com/POWERFULMOVES/PMOVES.AI/pull/1462"
        assert result["committer"] == "DARKXSIDE"

    def test_closed_and_merged_emits_merge(self, shim):
        result = shim.parse_github_event(
            event_name="pull_request",
            event_data={
                "action": "closed",
                "pull_request": {
                    "number": 1462,
                    "merged": True,
                    "merged_by": {"login": "merger-bot"},
                    "merge_commit_sha": "feedface" * 5,
                    "head": {"ref": "feat/9-4-e2e", "sha": "cafebabe" * 5},
                    "user": {"login": "DARKXSIDE"},
                },
            },
            ref="refs/pull/1462/merge",
            sha="feedface" * 5,
            repository=REPO,
        )
        assert result is not None
        assert result["event"] == "merge"
        assert result["sha"] == "feedface" * 5
        assert result["committer"] == "merger-bot"

    def test_closed_without_merge_skips(self, shim):
        result = shim.parse_github_event(
            event_name="pull_request",
            event_data={
                "action": "closed",
                "pull_request": {
                    "number": 99,
                    "merged": False,
                    "head": {"ref": "feat/foo", "sha": "abc"},
                },
            },
            ref="refs/pull/99/merge",
            sha="abc",
            repository=REPO,
        )
        assert result is None

    def test_other_actions_skip(self, shim):
        for action in ["reopened", "synchronize", "labeled", "ready_for_review"]:
            result = shim.parse_github_event(
                event_name="pull_request",
                event_data={
                    "action": action,
                    "pull_request": {"head": {"ref": "feat/x"}, "number": 1},
                },
                ref="refs/pull/1/merge",
                sha="abc",
                repository=REPO,
            )
            assert result is None, f"action={action} should skip"


class TestDeleteEvent:
    def test_branch_delete_emits_delete(self, shim):
        result = shim.parse_github_event(
            event_name="delete",
            event_data={
                "ref": "feat/9-4-e2e",
                "ref_type": "branch",
                "sender": {"login": "darkxside"},
            },
            ref="refs/heads/feat/9-4-e2e",
            sha="",
            repository=REPO,
        )
        assert result is not None
        assert result["event"] == "delete"
        assert result["branch"] == "feat/9-4-e2e"
        assert result["committer"] == "darkxside"

    def test_tag_delete_skips(self, shim):
        result = shim.parse_github_event(
            event_name="delete",
            event_data={"ref": "v1.0.0", "ref_type": "tag"},
            ref="",
            sha="",
            repository=REPO,
        )
        assert result is None

    def test_main_delete_skips(self, shim):
        result = shim.parse_github_event(
            event_name="delete",
            event_data={"ref": "main", "ref_type": "branch"},
            ref="",
            sha="",
            repository=REPO,
        )
        assert result is None


class TestUnknownEvent:
    def test_workflow_dispatch_skips(self, shim):
        assert shim.parse_github_event(
            event_name="workflow_dispatch",
            event_data={},
            ref="refs/heads/main",
            sha="",
            repository=REPO,
        ) is None


class TestRefStripping:
    def test_strip_refs_heads(self, shim):
        assert shim._strip_refs_heads("refs/heads/feat/foo") == "feat/foo"
        assert shim._strip_refs_heads("feat/foo") == "feat/foo"
        assert shim._strip_refs_heads("refs/heads/main") == "main"


class TestConstants:
    def test_ci_agent_id(self, shim):
        assert shim.CI_AGENT_ID == "pmoves-ci-bot"

    def test_zero_sha_is_40_zeros(self, shim):
        assert shim.ZERO_SHA == "0" * 40
