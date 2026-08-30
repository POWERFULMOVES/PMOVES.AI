"""
Unit tests for cipher_layer.py

Tests the Cipher Memory pre-check layer (Layer 0) including:
- Cipher search (hit/miss)
- Disabled layer behavior (immediate None return)
- Storing as Cipher memory
- Store failure handling (non-blocking, fail-open)
- Lifecycle (init / close)

The MCP HTTP client is mocked for all tests.  cipher_layer.py may not exist
as a standalone module; these tests exercise the interface that main.py
expects via ``from .cipher_layer import CipherLayer``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cipher_enabled_config() -> MagicMock:
    """Return settings-like object with Cipher layer enabled."""
    return MagicMock(
        cipher_mcp_url="http://cipher-mcp:8080",
        cipher_layer_enabled=True,
    )


@pytest.fixture
def cipher_disabled_config() -> MagicMock:
    """Return settings-like object with Cipher layer disabled."""
    return MagicMock(
        cipher_mcp_url="http://cipher-mcp:8080",
        cipher_layer_enabled=False,
    )


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Return a mocked async httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Helper to build a CipherLayer with fully-mocked internals
# ---------------------------------------------------------------------------

def _make_cipher_layer(
    mcp_url: str = "http://cipher-mcp:8080",
    enabled: bool = True,
) -> Any:
    """
    Import and construct CipherLayer, patching away any real HTTP setup.
    Returns the instance with a mock HTTP client pre-injected.
    """
    with patch(
        "pmoves.services.semantic_cache.cipher_layer.httpx.AsyncClient",
        return_value=AsyncMock(spec=httpx.AsyncClient),
    ):
        from pmoves.services.semantic_cache.cipher_layer import CipherLayer

        layer = CipherLayer(
            mcp_endpoint=mcp_url,
            enabled=enabled,
        )
        # Inject a mock client so we never hit the network
        layer._client = AsyncMock(spec=httpx.AsyncClient)
        layer._client.aclose = AsyncMock()
        return layer


# ---------------------------------------------------------------------------
# Tests — Layer 0: Cipher Memory Pre-Check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCipherSearch:
    """Tests for CipherLayer.search() — Qdrant KG lookup via MCP."""

    async def test_search_hit(self) -> None:
        """
        Arrange: Cipher MCP returns a matching memory with high score.
        Act:    Call search(query_text, model).
        Assert: The memory dict is returned.
        """
        # Arrange
        cipher = _make_cipher_layer()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "score": 0.97,
                    "payload": {
                        "response_text": '{"role": "assistant", "content": "Paris"}',
                    },
                }
            ]
        }
        cipher._client.post = AsyncMock(return_value=mock_response)

        # Act
        result = await cipher.search("What is the capital of France?", "gpt-4")

        # Assert
        assert result is not None
        assert "response_text" in result

    async def test_search_miss(self) -> None:
        """
        Arrange: Cipher MCP returns empty results.
        Act:    Call search().
        Assert: None is returned.
        """
        # Arrange
        cipher = _make_cipher_layer()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        cipher._client.post = AsyncMock(return_value=mock_response)

        # Act
        result = await cipher.search("unmatched query", "gpt-4")

        # Assert
        assert result is None

    async def test_search_disabled(self) -> None:
        """
        Arrange: Cipher layer is disabled (enabled=False).
        Act:    Call search().
        Assert: None is returned immediately (no HTTP call made).
        """
        # Arrange
        cipher = _make_cipher_layer(enabled=False)

        # Act
        result = await cipher.search("any query", "gpt-4")

        # Assert
        assert result is None
        cipher._client.post.assert_not_called()

    async def test_search_http_error_fail_open(self) -> None:
        """
        Arrange: Cipher MCP returns 500.
        Act:    Call search().
        Assert: None is returned (fail-open — never raise).
        """
        # Arrange
        cipher = _make_cipher_layer()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        cipher._client.post = AsyncMock(return_value=mock_response)

        # Act — must NOT raise
        result = await cipher.search("query", "gpt-4")

        # Assert
        assert result is None


@pytest.mark.asyncio
class TestCipherStore:
    """Tests for CipherLayer.store() — persisting to Qdrant KG."""

    async def test_store(self) -> None:
        """
        Arrange: A query/response pair to store as Cipher memory.
        Act:    Call store(query_text, response_text).
        Assert: HTTP POST to MCP endpoint is issued with correct payload.
        """
        # Arrange
        cipher = _make_cipher_layer()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"stored": True}
        cipher._client.post = AsyncMock(return_value=mock_response)

        # Act
        await cipher.store(
            query_text="What is 2+2?",
            response_text='{"role": "assistant", "content": "4"}',
        )

        # Assert
        cipher._client.post.assert_called_once()
        call_args = cipher._client.post.call_args
        assert "store" in str(call_args) or "memory" in str(call_args)

    async def test_store_failure_is_non_blocking(self) -> None:
        """
        Arrange: Cipher MCP /store endpoint returns 500.
        Act:    Call store().
        Assert: Exception is caught, logged, and NOT raised (non-blocking).
        """
        # Arrange
        cipher = _make_cipher_layer()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        cipher._client.post = AsyncMock(return_value=mock_response)

        # Act — must NOT raise
        await cipher.store(
            query_text="What is 2+2?",
            response_text="4",
        )

        # Assert — the call was attempted and failure was swallowed
        cipher._client.post.assert_called_once()

    async def test_store_network_exception_fail_open(self) -> None:
        """
        Arrange: Network is unreachable (ConnectionError).
        Act:    Call store().
        Assert: Exception is caught, NOT raised (non-blocking).
        """
        # Arrange
        cipher = _make_cipher_layer()
        cipher._client.post = AsyncMock(
            side_effect=Exception("Cannot connect to Cipher MCP"),
        )

        # Act — must NOT raise
        await cipher.store(
            query_text="What is 2+2?",
            response_text="4",
        )

        # Assert
        cipher._client.post.assert_called_once()


@pytest.mark.asyncio
class TestCipherLifecycle:
    """Tests for CipherLayer.init() and close()."""

    async def test_init(self) -> None:
        """
        Arrange: Fresh CipherLayer instance.
        Act:    Call init().
        Assert: HTTP client is created.
        """
        cipher = _make_cipher_layer()
        # _client was injected by _make_cipher_layer; reset it
        cipher._client = None

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client_cls.return_value = mock_client

            await cipher.init()

        assert cipher._client is not None

    async def test_close(self) -> None:
        """
        Arrange: Initialised CipherLayer.
        Act:    Call close().
        Assert: Client aclose() invoked.
        """
        cipher = _make_cipher_layer()
        await cipher.close()

        cipher._client.aclose.assert_awaited_once()
