"""Prometheus metrics for semantic cache (issue #1427).

Includes:
    - Layer 0 (Cipher Memory) cache metrics
    - Layer 1 (pgvector) cache metrics
    - LRU eviction metrics
    - CHIT bus invalidation metrics
    - BGE-M3 hybrid scoring metrics (Phase 2)

Usage:
    from pmoves.services.semantic_cache.metrics import (
        cache_hits_total,
        cache_misses_total,
        cache_lookup_duration,
    )

    cache_hits_total.labels(model="bge-m3").inc()
    cache_lookup_duration.labels(status="hit").observe(0.005)

Naming convention:
    All metrics follow the pmoves_* prefix per PMOVES conventions.
"""

from prometheus_client import Counter, Histogram, Gauge

# ---------------------------------------------------------------------------
# Layer 1 (pgvector) -- required by issue #1427 acceptance criteria
# ---------------------------------------------------------------------------

cache_hits_total = Counter(
    "pmoves_cache_hits_total",
    "Total semantic cache hits (Layer 1: pgvector)",
    ["model"],
)

cache_misses_total = Counter(
    "pmoves_cache_misses_total",
    "Total semantic cache misses (Layer 1: pgvector)",
    ["model"],
)

cache_similarity_score = Gauge(
    "pmoves_cache_similarity_score",
    "Similarity score of last cache hit",
    ["model"],
)

# ---------------------------------------------------------------------------
# Layer 0 (Cipher Memory)
# ---------------------------------------------------------------------------

cache_layer0_hits_total = Counter(
    "pmoves_cache_layer0_hits_total",
    "Total Layer 0 cache hits (Cipher Memory)",
    ["model"],
)

cache_layer0_misses_total = Counter(
    "pmoves_cache_layer0_misses_total",
    "Total Layer 0 cache misses (Cipher Memory)",
    ["model"],
)

# ---------------------------------------------------------------------------
# Additional operational metrics
# ---------------------------------------------------------------------------

cache_lookup_duration = Histogram(
    "pmoves_cache_lookup_duration_seconds",
    "Time spent on cache lookup",
    ["status"],  # hit, miss, layer0_hit, layer0_miss
    buckets=(0.001, 0.003, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

cache_entries_total = Gauge(
    "pmoves_cache_entries_total",
    "Total entries in semantic cache",
)

cache_embedding_model = Gauge(
    "pmoves_cache_embedding_model_info",
    "Current embedding model info (value=1 always, labels carry metadata)",
    ["model", "dimensions"],
)

# ---------------------------------------------------------------------------
# LRU Eviction metrics
# ---------------------------------------------------------------------------

cache_evictions_total = Counter(
    "pmoves_cache_evictions_total",
    "Total cache entries evicted (LRU)",
    ["reason"],  # lru, ttl, invalidation
)

cache_size_bytes = Gauge(
    "pmoves_cache_size_bytes",
    "Estimated cache storage size in bytes",
)

# ---------------------------------------------------------------------------
# CHIT Bus Invalidation metrics
# ---------------------------------------------------------------------------

cache_invalidations_total = Counter(
    "pmoves_cache_invalidations_total",
    "Total cache invalidations via CHIT bus",
    ["source"],  # model_change, embedding_swap, manual
)

# ---------------------------------------------------------------------------
# BGE-M3 Hybrid metrics (Phase 2)
# ---------------------------------------------------------------------------
# These gauges capture the three-component similarity score produced by
# BGE-M3 (dense + sparse + ColBERT) when it is the active embedding model.

cache_hybrid_dense_score = Gauge(
    "pmoves_cache_hybrid_dense_score",
    "BGE-M3 dense similarity score of last hit",
    ["model"],
)

cache_hybrid_sparse_score = Gauge(
    "pmoves_cache_hybrid_sparse_score",
    "BGE-M3 sparse similarity score of last hit",
    ["model"],
)

cache_hybrid_colbert_score = Gauge(
    "pmoves_cache_hybrid_colbert_score",
    "BGE-M3 ColBERT similarity score of last hit",
    ["model"],
)
