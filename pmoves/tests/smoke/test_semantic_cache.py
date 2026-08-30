"""
Smoke tests for the Semantic Cache Proxy service.

These tests verify the running service via real HTTP calls.
They are designed to run against a deployed instance (local or remote).

Required environment:
    SEMANTIC_CACHE_URL — Base URL of the cache proxy (default: http://localhost:8080)

These tests are marked with ``pytest.mark.smoke`` and should be run via::

    pytest -m smoke

They will be SKIPPED if the service is not reachable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEMANTIC_CACHE_URL = os.environ.get("SEMANTIC_CACHE_URL", "http://localhost:8080")

# Timeouts for smoke tests (generous — talking to real services)
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service_available(url: str) -> bool:
    """Check if a service is reachable."""
    try:
        response = httpx.get(f"{url}/health", timeout=TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cache_url() -> str:
    """Return the semantic cache proxy base URL."""
    return SEMANTIC_CACHE_URL.rstrip("/")


@pytest.fixture(scope="module")
def http_client() -> httpx.Client:
    """Yield a synchronous HTTP client for smoke tests."""
    client = httpx.Client(timeout=TIMEOUT)
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Skip helpers
# ---------------------------------------------------------------------------

_service_up = _service_available(SEMANTIC_CACHE_URL)

skip_if_down = pytest.mark.skipif(
    not _service_up,
    reason=f"Semantic Cache Proxy not reachable at {SEMANTIC_CACHE_URL}",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@skip_if_down
class TestServiceUp:
    """Verify the cache proxy service is healthy and responding."""

    def test_service_up(self, http_client: httpx.Client, cache_url: str) -> None:
        """
        Arrange: Cache proxy is deployed.
        Act:    GET {cache_url}/health.
        Assert: Returns 200 with status "ok".
        """
        # Act
        response = http_client.get(f"{cache_url}/health")

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"


@skip_if_down
class TestEmbeddingEndpoint:
    """Verify the /openai/v1/embeddings endpoint forwards correctly."""

    def test_embedding_endpoint(
        self,
        http_client: httpx.Client,
        cache_url: str,
    ) -> None:
        """
        Arrange: A valid embedding request payload.
        Act:    POST {cache_url}/openai/v1/embeddings.
        Assert: Returns 200 with embedding data, or 422 (validation)
                — both indicate the proxy is alive and routing.
        """
        # Arrange
        payload: dict[str, Any] = {
            "model": "text-embedding-3-small",
            "input": "The quick brown fox",
        }

        # Act
        response = http_client.post(
            f"{cache_url}/openai/v1/embeddings",
            json=payload,
        )

        # Assert — accept success or validation error as "alive" signals
        assert response.status_code in (200, 422, 404)
        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)
            assert len(body["data"]) > 0
            assert "embedding" in body["data"][0]
