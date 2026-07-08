"""
Integration tests for main.py (FastAPI proxy app)

Tests the full request lifecycle including:
- Health and metrics endpoints
- Passthrough for non-cacheable requests (>3 messages, tools, high temp)
- Cache hit path — Layer 0 (Cipher) and Layer 1 (pgvector)
- Cache miss forward to TensorZero

All external dependencies (Supabase, Hi-RAG, Cipher MCP, TensorZero)
are mocked.  Module-level globals in main.py (http_client, hirag_client,
cipher, cache) are controlled by patching the classes the lifespan
manager instantiates.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings() -> MagicMock:
    """Return a fully-populated settings mock for main.py."""
    return MagicMock(
        tensorzero_url="http://tensorzero:3000",
        hirag_gateway_url="http://hirag-gateway:8080",
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        cipher_mcp_url="http://cipher-mcp:8080",
        cipher_layer_enabled=True,
        similarity_threshold=0.92,
        max_cacheable_temperature=0.5,
        cache_ttl_chat_secs=3600,
        chit_bus_enabled=False,
        chit_cache_invalidate_topic="cache.invalidate",
        nats_url="nats://nats:4222",
    )


@pytest.fixture
def mock_hirag_client() -> AsyncMock:
    """Return a mock HiRAGClient that returns a fixed embedding."""
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[0.1] * 768)
    client.init = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_tensorzero_http_client() -> AsyncMock:
    """
    Return a mock httpx.AsyncClient for TensorZero forwarding.
    Returns a realistic chat.completions response by default.
    """
    client = AsyncMock()

    tz_response = MagicMock()
    tz_response.status_code = 200
    tz_response.content = json.dumps({
        "id": "chatcmpl-tz-001",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "tensorzero::model_name=firefunction",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "42"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20},
    }).encode()
    tz_response.text = tz_response.content.decode()
    tz_response.headers = {"content-type": "application/json"}

    client.post = AsyncMock(return_value=tz_response)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_cache_store() -> AsyncMock:
    """Return a fully mocked CacheStore (L1 pgvector)."""
    store = AsyncMock()
    store.lookup = AsyncMock(return_value=None)
    store.store = AsyncMock()
    store.increment_hit = AsyncMock()
    store.count = AsyncMock(return_value=100)
    store.init = AsyncMock()
    store.close = AsyncMock()
    return store


@pytest.fixture
def mock_cipher_layer() -> AsyncMock:
    """Return a fully mocked CipherLayer (L0)."""
    layer = AsyncMock()
    layer.enabled = True
    layer.search = AsyncMock(return_value=None)
    layer.store = AsyncMock()
    layer.init = AsyncMock()
    layer.close = AsyncMock()
    return layer


@pytest.fixture
def app_client(
    mock_settings: MagicMock,
    mock_hirag_client: AsyncMock,
    mock_tensorzero_http_client: AsyncMock,
    mock_cache_store: AsyncMock,
    mock_cipher_layer: AsyncMock,
) -> TestClient:
    """
    Build a FastAPI TestClient with all external dependencies mocked.

    Patches the classes that lifespan() instantiates so that module-level
