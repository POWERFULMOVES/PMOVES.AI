"""
PMOVES Health/Wealth Integrations Tests

Tests the external service integrations:
- Jellyfin (Media server)
- Firefly III (Finance/Wealth management)
- wger (Health/Fitness tracking)
- Open Notebook (Knowledge base)

TAC Worktree: tac-6-pmoves-integrations
Branch: feature/pmoves-integrations-tests
"""

import os
import pytest
import httpx
from typing import Any, Dict

# Service URLs from environment or defaults
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://localhost:8096")
FIREFLY_URL = os.getenv("FIREFLY_URL", "http://localhost:8082")
WGER_URL = os.getenv("WGER_URL", "http://localhost:8002")
OPEN_NOTEBOOK_URL = os.getenv("OPEN_NOTEBOOK_URL", "http://localhost:5055")

# API Keys from environment
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "")
FIREFLY_ACCESS_TOKEN = os.getenv("FIREFLY_ACCESS_TOKEN", "")
WGER_API_TOKEN = os.getenv("WGER_API_TOKEN", "")


@pytest.fixture
def jellyfin_client():
    """Create HTTP client for Jellyfin API."""
    headers = {}
    if JELLYFIN_API_KEY:
        headers["X-Emby-Token"] = JELLYFIN_API_KEY
    return httpx.Client(base_url=JELLYFIN_URL, headers=headers, timeout=30.0)


@pytest.fixture
def firefly_client():
    """Create HTTP client for Firefly III API."""
    headers = {"Accept": "application/json"}
    if FIREFLY_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {FIREFLY_ACCESS_TOKEN}"
    return httpx.Client(base_url=FIREFLY_URL, headers=headers, timeout=30.0)


@pytest.fixture
def wger_client():
    """Create HTTP client for wger API."""
    headers = {"Accept": "application/json"}
    if WGER_API_TOKEN:
        headers["Authorization"] = f"Token {WGER_API_TOKEN}"
    return httpx.Client(base_url=WGER_URL, headers=headers, timeout=30.0)


@pytest.fixture
def open_notebook_client():
    """Create HTTP client for Open Notebook API."""
    return httpx.Client(base_url=OPEN_NOTEBOOK_URL, timeout=30.0)


class TestJellyfinIntegration:
    """Test Jellyfin media server integration."""

    def test_jellyfin_health(self, jellyfin_client):
        """Verify Jellyfin is healthy."""
        response = jellyfin_client.get("/health")
        assert response.status_code == 200
        assert response.text == "Healthy"

    def test_jellyfin_system_info(self, jellyfin_client):
        """Verify Jellyfin system info is accessible."""
        response = jellyfin_client.get("/System/Info/Public")
        assert response.status_code == 200
        data = response.json()
        assert "ServerName" in data
        assert "Version" in data

    @pytest.mark.skipif(not JELLYFIN_API_KEY, reason="JELLYFIN_API_KEY not set")
    def test_jellyfin_authenticated_access(self, jellyfin_client):
        """Verify authenticated access to Jellyfin."""
        response = jellyfin_client.get("/System/Info")
        assert response.status_code == 200
        data = response.json()
        assert "Id" in data

    @pytest.mark.skipif(not JELLYFIN_API_KEY, reason="JELLYFIN_API_KEY not set")
    def test_jellyfin_libraries(self, jellyfin_client):
        """Verify Jellyfin libraries are accessible."""
        response = jellyfin_client.get("/Library/VirtualFolders")
        assert response.status_code == 200
        # Should return a list (may be empty)
        assert isinstance(response.json(), list)


class TestFireflyIntegration:
    """Test Firefly III finance integration."""

    def test_firefly_health(self, firefly_client):
        """Verify Firefly III is healthy."""
        response = firefly_client.get("/health")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_firefly_about(self, firefly_client):
        """Verify Firefly III API is accessible."""
        response = firefly_client.get("/api/v1/about")
        if response.status_code == 401:
            pytest.skip("Firefly API requires authentication - token may be expired")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "version" in data["data"]

    def test_firefly_user_info(self, firefly_client):
        """Verify authenticated user access."""
        response = firefly_client.get("/api/v1/about/user")
        if response.status_code == 401:
            pytest.skip("Firefly API requires authentication - token may be expired")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "attributes" in data["data"]

    def test_firefly_accounts(self, firefly_client):
        """Verify accounts endpoint is accessible."""
        response = firefly_client.get("/api/v1/accounts")
        if response.status_code == 401:
            pytest.skip("Firefly API requires authentication - token may be expired")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)


class TestWgerIntegration:
    """Test wger health/fitness integration."""

    def test_wger_accessible(self, wger_client):
        """Verify wger is accessible (may redirect to login)."""
        response = wger_client.get("/", follow_redirects=True)
        # Accept 200 or 302 redirect (to login page)
        assert response.status_code in [200, 302]

    def test_wger_api_info(self, wger_client):
        """Verify wger API is accessible."""
        response = wger_client.get("/api/v2/")
        if response.status_code == 403:
            pytest.skip("wger API requires authentication")
        assert response.status_code == 200
        data = response.json()
        # Should have API endpoints listed
        assert isinstance(data, dict)

    def test_wger_exercises(self, wger_client):
        """Verify exercises endpoint is accessible."""
        response = wger_client.get("/api/v2/exercise/")
        if response.status_code == 403:
            pytest.skip("wger API requires authentication for exercises")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_wger_muscles(self, wger_client):
        """Verify muscles endpoint is accessible."""
        response = wger_client.get("/api/v2/muscle/")
        if response.status_code == 403:
            pytest.skip("wger API requires authentication for muscles")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


class TestOpenNotebookIntegration:
    """Test Open Notebook knowledge base integration."""

    def test_open_notebook_health(self, open_notebook_client):
        """Verify Open Notebook is healthy."""
        response = open_notebook_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "running" in data["message"].lower()

    def test_open_notebook_api(self, open_notebook_client):
        """Verify Open Notebook API endpoints."""
        # Check if notebooks endpoint exists
        response = open_notebook_client.get("/api/notebooks")
        # May return 200 or require auth
        assert response.status_code in [200, 401, 403]


class TestArchonUIIntegration:
    """Test Archon UI integration."""

    def test_archon_ui_accessible(self):
        """Verify Archon UI is accessible."""
        client = httpx.Client(base_url="http://localhost:3737", timeout=30.0)
        response = client.get("/")
        assert response.status_code == 200

    def test_archon_api_proxy(self):
        """Verify Archon UI can proxy to API."""
        client = httpx.Client(base_url="http://localhost:3737", timeout=30.0)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestSupabaseBootUser:
    """Test Supabase boot user configuration."""

    def test_supabase_reachable(self):
        """Verify Supabase is reachable."""
        client = httpx.Client(timeout=30.0)
        response = client.get("http://localhost:65421/rest/v1/")
        # Should return some response (may be auth error)
        assert response.status_code in [200, 400, 401]

    def test_supabase_kong_health(self):
        """Verify Supabase Kong gateway is healthy."""
        client = httpx.Client(timeout=30.0)
        # Kong doesn't have a /health endpoint, check if it responds
        response = client.get("http://localhost:65421/")
        # Kong returns 404 for root but that means it's running
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
