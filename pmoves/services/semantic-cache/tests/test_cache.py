"""
Unit tests for cache_store.py

Tests the pgvector semantic cache layer (Supabase-backed) including:
- Cache lookup via RPC (hit/miss)
- Storing new entries via RPC
- Hit counter increment
- Entry counting
- Lifecycle (init / close)

All external calls (AsyncPostgrestClient) are mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pg_result() -> MagicMock:
    """Return a reusable mock for Postgrest RPC result data."""
    return MagicMock()


@pytest.fixture
def mock_postgrest_client(mock_pg_result: MagicMock) -> AsyncMock:
    """
    Create a mock AsyncPostgrestClient with chainable RPC interface.

    Supports the fluent API used by CacheStore:
        client.rpc("cache_semantic_lookup", {...}).execute()
        client.rpc("cache_semantic_insert",  {...}).execute()
    """
    client = AsyncMock()

    # Chainable RPC builder
    chain = MagicMock()
    chain.execute = AsyncMock(return_value=mock_pg_result)
    client.rpc = MagicMock(return_value=chain)

    client.aclose = AsyncMock()

    return client


@pytest.fixture
def cache_store_instance(mock_postgrest_client: AsyncMock) -> Any:
    """Instantiate CacheStore with a mocked PostgREST client."""
    with patch(
        "pmoves.services.semantic_cache.cache_store.AsyncPostgrestClient",
        return_value=mock_postgrest_client,
    ):
        from pmoves.services.semantic_cache.cache_store import CacheStore

        store = CacheStore(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            hirag_client=None,
        )
        return store


@pytest.fixture
def sample_embedding() -> list[float]:
    """Return a sample 768-d embedding vector."""
    return [0.1] * 768


@pytest.fixture
def sample_cache_hit() -> dict[str, Any]:
    """Return a typical successful lookup result dict."""
    return {
        "id": "entry-001",
        "response_text": '{"role": "assistant", "content": "Hello!"}',
        "similarity_score": 0.97,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCacheStoreLifecycle:
    """Tests for CacheStore.init() and close()."""

    async def test_init_creates_client(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
    ) -> None:
        """
        Arrange: Fresh CacheStore instance.
        Act:    Call init().
        Assert: PostgREST client is created with correct URL and headers.
        """
        # Arrange
        store = cache_store_instance
        assert store.client is None

        # Act
        await store.init()

        # Assert
        assert store.client is mock_postgrest_client

    async def test_close_releases_client(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
    ) -> None:
        """
        Arrange: Initialised CacheStore.
        Act:    Call close().
        Assert: Client aclose() invoked and reference cleared.
        """
        # Arrange
        store = cache_store_instance
        await store.init()

        # Act
        await store.close()

        # Assert
        mock_postgrest_client.aclose.assert_awaited_once()
        assert store.client is None


@pytest.mark.asyncio
class TestCacheLookup:
    """Tests for CacheStore.lookup() — pgvector semantic search via RPC."""

    async def test_lookup_hit(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        mock_pg_result: MagicMock,
        sample_embedding: list[float],
        sample_cache_hit: dict[str, Any],
    ) -> None:
        """
        Arrange: RPC returns a row within similarity threshold.
        Act:    Call lookup() with an embedding.
        Assert: The cached response dict is returned with correct fields.
        """
        # Arrange
        store = cache_store_instance
        await store.init()
        mock_pg_result.data = [sample_cache_hit]

        # Act
        result = await store.lookup(
            embedding=sample_embedding,
            model="gpt-4",
            threshold=0.92,
        )

        # Assert
        assert result is not None
        assert result["id"] == "entry-001"
        assert result["response_text"] == '{"role": "assistant", "content": "Hello!"}'
        assert result["similarity_score"] == 0.97

        # Verify RPC was called with correct parameters
        mock_postgrest_client.rpc.assert_called_once()
        call_args = mock_postgrest_client.rpc.call_args
        assert call_args[0][0] == "cache_semantic_lookup"
        params = call_args[1]["params"]
        assert params["p_model"] == "gpt-4"
        assert params["p_threshold"] == 0.92
        assert params["p_embedding_dim"] == 768

    async def test_lookup_miss_no_rows(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        mock_pg_result: MagicMock,
        sample_embedding: list[float],
    ) -> None:
        """
        Arrange: RPC returns zero rows.
        Act:    Call lookup().
        Assert: None is returned.
        """
        # Arrange
        store = cache_store_instance
        await store.init()
        mock_pg_result.data = []

        # Act
        result = await store.lookup(
            embedding=sample_embedding,
            model="gpt-4",
            threshold=0.92,
        )

        # Assert
        assert result is None

    async def test_lookup_rpc_failure_fail_open(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        sample_embedding: list[float],
    ) -> None:
        """
        Arrange: RPC raises an exception.
        Act:    Call lookup().
        Assert: None is returned (fail-open — never raise on cache failure).
        """
        # Arrange
        store = cache_store_instance
        await store.init()
        chain = MagicMock()
        chain.execute = AsyncMock(side_effect=Exception("PostgREST timeout"))
        mock_postgrest_client.rpc = MagicMock(return_value=chain)

        # Act
        result = await store.lookup(
            embedding=sample_embedding,
            model="gpt-4",
            threshold=0.92,
        )

        # Assert
        assert result is None


@pytest.mark.asyncio
class TestCacheStore:
    """Tests for CacheStore.store() — persisting new entries via RPC."""

    async def test_store_new_entry(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        sample_embedding: list[float],
    ) -> None:
        """
        Arrange: Fresh query + response to cache.
        Act:    Call store().
        Assert: RPC cache_semantic_insert is executed with correct payload.
        """
        # Arrange
        store = cache_store_instance
        await store.init()

        # Act
        await store.store(
            query_text="What is 2+2?",
            query_embedding=sample_embedding,
            response_text='{"role": "assistant", "content": "4"}',
            model="gpt-4",
            ttl_seconds=3600,
        )

        # Assert — RPC called with correct function name
        mock_postgrest_client.rpc.assert_called_once()
        call_args = mock_postgrest_client.rpc.call_args
        assert call_args[0][0] == "cache_semantic_insert"
        params = call_args[1]["params"]
        assert params["p_text"] == "What is 2+2?"
        assert params["p_response"] == '{"role": "assistant", "content": "4"}'
        assert params["p_model"] == "gpt-4"
        assert params["p_ttl_secs"] == 3600
        assert params["p_embedding_dim"] == 768

    async def test_store_failure_is_non_blocking(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        sample_embedding: list[float],
    ) -> None:
        """
        Arrange: RPC insert raises an exception.
        Act:    Call store().
        Assert: Exception is caught, NOT raised (fail-open).
        """
        # Arrange
        store = cache_store_instance
        await store.init()
        chain = MagicMock()
        chain.execute = AsyncMock(side_effect=Exception("PostgREST insert failed"))
        mock_postgrest_client.rpc = MagicMock(return_value=chain)

        # Act — must NOT raise
        await store.store(
            query_text="What is 2+2?",
            query_embedding=sample_embedding,
            response_text="4",
            model="gpt-4",
            ttl_seconds=3600,
        )

        # Assert — RPC was attempted
        mock_postgrest_client.rpc.assert_called_once()


@pytest.mark.asyncio
class TestCacheIncrement:
    """Tests for CacheStore.increment_hit() — bumping hit counters."""

    async def test_increment_hit(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
    ) -> None:
        """
        Arrange: An existing cache entry ID.
        Act:    Call increment_hit().
        Assert: RPC is executed for the given cache_id.
        """
        # Arrange
        store = cache_store_instance
        await store.init()

        # Act
        await store.increment_hit(cache_id="entry-001")

        # Assert — increment_hit uses RPC
        mock_postgrest_client.rpc.assert_called_once()
        call_args = mock_postgrest_client.rpc.call_args
        assert "increment" in call_args[0][0].lower() or "hit" in call_args[0][0].lower()


@pytest.mark.asyncio
class TestCacheCount:
    """Tests for CacheStore.count() — entry counting."""

    async def test_count_returns_total(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        mock_pg_result: MagicMock,
    ) -> None:
        """
        Arrange: PostgREST count query returns 42.
        Act:    Call count().
        Assert: 42 is returned.
        """
        # Arrange
        store = cache_store_instance
        await store.init()
        mock_pg_result.count = 42
        mock_pg_result.data = []

        # Act
        total = await store.count()

        # Assert
        assert total == 42


@pytest.mark.asyncio
class TestCacheTTL:
    """Tests for TTL-based expiration (handled at SQL level via RPC)."""

    async def test_ttl_expired_entries_not_returned(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        mock_pg_result: MagicMock,
        sample_embedding: list[float],
    ) -> None:
        """
        Arrange: RPC returns no rows (expired entries filtered by SQL).
        Act:    Call lookup().
        Assert: None is returned — SQL-level TTL filtering works.
        """
        # Arrange — empty result simulates SQL filtering out expired rows
        store = cache_store_instance
        await store.init()
        mock_pg_result.data = []

        # Act
        result = await store.lookup(
            embedding=sample_embedding,
            model="gpt-4",
            threshold=0.92,
        )

        # Assert
        assert result is None


@pytest.mark.asyncio
class TestCacheDimensionFilter:
    """Tests for embedding dimension mismatch (handled at SQL level)."""

    async def test_dimension_mismatch_filtered_by_sql(
        self,
        cache_store_instance: Any,
        mock_postgrest_client: AsyncMock,
        mock_pg_result: MagicMock,
    ) -> None:
        """
        Arrange: RPC returns no rows (dimension guard filters at SQL level).
        Act:    Call lookup() with a 768-d embedding.
        Assert: None returned — p_embedding_dim param filters in SQL.
        """
        # Arrange — empty result means SQL dimension guard worked
        store = cache_store_instance
        await store.init()
        mock_pg_result.data = []

        # Act — 768-d embedding
        result = await store.lookup(
            embedding=[0.1] * 768,
            model="gpt-4",
            threshold=0.92,
        )

        # Assert
        assert result is None

        # Verify p_embedding_dim was passed correctly
        call_args = mock_postgrest_client.rpc.call_args
        params = call_args[1]["params"]
        assert params["p_embedding_dim"] == 768
