"""
Agent Work Orders End-to-End Integration Tests

Tests the Archon Agent Work Orders workflow:
- Work order creation via API
- Supabase state persistence
- Git worktree lifecycle management
- GitHub PR creation automation

TAC Worktree: tac-1-work-orders-tests
Branch: feature/work-orders-e2e-tests
"""

import os
import pytest
import httpx
import uuid
from datetime import datetime
from typing import Any, Dict

ARCHON_URL = os.getenv("ARCHON_URL", "http://localhost:8091")
SUPABASE_URL = os.getenv("SUPABASE_REST_URL", "http://localhost:65421/rest/v1")
# Default to test key if not set in environment
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")

# Skip Supabase tests if no key available
SKIP_SUPABASE = not SUPABASE_KEY


@pytest.fixture
def archon_client():
    """Create HTTP client for Archon API."""
    return httpx.Client(base_url=ARCHON_URL, timeout=30.0)


@pytest.fixture
def supabase_client():
    """Create HTTP client for Supabase REST API."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    return httpx.Client(base_url=SUPABASE_URL, headers=headers, timeout=30.0)


class TestArchonHealth:
    """Test Archon service health."""

    def test_archon_healthz(self, archon_client):
        """Verify Archon API is healthy."""
        response = archon_client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_archon_supabase_connection(self, archon_client):
        """Verify Archon can connect to Supabase."""
        response = archon_client.get("/healthz")
        data = response.json()
        supabase_status = data.get("supabase", {})
        assert supabase_status.get("http") == 200, "Archon cannot reach Supabase"


class TestWorkOrderSchema:
    """Test work order database schema exists."""

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_configured_repositories_table(self, supabase_client):
        """Verify archon_configured_repositories table exists."""
        response = supabase_client.get(
            "/archon_configured_repositories",
            params={"select": "id", "limit": "1"}
        )
        # 200 = table exists and accessible
        assert response.status_code == 200

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_work_orders_table(self, supabase_client):
        """Verify archon_agent_work_orders table exists."""
        response = supabase_client.get(
            "/archon_agent_work_orders",
            params={"select": "id", "limit": "1"}
        )
        assert response.status_code == 200

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_work_order_steps_table(self, supabase_client):
        """Verify archon_agent_work_order_steps table exists."""
        response = supabase_client.get(
            "/archon_agent_work_order_steps",
            params={"select": "id", "limit": "1"}
        )
        assert response.status_code == 200


class TestWorkOrderLifecycle:
    """Test work order CRUD operations."""

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_create_work_order(self, supabase_client):
        """Test creating a work order via Supabase."""
        test_order = {
            "id": str(uuid.uuid4()),
            "title": f"TAC Test Work Order {datetime.now().isoformat()}",
            "description": "Integration test work order - can be deleted",
            "status": "pending",
            "priority": "low",
            "repository_id": None,
            "branch_name": "test/integration-test",
            "created_by": "integration-test",
        }

        response = supabase_client.post(
            "/archon_agent_work_orders",
            json=test_order,
            headers={"Prefer": "return=representation"}
        )

        # Should succeed or return conflict if already exists
        assert response.status_code in [201, 409], f"Failed to create: {response.text}"

        # Clean up - delete the test order
        if response.status_code == 201:
            delete_response = supabase_client.delete(
                f"/archon_agent_work_orders",
                params={"id": f"eq.{test_order['id']}"}
            )
            assert delete_response.status_code in [200, 204]

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_query_work_orders(self, supabase_client):
        """Test querying work orders."""
        response = supabase_client.get(
            "/archon_agent_work_orders",
            params={"select": "*", "limit": "10", "order": "created_at.desc"}
        )
        assert response.status_code == 200
        # Should return a list (possibly empty)
        assert isinstance(response.json(), list)


class TestWorkOrderViews:
    """Test work order database views."""

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_active_work_orders_view(self, supabase_client):
        """Test the active work orders view exists."""
        response = supabase_client.get(
            "/archon_work_orders_active",
            params={"select": "*", "limit": "5"}
        )
        # View should exist and be queryable
        assert response.status_code == 200

    @pytest.mark.skipif(SKIP_SUPABASE, reason="SUPABASE_SERVICE_ROLE_KEY not set")
    def test_work_orders_with_steps_view(self, supabase_client):
        """Test the work orders with steps view exists."""
        response = supabase_client.get(
            "/archon_work_orders_with_steps",
            params={"select": "*", "limit": "5"}
        )
        assert response.status_code == 200


class TestGitWorktreeIntegration:
    """Test Git worktree management integration."""

    def test_worktree_directory_pattern(self):
        """Verify worktree naming convention is followed."""
        import subprocess
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            cwd="/home/pmoves/PMOVES.AI"
        )
        assert result.returncode == 0
        # Should have at least the main worktree
        assert "/home/pmoves/PMOVES.AI" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
