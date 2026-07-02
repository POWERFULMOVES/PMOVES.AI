#!/usr/bin/env python3
"""Prometheus metrics for the PMOVES semantic cache.

Exposes counters and histograms at /metrics for observability.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# Counters
cache_hits_total = Counter(
    "pmoves_cache_hits_total",
    "Total semantic cache hits",
)

cache_misses_total = Counter(
    "pmoves_cache_misses_total",
    "Total semantic cache misses",
)

cache_errors_total = Counter(
    "pmoves_cache_errors_total",
    "Total cache errors (fail-open events)",
)

# Histograms
cache_similarity_score = Histogram(
    "pmoves_cache_similarity_score",
    "Distribution of cosine similarity scores for cache hits",
    buckets=(0.80, 0.85, 0.90, 0.92, 0.94, 0.96, 0.98, 0.99, 1.0),
)

cache_latency_seconds = Histogram(
    "pmoves_cache_latency_seconds",
    "Cache lookup + store latency in seconds",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
