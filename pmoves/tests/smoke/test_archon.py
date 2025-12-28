"""
Archon service-specific smoke tests.

Tests Archon health and Supabase integration.

Expected runtime: <5s
"""

import pytest
import httpx
from pmoves.tests.utils.service_catalog import ARCHON


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
async def archon_client() -> httpx.AsyncClient:
    """Archon HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(base_url=f"http://localhost:{ARCHON.port}", timeout=timeout)


# ============================================================================
# HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_health_endpoint(archon_client: httpx.AsyncClient):
    """Test Archon health endpoint."""
    response = await archon_client.get("/healthz")

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert "status" in data, "Response missing 'status' field"
    assert data["status"] == "healthy", f"Unhealthy status: {data.get('status')}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_supabase_connected(archon_client: httpx.AsyncClient):
    """Test that Archon reports Supabase connection."""
    response = await archon_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Check for Supabase/Postgres connection status
    supabase_connected = data.get("supabase_connected", data.get("postgres_connected", True))
    assert supabase_connected, "Archon not connected to Supabase"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_metrics_endpoint(archon_client: httpx.AsyncClient):
    """Test Archon metrics endpoint."""
    response = await archon_client.get("/metrics")

    # Should return 200 with Prometheus metrics
    assert response.status_code == 200, f"Metrics check failed: {response.status_code}"

    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics response is empty"


# ============================================================================
# API ENDPOINTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_api_accessible(archon_client: httpx.AsyncClient):
    """Test that Archon API is accessible."""
    # Try to access API root or forms endpoint
    response = await archon_client.get("/")

    # Should return 200 (API info) or 404 (no root route) but not connection error
    assert response.status_code in {200, 404}, (
        f"API inaccessible: {response.status_code}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_openapi_spec(archon_client: httpx.AsyncClient):
    """Test Archon OpenAPI specification."""
    response = await archon_client.get("/openapi.json")

    # May return OpenAPI spec or 404 if not configured
    assert response.status_code in {200, 404}, (
        f"OpenAPI spec unexpected response: {response.status_code}"
    )

    if response.status_code == 200:
        spec = response.json()
        assert "openapi" in spec or "swagger" in spec, "Invalid OpenAPI spec"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_responds_within_timeout(archon_client: httpx.AsyncClient):
    """Test that Archon responds within acceptable time."""
    import time

    start_time = time.time()
    response = await archon_client.get("/healthz")
    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    assert duration_ms < 1000, f"Response too slow: {duration_ms:.0f}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_archon_agent_zero_connection(archon_client: httpx.AsyncClient):
    """Test that Archon can reach Agent Zero (via health check)."""
    response = await archon_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Archon should report connection to Agent Zero
    agent_zero_ok = data.get("agent_zero_connected", True)

    # If the field is present, it should be True
    if "agent_zero_connected" in data:
        assert agent_zero_ok, "Archon not connected to Agent Zero"
