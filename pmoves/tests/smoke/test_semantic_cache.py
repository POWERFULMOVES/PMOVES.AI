#!/usr/bin/env python3
"""Unit tests for the PMOVES semantic cache proxy (#1427).

All external calls (DB, HTTP, NATS) are mocked — no live dependencies.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import from service dir via sys.path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "semantic-cache"))

from config import CacheSettings, is_cacheable_request
from cache_store import build_cache_key


class TestIsCacheableRequest:
    """Tests for request cacheability filtering."""

    def test_is_cacheable_request_filters_streaming(self):
        """Streaming requests should be passthrough (not cached)."""
        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}], "stream": True}
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is False
        assert "stream" in reason

    def test_is_cacheable_request_filters_tools(self):
        """Requests with tool definitions should not be cached."""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "test"}}],
        }
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is False
        assert "tool" in reason

    def test_is_cacheable_request_filters_tool_choice(self):
        """Requests with tool_choice should not be cached."""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "tool_choice": "auto",
        }
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is False
        assert "tool" in reason

    def test_is_cacheable_request_filters_high_temperature(self):
        """High-temperature requests should not be cached."""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.8,
        }
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is False
        assert "temperature" in reason

    def test_is_cacheable_request_allows_simple_request(self):
        """Simple low-temp single-message request should be cacheable."""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "What is 2+2?"}],
            "temperature": 0.0,
        }
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is True
        assert reason == "ok"

    def test_is_cacheable_request_filters_too_many_messages(self):
        """Multi-turn conversations (>3 msgs) should not be cached."""
        body = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ],
            "temperature": 0.0,
        }
        cacheable, reason = is_cacheable_request(body)
        assert cacheable is False
        assert "messages" in reason


class TestBuildCacheKey:
    """Tests for cache key construction."""

    def test_build_cache_key_includes_model(self):
        """Different models should produce different cache keys."""
        body1 = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
        body2 = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}]}
        key1 = build_cache_key(body1)
        key2 = build_cache_key(body2)
        assert key1 != key2

    def test_build_cache_key_includes_tools_hash(self):
        """Different tool schemas should produce different cache keys."""
        body1 = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "tool_a"}}],
        }
        body2 = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "tool_b"}}],
        }
        key1 = build_cache_key(body1)
        key2 = build_cache_key(body2)
        assert key1 != key2

    def test_build_cache_key_is_deterministic(self):
        """Same body should produce same key."""
        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.0}
        key1 = build_cache_key(body)
        key2 = build_cache_key(body)
        assert key1 == key2

    def test_build_cache_key_returns_hex_string(self):
        """Cache key should be a hex string."""
        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
        key = build_cache_key(body)
        assert len(key) == 64  # SHA-256 hex
        int(key, 16)  # Should not raise (valid hex)


class TestMetrics:
    """Tests for Prometheus metrics."""

    def test_metrics_increment_hits(self):
        """Counter should increment on .inc()."""
        from metrics import cache_hits_total

        before = cache_hits_total._value.get()
        cache_hits_total.inc()
        after = cache_hits_total._value.get()
        assert after == before + 1

    def test_metrics_increment_misses(self):
        """Counter should increment on .inc()."""
        from metrics import cache_misses_total

        before = cache_misses_total._value.get()
        cache_misses_total.inc()
        after = cache_misses_total._value.get()
        assert after == before + 1

    def test_metrics_similarity_observe(self):
        """Histogram should accept observations."""
        from metrics import cache_similarity_score

        cache_similarity_score.observe(0.95)
        cache_similarity_score.observe(0.92)
        # No assertion needed — just verify no exception

    def test_metrics_latency_observe(self):
        """Histogram should accept observations."""
        from metrics import cache_latency_seconds

        cache_latency_seconds.observe(0.025)
        # No assertion needed — just verify no exception


class TestConfigSettings:
    """Tests for configuration."""

    def test_settings_defaults(self):
        """Default settings should have expected values."""
        settings = CacheSettings()
        assert settings.port == 3001
        assert settings.similarity_threshold == 0.90
        assert settings.ttl_chat_secs == 300
        assert settings.max_messages_for_cache == 3
        assert settings.max_temperature_for_cache == 0.3

    def test_embeddings_endpoint(self):
        """Embeddings endpoint should resolve from gateway URL."""
        settings = CacheSettings(hirag_gateway_url="http://gateway:8086")
        assert settings.embeddings_endpoint == "http://gateway:8086/v1/embeddings"


class TestCacheStoreLookup:
    """Tests for cache store lookup (mocked DB)."""

    @pytest.mark.asyncio
    async def test_lookup_returns_none_when_no_db(self):
        """Lookup should return None when DATABASE_URL is empty."""
        from cache_store import CacheStore

        store = CacheStore(CacheSettings(database_url=""))
        result = await store.lookup([0.1] * 2560, "gpt-4")
        assert result is None
        await store.close()

    @pytest.mark.asyncio
    async def test_store_noop_when_no_db(self):
        """Store should be a no-op when DATABASE_URL is empty."""
        from cache_store import CacheStore

        store = CacheStore(CacheSettings(database_url=""))
        await store.store("key", "query", [0.1] * 2560, "gpt-4", {"id": "test"})
        # Should not raise
        await store.close()
