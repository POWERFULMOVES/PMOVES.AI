# Issue #1427: Semantic Caching Layer for LLM Inference
## Implementation Specification

**Date**: 2026-07-02
**Status**: Draft
**Priority**: P0 — blocks token cost governance and production scale

---

## 1. Executive Summary

PMOVES.AI needs a semantic caching layer that intercepts LLM queries, embeds them, and checks pgvector for semantically similar cached responses before forwarding to TensorZero. This catches paraphrased queries ("what time is it" vs "what is the time") that exact-match caching misses.

TensorZero already has **exact-match** caching via ClickHouse/Valkey, but cannot do **similarity-based** matching. This spec adds a pgvector-powered semantic cache that complements (not replaces) TensorZero's built-in cache.

**Architecture**: Thin FastAPI sidecar proxy that sits between Agent Zero and TensorZero, intercepts `POST /openai/v1/chat/completions`, embeds the last user message, queries Supabase pgvector for similar cached queries, and returns cached responses on hit. On miss, forwards to TensorZero and stores the response.

**Estimated effort**: 3-5 days for MVP (Phase 1), 2-3 days for production hardening (Phase 2).

---

## 2. Architecture Diagram (Text)

~~~
                          PMOVES.AI LLM Inference Path

  ┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
  │   Agent Zero    │     │   Semantic Cache Proxy   │     │  TensorZero Gateway │
  │   (LLM Client)  │────▶│   (FastAPI :3001)        │────▶│   (:3000)           │
  │                 │     │                          │     │                     │
  │ POST /openai/   │     │  1. Extract query text    │     │  Exact-match cache  │
  │ v1/chat/        │     │  2. Embed (nomic-embed)   │     │  (ClickHouse/Valkey)│
  │ completions     │     │  3. pgvector cosine search │     │                     │
  │                 │     │  4a. HIT → return cached  │     │  Routes to:         │
  │ model=tensorzero│     │  4b. MISS → forward      │────▶│  - Ollama (local)   │
  │ ::function::... │     │                          │     │  - Z.AI cloud       │
  │                 │     │  5. Store response +     │     │  - OpenAI           │
  │                 │◀────│     embedding on miss    │◀────│  - OpenRouter       │
  └─────────────────┘     └──────────────────────────┘     └─────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │   Supabase PG    │
                          │   (pgvector)     │
                          │                  │
                          │ llm_semantic_    │
                          │   cache table    │
                          │                  │
                          │ HNSW index on    │
                          │ query_embedding  │
                          │ vector(768)      │
                          └──────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  Prometheus :9090│
                          │                  │
                          │ pmoves_cache_    │
                          │   hits_total     │
                          │ pmoves_cache_    │
                          │   misses_total   │
                          │ pmoves_cache_    │
                          │   similarity_    │
                          │   score          │
                          └──────────────────┘
~~~

### Two-Layer Cache Strategy

~~~
Query arrives at Agent Zero
     │
     ▼
Layer 1: Semantic Cache Proxy (:3001)
     ├── Embeds query with nomic-embed-text (768d)
     ├── Cosine similarity search via pgvector (<=> operator)
     ├── Threshold: distance < 0.10 (similarity > 0.90)
     ├── HIT → return cached response (sub-5ms)
     └── MISS → forward to TensorZero
              │
              ▼
Layer 2: TensorZero Built-in Cache
     ├── Exact-match on full request params
     ├── HIT → return (0 tokens reported)
     └── MISS → forward to provider (Ollama/Z.AI/OpenAI)
                   │
                   ▼
              Provider returns response
                   │
                   ▼
              Store in BOTH caches:
              - Semantic cache: query embedding + response
              - TensorZero cache: exact request + response
~~~

---

## 3. Key Design Decisions

### 3.1 Embedding Model: `nomic-embed-text` (768 dimensions)

**Rationale**:
- Already configured in TensorZero: `archon_nomic_embed_local`
- 768 dimensions: sweet spot for semantic caching (small enough for fast HNSW search, large enough for quality)
- Available locally via Ollama: `http://pmoves-ollama:11434/v1`
- No external API dependency — works in island/offline mode
- Latency: ~20-50ms per embedding on GPU, ~100-200ms on CPU

### 3.2 Similarity Threshold: cosine distance < 0.10 (similarity > 0.90)

