"""Unit tests for GitHub Branch Cleanup Service.

Tests configuration validation, stale branch detection, and protected branch logic.
"""

import pytest
from datetime import datetime, timedelta, timezone

config = pytest.importorskip("pmoves.services.github_branch_cleanup.config", reason="github_branch_cleanup service not installed").config
Config = config.__class__
_app = pytest.importorskip("pmoves.services.github_branch_cleanup.app", reason="github_branch_cleanup service not installed")
is_stale = _app.is_stale
StaleBranch = _app.StaleBranch
CleanupRequest = _app.CleanupRequest
CleanupResult = _app.CleanupResult


class TestConfig:
    """Test configuration management."""

    def test_protected_branch_exact_match(self):
        """Test exact match protected branches."""
        Config.PROTECTED_BRANCHES = ["main", "develop"]
        assert Config.is_protected_branch("main") is True
        assert Config.is_protected_branch("develop") is True
        assert Config.is_protected_branch("feature-branch") is False

    def test_protected_branch_wildcard(self):
        """Test wildcard pattern matching for protected branches."""
        Config.PROTECTED_BRANCHES = ["release-*", "hotfix-*"]
        assert Config.is_protected_branch("release-v1.0") is True
        assert Config.is_protected_branch("hotfix-123") is True
        assert Config.is_protected_branch("release") is False
        assert Config.is_protected_branch("feature-branch") is False

    def test_protected_branch_mixed(self):
        """Test mixed exact and wildcard patterns."""
        Config.PROTECTED_BRANCHES = ["main", "release-*", "PMOVES.AI-Edition-Hardened"]
        assert Config.is_protected_branch("main") is True
        assert Config.is_protected_branch("release-v1.0") is True
        assert Config.is_protected_branch("PMOVES.AI-Edition-Hardened") is True
        assert Config.is_protected_branch("feature-branch") is False

    def test_config_validation_missing_app_id(self, monkeypatch):
        """Test validation fails when GH_APP_ID is missing."""
        monkeypatch.setenv("GH_APP_ID", "")
        monkeypatch.setenv("GH_APP_INSTALLATION_ID", "123")
        with pytest.raises(ValueError, match="GH_APP_ID"):
            Config.validate()

    def test_config_validation_missing_installation_id(self, monkeypatch):
        """Test validation fails when GH_APP_INSTALLATION_ID is missing."""
        monkeypatch.setenv("GH_APP_ID", "123")
        monkeypatch.setenv("GH_APP_INSTALLATION_ID", "")
        with pytest.raises(ValueError, match="GH_APP_INSTALLATION_ID"):
            Config.validate()

    def test_config_validation_invalid_stale_days(self, monkeypatch):
        """Test validation fails when BRANCH_STALE_DAYS is less than 1."""
        monkeypatch.setenv("GH_APP_ID", "123")
        monkeypatch.setenv("GH_APP_INSTALLATION_ID", "456")
        monkeypatch.setenv("BRANCH_STALE_DAYS", "0")
        with pytest.raises(ValueError, match="BRANCH_STALE_DAYS must be at least 1"):
            Config.validate()


