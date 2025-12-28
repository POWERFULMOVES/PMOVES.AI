"""
Hi-RAG Gateway v2 service-specific smoke tests.

Tests Hi-RAG v2 health and dependency connections (Qdrant, Neo4j, Meilisearch).

Expected runtime: <5s
"""

import pytest
import httpx
from pmoves.tests.utils.service_catalog import HIRAG_V2, QDRANT, NEO4J, MEILISEARCH


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
async def hirag_v2_client() -> httpx.AsyncClient:
    """Hi-RAG v2 HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(base_url=f"http://localhost:{HIRAG_V2.port}", timeout=timeout)


@pytest.fixture(scope="session")
async def qdrant_client() -> httpx.AsyncClient:
    """Qdrant HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(base_url=f"http://localhost:{QDRANT.port}", timeout=timeout)


@pytest.fixture(scope="session")
async def neo4j_client() -> httpx.AsyncClient:
    """Neo4j HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(base_url=f"http://localhost:{NEO4J.port}", timeout=timeout)


@pytest.fixture(scope="session")
async def meilisearch_client() -> httpx.AsyncClient:
    """Meilisearch HTTP client."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    return httpx.AsyncClient(base_url=f"http://localhost:{MEILISEARCH.port}", timeout=timeout)


# ============================================================================
# HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_health_endpoint(hirag_v2_client: httpx.AsyncClient):
    """Test Hi-RAG v2 health endpoint."""
    response = await hirag_v2_client.get("/healthz")

    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert "status" in data, "Response missing 'status' field"
    assert data["status"] == "healthy", f"Unhealthy status: {data.get('status')}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_qdrant_connected(hirag_v2_client: httpx.AsyncClient):
    """Test that Hi-RAG v2 reports Qdrant connection."""
    response = await hirag_v2_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Check for Qdrant connection status
    qdrant_connected = data.get("qdrant_connected", False)
    assert qdrant_connected, "Hi-RAG v2 not connected to Qdrant"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_neo4j_connected(hirag_v2_client: httpx.AsyncClient):
    """Test that Hi-RAG v2 reports Neo4j connection."""
    response = await hirag_v2_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Check for Neo4j connection status
    neo4j_connected = data.get("neo4j_connected", False)
    assert neo4j_connected, "Hi-RAG v2 not connected to Neo4j"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_meilisearch_connected(hirag_v2_client: httpx.AsyncClient):
    """Test that Hi-RAG v2 reports Meilisearch connection."""
    response = await hirag_v2_client.get("/healthz")

    assert response.status_code == 200
    data = response.json()

    # Check for Meilisearch connection status
    meilisearch_connected = data.get("meilisearch_connected", False)
    assert meilisearch_connected, "Hi-RAG v2 not connected to Meilisearch"


# ============================================================================
# DEPENDENCY HEALTH TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_qdrant_health(qdrant_client: httpx.AsyncClient):
    """Test Qdrant health."""
    response = await qdrant_client.get("/readyz")

    assert response.status_code == 200, f"Qdrant not ready: {response.status_code}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_neo4j_health(neo4j_client: httpx.AsyncClient):
    """Test Neo4j health."""
    response = await neo4j_client.get("/")

    # Neo4j browser UI should be accessible
    assert response.status_code in {200, 401}, (
        f"Neo4j not accessible: {response.status_code}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_meilisearch_health(meilisearch_client: httpx.AsyncClient):
    """Test Meilisearch health."""
    response = await meilisearch_client.get("/health")

    assert response.status_code == 200, f"Meilisearch unhealthy: {response.status_code}"

    data = response.json()
    assert data.get("status") == "available", f"Meilisearch status: {data.get('status')}"


# ============================================================================
# API ENDPOINTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_query_endpoint_exists(hirag_v2_client: httpx.AsyncClient):
    """Test that Hi-RAG v2 query endpoint is accessible."""
    # Send a minimal query (may fail auth/validation but should prove endpoint exists)
    response = await hirag_v2_client.post(
        "/hirag/query",
        json={"query": "test", "top_k": 1}
    )

    # Should return 200 (success), 400 (validation), or 422 (validation error)
    # but not 404 (endpoint missing) or connection error
    assert response.status_code in {200, 400, 422, 401}, (
        f"Query endpoint unexpected response: {response.status_code}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_metrics_endpoint(hirag_v2_client: httpx.AsyncClient):
    """Test Hi-RAG v2 metrics endpoint."""
    response = await hirag_v2_client.get("/metrics")

    # Should return 200 with Prometheus metrics
    assert response.status_code == 200, f"Metrics check failed: {response.status_code}"

    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics response is empty"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_responds_within_timeout(hirag_v2_client: httpx.AsyncClient):
    """Test that Hi-RAG v2 responds within acceptable time."""
    import time

    start_time = time.time()
    response = await hirag_v2_client.get("/healthz")
    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    assert duration_ms < 1000, f"Response too slow: {duration_ms:.0f}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_hirag_v2_dependencies_latency_summary(
    hirag_v2_client: httpx.AsyncClient,
    qdrant_client: httpx.AsyncClient,
    meilisearch_client: httpx.AsyncClient,
):
    """Test latency summary for Hi-RAG v2 and dependencies."""
    import time

    latencies = {}

    # Test Hi-RAG v2
    start = time.time()
    await hirag_v2_client.get("/healthz")
    latencies["hirag_v2"] = (time.time() - start) * 1000

    # Test Qdrant
    start = time.time()
    await qdrant_client.get("/readyz")
    latencies["qdrant"] = (time.time() - start) * 1000

    # Test Meilisearch
    start = time.time()
    await meilisearch_client.get("/health")
    latencies["meilisearch"] = (time.time() - start) * 1000

    # All should respond in <500ms
    for service, latency_ms in latencies.items():
        assert latency_ms < 500, f"{service} too slow: {latency_ms:.0f}ms"

    # Overall should be fast
    total_latency_ms = sum(latencies.values())
    assert total_latency_ms < 1500, f"Total latency too high: {total_latency_ms:.0f}ms"
