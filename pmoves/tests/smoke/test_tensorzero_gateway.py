"""
TensorZero Gateway service-specific smoke tests.

Tests TensorZero Gateway health and ClickHouse integration.

Expected runtime: <5s (skips gracefully when services are unavailable)
"""

import pytest
import httpx
from pmoves.tests.utils.service_catalog import TENSORZERO_GATEWAY, TENSORZERO_CLICKHOUSE


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def tensorzero_client():
    """TensorZero Gateway HTTP client. Skips dependent tests if service is unavailable."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    client = httpx.AsyncClient(
        base_url=f"http://localhost:{TENSORZERO_GATEWAY.port}",
        timeout=timeout,
    )
    # Probe connectivity AND service identity — skip if unreachable or wrong service
    try:
        resp = await client.get(TENSORZERO_GATEWAY.health_path)
        if resp.status_code == 404:
            await client.aclose()
            pytest.skip(
                f"Port {TENSORZERO_GATEWAY.port} is responding but {TENSORZERO_GATEWAY.health_path} returned 404 "
                "(TensorZero Gateway may not be running)"
            )
        # Validate response body is actually TensorZero (not another service on same port)
        try:
            data = resp.json()
            if "gateway" not in data:
                await client.aclose()
                pytest.skip("Port responds but doesn't look like TensorZero Gateway")
        except Exception:
            pass  # Non-JSON health response is acceptable for probe
    except (httpx.ConnectError, httpx.ConnectTimeout):
        await client.aclose()
        pytest.skip(
            f"TensorZero Gateway not reachable at localhost:{TENSORZERO_GATEWAY.port}"
        )
    yield client
    await client.aclose()


@pytest.fixture
async def clickhouse_client():
    """TensorZero ClickHouse HTTP client. Skips dependent tests if service is unavailable."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    client = httpx.AsyncClient(
        base_url=f"http://localhost:{TENSORZERO_CLICKHOUSE.port}",
        timeout=timeout,
    )
    try:
        resp = await client.get("/ping")
        if resp.status_code == 404:
            await client.aclose()
            pytest.skip(
                f"Port {TENSORZERO_CLICKHOUSE.port} is responding but /ping returned 404 "
                "(ClickHouse may not be running)"
            )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        await client.aclose()
        pytest.skip(
            f"ClickHouse not reachable at localhost:{TENSORZERO_CLICKHOUSE.port}"
        )
    yield client
    await client.aclose()


# ============================================================================
# HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_health_endpoint(tensorzero_client: httpx.AsyncClient):
    """Test TensorZero Gateway health endpoint."""
    response = await tensorzero_client.get(TENSORZERO_GATEWAY.health_path)

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert "gateway" in data, "Response missing 'gateway' field"
    assert data["gateway"] == "ok", f"Unhealthy gateway status: {data.get('gateway')}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_clickhouse_connected(tensorzero_client: httpx.AsyncClient):
    """Test that TensorZero reports ClickHouse connection."""
    response = await tensorzero_client.get(TENSORZERO_GATEWAY.health_path)

    assert response.status_code == 200
    data = response.json()

    # TZ /health returns {"gateway":"ok","clickhouse":"ok","postgres":"ok","valkey":"ok"}
    clickhouse_status = data.get("clickhouse", "")
    assert clickhouse_status == "ok", f"ClickHouse not ok: {clickhouse_status}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_tensorzero_api_versions(tensorzero_client: httpx.AsyncClient):
    """Test TensorZero API version endpoints."""
    # Check OpenAPI spec (TZ may not serve this endpoint)
    response = await tensorzero_client.get("/openapi.json")

    if response.status_code == 404:
        pytest.skip("TensorZero does not serve /openapi.json")

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
    response = await tensorzero_client.get(TENSORZERO_GATEWAY.health_path)
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


# ============================================================================
# STATIC CONFIGURATION TESTS (no running services required)
# ============================================================================

@pytest.mark.smoke
def test_tensorzero_compose_configuration():
    """Validate TensorZero Gateway compose config statically."""
    import yaml
    from _smoke_helpers import PMOVES_DIR

    compose = PMOVES_DIR / "docker-compose.yml"
    if not compose.exists():
        pytest.skip("docker-compose.yml not found")

    data = yaml.safe_load(compose.read_text())
    services = data.get("services", {})
    svc = services.get("tensorzero-gateway", {})
    assert svc, "tensorzero-gateway service should exist in compose"

    # Validate port mapping
    ports = svc.get("ports", [])
    assert any("3030" in str(p) for p in ports), "Should map host port 3030"

    # Validate healthcheck exists (directly or via anchor inheritance)
    hc = svc.get("healthcheck", {})
    assert hc, "Should have healthcheck defined (directly or via anchor)"


@pytest.mark.smoke
def test_tensorzero_clickhouse_compose_configuration():
    """Validate TensorZero ClickHouse compose config statically."""
    import yaml
    from _smoke_helpers import PMOVES_DIR

    compose = PMOVES_DIR / "docker-compose.yml"
    if not compose.exists():
        pytest.skip("docker-compose.yml not found")

    data = yaml.safe_load(compose.read_text())
    services = data.get("services", {})
    svc = services.get("tensorzero-clickhouse", {})
    assert svc, "tensorzero-clickhouse service should exist in compose"

    # Validate port mapping
    ports = svc.get("ports", [])
    assert any("8123" in str(p) for p in ports), "Should map host port 8123"
