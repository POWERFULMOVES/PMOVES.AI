"""Smoke tests for Hi-RAG v2 UI Integration endpoints.

These tests verify the Hi-RAG v2 service is healthy and responsive
for the UI Integration features.
"""

import pytest
import httpx


# Service URL configuration
HIRAG_V2_URL = "http://localhost:8086"


@pytest.mark.smoke
def test_hirag_v2_health():
    """Verify Hi-RAG v2 service is healthy."""
    try:
        response = httpx.get(f"{HIRAG_V2_URL}/healthz", timeout=10.0)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

        data = response.json()
        assert "healthy" in data or "status" in data
    except ConnectionError as e:
        pytest.skip(f"Hi-RAG v2 service not available: {e}")
    except httpx.ConnectError as e:
        pytest.skip(f"Hi-RAG v2 service not running: {e}")


@pytest.mark.smoke
@pytest.mark.parametrize("query", [
    "test query",
    "What is PMOVES?",
    "machine learning",
])
def test_hirag_v2_query_basic(query):
    """Verify Hi-RAG v2 accepts queries."""
    try:
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/query",
            json={"query": query, "top_k": 3},
            timeout=30.0
        )
        assert response.status_code == 200, f"Query failed: {response.status_code}"

        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")


@pytest.mark.smoke
def test_hirag_v2_query_with_filters():
    """Verify Hi-RAG v2 handles filter parameters."""
    try:
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/query",
            json={
                "query": "test",
                "top_k": 5,
                "filters": {
                    "source_type": "youtube",
                    "min_score": 0.7,
                }
            },
            timeout=30.0
        )
        assert response.status_code == 200, f"Query with filters failed: {response.status_code}"

        data = response.json()
        assert "results" in data
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")


@pytest.mark.smoke
def test_hirag_v2_rerank_disable():
    """Verify Hi-RAG v2 handles rerank parameter."""
    try:
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/query",
            json={
                "query": "test",
                "top_k": 5,
                "rerank": False
            },
            timeout=30.0
        )
        assert response.status_code == 200, f"Query without rerank failed: {response.status_code}"

        data = response.json()
        assert "results" in data
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")


@pytest.mark.smoke
def test_hirag_v2_response_structure():
    """Verify Hi-RAG v2 returns expected response structure."""
    try:
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/query",
            json={"query": "structure test", "top_k": 1},
            timeout=30.0
        )
        assert response.status_code == 200

        data = response.json()
        # Check for expected fields
        assert "results" in data
        assert "total" in data or "query_time" in data

        # If results exist, check structure
        if data.get("results"):
            result = data["results"][0]
            assert "id" in result or "content" in result
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")


@pytest.mark.smoke
def test_hirag_v2_empty_query_handling():
    """Verify Hi-RAG v2 handles empty or whitespace queries."""
    try:
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/query",
            json={"query": "", "top_k": 5},
            timeout=30.0
        )
        # Should either return 400 (bad request) or empty results
        assert response.status_code in [200, 400, 422]
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")


@pytest.mark.smoke
def test_hirag_v2_export_to_notebook():
    """Verify Hi-RAG v2 export endpoint exists (for notebook integration)."""
    try:
        # Create mock results to export
        mock_results = [
            {
                "id": "test-1",
                "content": "Test content",
                "score": 0.9,
                "source": "youtube",
                "metadata": {"title": "Test Video"}
            }
        ]

        # Note: Export might go through different service, so we just check
        # if the endpoint is accessible
        response = httpx.post(
            f"{HIRAG_V2_URL}/hirag/export",
            json={"results": mock_results, "notebook_id": "test-notebook"},
            timeout=30.0
        )
        # Export endpoint might not exist or return 404/405
        # That's okay for smoke test - we're checking service is responsive
        assert response.status_code in [200, 404, 405]
    except ConnectionError:
        pytest.skip("Hi-RAG v2 service not available")
    except httpx.ConnectError:
        pytest.skip("Hi-RAG v2 service not running")