globals (http_client, hirag_client, cipher, cache) are all mocks.
    """
    with patch(
        "pmoves.services.semantic_cache.main.settings",
        mock_settings,
    ):
        with patch(
            "pmoves.services.semantic_cache.main.HiRAGClient",
            return_value=mock_hirag_client,
        ):
            with patch(
                "pmoves.services.semantic_cache.main.httpx.AsyncClient",
                return_value=mock_tensorzero_http_client,
            ):
                with patch(
                    "pmoves.services.semantic_cache.main.CipherLayer",
                    return_value=mock_cipher_layer,
                ):
                    with patch(
                        "pmoves.services.semantic_cache.main.CacheStore",
                        return_value=mock_cache_store,
                    ):
                        from pmoves.services.semantic_cache.main import app

                        return TestClient(app)


@pytest.fixture
def cacheable_payload() -> dict[str, Any]:
    """Return a minimal cacheable chat completion request."""
    return {
        "model": "tensorzero::function_name=hello",
        "messages": [
            {"role": "user", "content": "What is the capital of France?"},
        ],
        "temperature": 0.1,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_endpoint(self, app_client: TestClient) -> None:
        """
        Arrange: App is running with mocked deps.
        Act:    GET /health.
        Assert: Returns 200 with status "ok".
        """
        # Act
        response = app_client.get("/health")

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body


class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    def test_metrics_endpoint(self, app_client: TestClient) -> None:
        """
        Arrange: Metrics are enabled via the metrics module.
        Act:    GET /metrics.
        Assert: Returns 200 with Prometheus-format text.
        """
        # Act
        response = app_client.get("/metrics")

        # Assert
        assert response.status_code == 200
        content = response.text
        assert "# HELP" in content or "# TYPE" in content or "pmoves_" in content


class TestPassthroughNonCacheable:
    """Tests for requests that bypass the cache entirely."""

    def test_passthrough_more_than_three_messages(
        self,
        app_client: TestClient,
        mock_hirag_client: AsyncMock,
    ) -> None:
        """
        Arrange: Request has >3 messages.
        Act:    POST /openai/v1/chat/completions.
        Assert: Forwards to TensorZero; no embedding call made.
        """
        # Arrange — 4 messages exceeds the ≤3 threshold
        payload = {
            "model": "tensorzero::function_name=hello",
            "messages": [
                {"role": "system", "content": "Sys 1"},
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
                {"role": "user", "content": "Q2"},
            ],
            "temperature": 0.1,
        }

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=payload)

        # Assert
        assert response.status_code == 200
        # Embedding should NOT be called for >3 messages
        mock_hirag_client.embed.assert_not_called()

    def test_passthrough_tools(
        self,
        app_client: TestClient,
        mock_hirag_client: AsyncMock,
    ) -> None:
        """
        Arrange: Request contains tool definitions.
        Act:    POST /openai/v1/chat/completions.
        Assert: Forwards to TensorZero; no embedding call made.
        """
        # Arrange — tools present make it non-cacheable
        payload = {
            "model": "tensorzero::function_name=hello",
            "messages": [
                {"role": "user", "content": "What's the weather?"},
            ],
            "temperature": 0.1,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather info",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=payload)

        # Assert
        assert response.status_code == 200
        mock_hirag_client.embed.assert_not_called()

    def test_passthrough_high_temperature(
        self,
        app_client: TestClient,
        mock_hirag_client: AsyncMock,
    ) -> None:
        """
        Arrange: Request temperature > 0.5 (max_cacheable_temperature).
        Act:    POST /openai/v1/chat/completions.
        Assert: Forwards to TensorZero; no embedding call made.
        """
        # Arrange
        payload = {
            "model": "tensorzero::function_name=hello",
            "messages": [{"role": "user", "content": "Be creative!"}],
            "temperature": 0.9,
        }

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=payload)

        # Assert
        assert response.status_code == 200
        mock_hirag_client.embed.assert_not_called()


class TestCacheHit:
    """Tests for cache hit paths — Layer 0 (Cipher) and Layer 1 (pgvector)."""

    def test_cache_hit_cipher_l0(
        self,
        app_client: TestClient,
        mock_cipher_layer: AsyncMock,
        mock_hirag_client: AsyncMock,
        cacheable_payload: dict[str, Any],
    ) -> None:
        """
        Arrange: Cipher L0 returns a hit.
        Act:    POST /openai/v1/chat/completions.
        Assert: Cached response returned; no embedding/L1 lookup needed.
        """
        # Arrange — L0 returns a valid cache hit
        mock_cipher_layer.search.return_value = {
            "id": "cipher-hit-001",
            "response_text": json.dumps({
                "choices": [{"message": {"role": "assistant", "content": "Paris"}}],
            }),
            "similarity_score": 0.98,
            "layer": "layer0",
        }

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=cacheable_payload)

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["choices"][0]["message"]["content"] == "Paris"
        # L1 (pgvector) and embedding should be skipped on L0 hit
        mock_hirag_client.embed.assert_not_called()

    def test_cache_hit_pgvector_l1(
        self,
        app_client: TestClient,
        mock_cache_store: AsyncMock,
        mock_hirag_client: AsyncMock,
        mock_cipher_layer: AsyncMock,
        cacheable_payload: dict[str, Any],
    ) -> None:
        """
        Arrange: Cipher L0 misses, L1 pgvector hits.
        Act:    POST /openai/v1/chat/completions.
        Assert: Cached response returned from L1; embedding was called.
        """
        # Arrange — L0 miss, L1 hit
        mock_cipher_layer.search.return_value = None
        mock_cache_store.lookup.return_value = {
            "id": "l1-hit-001",
            "response_text": json.dumps({
                "choices": [{"message": {"role": "assistant", "content": "Paris"}}],
            }),
            "similarity_score": 0.95,
            "layer": "layer1",
        }

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=cacheable_payload)

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["choices"][0]["message"]["content"] == "Paris"
        # Embedding must have been called for L1 lookup
        mock_hirag_client.embed.assert_called_once()
        # Increment hit should fire
        mock_cache_store.increment_hit.assert_called_once_with("l1-hit-001")


class TestCacheMissForward:
    """Tests for cache miss that forwards to TensorZero."""

    def test_cache_miss_forwards_to_tensorzero(
        self,
        app_client: TestClient,
        mock_cache_store: AsyncMock,
        mock_cipher_layer: AsyncMock,
        mock_tensorzero_http_client: AsyncMock,
        mock_hirag_client: AsyncMock,
        cacheable_payload: dict[str, Any],
    ) -> None:
        """
        Arrange: Both L0 and L1 miss.
        Act:    POST /openai/v1/chat/completions.
        Assert: Response from TensorZero returned; embedding was called;
                TensorZero was forwarded to; cache store may be populated.
        """
        # Arrange — both layers miss
        mock_cipher_layer.search.return_value = None
        mock_cache_store.lookup.return_value = None

        # Act
        response = app_client.post("/openai/v1/chat/completions", json=cacheable_payload)

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["choices"][0]["message"]["content"] == "42"

        # Embedding must have been called
        mock_hirag_client.embed.assert_called_once()

        # TensorZero must have been called
        mock_tensorzero_http_client.post.assert_called_once()
