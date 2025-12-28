"""
TensorZero Gateway service-specific smoke tests.

Tests TensorZero Gateway health and ClickHouse integration.

Expected runtime: <5s
"""

import pytest
import httpx
from pmoves.tests.utils.service_catalog import TENSORZERO_GATEWAY, TENSORZERO_CLICKHOUSE


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
async def tensorzero_client() -> httpx.AsyncClient:
    """TensorZero Gateway HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(
        base_url=f"http://localhost:{TENSORZERO_GATEWAY.port}",
        timeout=timeout
    )


@pytest.fixture(scope="session")
async def clickhouse_client() -> httpx.AsyncClient:
    """TensorZero ClickHouse HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(
        base_url=f"http://localhost:{TENSORZERO_CLICKHOUSE.port}",
        timeout=timeout
    )


# ============================================================================
# HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_health_endpoint(tensorzero_client: httpx.AsyncClient):
    """Test TensorZero Gateway health endpoint."""
    response = await tensorzero_client.get("/healthz")

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert "status" in data, "Response missing 'status' field"
    assert data["status"] == "healthy", f"Unhealthy status: {data.get('status')}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_clickhouse_connected(tensorzero_client: httpx.AsyncClient):
    """Test that TensorZero reports ClickHouse connection."""
    response = await tensorzero_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Check for ClickHouse connection status
    clickhouse_connected = data.get("clickhouse_connected", False)
    assert clickhouse_connected, "TensorZero not connected to ClickHouse"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_api_versions(tensorzero_client: httpx.AsyncClient):
    """Test TensorZero API version endpoints."""
    # Check OpenAPI spec
    response = await tensorzero_client.get("/openapi.json")

    assert response.status_code == 200, f"OpenAPI spec failed: {response.status_code}"

    spec = response.json()
    assert "openapi" in spec, "OpenAPI spec missing version"
    assert "info" in spec, "OpenAPI spec missing info"


# ============================================================================
# CLICKHOUSE TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_clickhouse_ping_endpoint(clickhouse_client: httpx.AsyncClient):
    """Test ClickHouse ping endpoint."""
    response = await clickhouse_client.get("/ping")

    assert response.status_code == 200, f"ClickHouse ping failed: {response.status_code}"

    # ClickHouse ping returns "Ok.\n" text
    assert response.text.strip().startswith("Ok"), f"Unexpected ping response: {response.text}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_clickhouse_metrics_accessible(clickhouse_client: httpx.AsyncClient):
    """Test that ClickHouse metrics are accessible."""
    response = await clickhouse_client.get("/metrics")

    # May return 401 if auth required, or 200 with metrics
    assert response.status_code in {200, 401}, (
        f"Metrics endpoint unexpected response: {response.status_code}"
    )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_responds_within_timeout(tensorzero_client: httpx.AsyncClient):
    """Test that TensorZero responds within acceptable time."""
    import time

    start_time = time.time()
    response = await tensorzero_client.get("/healthz")
    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    assert duration_ms < 1000, f"Response too slow: {duration_ms:.0f}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_clickhouse_latency(clickhouse_client: httpx.AsyncClient):
    """Test ClickHouse query latency."""
    import time

    start_time = time.time()
    response = await clickhouse_client.get("/ping")
    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    assert duration_ms < 500, f"ClickHouse too slow: {duration_ms:.0f}ms"
