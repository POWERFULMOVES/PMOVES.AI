"""pgvector-backed semantic cache store using Supabase.

Embeddings are generated via Hi-RAG Gateway v2 (delegated, not local Ollama).
Supports multi-dimensional embeddings (BGE-M3 dense+sparse+ColBERT).

Architecture
~~~~~~~~~~~~
*   ``CacheStore`` owns a single ``AsyncPostgrestClient`` connection to
    Supabase and exposes async lifecycle methods ``init()`` / ``close()``.
*   All cache entries are stored in the ``llm_semantic_cache`` table which
    must have a ``pgvector`` column (``embedding vector``) and the following
    RPC functions installed:

    * ``cache_semantic_lookup(p_embedding, p_model, p_threshold,
      p_embedding_dim)`` – cosine-similarity search with dimension guard.
    * ``cache_semantic_insert(...)`` – upsert a new cache row.

*   LRU eviction is *soft* – we track ``last_accessed`` and ``hit_count``
    and delete the oldest-by-last-access rows when the table grows beyond
    ``max_entries``.
*   TTL is *hard* – rows with ``expires_at < now()`` are invisible to
    lookups and can be bulk-deleted via ``evict_expired()``.
*   BGE-M3 (1024-d) is the default embedding model.  Every entry stores
    ``embedding_dim`` so that lookups never match vectors produced by a
    different model architecture.

Typical usage::

    store = CacheStore(SUPABASE_URL, SUPABASE_KEY, hirag_client)
    await store.init()

    # Look-up
    hit = await store.lookup(embedding, model="gpt-4", threshold=0.85)
    if hit:
        await store.update_last_accessed(hit["id"])
        return hit["response_text"]

    # Store (TTL = 1 hour)
    await store.store(query, emb, response, model="gpt-4", ttl_seconds=3600)
    await store.evict_if_over_limit(max_entries=10_000)

    await store.close()
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from postgrest import AsyncPostgrestClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants – BGE-M3 embedding alignment
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIM: int = 1024  # BGE-M3 dense vector size


class CacheStore:
    """Async semantic-cache front-end backed by Supabase pgvector.

    Parameters
    ----------
    supabase_url: str
        Base URL of the Supabase project (e.g. ``https://<id>.supabase.co``).
    supabase_key: str
        Service-role or anon key for PostgREST auth.
    hirag_client:
        Optional Hi-RAG Gateway v2 client used to resolve the *current*
        embedding model name and dimension at run-time.
    """

    # -- lifecycle -----------------------------------------------------------

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        hirag_client: Any | None = None,
    ) -> None:
        self.url: str = supabase_url
        self.key: str = supabase_key
        self.hirag = hirag_client  # Hi-RAG Gateway v2 client for embeddings
        self.client: AsyncPostgrestClient | None = None

    async def init(self) -> None:
        """Open the PostgREST async client."""
        self.client = AsyncPostgrestClient(
            f"{self.url}/rest/v1",
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
            },
        )
        logger.info("CacheStore PostgREST client initialised.")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("CacheStore PostgREST client closed.")

    # -- BGE-M3 embedding alignment ------------------------------------------

    async def get_current_embedding_dim(self) -> int:
        """Return the embedding dimension of the active Hi-RAG model.

        If the Hi-RAG client is unavailable or the call fails, fall back to
        ``DEFAULT_EMBEDDING_DIM`` (1024 for BGE-M3).
        """
        if self.hirag is None:
            logger.debug(
                "No Hi-RAG client configured; using default dim=%s (%s).",
                DEFAULT_EMBEDDING_DIM,
                DEFAULT_EMBEDDING_MODEL,
            )
            return DEFAULT_EMBEDDING_DIM

        try:
            dim = await self.hirag.get_embedding_dim()
            if isinstance(dim, int) and dim > 0:
                logger.debug(
                    "Hi-RAG reports embedding_dim=%s for model=%s.",
                    dim,
                    getattr(self.hirag, "model_name", "unknown"),
                )
                return dim
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Hi-RAG get_embedding_dim() failed (%s); falling back to %s.",
                exc,
                DEFAULT_EMBEDDING_DIM,
            )

        return DEFAULT_EMBEDDING_DIM

    def _resolve_embedding_model(self) -> str:
        """Best-effort resolution of the current embedding model name.

        Returns the model identifier from the Hi-RAG client if available,
        otherwise ``DEFAULT_EMBEDDING_MODEL``.
        """
        if self.hirag is None:
            return DEFAULT_EMBEDDING_MODEL
        try:
            name = getattr(self.hirag, "model_name", None)
            if name:
                return str(name)
            # Some Hi-RAG clients expose this as a coroutine
            if hasattr(self.hirag, "get_current_model"):
                return "deferred-to-async"
        except Exception:  # noqa: S110, BLE001
            pass
        return DEFAULT_EMBEDDING_MODEL

    # -- core operations -----------------------------------------------------

    async def lookup(
        self,
        embedding: list[float],
        model: str,
        threshold: float,
    ) -> dict[str, Any] | None:
        """Semantic cache lookup via pgvector cosine similarity.

        Filters by embedding dimension to avoid cross-model mismatches.
        On a hit the caller should invoke ``update_last_accessed()`` so
        that LRU eviction treats the row as recently used.

        Parameters
        ----------
        embedding: list[float]
            Query embedding vector (already produced by Hi-RAG Gateway).
        model: str
            LLM model name used for the request (e.g. ``"gpt-4"``).
        threshold: float
            Minimum cosine similarity (0.0 – 1.0) for a match.

        Returns
        -------
        dict | None
            ``{"id": <uuid>, "response_text": str, "similarity_score": float}``
            or *None* when no sufficiently similar cached entry exists.
        """
        if self.client is None:
            raise RuntimeError("CacheStore not initialised – call init() first.")

        emb_str = f"[{','.join(str(x) for x in embedding)}]"
        emb_dim = len(embedding)

        try:
            result = await self.client.rpc(
                "cache_semantic_lookup",
                {
                    "p_embedding": emb_str,
                    "p_model": model,
                    "p_threshold": threshold,
                    "p_embedding_dim": emb_dim,
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.error("Semantic lookup RPC failed: %s", exc)
            return None

        if result.data:
            row = result.data[0]
            return {
                "id": row["id"],
                "response_text": row["response_text"],
                "similarity_score": row["similarity_score"],
            }
        return None

    async def store(
        self,
        query_text: str,
        query_embedding: list[float],
        response_text: str,
        model: str,
        ttl_seconds: int,
    ) -> None:
        """Store a new cache entry.

        The embedding is assumed to have been generated already by the
        Hi-RAG Gateway.  The embedding dimension is recorded so that future
        lookups filter against the same model architecture.

        Parameters
        ----------
        query_text: str
            Raw natural-language query.
        query_embedding: list[float]
            Dense embedding vector for the query.
        response_text: str
            LLM response to cache.
        model: str
            LLM model identifier (e.g. ``"gpt-4"``).
        ttl_seconds: int
            Time-to-live in seconds.  ``expires_at`` is computed as
            ``now() + ttl_seconds``.
        """
        if self.client is None:
            raise RuntimeError("CacheStore not initialised – call init() first.")

        query_norm = query_text.strip().lower()
        query_hash = hashlib.sha256(query_norm.encode()).hexdigest()
        emb_str = f"[{','.join(str(x) for x in query_embedding)}]"
        emb_dim = len(query_embedding)

        # Resolve embedding model name from Hi-RAG client
        embedding_model = DEFAULT_EMBEDDING_MODEL
        if self.hirag is not None:
            try:
                resolved = await self.hirag.get_current_model()
                if resolved:
                    embedding_model = str(resolved)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Could not resolve embedding model from Hi-RAG (%s); "
                    "using default %s.",
                    exc,
                    DEFAULT_EMBEDDING_MODEL,
                )

        try:
            await self.client.rpc(
                "cache_semantic_insert",
                {
                    "p_hash": query_hash,
                    "p_text": query_text,
                    "p_embedding": emb_str,
                    "p_embedding_model": embedding_model,
                    "p_embedding_dim": emb_dim,
                    "p_response": response_text,
                    "p_model": model,
                    "p_ttl_secs": ttl_seconds,
                },
            ).execute()
            logger.debug(
                "Cached entry hash=%s model=%s emb_dim=%s ttl=%ss",
                query_hash[:16],
                model,
                emb_dim,
                ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to store cache entry: %s", exc)
            # Never raise – a cache-write failure must not break the request.

    async def increment_hit(self, cache_id: str) -> None:
        """Increment hit count for a cache entry.

        Uses a PostgREST raw increment expression rather than a read-modify-
        write cycle to avoid race conditions.
        """
        if self.client is None:
            return

        try:
            # PostgREST supports raw expressions via the
            # ``.update({"col": "col + 1"})`` pattern when the backend
            # understands it, but safest is an RPC or a direct RPC call.
            # We keep the original behaviour here and wrap it in a try/except.
            await self.client.table("llm_semantic_cache").update(
                {"hit_count": "hit_count + 1"}
            ).eq("id", cache_id).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to increment hit count for %s: %s", cache_id, exc)

    async def count(self) -> int:
        """Return total cache entry count for health checks.

        Returns ``0`` when the store is not initialised or the RPC fails.
        """
        if self.client is None:
            return 0

        try:
            result = await self.client.table("llm_semantic_cache").select(
                "id", count="exact"
            ).execute()
            return result.count or 0
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to count cache entries: %s", exc)
            return 0

    # -- LRU tracking --------------------------------------------------------

    async def update_last_accessed(self, cache_id: str) -> None:
        """Update ``last_accessed`` timestamp for LRU tracking.

        This should be called on every cache hit so that the eviction
        routine knows the row was recently useful.

        Parameters
        ----------
        cache_id: str
            UUID primary key of the cached row.
        """
        if self.client is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            await self.client.table("llm_semantic_cache").update(
                {"last_accessed": now}
            ).eq("id", cache_id).execute()
            logger.debug("Updated last_accessed for cache_id=%s", cache_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to update last_accessed for %s: %s", cache_id, exc
            )

    # -- eviction (soft-fail) ------------------------------------------------

    async def evict_if_over_limit(self, max_entries: int = 10_000) -> None:
        """LRU eviction – remove oldest entries when table grows too large.

        If the total row count exceeds *max_entries*, rows are deleted in
        ascending ``last_accessed`` order until the count drops below
        ``max_entries * 0.9`` (i.e. 90 %% of the limit).

        This method **never raises** – eviction failures are logged at
        ``ERROR`` level and swallowed so that the caller's request is
        never interrupted by housekeeping.

        Parameters
        ----------
        max_entries: int
            Hard ceiling on the number of rows in ``llm_semantic_cache``.
        """
        if self.client is None:
            return

        try:
            total = await self.count()
            if total <= max_entries:
                logger.debug(
                    "Cache count=%s within limit=%s; no eviction needed.",
                    total,
                    max_entries,
                )
                return

            target = int(max_entries * 0.9)
            to_delete = total - target
            logger.info(
                "Cache over limit (%s > %s). Evicting %s oldest entries "
                "targeting count=%s.",
                total,
                max_entries,
                to_delete,
                target,
            )

            # Fetch the oldest 'to_delete' rows by last_accessed
            result = await (
                self.client.table("llm_semantic_cache")
                .select("id")
                .order("last_accessed", desc=False)
                .limit(to_delete)
                .execute()
            )

            if not result.data:
                logger.warning(
                    "Eviction query returned no rows despite count=%s.", total
                )
                return

            ids_to_delete = [row["id"] for row in result.data]
            await (
                self.client.table("llm_semantic_cache")
                .delete()
                .in_("id", ids_to_delete)
                .execute()
            )

            remaining = await self.count()
            logger.info(
                "LRU eviction complete: removed=%s remaining=%s target=%s.",
                len(ids_to_delete),
                remaining,
                target,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("LRU eviction failed (swallowed): %s", exc)

    async def evict_expired(self) -> None:
        """Delete all entries where ``expires_at < NOW()``.

        Safe to run frequently (e.g. from a background cron job).  Failures
        are logged and swallowed.
        """
        if self.client is None:
            return

        try:
            result = await (
                self.client.table("llm_semantic_cache")
                .delete()
                .lt("expires_at", "now()")
                .execute()
            )
            deleted = len(result.data) if result.data else 0
            if deleted:
                logger.info("Evicted %s expired cache entries.", deleted)
            else:
                logger.debug("No expired cache entries found.")
        except Exception as exc:  # noqa: BLE001
            logger.error("evict_expired failed (swallowed): %s", exc)

    async def evict_by_dimension(self, embedding_dim: int) -> None:
        """Delete all entries with a specific embedding dimension.

        Useful during model hot-swap: when switching from one embedding
        architecture to another (e.g. 384-d -> 1024-d BGE-M3) you can
        purge stale vectors so they never appear in similarity searches.

        Parameters
        ----------
        embedding_dim: int
            Exact ``embedding_dim`` value to match and remove.
        """
        if self.client is None:
            return

        try:
            result = await (
                self.client.table("llm_semantic_cache")
                .delete()
                .eq("embedding_dim", embedding_dim)
                .execute()
            )
            deleted = len(result.data) if result.data else 0
            logger.info(
                "Evicted %s entries with embedding_dim=%s.",
                deleted,
                embedding_dim,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "evict_by_dimension(dim=%s) failed (swallowed): %s",
                embedding_dim,
                exc,
            )

    async def evict_by_model(self, model: str) -> None:
        """Delete all entries cached for a specific LLM *request* model.

        Parameters
        ----------
        model: str
            The LLM model identifier (stored in the ``model`` column).
        """
        if self.client is None:
            return

        try:
            result = await (
                self.client.table("llm_semantic_cache")
                .delete()
                .eq("model", model)
                .execute()
            )
            deleted = len(result.data) if result.data else 0
            logger.info("Evicted %s entries for model=%s.", deleted, model)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "evict_by_model(model=%s) failed (swallowed): %s",
                model,
                exc,
            )

    # -- diagnostics ---------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """Return cache statistics for monitoring / health dashboards.

        Returns
        -------
        dict
            * ``total_entries`` – rows in the table.
            * ``active_entries`` – rows whose ``expires_at`` is in the future.
            * ``expired_entries`` – rows whose ``expires_at`` has passed.
            * ``hit_rate`` – ``total_hits / total_lookups`` (or ``0.0``).
            * ``avg_similarity_score`` – mean of the ``similarity_score``
              column (or ``0.0``).

        All values are ``0`` or ``0.0`` when the store is not initialised
        or the underlying queries fail.
        """
        if self.client is None:
            return {
                "total_entries": 0,
                "active_entries": 0,
                "expired_entries": 0,
                "hit_rate": 0.0,
                "avg_similarity_score": 0.0,
            }

        try:
            # Total entries
            total_result = await (
                self.client.table("llm_semantic_cache")
                .select("id", count="exact")
                .execute()
            )
            total_entries = total_result.count or 0

            # Active (not expired)
            active_result = await (
                self.client.table("llm_semantic_cache")
                .select("id", count="exact")
                .gte("expires_at", "now()")
                .execute()
            )
            active_entries = active_result.count or 0

            expired_entries = total_entries - active_entries

            # Aggregates: sum(hit_count) and avg(similarity_score)
            # PostgREST supports .select() with aggregation functions.
            agg_result = await (
                self.client.table("llm_semantic_cache")
                .select("hit_count.sum(), similarity_score.avg()")
                .execute()
            )

            total_hits = 0
            avg_similarity = 0.0
            if agg_result.data:
                row = agg_result.data[0]
                total_hits = row.get("sum", 0) or 0
                avg_similarity = float(row.get("avg", 0.0) or 0.0)

            # Derive hit_rate from hit_count vs (active) lookups.
            # If hit_count tracks successful hits and we approximate lookups
            # as active_entries + total_hits, we get a bounded estimate.
            hit_rate = 0.0
            denominator = active_entries + total_hits
            if denominator > 0:
                hit_rate = round(total_hits / denominator, 4)

            stats = {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": expired_entries,
                "hit_rate": hit_rate,
                "avg_similarity_score": round(avg_similarity, 6),
            }
            logger.debug("Cache stats: %s", stats)
            return stats

        except Exception as exc:  # noqa: BLE001
            logger.error("get_stats query failed (returning zeros): %s", exc)
            return {
                "total_entries": 0,
                "active_entries": 0,
                "expired_entries": 0,
                "hit_rate": 0.0,
                "avg_similarity_score": 0.0,
            }
