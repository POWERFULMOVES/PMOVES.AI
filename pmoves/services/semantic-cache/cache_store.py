#!/usr/bin/env python3
"""pgvector-backed semantic cache store.

All methods fail-open: DB errors return None / no-op so the proxy
degrades to passthrough.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import asyncpg

from config import CacheSettings, get_settings
from metrics import cache_latency_seconds

logger = logging.getLogger(__name__)


def build_cache_key(body: dict[str, Any]) -> str:
    """Build a deterministic cache key from request components.

    Includes messages, model, tools, and tool_choice (tool-schema-aware).
    """
    parts: list[str] = []

    # Messages (normalized)
    messages = body.get("messages", [])
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content, sort_keys=True)
        parts.append(f"{role}:{content}")

    # Model
    parts.append(f"model:{body.get('model', '')}")

    # Tools schema hash (tool-schema-aware cache keys)
    tools = body.get("tools")
    if tools:
        tools_json = json.dumps(tools, sort_keys=True)
        parts.append(f"tools:{hashlib.sha256(tools_json.encode()).hexdigest()}")

    tool_choice = body.get("tool_choice")
    if tool_choice:
        parts.append(f"tool_choice:{json.dumps(tool_choice, sort_keys=True)}")

    # Temperature (deterministic at cache boundary)
    temp = body.get("temperature", 0.0)
    parts.append(f"temp:{temp}")

    key_str = "|".join(parts)
    return hashlib.sha256(key_str.encode()).hexdigest()


class CacheStore:
    """Async pgvector cache with HNSW similarity search."""

    def __init__(self, settings: CacheSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> Optional[asyncpg.Pool]:
        """Lazily create connection pool. Returns None if unavailable."""
        if self._pool is not None:
            return self._pool
        if not self.settings.database_url:
            logger.warning("No CACHE_DATABASE_URL — cache disabled")
            return None
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.database_url,
                min_size=1,
                max_size=10,
                command_timeout=5,
            )
            return self._pool
        except Exception as exc:
            logger.warning("DB pool creation failed (fail-open): %s", exc)
            self._pool = None
            return None

    async def lookup(
        self,
        embedding: list[float],
        model: str,
        threshold: float | None = None,
    ) -> Optional[dict[str, Any]]:
        """Semantic lookup via search_semantic_cache RPC.

        Returns cached response dict or None. Fail-open on DB error.
        """
        pool = await self._get_pool()
        if pool is None:
            return None

        threshold = threshold or self.settings.similarity_threshold

        start = time.monotonic()
        try:
            async with pool.acquire() as conn:
                # Convert embedding to pgvector string format
                vec_str = f"[{','.join(str(x) for x in embedding)}]"
                row = await conn.fetchrow(
                    "SELECT * FROM pmoves_cache.search_semantic_cache($1, $2, $3, 1)",
                    vec_str,
                    model,
                    threshold,
                )
            cache_latency_seconds.labels().observe(time.monotonic() - start)

            if row is None:
                return None

            # Update access stats (fire-and-forget)
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE pmoves_cache.llm_semantic_cache "
                        "SET access_count = access_count + 1, "
                        "    last_accessed_at = now() "
                        "WHERE id = $1",
                        row["id"],
                    )
            except Exception:
                pass  # access stats are non-critical

            return {
                "response": row["response_json"],
                "similarity": float(row["similarity"]),
                "query_text": row["query_text"],
                "tokens_saved": row["tokens_saved"],
            }
        except Exception as exc:
            logger.warning("Cache lookup failed (fail-open): %s", exc)
            return None

    async def store(
        self,
        cache_key: str,
        query: str,
        embedding: list[float],
        model: str,
        response: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store a cache entry. Fail-open (no-op on DB error)."""
        pool = await self._get_pool()
        if pool is None:
            return

        ttl = ttl or self.settings.ttl_chat_secs
        vec_str = f"[{','.join(str(x) for x in embedding)}]"

        start = time.monotonic()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO pmoves_cache.llm_semantic_cache
                       (cache_key, query_text, model, query_embedding,
                        embedding_model, embedding_dim, response_json, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, now() + make_interval(secs => $8))
                    ON CONFLICT (cache_key) DO UPDATE
                    SET response_json = $7::jsonb,
                        expires_at = now() + make_interval(secs => $8),
                        query_embedding = $4,
                        embedding_model = $5,
                        embedding_dim = $6,
                        created_at = now()
                    """,
                    cache_key,
                    query,
                    model,
                    vec_str,
                    self.settings.embedding_model,
                    self.settings.embedding_dim,
                    json.dumps(response),
                    ttl,
                )
            cache_latency_seconds.labels().observe(time.monotonic() - start)
        except Exception as exc:
            logger.warning("Cache store failed (fail-open): %s", exc)

    async def evict_expired(self) -> int:
        """Evict expired entries. Returns count evicted."""
        pool = await self._get_pool()
        if pool is None:
            return 0
        try:
            async with pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT pmoves_cache.evict_expired()"
                )
        except Exception as exc:
            logger.warning("Eviction failed (fail-open): %s", exc)
            return 0

    async def close(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
            self._pool = None
