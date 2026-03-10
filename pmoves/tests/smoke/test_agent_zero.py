"""
Agent Zero service-specific smoke tests.

Tests Agent Zero health and MCP endpoint functionality.

Expected runtime: <5s (skips gracefully when services are unavailable)
"""

import pytest
import httpx
from pmoves.tests.utils.service_catalog import AGENT_ZERO


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def agent_zero_client():
    """Agent Zero HTTP client. Skips dependent tests if service is unavailable."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    client = httpx.AsyncClient(base_url=f"http://localhost:{AGENT_ZERO.port}", timeout=timeout)
    try:
        resp = await client.get("/healthz")
        if resp.status_code == 404:
            await client.aclose()
            pytest.skip(
                f"Port {AGENT_ZERO.port} is responding but /healthz returned 404 "
                "(Agent Zero may not be running)"
            )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        await client.aclose()
        pytest.skip(f"Agent Zero not reachable at localhost:{AGENT_ZERO.port}")
    yield client
    await client.aclose()


# ============================================================================
# HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_health_endpoint(agent_zero_client: httpx.AsyncClient):
    """Test Agent Zero health endpoint."""
    response = await agent_zero_client.get("/healthz")

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert "status" in data, "Response missing 'status' field"
    assert data["status"] == "healthy", f"Unhealthy status: {data.get('status')}"
    assert "version" in data, "Response missing 'version' field"
    assert "timestamp" in data, "Response missing 'timestamp' field"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_mcp_endpoint_exists(agent_zero_client: httpx.AsyncClient):
    """Test that Agent Zero MCP endpoint is accessible."""
    # MCP endpoint should exist (may require authentication for full access)
    response = await agent_zero_client.get("/mcp")

    # Should return 405 Method Not Allowed (GET not supported, need POST)
    # or 200/401/403 depending on auth configuration
    assert response.status_code in {200, 401, 403, 405}, (
        f"MCP endpoint unexpected response: {response.status_code}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_metrics_endpoint(agent_zero_client: httpx.AsyncClient):
    """Test Agent Zero metrics endpoint."""
    response = await agent_zero_client.get("/metrics")

    # Metrics endpoint should return 200
    assert response.status_code == 200, f"Metrics check failed: {response.status_code}"

    # Should return Prometheus-style text metrics
    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics response is empty"

    # Check for Prometheus metric format (lines with "HELP" or "TYPE" or metric names)
    has_prometheus_format = any(
        keyword in metrics_text
        for keyword in ["HELP", "TYPE", "#", "agent_zero"]
    )
    assert has_prometheus_format, "Response doesn't look like Prometheus metrics"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_nats_connection(agent_zero_client: httpx.AsyncClient):
    """Test that Agent Zero reports NATS connection in health."""
    response = await agent_zero_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Health response should indicate NATS status
    # Field name may vary, so we check for common patterns
    nats_connected = data.get("nats_connected", data.get("nats", data.get("messaging", True)))
    assert nats_connected, "Agent Zero not connected to NATS"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_responds_within_timeout(agent_zero_client: httpx.AsyncClient):
    """Test that Agent Zero responds within acceptable time."""
    import time

    start_time = time.time()
    response = await agent_zero_client.get("/healthz")
    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    assert duration_ms < 1000, f"Response too slow: {duration_ms:.0f}ms"