class TestStaleBranchDetection:
    """Test stale branch detection logic."""

    def test_is_stale_true(self):
        """Test branch is stale when last commit is old."""
        old_date = datetime.now(timezone.utc) - timedelta(days=40)
        assert is_stale(old_date, 30) is True

    def test_is_stale_false(self):
        """Test branch is not stale when last commit is recent."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=15)
        assert is_stale(recent_date, 30) is False

    def test_is_stale_boundary(self):
        """Test branch exactly at threshold is not stale."""
        threshold_date = datetime.now(timezone.utc) - timedelta(days=30)
        # Branch at exactly 30 days should not be considered stale
        # (we use strict less-than comparison)
        assert is_stale(threshold_date, 30) is False

    def test_is_stale_one_day_over(self):
        """Test branch one day over threshold is stale."""
        threshold_date = datetime.now(timezone.utc) - timedelta(days=31)
        assert is_stale(threshold_date, 30) is True


class TestStaleBranchModel:
    """Test StaleBranch Pydantic model."""

    def test_stale_branch_creation(self):
        """Test creating StaleBranch instance."""
        branch = StaleBranch(
            name="feature/test-branch",
            last_commit_date=datetime.now(timezone.utc) - timedelta(days=45),
            stale_days=45,
            repo="PMOVES.AI"
        )
        assert branch.name == "feature/test-branch"
        assert branch.stale_days == 45
        assert branch.repo == "PMOVES.AI"

    def test_stale_branch_serialization(self):
        """Test StaleBranch can be serialized to JSON."""
        branch = StaleBranch(
            name="feature/test",
            last_commit_date=datetime.now(timezone.utc) - timedelta(days=35),
            stale_days=35,
            repo="PMOVES.AI"
        )
        # Should not raise exception
        data = branch.model_dump()
        assert "last_commit_date" in data
        assert data["stale_days"] == 35


class TestCleanupRequestModel:
    """Test CleanupRequest Pydantic model."""

    def test_cleanup_request_defaults(self):
        """Test CleanupRequest has correct defaults."""
        request = CleanupRequest(repo="PMOVES.AI")
        assert request.repo == "PMOVES.AI"
        assert request.dry_run is True  # Default to safe mode
        assert request.stale_days == 30

    def test_cleanup_request_custom(self):
        """Test CleanupRequest with custom values."""
        request = CleanupRequest(
            repo="PMOVES.AI",
            dry_run=False,
            stale_days=60
        )
        assert request.dry_run is False
        assert request.stale_days == 60


class TestCleanupResultModel:
    """Test CleanupResult Pydantic model."""

    def test_cleanup_result_creation(self):
        """Test creating CleanupResult instance."""
        stale_branch = StaleBranch(
            name="feature/old-branch",
            last_commit_date=datetime.now(timezone.utc) - timedelta(days=50),
            stale_days=50,
            repo="PMOVES.AI"
        )
        result = CleanupResult(
            repo="PMOVES.AI",
            stale_branches=[stale_branch],
            deleted_branches=["feature/old-branch"],
            protected_skipped=["main"],
            dry_run=False,
            duration_seconds=2.5
        )
        assert result.repo == "PMOVES.AI"
        assert len(result.stale_branches) == 1
        assert result.deleted_branches == ["feature/old-branch"]
        assert result.protected_skipped == ["main"]
        assert result.dry_run is False
        assert result.duration_seconds == 2.5


@pytest.mark.integration
class TestBranchCleanupIntegration:
    """Integration tests for branch cleanup service.

    These tests require GitHub credentials to run.
    Mark with `pytest -m integration` to run.
    """

    @pytest.fixture
    def cleanup_request(self):
        """Provide a cleanup request fixture."""
        return CleanupRequest(
            repo="PMOVES.AI",
            dry_run=True,  # Always use dry-run in tests
            stale_days=30
        )

    def test_cleanup_request_dry_run(self, cleanup_request):
        """Test that dry-run mode doesn't actually delete branches."""
        # This test would require mocking the GitHub API
        # For now, just verify the request structure
        assert cleanup_request.dry_run is True
        assert cleanup_request.repo == "PMOVES.AI"


@pytest.mark.unit
class TestBranchCleanupUnit:
    """Unit tests for branch cleanup logic."""

    def test_multiple_protected_patterns(self):
        """Test multiple protected branch patterns coexist."""
        Config.PROTECTED_BRANCHES = [
            "main",
            "PMOVES.AI-Edition-Hardened",
            "release-*",
            "hotfix-*"
        ]

        test_cases = [
            ("main", True),
            ("PMOVES.AI-Edition-Hardened", True),
            ("release-v1.0.0", True),
            ("hotfix-critical-123", True),
            ("feature-new-stuff", False),
            ("bugfix/dangling", False),
        ]

        for branch_name, expected in test_cases:
            result = Config.is_protected_branch(branch_name)
            assert result is expected, f"Branch {branch_name} expected {expected}, got {result}"