**Rationale**:
- 0.90 similarity catches paraphrases while minimizing false positives
- Configurable per model via `CACHE_SIMILARITY_THRESHOLD` env var
- Start conservative (0.10), can loosen to 0.15 if hit rate < 30%

### 3.3 Cache Only Single-Query Requests

Per acceptance criteria: no caching for multi-turn conversations.

**Filter rule**: Cache only requests where:
- `messages` array has ≤ 3 messages (system + 1 user, or just 1 user)
- No `tools` or `functions` in the request
- `temperature` ≤ 0.3 (deterministic-ish)
- No conversation ID or thread context headers

### 3.4 TTL: Configurable Per Model

| Model Type | Default TTL | Rationale |
|-----------|-------------|----------|
| Chat (qwen3.5, lfm2) | 5 minutes | Dynamic responses, short relevance window |
| Embeddings | 1 hour | Deterministic output, high reuse value |
| Code generation | 1 hour | Deterministic for same input |
| Research/analysis | 30 minutes | Moderate reuse window |

Configurable via `CACHE_TTL_CHAT_SECS=300`, `CACHE_TTL_EMBED_SECS=3600`.

---

## 4. Database Schema

### 4.1 Migration: `pmoves/supabase/migrations/20260702000000_semantic_cache.sql`

~~~sql
-- Issue #1427: Semantic Caching Layer for LLM Inference
-- Uses pgvector for cosine similarity search on cached query embeddings

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS llm_semantic_cache (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash        VARCHAR(64) UNIQUE NOT NULL,
    query_text        TEXT NOT NULL,
    query_embedding   vector(768) NOT NULL,
    response_text     TEXT NOT NULL,
    response_model    VARCHAR(100) NOT NULL,
    request_model     VARCHAR(100) NOT NULL,
    provider          VARCHAR(50) NOT NULL DEFAULT 'tensorzero',
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    similarity_threshold FLOAT DEFAULT 0.10,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL,
    last_accessed     TIMESTAMPTZ DEFAULT NOW(),
    hit_count         INTEGER DEFAULT 0
);

-- HNSW index for production-grade vector search
CREATE INDEX idx_cache_embedding_hnsw
    ON llm_semantic_cache
    USING hnsw (query_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Auxiliary indexes
CREATE INDEX idx_cache_hash ON llm_semantic_cache(query_hash);
CREATE INDEX idx_cache_expires ON llm_semantic_cache(expires_at);
CREATE INDEX idx_cache_model ON llm_semantic_cache(request_model, provider);

-- Analytics view for dashboard
CREATE VIEW v_cache_stats AS
SELECT
    request_model,
    provider,
    COUNT(*) AS total_entries,
    SUM(hit_count) AS total_hits,
    AVG(hit_count) AS avg_hits_per_entry,
    COUNT(*) FILTER (WHERE expires_at > NOW()) AS active_entries,
    COUNT(*) FILTER (WHERE expires_at < NOW()) AS expired_entries
FROM llm_semantic_cache
GROUP BY request_model, provider;

-- Enable RLS (cache is system-managed, not user-facing)
ALTER TABLE llm_semantic_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY cache_service_write ON llm_semantic_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);
~~~

---

## 5. Files to Create / Modify

### 5.1 New Files

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `pmoves/services/semantic-cache/Dockerfile` | Container image for cache proxy | ~25 |
| `pmoves/services/semantic-cache/main.py` | FastAPI app: intercept, embed, lookup, forward | ~200 |
| `pmoves/services/semantic-cache/cache_store.py` | pgvector CRUD: lookup, insert, evict | ~150 |
| `pmoves/services/semantic-cache/metrics.py` | Prometheus metrics definitions | ~40 |
| `pmoves/services/semantic-cache/config.py` | Env-driven configuration | ~50 |
| `pmoves/services/semantic-cache/requirements.txt` | Python dependencies | ~12 |
| `pmoves/services/semantic-cache/tests/test_cache.py` | Unit tests for cache lookup/store | ~150 |
| `pmoves/services/semantic-cache/tests/test_proxy.py` | Integration test: full request flow | ~100 |
| `pmoves/supabase/migrations/20260702000000_semantic_cache.sql` | Database migration | ~50 |
| `pmoves/tests/smoke/test_semantic_cache.py` | Smoke test for cache service | ~60 |
| `pmoves/docker-compose.cache.yml` | Compose overlay for cache service | ~50 |

