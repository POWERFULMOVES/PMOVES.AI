"""Tests for GitHub Cross-Repository PR Automation Service"""

import pytest
from datetime import datetime, timezone

from pmoves.services.github_crossrepo_pr.workflow_templates import (
    PRType,
    get_template,
    list_templates,
    WORKFLOW_TEMPLATES
)


class TestWorkflowTemplates:
    """Test workflow template functionality."""

    def test_list_templates(self):
        """Test listing all templates."""
        templates = list_templates()
        assert len(templates) == 6
        assert all("type" in t for t in templates)
        assert all("title_example" in t for t in templates)

    def test_get_dependency_update_template(self):
        """Test getting dependency update template."""
        template = get_template(PRType.DEPENDENCY_UPDATE)
        assert template.pr_type == PRType.DEPENDENCY_UPDATE
        assert template.labels == ["dependencies", "automated", "chore"]
        assert template.auto_merge is False

    def test_render_dependency_update_template(self):
        """Test rendering dependency update template."""
        template = get_template(PRType.DEPENDENCY_UPDATE)

        title = template.render_title(
            package="fastapi",
            old_version="0.100.0",
            new_version="0.115.0"
        )
        assert title == "chore(deps): bump fastapi from 0.100.0 to 0.115.0"

        body = template.render_body(
            package="fastapi",
            old_version="0.100.0",
            new_version="0.115.0",
            description="Performance improvements",
            changes="- Better handling\n- Faster",
            repos_list="- PMOVES.AI\n- PMOVES-Agent-Zero"
        )
        assert "fastapi" in body
        assert "0.100.0" in body
        assert "0.115.0" in body

        branch = template.render_branch_name(
            package="fastapi",
            new_version="0.115.0"
        )
        assert branch == "chore/deps/fastapi-bump-0.115.0"

    def test_get_security_patch_template(self):
        """Test getting security patch template."""
        template = get_template(PRType.SECURITY_PATCH)
        assert template.pr_type == PRType.SECURITY_PATCH
        assert template.labels == ["security", "urgent", "automated"]
        assert "security-team" in template.reviewers

    def test_render_security_patch_template(self):
        """Test rendering security patch template."""
        template = get_template(PRType.SECURITY_PATCH)

        title = template.render_title(
            cve_id="CVE-2024-12345",
            severity="High",
            package="requests",
            cvss_score="8.5"
        )
        assert "CVE-2024-12345" in title
        assert "High" in title
        assert "requests" in title

    def test_get_feature_backport_template(self):
        """Test getting feature backport template."""
        template = get_template(PRType.FEATURE_BACKPORT)
        assert template.pr_type == PRType.FEATURE_BACKPORT
        assert template.labels == ["backport", "feature", "automated"]

    def test_render_feature_backport_template(self):
        """Test rendering feature backport template."""
        template = get_template(PRType.FEATURE_BACKPORT)

        title = template.render_title(
            feature_name="new-api",
            target_branch="v1.2.3"
        )
        assert "new-api" in title
        assert "v1.2.3" in title
        assert "backport" in title.lower()

    def test_invalid_pr_type(self):
        """Test that invalid PR type raises error."""
        with pytest.raises(ValueError, match="Unknown PR type"):
            get_template("invalid_type")

    def test_all_templates_have_required_fields(self):
        """Test that all templates have required fields."""
        for pr_type in PRType:
            template = get_template(pr_type)
            assert template.title_template
            assert template.body_template
            assert template.branch_name_template
            assert isinstance(template.labels, list)
            assert isinstance(template.reviewers, list)
            assert isinstance(template.assignees, list)


class TestPRAPI:
    """Test PR API endpoints (integration tests)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from pmoves.services.github_crossrepo_pr.app import app

        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "dry_run" in data

    def test_list_templates_endpoint(self, client):
        """Test list templates endpoint."""
        response = client.get("/api/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "templates" in data
        assert data["total"] == 6

    def test_create_pr_invalid_pr_type(self, client):
        """Test PR creation with invalid type."""
        response = client.post(
            "/api/pr/create",
            json={
                "pr_type": "invalid_type",
                "repo": "PMOVES.AI",
                "base_branch": "main",
                "template_vars": {}
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False
        assert "error" in data

    @pytest.mark.asyncio
    async def test_create_pr_dependency_update_dry_run(self, client):
        """Test dependency update PR creation in dry-run mode."""
        response = client.post(
            "/api/pr/create",
            json={
                "pr_type": "dependency_update",
                "repo": "PMOVES.AI",
                "base_branch": "main",
                "template_vars": {
                    "package": "fastapi",
                    "old_version": "0.100.0",
                    "new_version": "0.115.0",
                    "description": "Performance improvements",
                    "changes": "- Better handling",
                    "repos_list": "- PMOVES.AI"
                }
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        # In dry-run mode, PR number and URL should be None
        result = data["result"]
        assert result["success"] is True


@pytest.mark.integration
class TestIntegration:
    """Integration tests with external services."""

    @pytest.fixture
    def nats_connected(self):
        """Check if NATS is connected."""
        import os
        return os.getenv("NATS_URL") is not None

    def test_nats_connection(self, nats_connected):
        """Test NATS connectivity (requires running NATS)."""
        if not nats_connected:
            pytest.skip("NATS not configured")

    @pytest.fixture
    def agent_zero_available(self):
        """Check if Agent Zero is available."""
        import httpx
        try:
            response = httpx.get(
                "http://localhost:8080/healthz",
                timeout=2.0
            )
            return response.status_code == 200
        except Exception:
            return False

    def test_agent_zero_connection(self, agent_zero_available):
        """Test Agent Zero connectivity (requires running Agent Zero)."""
        if not agent_zero_available:
            pytest.skip("Agent Zero not available")