### 5.2 Files to Modify

| File | Change | Effort |
|------|--------|--------|
| `pmoves/env.shared` | Add cache config vars (CACHE_PROXY_PORT, CACHE_SIMILARITY_THRESHOLD, etc.) | 15 min |
| `pmoves/env.shared.example` | Document new vars | 15 min |
| `pmoves/Makefile` | Add `cache-up`, `cache-down`, `cache-stats` targets | 30 min |
| `pmoves/docker-compose.yml` | Reference cache overlay in base compose | 15 min |
| Agent Zero env (compose) | Point `A0_SET_chat_model_api_base` to cache proxy when enabled | 15 min |
| `pmoves/tensorzero/config/tensorzero.toml` | (Optional) Enable TensorZero built-in cache as Layer 2 | 30 min |
| `pmoves/docs/SERVICE_DOCS_MATRIX.md` | Add semantic-cache service entry | 10 min |

---

## 6. Core Implementation Outline

### 6.1 `main.py` — Cache Proxy Entry Point

~~~python
"""
Semantic Cache Proxy for PMOVES.AI LLM Inference
Issue #1427: Intercepts OpenAI-compatible requests, checks pgvector
for semantically similar cached queries, returns on hit or forwards to TensorZero.
"""

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .cache_store import CacheStore
from .config import settings
from .metrics import (
    cache_hits_total, cache_misses_total,
    cache_similarity_score, cache_lookup_duration,
)

logger = logging.getLogger(__name__)

# Shared clients
http_client: httpx.AsyncClient
embed_client: httpx.AsyncClient  # Ollama embedding endpoint
cache: CacheStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, embed_client, cache
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    embed_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    cache = CacheStore(settings.supabase_url, settings.supabase_key)
    await cache.init()
    yield
    await http_client.aclose()
    await embed_client.aclose()
    await cache.close()


app = FastAPI(title="PMOVES Semantic Cache", lifespan=lifespan)


@app.post("/openai/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Intercept chat completion requests with semantic cache lookup."""
    body = await request.json()

    # --- Filter: only cache cacheable requests ---
    if not _is_cacheable(body):
        return await _forward_passthrough(body)

    query_text = _extract_query_text(body)
    model = body.get("model", "unknown")

    # --- Step 1: Embed the query ---
    embedding = await _embed_query(query_text)
    if embedding is None:
        # Embedding failed — fail-open to TensorZero
        return await _forward_passthrough(body)

    # --- Step 2: Semantic cache lookup ---
    t0 = time.monotonic()
    cached = await cache.lookup(embedding, model, settings.similarity_threshold)
    duration = time.monotonic() - t0
    cache_lookup_duration.labels(status="hit" if cached else "miss").observe(duration)

    if cached:
        # --- HIT: return cached response ---
        cache_hits_total.labels(model=model).inc()
        cache_similarity_score.labels(model=model).set(cached["similarity_score"])
        await cache.increment_hit(cached["id"])
        return _build_cached_response(cached, body)

    # --- MISS: forward to TensorZero ---
    cache_misses_total.labels(model=model).inc()
    response = await _forward_and_capture(body)

    # --- Store in cache (async, non-blocking) ---
    if response and response.status_code == 200:
        asyncio.create_task(
            cache.store(
                query_text=query_text,
                query_embedding=embedding,
                response_text=response.text,
                model=model,
                ttl_seconds=settings.cache_ttl_chat_secs,
            )
        )

    return response


@app.post("/openai/v1/embeddings")
async def embeddings(request: Request) -> Response:
    """Embeddings endpoint — forward to TensorZero (higher TTL caching optional)."""
    return await _forward_passthrough(await request.json(), path="/openai/v1/embeddings")


@app.get("/metrics")
async def prometheus_metrics():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    return {"status": "ok", "cache_entries": await cache.count()}


# --- Helpers ---

def _is_cacheable(body: dict) -> bool:
    """Only cache single-query, low-temperature, tool-free requests."""
    messages = body.get("messages", [])
    if len(messages) > 3:
        return False
    if body.get("tools") or body.get("functions"):
        return False
    if body.get("temperature", 0.0) > settings.max_cacheable_temperature:
        return False
    # Must have at least one user message
    if not any(m.get("role") == "user" for m in messages):
        return False
    return True


def _extract_query_text(body: dict) -> str:
    """Extract the last user message as the query text for embedding."""
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multi-modal: extract text parts
                return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
            return content
    return ""


async def _embed_query(text: str) -> list[float] | None:
    """Embed query using Ollama nomic-embed-text via TensorZero."""
    try:
        resp = await embed_client.post(
            f"{settings.tensorzero_url}/openai/v1/embeddings",
            json={
                "model": settings.embed_model,
                "input": text,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"Embedding failed, fail-open: {e}")
        return None


async def _forward_passthrough(body: dict, path: str = None) -> Response:
    """Forward request to TensorZero without caching."""
    target = f"{settings.tensorzero_url}{path or '/openai/v1/chat/completions'}"
    resp = await http_client.post(target, json=body)
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type="application/json")


async def _forward_and_capture(body: dict) -> httpx.Response | None:
    """Forward to TensorZero and return the raw response for caching."""
    try:
        resp = await http_client.post(
            f"{settings.tensorzero_url}/openai/v1/chat/completions",
            json=body,
        )
        return resp
    except Exception as e:
        logger.error(f"TensorZero forward failed: {e}")
        return None


def _build_cached_response(cached: dict, original_body: dict) -> JSONResponse:
    """Build an OpenAI-compatible response from cached data."""
    return JSONResponse(content=json.loads(cached["response_text"]))
~~~

### 6.2 `cache_store.py` — pgvector CRUD

~~~python
"""pgvector-backed semantic cache store using Supabase."""

import hashlib
import logging
from typing import Any
from postgrest import AsyncPostgrestClient

logger = logging.getLogger(__name__)


class CacheStore:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.url = supabase_url
        self.key = supabase_key
        self.client: AsyncPostgrestClient | None = None

    async def init(self):
        self.client = AsyncPostgrestClient(f"{self.url}/rest/v1", headers={
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        })

    async def close(self):
        if self.client:
            await self.client.aclose()

    async def lookup(self, embedding: list[float], model: str,
                     threshold: float) -> dict[str, Any] | None:
        """Semantic cache lookup via pgvector cosine similarity."""
        emb_str = f"[{','.join(str(x) for x in embedding)}]"
        result = await self.client.rpc("cache_semantic_lookup", {
            "p_embedding": emb_str,
            "p_model": model,
            "p_threshold": threshold,
        }).execute()
        if result.data:
            row = result.data[0]
            return {
                "id": row["id"],
                "response_text": row["response_text"],
                "similarity_score": row["similarity_score"],
            }
        return None

    async def store(self, query_text: str, query_embedding: list[float],
                    response_text: str, model: str, ttl_seconds: int):
        """Store a new cache entry."""
        query_norm = query_text.strip().lower()
        query_hash = hashlib.sha256(query_norm.encode()).hexdigest()
        emb_str = f"[{','.join(str(x) for x in query_embedding)}]"
        await self.client.rpc("cache_semantic_insert", {
            "p_hash": query_hash,
            "p_text": query_text,
            "p_embedding": emb_str,
            "p_response": response_text,
            "p_model": model,
            "p_ttl_secs": ttl_seconds,
        }).execute()

    async def increment_hit(self, cache_id: str):
        """Increment hit count for a cache entry."""
        await self.client.table("llm_semantic_cache").update({
            "hit_count": "+1",  # postgrest increment via raw SQL preferred
        }).eq("id", cache_id).execute()

    async def count(self) -> int:
        """Return total cache entry count for health checks."""
        result = await self.client.table("llm_semantic_cache").select(
            "id", count="exact"
        ).execute()
        return result.count or 0
~~~

### 6.3 Migration RPC Functions (add to migration SQL)

~~~sql
-- RPC: Semantic cache lookup
CREATE OR REPLACE FUNCTION cache_semantic_lookup(
    p_embedding vector(768),
    p_model VARCHAR,
    p_threshold FLOAT DEFAULT 0.10
) RETURNS TABLE (
    id UUID,
    response_text TEXT,
    similarity_score FLOAT
) AS $$
    SELECT
        id,
        response_text,
        1 - (query_embedding <=> p_embedding) AS similarity_score
    FROM llm_semantic_cache
    WHERE query_embedding <=> p_embedding < p_threshold
      AND request_model = p_model
      AND expires_at > NOW()
    ORDER BY query_embedding <=> p_embedding
    LIMIT 1;
$$ LANGUAGE sql STABLE;

-- RPC: Semantic cache insert
CREATE OR REPLACE FUNCTION cache_semantic_insert(
    p_hash VARCHAR,
    p_text TEXT,
    p_embedding vector(768),
    p_response TEXT,
    p_model VARCHAR,
    p_ttl_secs INTEGER DEFAULT 300
) RETURNS void AS $$
    INSERT INTO llm_semantic_cache
        (query_hash, query_text, query_embedding, response_text,
         request_model, expires_at)
    VALUES
        (p_hash, p_text, p_embedding, p_response, p_model, NOW() + (p_ttl_secs || ' seconds')::INTERVAL)
    ON CONFLICT (query_hash) DO UPDATE
        SET response_text = EXCLUDED.response_text,
            query_embedding = EXCLUDED.query_embedding,
            expires_at = EXCLUDED.expires_at,
            hit_count = 0;
$$ LANGUAGE sql;
~~~

### 6.4 `metrics.py` — Prometheus Instrumentation

~~~python
"""Prometheus metrics for semantic cache (issue #1427)."""

from prometheus_client import Counter, Histogram, Gauge

# Required by issue acceptance criteria
cache_hits_total = Counter(
    "pmoves_cache_hits_total",
    "Total semantic cache hits",
    ["model"],
)

cache_misses_total = Counter(
    "pmoves_cache_misses_total",
    "Total semantic cache misses",
    ["model"],
)

cache_similarity_score = Gauge(
    "pmoves_cache_similarity_score",
    "Similarity score of last cache hit",
    ["model"],
)

# Additional operational metrics
cache_lookup_duration = Histogram(
    "pmoves_cache_lookup_duration_seconds",
    "Time spent on cache lookup",
    ["status"],  # hit, miss
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

cache_entries_total = Gauge(
    "pmoves_cache_entries_total",
    "Total entries in semantic cache",
)
~~~

### 6.5 `config.py` — Environment Configuration

~~~python
"""Configuration for semantic cache proxy."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Connection
    tensorzero_url: str = "http://tensorzero-gateway:3000"
    supabase_url: str = "http://supabase:8000"
    supabase_key: str = ""

    # Embedding
    embed_model: str = "tensorzero::embedding_model_name::archon_nomic_embed_local"
    embed_dimensions: int = 768

    # Cache behavior
    similarity_threshold: float = 0.10  # cosine distance; similarity > 0.90
    cache_ttl_chat_secs: int = 300      # 5 min default for chat
    cache_ttl_embed_secs: int = 3600    # 1 hour for embeddings
    max_cacheable_temperature: float = 0.3

    # Proxy
    proxy_port: int = 3001

    class Config:
        env_prefix = "CACHE_"

settings = Settings()
~~~

### 6.6 `docker-compose.cache.yml` — Service Overlay

~~~yaml
# Semantic Cache Proxy for issue #1427
# Usage: docker compose -f docker-compose.yml -f docker-compose.cache.yml up

services:
  semantic-cache:
    build:
      context: ./services/semantic-cache
      dockerfile: Dockerfile
    container_name: pmoves-semantic-cache
    restart: unless-stopped
    ports:
      - "${CACHE_PROXY_PORT:-3001}:3001"
    environment:
      - CACHE_TENSORZERO_URL=http://tensorzero-gateway:3000
      - CACHE_SUPABASE_URL=${SUPABASE_URL:-http://supabase:8000}
      - CACHE_SUPABASE_KEY=${SUPABASE_SERVICE_KEY}
      - CACHE_SIMILARITY_THRESHOLD=${CACHE_SIMILARITY_THRESHOLD:-0.10}
      - CACHE_CACHE_TTL_CHAT_SECS=${CACHE_TTL_CHAT_SECS:-300}
      - CACHE_CACHE_TTL_EMBED_SECS=${CACHE_TTL_EMBED_SECS:-3600}
      - CACHE_EMBED_MODEL=tensorzero::embedding_model_name::archon_nomic_embed_local
      - CACHE_MAX_CACHEABLE_TEMPERATURE=0.3
    depends_on:
      - tensorzero-gateway
    networks:
      - pmoves-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Override Agent Zero to route through cache proxy
  agent-zero:
    environment:
      - A0_SET_chat_model_api_base=http://semantic-cache:3001/openai/v1
      - A0_SET_util_model_api_base=http://semantic-cache:3001/openai/v1
      - A0_SET_browser_model_api_base=http://semantic-cache:3001/openai/v1
~~~

---

## 7. Env Variables to Add (`env.shared`)

~~~bash
# ─── Semantic Cache (Issue #1427) ──────────────────────────────────
CACHE_PROXY_PORT=3001
CACHE_SIMILARITY_THRESHOLD=0.10
CACHE_TTL_CHAT_SECS=300
CACHE_TTL_EMBED_SECS=3600
CACHE_EMBED_MODEL=tensorzero::embedding_model_name::archon_nomic_embed_local
CACHE_MAX_CACHEABLE_TEMPERATURE=0.3
# Set to true to route Agent Zero through the cache proxy
CACHE_ENABLED=false
~~~

---

## 8. Makefile Targets

~~~makefile
# Semantic Cache (Issue #1427)
cache-up:
	@echo "Starting semantic cache proxy..."
	docker compose -f docker-compose.yml -f docker-compose.cache.yml up -d semantic-cache
	@echo "Cache proxy running on :$$(CACHE_PROXY_PORT 2>/dev/null || echo 3001)"

cache-down:
	docker compose -f docker-compose.yml -f docker-compose.cache.yml stop semantic-cache

cache-stats:
	@echo "Cache statistics:"
	docker exec pmoves-semantic-cache curl -s http://localhost:3001/health | jq .
	@echo "\nPrometheus metrics:"
	curl -s http://localhost:3001/metrics | grep pmoves_cache

cache-evict:
	@echo "Evicting expired cache entries..."
	docker exec pmoves-semantic-cache python -c "import asyncio; from cache_store import CacheStore; ..."
~~~

---

## 9. Phased Delivery Plan

### Phase 1: MVP — Core Cache (3-5 days)

**Goal**: Working semantic cache proxy with pgvector lookup, forward-to-TensorZero, and Prometheus metrics.

| Day | Tasks |
|-----|-------|
| 1 | Create migration SQL (schema + HNSW index + RPC functions). Create `services/semantic-cache/` scaffold: `config.py`, `metrics.py`, `requirements.txt`, `Dockerfile`. |
| 2 | Implement `cache_store.py` (pgvector CRUD via Supabase REST). Implement `main.py` (FastAPI proxy: intercept, embed, lookup, forward, store). |
| 3 | Create `docker-compose.cache.yml`. Add env vars to `env.shared`. Add Makefile targets. Write unit tests (`test_cache.py`). |
| 4 | Write integration test (`test_proxy.py`). Wire up Agent Zero env override. Manual smoke test: verify hit/miss flow with real queries. |
| 5 | Buffer: fix issues from smoke testing. Add smoke test to `pmoves/tests/smoke/`. Update `SERVICE_DOCS_MATRIX.md`. |

**Phase 1 Deliverables**:
- [x] Migration applied to Supabase
- [x] Cache proxy container builds and runs
- [x] Agent Zero can route through cache (toggle via `CACHE_ENABLED`)
- [x] Prometheus metrics endpoint live at `:3001/metrics`
- [x] Cache hit rate visible after repeated queries

### Phase 2: Production Hardening (2-3 days)

**Goal**: Circuit breaker, TTL eviction cron, observability dashboard, threshold tuning.

| Task | Detail |
|------|--------|
| Circuit breaker | If pgvector lookup fails 3x consecutively, fail-open to passthrough (CIRCUIT_BREAKER_PRINCIPLE). Log degradation, expose `/health` degradation state. |
| TTL eviction | Supabase pg_cron job: `SELECT cron.schedule('cache-evict', '*/15 * * * *', 'DELETE FROM llm_semantic_cache WHERE expires_at < NOW()');` |
| Grafana dashboard | Cache hit rate panel, similarity score histogram, lookup latency p50/p95, entry count over time. |
| Threshold tuning | Run for 48h with threshold=0.10, analyze hit rate. If <30%, loosen to 0.15. If false positives detected, tighten to 0.07. |
| TensorZero Layer 2 | Enable `[gateway.cache]` in tensorzero.toml for exact-match cache as second layer. Configure Valkey or ClickHouse backend. |
| Cache invalidation hook | On model config change in `agent_registry.yaml`, emit NATS event to flush cache entries for that model. |

### Phase 3: Fleet Integration (future, 3-5 days)

**Goal**: Cross-node cache sharing for fleet topology.

| Task | Detail |
|------|--------|
| Shared cache table | All nodes point to same Supabase instance → automatic shared cache. No code change needed. |
| Embedding model sync | Ensure all nodes use same `nomic-embed-text` version (embedding model change = full cache flush). |
| Fleet cache metrics | Aggregate `pmoves_cache_hits_total` across nodes in Prometheus federation. |
| Semantic cache for embeddings | Extend proxy to cache `/openai/v1/embeddings` responses (1h TTL, exact-match since embeddings are deterministic). |

---

## 10. Acceptance Criteria Traceability

| Issue Requirement | Implementation |
|-------------------|----------------|
| Cache hit rate >30% on repeated queries | Phase 1 + Phase 2 threshold tuning |
| Cache miss falls through to LLM inference | `_forward_passthrough()` in `main.py` — always forwards on miss |
| `pmoves_cache_hits_total` metric | `metrics.py` Counter, exposed at `/metrics` |
| `pmoves_cache_misses_total` metric | `metrics.py` Counter, exposed at `/metrics` |
| `pmoves_cache_similarity_score` metric | `metrics.py` Gauge, set on each hit |
| TTL configurable per model | `CACHE_TTL_CHAT_SECS` / `CACHE_TTL_EMBED_SECS` env vars, per-model config in Phase 2 |
| No cache for multi-turn conversations | `_is_cacheable()` filter: >3 messages or has tools → passthrough |
| Semantic cache using pgvector | `llm_semantic_cache` table with HNSW index, `<=>` operator |
| Integration: TensorZero gateway | Proxy forwards misses to `http://tensorzero-gateway:3000` |
| Cache invalidation on config changes | Phase 2: NATS event hook for model config changes |

---

## 11. Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Embedding model unavailable (Ollama down) | All queries bypass cache (fail-open) | Circuit breaker in Phase 2; health check degrades gracefully |
| pgvector latency spikes under load | Cache lookup adds latency to all requests | HNSW index (<5ms p95 expected); circuit breaker to bypass on SLO breach |
| False positive semantic matches | Wrong cached response returned | Conservative threshold (0.10); Phase 2 tuning; similarity_score metric for monitoring |
| Supabase connection failure | Cache unavailable | Fail-open to passthrough; health check reports degraded state |
| Cache poisoning (stored wrong response) | Corrupt responses served | Only store on HTTP 200 from TensorZero; Phase 2 adds response validation |
| Storage growth | Supabase storage fills | TTL eviction cron + `hit_count=0 AND created_at < 7 days` cleanup |

---

## 12. Dependencies

~~~text
# semantic-cache/requirements.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
pydantic-settings>=2.1.0
postgrest-py>=0.13.0
prometheus-client>=0.19.0
python-dotenv>=1.0.0
~~~

---

## 13. Summary

| Dimension | Decision |
|-----------|----------|
| **Architecture** | FastAPI sidecar proxy (:3001) between Agent Zero and TensorZero (:3000) |
| **Vector store** | Supabase pgvector, `vector(768)` with HNSW index |
| **Embedding model** | `nomic-embed-text` (768d) via Ollama — local, no API dependency |
| **Similarity threshold** | cosine distance < 0.10 (similarity > 0.90), configurable |
| **TTL** | 5 min chat, 1 hour embeddings, configurable per model |
| **Metrics** | 3 Prometheus counters/gauges per issue spec + lookup latency histogram |
| **Failure mode** | Fail-open: any cache error → passthrough to TensorZero |
| **Phase 1 effort** | 3-5 days (working MVP with tests) |
| **Phase 2 effort** | 2-3 days (circuit breaker, cron eviction, Grafana, TensorZero Layer 2) |
| **Phase 3 effort** | 3-5 days (fleet-wide shared cache, embedding cache) |
