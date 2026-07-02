# Issue #1427: Semantic Caching Layer for LLM Inference
## Implementation Specification

**Date**: 2026-07-02
**Status**: Draft
**Priority**: P0 — blocks token cost governance and production scale

---

## 1. Executive Summary

PMOVES.AI needs a semantic caching layer that intercepts LLM queries, embeds them, and checks pgvector for semantically similar cached responses before forwarding to TensorZero. This catches paraphrased queries ("what time is it" vs "what is the time") that exact-match caching misses.

TensorZero already has **exact-match** caching via ClickHouse/Valkey, but cannot do **similarity-based** matching. This spec adds a pgvector-powered semantic cache that complements (not replaces) TensorZero's built-in cache.

**Architecture**: Thin FastAPI sidecar proxy that sits between Agent Zero and TensorZero, intercepts `POST /openai/v1/chat/completions`, embeds the last user message via Hi-RAG Gateway v2, checks Cipher memory (Layer 0) and Supabase pgvector (Layer 1) for similar cached queries, and returns cached responses on hit. On miss, forwards to TensorZero and stores the response in both pgvector and Cipher.

**Estimated effort**: 3-5 days for MVP (Phase 1), 2-3 days for production hardening (Phase 2).

---

## 2. Architecture Diagram (Text)

~~~
                          PMOVES.AI LLM Inference Path (Updated)

  ┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
  │   Agent Zero    │     │   Semantic Cache Proxy   │     │  TensorZero Gateway │
  │   (LLM Client)  │────▶│   (FastAPI :3001)        │────▶│   (:3000)           │
  │                 │     │                          │     │                     │
  │ POST /openai/   │     │  Layer 0: Cipher Memory  │     │  Exact-match cache  │
  │ v1/chat/        │     │    pre-check (KG search) │     │  (ClickHouse/Valkey)│
  │ completions     │     │  Layer 1: pgvector HNSW  │     │                     │
  │                 │     │    cosine similarity     │     │  Routes to:         │
  │ model=tensorzero│     │  4a. HIT → return cached  │     │  - Ollama (local)   │
  │ ::function::... │     │  4b. MISS → forward      │────▶│  - Z.AI cloud       │
  │                 │     │                          │     │  - OpenAI           │
  │                 │     │  Embedding generation    │     │  - OpenRouter       │
  │                 │◀────│  routed to Hi-RAG GW v2  │◀────│                     │
  └─────────────────┘     └──────────────────────────┘     └─────────────────────┘
                            │       │         │
                     ┌──────┘       │         └──────────────┐
                     ▼              ▼                        ▼
           ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
           │  Cipher Memory │  │   Supabase PG    │  │  Hi-RAG Gateway v2   │
           │  (Qdrant)      │  │   (pgvector)     │  │  (:8086/:8087)       │
           │                │  │                  │  │                      │
           │ Layer 0:       │  │ Layer 1:         │  │ Embedding Backend:   │
           │  KG semantic   │  │  llm_semantic_   │  │  BGE-M3 (1024d       │
           │  pre-check     │  │    cache table   │  │   dense+sparse+      │
           │  via           │  │                  │  │   ColBERT)           │
           │  pmoves_cipher │  │ HNSW index on    │  │  SentenceTransformer │
           │  _search       │  │ query_embedding  │  │  nomic-embed-text    │
           │                │  │                  │  │  OpenAI text-emb-3   │
           │ Store misses   │  │ Configurable     │  │                      │
           │ as memories    │  │ vector dim       │  │ Hot-swap via         │
           │ category=      │  │                  │  │  /hirag/admin/       │
           │  'context'     │  │                  │  │  embedding/model     │
           └────────────────┘  └──────────────────┘  └──────────────────────┘
                     │                                      │
                     ▼                                      ▼
           ┌──────────────────┐               ┌──────────────────────┐
           │  Prometheus :9090│               │  Provider Chain      │
           │                  │               │  (Hi-RAG fallback)   │
           │ pmoves_cache_    │               │                      │
           │   hits_total     │               │  1. Remote providers │
           │ pmoves_cache_    │               │  2. Local model      │
           │   misses_total   │               │     (SentenceTransformer│
           │ pmoves_cache_    │               │      / BGE-M3)       │
           │   similarity_    │               │                      │
           │   score          │               └──────────────────────┘
           │ pmoves_cache_    │
           │   layer0_hits    │
           │ pmoves_cache_    │
           │   layer0_misses  │
           └──────────────────┘
~~~

### Three-Layer Cache Strategy

~~~
Query arrives at Agent Zero
     │
     ▼
Layer 0: Cipher Memory Pre-Check (Qdrant Knowledge Graph)
     ├── pmoves_cipher_search on query text
     ├── Filters: category='context', tags=['semantic-cache']
     ├── Cross-session knowledge graph retrieval
     ├── HIT → return cached reasoning/context (sub-3ms)
     ├── MISS → continue to Layer 1
     └── (async: store result as Cipher memory after Layer 1 miss)
          │
          ▼
Layer 1: Semantic Cache Proxy (:3001) — pgvector
     ├── Embeds query via Hi-RAG Gateway v2 (current model)
     ├──   (BGE-M3 1024d / SentenceTransformer / nomic-embed-text / OpenAI)
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
               Store in ALL cache layers:
               - Cipher memory: query text + response (category='context', tags=['semantic-cache'])
               - Semantic cache: query embedding + response
               - TensorZero cache: exact request + response
~~~

---

## 3. Key Design Decisions

### 3.1 Embedding Model: Multi-Model Strategy (via Hi-RAG Gateway v2)

The semantic cache no longer hardcodes `nomic-embed-text` as the sole embedding model. Instead, it delegates embedding generation to **Hi-RAG Gateway v2** (`pmoves/services/hi-rag-gateway-v2/embeddings.py`), which already supports multiple embedding backends with hot-swap capability. The cache inherits whatever model Hi-RAG is currently using, ensuring embedding consistency between the cache and the RAG pipeline.

**Multi-Model Embedding Strategy Table**:

| Model | Dimensions | Output Type | Source | Use Case |
|-------|-----------|-------------|--------|----------|
| **BGE-M3** (`BAAI/bge-m3`) | 1024 dense + sparse + ColBERT | Multi-dimensional | Hi-RAG Gateway v2 (`BGEM3FlagModel`) | **Preferred**: Hybrid caching (dense for semantic, sparse for keyword, ColBERT for token-level) |
| **SentenceTransformer** (`all-MiniLM-L6-v2`) | 384 | Single dense vector | Hi-RAG Gateway v2 (default) | Lightweight, fast HNSW lookup, low memory |
| **nomic-embed-text** | 768 | Single dense vector | Ollama via TensorZero | Offline/island mode fallback, no API dependency |
| **OpenAI text-embedding-3-large** | 3072 | Single dense vector | OpenAI API via provider chain | Maximum quality in cloud mode, high-dimensional precision |

**How it works**:
- The cache proxy calls Hi-RAG Gateway v2's embedding endpoint (not local Ollama directly)
- Hi-RAG Gateway uses its currently-active model (hot-swappable via `swap_embedding_model()` or `POST /hirag/admin/embedding/model`)
- Provider chain fallback (`_embed_via_providers`) runs before local model, so cloud providers are tried first when available
- The cache stores the embedding dimension alongside each entry, enabling multi-dimension coexistence
- On embedding model change, the cache proxy can optionally flush stale entries (different dimension = invalid similarity)

### 3.2 Multi-Dimensional Embedding (BGE-M3 Hybrid Caching)

BGE-M3 (`BAAI/bge-m3` via `BGEM3FlagModel`) is unique among the supported models because it produces **three complementary vector representations** from a single input text. This enables **hybrid caching** that combines the strengths of multiple retrieval strategies:

**Three Output Vectors from BGE-M3**:

| Vector Type | Dimensions | Purpose | Cache Match Strategy |
|-------------|-----------|---------|---------------------|
| **Dense** | 1024 | Overall semantic similarity | Cosine similarity — catches paraphrases ("what time is it" ≈ "what is the time") |
| **Sparse** | Vocabulary-sized | Keyword/BM25-style overlap | Exact term matching — catches shared keywords even when semantics differ |
| **ColBERT** | Token-level (1024 × seq_len) | Token-level late interaction | Fine-grained token matching — catches queries with overlapping phrasing |

**Hybrid Cache Lookup Flow (when BGE-M3 is active)**:

~~~
1. Embed query via Hi-RAG Gateway → BGE-M3 returns (dense, sparse, colbert)
2. Dense vector search: pgvector HNSW cosine (<=> operator)
   - Catches semantically similar queries
   - Threshold: cosine distance < 0.10
3. Sparse vector search: keyword overlap scoring
   - Catches queries with significant keyword overlap
   - Threshold: BM25-style score > 0.75
4. ColBERT token-level: late interaction scoring
   - Catches queries with partial phrasing overlap
   - Threshold: MaxSim score > 0.85
5. Combine: weighted fusion of all three scores
   - final_score = w_dense * dense_sim + w_sparse * sparse_sim + w_colbert * colbert_sim
   - Default weights: w_dense=0.5, w_sparse=0.2, w_colbert=0.3
6. HIT if final_score > threshold → return cached response
   MISS if below threshold → forward to TensorZero
~~~

**Database Impact**: When BGE-M3 is active, `llm_semantic_cache` stores all three vectors:
- `query_embedding` vector(1024) — dense
- `query_sparse` jsonb — sparse term weights
- `query_colbert` vector(1024)[] — token-level vectors (ColBERT)

When a single-dimensional model (SentenceTransformer, nomic-embed-text, OpenAI) is active, only `query_embedding` is populated and the lookup falls back to standard cosine similarity.

**Implementation Note**: The cache proxy queries Hi-RAG Gateway's `/hirag/admin/embedding/model` endpoint to determine the current model, then selects the appropriate lookup strategy (hybrid vs. single-dimension).

### 3.3 Cipher Integration (Layer 0 — Knowledge Graph Pre-Check)

**Cipher Memory** (`pmoves-cipher-mcp/cipher_mcp/client.py`) provides a Qdrant-backed semantic memory store with knowledge graph capabilities. It serves as a **Layer 0 pre-check** before the pgvector Layer 1 lookup.

**Why Cipher as Layer 0**:
- **Sub-3ms latency**: Qdrant is purpose-built for vector search, lower latency than pgvector round-trip
- **Cross-session persistence**: Cipher memories survive across agent sessions — a cache hit from a previous conversation is still valid
- **Knowledge graph enrichment**: Cipher connects cached queries via `embedding_id` relationships, enabling transitive lookups (query A → similar to query B → B's cached answer applies)
- **Reasoning patterns**: `pmoves_cipher_store_reasoning` and `pmoves_cipher_reasoning_patterns` can cache the *reasoning chain* that led to an answer, not just the answer text

**Layer 0 Lookup Flow**:

~~~
1. Before embedding, search Cipher memory:
   pmoves_cipher_search(
       query=<extracted query text>,
       filters={"category": "context", "tags": ["semantic-cache"]},
       limit=1
   )
2. If Cipher returns a result with similarity > threshold:
   → Layer 0 HIT: return cached response immediately (skip pgvector entirely)
3. If Cipher returns nothing or low similarity:
   → Layer 0 MISS: proceed to Layer 1 (pgvector)
~~~

**Storing Cache Misses in Cipher**:
After a Layer 1 pgvector miss and successful TensorZero response, the cache proxy asynchronously stores the result as a Cipher memory:

~~~python
pmoves_cipher_store(
    content=f"Query: {query_text}\nResponse: {response_text}",
    category="context",
    tags=["semantic-cache", f"model:{model}"],
    metadata={
        "source": "semantic-cache-proxy",
        "query_hash": query_hash,
        "response_model": model,
        "ttl_seconds": ttl_seconds,
        "stored_at": iso_timestamp,
    }
)
~~~

This means every cache miss enriches the Cipher knowledge graph, making future Layer 0 hits more likely over time.

**Cipher Tools Used**:

| Tool | Purpose |
|------|---------|
| `pmoves_cipher_search` | Layer 0 pre-check: search for similar cached queries in Qdrant |
| `pmoves_cipher_store` | Store cache misses as memories for future retrieval |
| `pmoves_cipher_store_reasoning` | (Optional) Store reasoning chains for complex cached answers |
| `pmoves_cipher_reasoning_patterns` | (Optional) Retrieve cached reasoning patterns for similar queries |

**Connection**: Cipher MCP is available via NATS SSE at `host.docker.internal:8105` on the primary host. On remote deployments where Cipher MCP is unavailable, the cache proxy silently skips Layer 0 and proceeds directly to pgvector (fail-open).

### 3.4 HiRAG Integration (Embedding Backend)

The semantic cache proxy delegates all embedding generation to **Hi-RAG Gateway v2** (`pmoves/services/hi-rag-gateway-v2/`) rather than calling local Ollama directly. This ensures the cache always uses the same embedding model as the RAG pipeline.

**Hi-RAG Gateway v2 Endpoints Used**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/hirag/admin/embedding/model` | GET | Query current active embedding model (determines lookup strategy) |
| `/hirag/admin/embedding/model` | POST | Hot-swap embedding model (administrative — triggers cache dimension check) |
| `/hirag/embeddings` | POST | Generate embeddings for query text (replaces direct Ollama calls) |
| `/hirag/health` | GET | Health check for embedding backend availability |

**Embedding Generation Flow**:

~~~
1. Cache proxy receives query text
2. Calls Hi-RAG Gateway: POST /hirag/embeddings {"input": query_text}
3. Hi-RAG Gateway:
   a. Checks provider chain (_embed_via_providers):
      - Tries remote embedding providers first (OpenAI, etc.) if configured
   b. Falls back to local model:
      - BGEM3FlagModel if BGE-M3 is active → returns dense+sparse+colbert
      - SentenceTransformer if default → returns single dense vector
   c. Returns embedding response
4. Cache proxy uses embedding for Layer 1 pgvector lookup
5. If BGE-M3 is active, cache proxy uses hybrid lookup (see §3.2)
~~~

**Model Hot-Swap Handling**:

When the Hi-RAG Gateway's embedding model is hot-swapped (via `swap_embedding_model()` or `POST /hirag/admin/embedding/model`), the dimensionality may change (e.g., 384d → 1024d). The cache proxy handles this via:

1. **Dimension check on startup**: Query `GET /hirag/admin/embedding/model` to get current model and dimensions
2. **Dimension mismatch detection**: If stored embeddings have different dimensions than current model, mark them as stale
3. **Graceful invalidation**: Stale entries are not returned in lookups (dimension filter in pgvector query)
4. **Optional flush**: `DELETE FROM llm_semantic_cache WHERE embedding_dim != :current_dim`

**Configuration**: The cache proxy connects to Hi-RAG Gateway at `http://hi-rag-gateway-v2:8086` (admin) and `http://hi-rag-gateway-v2:8087` (embeddings) by default. Override via `CACHE_HIRAG_GATEWAY_URL` env var.

**Fail-Open**: If Hi-RAG Gateway is unavailable, the cache proxy falls back to Ollama `nomic-embed-text` (768d) directly via TensorZero, maintaining the original behavior. This fallback is logged as a degradation metric.

### 3.5 Similarity Threshold: cosine distance < 0.10 (similarity > 0.90)

**Rationale**:
- 0.90 similarity catches paraphrases while minimizing false positives
- Configurable per model via `CACHE_SIMILARITY_THRESHOLD` env var
- Start conservative (0.10), can loosen to 0.15 if hit rate < 30%
- For BGE-M3 hybrid mode, the weighted fusion score threshold replaces raw cosine (see §3.2)

### 3.6 Cache Only Single-Query Requests

Per acceptance criteria: no caching for multi-turn conversations.

**Filter rule**: Cache only requests where:
- `messages` array has ≤ 3 messages (system + 1 user, or just 1 user)
- No `tools` or `functions` in the request
- `temperature` ≤ 0.3 (deterministic-ish)
- No conversation ID or thread context headers

### 3.7 TTL: Configurable Per Model

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
-- Supports multi-dimensional embeddings (BGE-M3 dense+sparse+ColBERT)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS llm_semantic_cache (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash        VARCHAR(64) UNIQUE NOT NULL,
    query_text        TEXT NOT NULL,
    query_embedding   vector(1024) NOT NULL,  -- max dim across supported models (BGE-M3 1024d)
    query_sparse      JSONB,                   -- BGE-M3 sparse vector (term weights)
    query_colbert     vector(1024)[],          -- BGE-M3 ColBERT token-level vectors
    embedding_model   VARCHAR(100) NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    embedding_dim     INTEGER NOT NULL DEFAULT 384,
    response_text     TEXT NOT NULL,
    response_model    VARCHAR(100) NOT NULL,
    request_model     VARCHAR(100) NOT NULL,
    provider          VARCHAR(50) NOT NULL DEFAULT 'tensorzero',
    cipher_memory_id  VARCHAR(200),            -- reference to Cipher memory if stored
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    similarity_threshold FLOAT DEFAULT 0.10,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL,
    last_accessed     TIMESTAMPTZ DEFAULT NOW(),
    hit_count         INTEGER DEFAULT 0
);

-- HNSW index for production-grade vector search
-- Uses vector_cosine_ops for <=> operator (cosine distance)
CREATE INDEX idx_cache_embedding_hnsw
    ON llm_semantic_cache
    USING hnsw (query_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN index for sparse vector JSONB queries (BGE-M3 keyword overlap)
CREATE INDEX idx_cache_sparse_gin
    ON llm_semantic_cache
    USING gin (query_sparse jsonb_path_ops);

-- Auxiliary indexes
CREATE INDEX idx_cache_hash ON llm_semantic_cache(query_hash);
CREATE INDEX idx_cache_expires ON llm_semantic_cache(expires_at);
CREATE INDEX idx_cache_model ON llm_semantic_cache(request_model, provider);
CREATE INDEX idx_cache_embedding_dim ON llm_semantic_cache(embedding_dim);
CREATE INDEX idx_cache_embedding_model ON llm_semantic_cache(embedding_model);

-- Analytics view for dashboard
CREATE VIEW v_cache_stats AS
SELECT
    embedding_model,
    embedding_dim,
    request_model,
    provider,
    COUNT(*) AS total_entries,
    SUM(hit_count) AS total_hits,
    AVG(hit_count) AS avg_hits_per_entry,
    COUNT(*) FILTER (WHERE expires_at > NOW()) AS active_entries,
    COUNT(*) FILTER (WHERE expires_at < NOW()) AS expired_entries,
    COUNT(*) FILTER (WHERE query_sparse IS NOT NULL) AS multidim_entries
FROM llm_semantic_cache
GROUP BY embedding_model, embedding_dim, request_model, provider;

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
| `pmoves/services/semantic-cache/main.py` | FastAPI app: intercept, embed, Layer 0/1 lookup, forward | ~250 |
| `pmoves/services/semantic-cache/cache_store.py` | pgvector CRUD: lookup, insert, evict; calls Hi-RAG Gateway for embeddings (not local Ollama directly) | ~180 |
| `pmoves/services/semantic-cache/cipher_layer.py` | Cipher Layer 0: pmoves_cipher_search pre-check + store misses as Cipher memories (category='context', tags=['semantic-cache']) | ~120 |
| `pmoves/services/semantic-cache/hirag_client.py` | Hi-RAG Gateway v2 client: embedding generation, model detection, hot-swap handling | ~100 |
| `pmoves/services/semantic-cache/metrics.py` | Prometheus metrics definitions (includes Layer 0 hit/miss counters) | ~50 |
| `pmoves/services/semantic-cache/config.py` | Env-driven configuration (includes HiRAG + Cipher settings) | ~60 |
| `pmoves/services/semantic-cache/requirements.txt` | Python dependencies | ~15 |
| `pmoves/services/semantic-cache/tests/test_cache.py` | Unit tests for cache lookup/store | ~150 |
| `pmoves/services/semantic-cache/tests/test_cipher_layer.py` | Unit tests for Cipher Layer 0 pre-check and storage | ~100 |
| `pmoves/services/semantic-cache/tests/test_proxy.py` | Integration test: full request flow (Layer 0 → Layer 1 → TensorZero) | ~120 |
| `pmoves/supabase/migrations/20260702000000_semantic_cache.sql` | Database migration (supports multi-dim embeddings) | ~60 |
| `pmoves/tests/smoke/test_semantic_cache.py` | Smoke test for cache service | ~60 |
| `pmoves/docker-compose.cache.yml` | Compose overlay for cache service (includes HiRAG + Cipher env) | ~60 |

### 5.2 Files to Modify

| File | Change | Effort |
|------|--------|--------|
| `pmoves/env.shared` | Add cache config vars (CACHE_PROXY_PORT, CACHE_SIMILARITY_THRESHOLD, CACHE_HIRAG_GATEWAY_URL, CACHE_CIPHER_*, etc.) | 20 min |
| `pmoves/env.shared.example` | Document new vars | 20 min |
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
Issue #1427: Intercepts OpenAI-compatible requests, checks Cipher (Layer 0)
and pgvector (Layer 1) for semantically similar cached queries, returns on hit
or forwards to TensorZero. Embeddings generated via Hi-RAG Gateway v2.
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
from .cipher_layer import CipherLayer
from .hirag_client import HiRAGClient
from .config import settings
from .metrics import (
    cache_hits_total, cache_misses_total,
    cache_similarity_score, cache_lookup_duration,
    cache_layer0_hits_total, cache_layer0_misses_total,
)

logger = logging.getLogger(__name__)

# Shared clients
http_client: httpx.AsyncClient
hirag_client: HiRAGClient         # Hi-RAG Gateway v2 embedding backend
cipher: CipherLayer               # Cipher Layer 0 pre-check
cache: CacheStore                 # pgvector Layer 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, hirag_client, cipher, cache
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    hirag_client = HiRAGClient(
        base_url=settings.hirag_gateway_url,
        fallback_url=settings.tensorzero_url,  # fail-open to Ollama via TensorZero
    )
    await hirag_client.init()
    cipher = CipherLayer(
        mcp_endpoint=settings.cipher_mcp_url,
        enabled=settings.cipher_layer_enabled,
    )
    await cipher.init()
    cache = CacheStore(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        hirag_client=hirag_client,  # delegate embedding to Hi-RAG
    )
    await cache.init()
    yield
    await http_client.aclose()
    await hirag_client.close()
    await cipher.close()
    await cache.close()


app = FastAPI(title="PMOVES Semantic Cache", lifespan=lifespan)


@app.post("/openai/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Intercept chat completion requests with three-layer cache lookup."""
    body = await request.json()

    # --- Filter: only cache cacheable requests ---
    if not _is_cacheable(body):
        return await _forward_passthrough(body)

    query_text = _extract_query_text(body)
    model = body.get("model", "unknown")

    # --- Layer 0: Cipher Memory Pre-Check ---
    if cipher.enabled:
        t0 = time.monotonic()
        cipher_result = await cipher.search(query_text, model)
        duration = time.monotonic() - t0

        if cipher_result:
            # Layer 0 HIT: return immediately, skip embedding + pgvector
            cache_layer0_hits_total.labels(model=model).inc()
            cache_lookup_duration.labels(status="layer0_hit").observe(duration)
            return _build_cached_response(cipher_result, body)

        cache_layer0_misses_total.labels(model=model).inc()
        cache_lookup_duration.labels(status="layer0_miss").observe(duration)

    # --- Step 1: Embed the query via Hi-RAG Gateway v2 ---
    embedding = await hirag_client.embed(query_text)
    if embedding is None:
        # Embedding failed — fail-open to TensorZero
        return await _forward_passthrough(body)

    # --- Layer 1: Semantic cache lookup (pgvector) ---
    t1 = time.monotonic()
    cached = await cache.lookup(embedding, model, settings.similarity_threshold)
    duration = time.monotonic() - t1
    cache_lookup_duration.labels(status="hit" if cached else "miss").observe(duration)

    if cached:
        # --- Layer 1 HIT: return cached response ---
        cache_hits_total.labels(model=model).inc()
        cache_similarity_score.labels(model=model).set(cached["similarity_score"])
        await cache.increment_hit(cached["id"])
        return _build_cached_response(cached, body)

    # --- MISS: forward to TensorZero ---
    cache_misses_total.labels(model=model).inc()
    response = await _forward_and_capture(body)

    # --- Store in cache layers (async, non-blocking) ---
    if response and response.status_code == 200:
        asyncio.create_task(
            _store_all_layers(
                query_text=query_text,
                query_embedding=embedding,
                response_text=response.text,
                model=model,
                ttl_seconds=settings.cache_ttl_chat_secs,
            )
        )

    return response


async def _store_all_layers(query_text, query_embedding, response_text, model, ttl_seconds):
    """Store cache miss in both pgvector (Layer 1) and Cipher (Layer 0)."""
    # Layer 1: pgvector
    await cache.store(
        query_text=query_text,
        query_embedding=query_embedding,
        response_text=response_text,
        model=model,
        ttl_seconds=ttl_seconds,
    )
    # Layer 0: Cipher memory (for future cross-session retrieval)
    if cipher.enabled:
        await cipher.store(
            query_text=query_text,
            response_text=response_text,
            model=model,
            ttl_seconds=ttl_seconds,
        )


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
    return {
        "status": "ok",
        "cache_entries": await cache.count(),
        "hirag_model": await hirag_client.get_current_model(),
        "cipher_enabled": cipher.enabled,
    }


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

### 6.2 `cache_store.py` — pgvector CRUD (Layer 1)

~~~python
"""pgvector-backed semantic cache store using Supabase.
Embeddings are generated via Hi-RAG Gateway v2 (delegated, not local Ollama).
Supports multi-dimensional embeddings (BGE-M3 dense+sparse+ColBERT).
"""

import hashlib
import logging
from typing import Any
from postgrest import AsyncPostgrestClient

logger = logging.getLogger(__name__)


class CacheStore:
    def __init__(self, supabase_url: str, supabase_key: str, hirag_client=None):
        self.url = supabase_url
        self.key = supabase_key
        self.hirag = hirag_client  # Hi-RAG Gateway v2 client for embeddings
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
        """Semantic cache lookup via pgvector cosine similarity.
        Filters by embedding dimension to avoid cross-model mismatches."""
        emb_str = f"[{','.join(str(x) for x in embedding)}]"
        emb_dim = len(embedding)
        result = await self.client.rpc("cache_semantic_lookup", {
            "p_embedding": emb_str,
            "p_model": model,
            "p_threshold": threshold,
            "p_embedding_dim": emb_dim,
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
        """Store a new cache entry. Embedding already generated by Hi-RAG Gateway."""
        query_norm = query_text.strip().lower()
        query_hash = hashlib.sha256(query_norm.encode()).hexdigest()
        emb_str = f"[{','.join(str(x) for x in query_embedding)}]"
        emb_dim = len(query_embedding)

        # Get current embedding model from Hi-RAG client
        embedding_model = "unknown"
        if self.hirag:
            embedding_model = await self.hirag.get_current_model() or "unknown"

        await self.client.rpc("cache_semantic_insert", {
            "p_hash": query_hash,
            "p_text": query_text,
            "p_embedding": emb_str,
            "p_embedding_model": embedding_model,
            "p_embedding_dim": emb_dim,
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

### 6.3 `cipher_layer.py` — Cipher Layer 0 Pre-Check

~~~python
"""Cipher Memory Layer 0: Knowledge graph pre-check before pgvector.
Uses pmoves_cipher_search for cross-session semantic retrieval and
pmoves_cipher_store to persist cache misses as Cipher memories.
"""

import hashlib
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


class CipherLayer:
    def __init__(self, mcp_endpoint: str, enabled: bool = True):
        self.mcp_url = mcp_endpoint  # e.g. http://host.docker.internal:8105
        self.enabled = enabled
        self.client: httpx.AsyncClient | None = None

    async def init(self):
        if not self.enabled:
            logger.info("Cipher Layer 0 disabled — skipping init")
            return
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        # Verify connectivity (fail-open if unavailable)
        try:
            resp = await self.client.get(f"{self.mcp_url}/health")
            if resp.status_code != 200:
                logger.warning("Cipher MCP health check failed — Layer 0 disabled")
                self.enabled = False
        except Exception as e:
            logger.warning(f"Cipher MCP unavailable — Layer 0 disabled: {e}")
            self.enabled = False

    async def close(self):
        if self.client:
            await self.client.aclose()

    async def search(self, query_text: str, model: str) -> dict | None:
        """Layer 0 pre-check: search Cipher memory for similar cached queries.
        Returns cached response dict on hit, None on miss."""
        if not self.enabled:
            return None
        try:
            resp = await self.client.post(
                f"{self.mcp_url}/mcp",
                json={
                    "tool": "pmoves_cipher_search",
                    "arguments": {
                        "query": query_text,
                        "filters": {
                            "category": "context",
                            "tags": ["semantic-cache"],
                        },
                        "limit": 1,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("results"):
                result = data["results"][0]
                # Check similarity score meets threshold
                if result.get("similarity", 0) > 0.85:
                    return {
                        "response_text": result.get("content", ""),
                        "similarity_score": result.get("similarity", 0),
                        "id": result.get("embedding_id", ""),
                    }
            return None
        except Exception as e:
            logger.warning(f"Cipher search failed, fail-open to Layer 1: {e}")
            return None

    async def store(self, query_text: str, response_text: str,
                    model: str, ttl_seconds: int) -> str | None:
        """Store cache miss as Cipher memory for future Layer 0 retrieval.
        Returns the Cipher embedding_id or None on failure."""
        if not self.enabled:
            return None
        try:
            query_hash = hashlib.sha256(
                query_text.strip().lower().encode()
            ).hexdigest()
            content = f"Query: {query_text}\nResponse: {response_text}"
            resp = await self.client.post(
                f"{self.mcp_url}/mcp",
                json={
                    "tool": "pmoves_cipher_store",
                    "arguments": {
                        "content": content,
                        "category": "context",
                        "tags": ["semantic-cache", f"model:{model}"],
                        "metadata": {
                            "source": "semantic-cache-proxy",
                            "query_hash": query_hash,
                            "response_model": model,
                            "ttl_seconds": ttl_seconds,
                            "stored_at": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            embedding_id = data.get("embedding_id")
            logger.debug(f"Stored Cipher memory: {embedding_id}")
            return embedding_id
        except Exception as e:
            logger.warning(f"Cipher store failed (non-blocking): {e}")
            return None
~~~

### 6.4 `hirag_client.py` — Hi-RAG Gateway v2 Client

~~~python
"""Hi-RAG Gateway v2 embedding client.
Delegates embedding generation to Hi-RAG Gateway v2 so the cache inherits
whatever model Hi-RAG is currently using (BGE-M3, SentenceTransformer, etc.).
Falls back to Ollama via TensorZero if Hi-RAG is unavailable.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class HiRAGClient:
    def __init__(self, base_url: str, fallback_url: str = None):
        self.base_url = base_url.rstrip("/")     # e.g. http://hi-rag-gateway-v2:8086
        self.fallback_url = fallback_url          # e.g. TensorZero for Ollama fallback
        self.client: httpx.AsyncClient | None = None
        self._current_model: str | None = None
        self._current_dim: int | None = None

    async def init(self):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        await self._refresh_model_info()

    async def close(self):
        if self.client:
            await self.client.aclose()

    async def _refresh_model_info(self):
        """Query current embedding model from Hi-RAG Gateway."""
        try:
            resp = await self.client.get(f"{self.base_url}/hirag/admin/embedding/model")
            resp.raise_for_status()
            data = resp.json()
            self._current_model = data.get("model", "unknown")
            self._current_dim = data.get("dimensions", 0)
            logger.info(f"Hi-RAG embedding model: {self._current_model} ({self._current_dim}d)")
        except Exception as e:
            logger.warning(f"Failed to query Hi-RAG model info: {e}")

    async def get_current_model(self) -> str | None:
        return self._current_model

    async def get_current_dim(self) -> int | None:
        return self._current_dim

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding via Hi-RAG Gateway v2.
        Falls back to Ollama nomic-embed-text via TensorZero if unavailable."""
        try:
            resp = await self.client.post(
                f"{self.base_url}/hirag/embeddings",
                json={"input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data["data"][0]["embedding"]

            # Refresh model info if dimension changed (model hot-swapped)
            if self._current_dim and len(embedding) != self._current_dim:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self._current_dim}, "
                    f"got {len(embedding)} — model may have been hot-swapped"
                )
                await self._refresh_model_info()

            return embedding
        except Exception as e:
            logger.warning(f"Hi-RAG embedding failed, trying fallback: {e}")
            return await self._embed_fallback(text)

    async def _embed_fallback(self, text: str) -> list[float] | None:
        """Fallback to Ollama nomic-embed-text via TensorZero."""
        if not self.fallback_url:
            return None
        try:
            resp = await self.client.post(
                f"{self.fallback_url}/openai/v1/embeddings",
                json={
                    "model": "tensorzero::embedding_model_name::archon_nomic_embed_local",
                    "input": text,
                },
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"Embedding fallback also failed, fail-open: {e}")
            return None
~~~

### 6.5 Migration RPC Functions (add to migration SQL)

~~~sql
-- RPC: Semantic cache lookup (supports variable embedding dimensions)
CREATE OR REPLACE FUNCTION cache_semantic_lookup(
    p_embedding vector(1024),
    p_model VARCHAR,
    p_threshold FLOAT DEFAULT 0.10,
    p_embedding_dim INTEGER DEFAULT NULL
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
      AND (p_embedding_dim IS NULL OR embedding_dim = p_embedding_dim)
    ORDER BY query_embedding <=> p_embedding
    LIMIT 1;
$$ LANGUAGE sql STABLE;

-- RPC: Semantic cache insert (records embedding model + dimension)
CREATE OR REPLACE FUNCTION cache_semantic_insert(
    p_hash VARCHAR,
    p_text TEXT,
    p_embedding vector(1024),
    p_embedding_model VARCHAR DEFAULT 'unknown',
    p_embedding_dim INTEGER DEFAULT 0,
    p_response TEXT,
    p_model VARCHAR,
    p_ttl_secs INTEGER DEFAULT 300
) RETURNS void AS $$
    INSERT INTO llm_semantic_cache
        (query_hash, query_text, query_embedding, embedding_model, embedding_dim,
         response_text, request_model, expires_at)
    VALUES
        (p_hash, p_text, p_embedding, p_embedding_model, p_embedding_dim,
         p_response, p_model, NOW() + (p_ttl_secs || ' seconds')::INTERVAL)
    ON CONFLICT (query_hash) DO UPDATE
        SET response_text = EXCLUDED.response_text,
            query_embedding = EXCLUDED.query_embedding,
            embedding_model = EXCLUDED.embedding_model,
            embedding_dim = EXCLUDED.embedding_dim,
            expires_at = EXCLUDED.expires_at,
            hit_count = 0;
$$ LANGUAGE sql;
~~~

### 6.6 `metrics.py` — Prometheus Instrumentation

~~~python
"""Prometheus metrics for semantic cache (issue #1427).
Includes Layer 0 (Cipher) and Layer 1 (pgvector) metrics."""

from prometheus_client import Counter, Histogram, Gauge

# Layer 1 (pgvector) — required by issue acceptance criteria
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

# Layer 0 (Cipher Memory)
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

# Additional operational metrics
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
~~~

### 6.7 `config.py` — Environment Configuration

~~~python
"""Configuration for semantic cache proxy."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Connection
    tensorzero_url: str = "http://tensorzero-gateway:3000"
    supabase_url: str = "http://supabase:8000"
    supabase_key: str = ""

    # Hi-RAG Gateway v2 (embedding backend)
    hirag_gateway_url: str = "http://hi-rag-gateway-v2:8086"
    hirag_embeddings_url: str = "http://hi-rag-gateway-v2:8087"

    # Cipher Memory (Layer 0)
    cipher_mcp_url: str = "http://host.docker.internal:8105"
    cipher_layer_enabled: bool = True

    # Embedding (defaults — actual model determined by Hi-RAG Gateway)
    embed_model: str = "auto"  # 'auto' = inherit from Hi-RAG Gateway
    embed_dimensions: int = 1024  # max supported (BGE-M3); actual may be less

    # BGE-M3 hybrid weights (when BGE-M3 is active)
    hybrid_weight_dense: float = 0.5
    hybrid_weight_sparse: float = 0.2
    hybrid_weight_colbert: float = 0.3

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

### 6.8 `docker-compose.cache.yml` — Service Overlay

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
      # Core connections
      - CACHE_TENSORZERO_URL=http://tensorzero-gateway:3000
      - CACHE_SUPABASE_URL=${SUPABASE_URL:-http://supabase:8000}
      - CACHE_SUPABASE_KEY=${SUPABASE_SERVICE_KEY}

      # Hi-RAG Gateway v2 (embedding backend — replaces direct Ollama)
      - CACHE_HIRAG_GATEWAY_URL=http://hi-rag-gateway-v2:8086
      - CACHE_HIRAG_EMBEDDINGS_URL=http://hi-rag-gateway-v2:8087

      # Cipher Memory (Layer 0)
      - CACHE_CIPHER_MCP_URL=http://host.docker.internal:8105
      - CACHE_CIPHER_LAYER_ENABLED=${CACHE_CIPHER_LAYER_ENABLED:-true}

      # BGE-M3 hybrid weights
      - CACHE_HYBRID_WEIGHT_DENSE=0.5
      - CACHE_HYBRID_WEIGHT_SPARSE=0.2
      - CACHE_HYBRID_WEIGHT_COLBERT=0.3

      # Cache behavior
      - CACHE_SIMILARITY_THRESHOLD=${CACHE_SIMILARITY_THRESHOLD:-0.10}
      - CACHE_CACHE_TTL_CHAT_SECS=${CACHE_CACHE_TTL_CHAT_SECS:-300}
      - CACHE_CACHE_TTL_EMBED_SECS=${CACHE_CACHE_TTL_EMBED_SECS:-3600}
      - CACHE_EMBED_MODEL=auto
      - CACHE_EMBED_DIMENSIONS=1024
      - CACHE_MAX_CACHEABLE_TEMPERATURE=0.3
    depends_on:
      - tensorzero-gateway
      - hi-rag-gateway-v2
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
CACHE_EMBED_MODEL=auto
CACHE_EMBED_DIMENSIONS=1024
CACHE_MAX_CACHEABLE_TEMPERATURE=0.3

# Hi-RAG Gateway v2 (embedding backend)
CACHE_HIRAG_GATEWAY_URL=http://hi-rag-gateway-v2:8086
CACHE_HIRAG_EMBEDDINGS_URL=http://hi-rag-gateway-v2:8087

# Cipher Memory (Layer 0)
CACHE_CIPHER_MCP_URL=http://host.docker.internal:8105
CACHE_CIPHER_LAYER_ENABLED=true

# BGE-M3 hybrid caching weights
CACHE_HYBRID_WEIGHT_DENSE=0.5
CACHE_HYBRID_WEIGHT_SPARSE=0.2
CACHE_HYBRID_WEIGHT_COLBERT=0.3

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

**Goal**: Working semantic cache proxy with HiRAG embeddings, Cipher Layer 0, pgvector Layer 1 lookup, forward-to-TensorZero, and Prometheus metrics.

| Day | Tasks |
|-----|-------|
| 1 | Create migration SQL (schema + HNSW index + sparse GIN index + RPC functions). Create `services/semantic-cache/` scaffold: `config.py`, `metrics.py`, `requirements.txt`, `Dockerfile`. |
| 2 | Implement `hirag_client.py` (Hi-RAG Gateway embedding delegation + fallback). Implement `cipher_layer.py` (Layer 0 pre-check + store misses). Implement `cache_store.py` (pgvector CRUD via Supabase REST). |
| 3 | Implement `main.py` (FastAPI proxy: intercept, Layer 0, embed via HiRAG, Layer 1 lookup, forward, store in all layers). Create `docker-compose.cache.yml`. Add env vars to `env.shared`. |
| 4 | Add Makefile targets. Write unit tests (`test_cache.py`, `test_cipher_layer.py`). Wire up Agent Zero env override. |
| 5 | Write integration test (`test_proxy.py`: full Layer 0 → Layer 1 → TensorZero flow). Manual smoke test: verify hit/miss flow with real queries. Add smoke test to `pmoves/tests/smoke/`. Update `SERVICE_DOCS_MATRIX.md`. |

**Phase 1 Deliverables**:
- [x] Migration applied to Supabase
- [x] Cache proxy container builds and runs
- [x] Hi-RAG Gateway v2 as embedding backend (with Ollama fallback)
- [x] Cipher Layer 0 pre-check operational
- [x] Agent Zero can route through cache (toggle via `CACHE_ENABLED`)
- [x] Prometheus metrics endpoint live at `:3001/metrics`
- [x] Cache hit rate visible after repeated queries

### Phase 2: Production Hardening (2-3 days)

**Goal**: BGE-M3 hybrid caching, circuit breaker, TTL eviction cron, observability dashboard, threshold tuning.

| Task | Detail |
|------|--------|
| BGE-M3 hybrid caching | Implement sparse + ColBERT vector storage and hybrid lookup in pgvector. Weighted fusion scoring (dense 0.5 + sparse 0.2 + ColBERT 0.3). |
| Circuit breaker | If pgvector lookup fails 3x consecutively, fail-open to passthrough (CIRCUIT_BREAKER_PRINCIPLE). Log degradation, expose `/health` degradation state. |
| TTL eviction | Supabase pg_cron job: `SELECT cron.schedule('cache-evict', '*/15 * * * *', 'DELETE FROM llm_semantic_cache WHERE expires_at < NOW()');` |
| Grafana dashboard | Cache hit rate panel (Layer 0 + Layer 1), similarity score histogram, lookup latency p50/p95, entry count over time, embedding model info. |
| Threshold tuning | Run for 48h with threshold=0.10, analyze hit rate. If <30%, loosen to 0.15. If false positives detected, tighten to 0.07. Tune hybrid weights for BGE-M3. |
| TensorZero Layer 2 | Enable `[gateway.cache]` in tensorzero.toml for exact-match cache as third layer. Configure Valkey or ClickHouse backend. |
| Cache invalidation hook | On model config change in `agent_registry.yaml`, emit NATS event to flush cache entries for that model. Also flush on Hi-RAG embedding model hot-swap (dimension change). |

### Phase 3: Fleet Integration (future, 3-5 days)

**Goal**: Cross-node cache sharing for fleet topology.

| Task | Detail |
|------|--------|
| Shared cache table | All nodes point to same Supabase instance → automatic shared cache. No code change needed. |
| Shared Cipher KG | All nodes share same Cipher Qdrant instance → Layer 0 knowledge graph accumulates across fleet. |
| Embedding model sync | Ensure all nodes use same Hi-RAG model (embedding model change = dimension check + optional flush). |
| Fleet cache metrics | Aggregate `pmoves_cache_hits_total` and `pmoves_cache_layer0_hits_total` across nodes in Prometheus federation. |
| Semantic cache for embeddings | Extend proxy to cache `/openai/v1/embeddings` responses (1h TTL, exact-match since embeddings are deterministic). |

---

## 10. Acceptance Criteria Traceability

| Issue Requirement | Implementation |
|-------------------|----------------|
| Cache hit rate >30% on repeated queries | Phase 1 + Phase 2 threshold tuning; Layer 0 (Cipher) boosts hit rate |
| Cache miss falls through to LLM inference | `_forward_passthrough()` in `main.py` — always forwards on miss |
| `pmoves_cache_hits_total` metric | `metrics.py` Counter, exposed at `/metrics` |
| `pmoves_cache_misses_total` metric | `metrics.py` Counter, exposed at `/metrics` |
| `pmoves_cache_similarity_score` metric | `metrics.py` Gauge, set on each hit |
| TTL configurable per model | `CACHE_TTL_CHAT_SECS` / `CACHE_TTL_EMBED_SECS` env vars, per-model config in Phase 2 |
| No cache for multi-turn conversations | `_is_cacheable()` filter: >3 messages or has tools → passthrough |
| Semantic cache using pgvector | `llm_semantic_cache` table with HNSW index, `<=>` operator |
| Integration: TensorZero gateway | Proxy forwards misses to `http://tensorzero-gateway:3000` |
| Cache invalidation on config changes | Phase 2: NATS event hook for model config changes + Hi-RAG model hot-swap dimension check |
| Layer 0 Cipher pre-check | `cipher_layer.py` — `pmoves_cipher_search` before pgvector |
| HiRAG embedding backend | `hirag_client.py` — delegates to Hi-RAG Gateway v2, not local Ollama |
| Multi-model embedding support | `§3.1` multi-model table + `§3.2` BGE-M3 hybrid caching |

---

## 11. Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Embedding model unavailable (Hi-RAG Gateway down) | Falls back to Ollama via TensorZero; different dimension may cause stale entries | `hirag_client.py` fallback chain; dimension check filters stale entries |
| Cipher MCP unavailable (remote deployment) | Layer 0 skipped, Layer 1 still functional | `cipher_layer.py` fail-open: `self.enabled = False` on connection failure |
| BGE-M3 model hot-swap changes dimensions | Stale entries with old dimensions cause incorrect lookups | Dimension filter in `cache_semantic_lookup` RPC; optional flush on dimension change |
| pgvector latency spikes under load | Cache lookup adds latency to all requests | HNSW index (<5ms p95 expected); circuit breaker to bypass on SLO breach |
| False positive semantic matches | Wrong cached response returned | Conservative threshold (0.10); Phase 2 tuning; similarity_score metric for monitoring; BGE-M3 hybrid scoring reduces false positives |
| Supabase connection failure | Cache unavailable | Fail-open to passthrough; health check reports degraded state |
| Cache poisoning (stored wrong response) | Corrupt responses served | Only store on HTTP 200 from TensorZero; Phase 2 adds response validation |
| Storage growth (multi-dim vectors) | Supabase storage fills faster with BGE-M3 sparse+ColBERT | TTL eviction cron + `hit_count=0 AND created_at < 7 days` cleanup; ColBERT vectors stored as arrays (compressible) |
| Cipher knowledge graph drift | Layer 0 returns stale or irrelevant memories | TTL metadata in Cipher entries; periodic Cipher memory cleanup job |

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
| **Cache layers** | Layer 0: Cipher Memory (Qdrant KG pre-check) → Layer 1: pgvector (HNSW) → Layer 2: TensorZero (exact-match) |
| **Vector store** | Supabase pgvector, `vector(1024)` with HNSW index (max dim = BGE-M3); Qdrant via Cipher for Layer 0 |
| **Embedding backend** | Hi-RAG Gateway v2 (BGE-M3 / SentenceTransformer / nomic-embed-text / OpenAI) with hot-swap support |
| **Multi-dim support** | BGE-M3 hybrid caching: dense (1024d) + sparse (keyword) + ColBERT (token-level) with weighted fusion |
| **Cipher integration** | Layer 0 pre-check via `pmoves_cipher_search`; misses stored via `pmoves_cipher_store` (category='context', tags=['semantic-cache']) |
| **HiRAG integration** | Embeddings delegated to Hi-RAG Gateway v2 `/hirag/embeddings`; model detected via `/hirag/admin/embedding/model`; fallback to Ollama |
| **Similarity threshold** | cosine distance < 0.10 (similarity > 0.90), configurable; weighted fusion for BGE-M3 hybrid |
| **TTL** | 5 min chat, 1 hour embeddings, configurable per model |
| **Metrics** | Layer 0 + Layer 1 Prometheus counters/gauges per issue spec + lookup latency histogram + embedding model info |
| **Failure mode** | Fail-open: any cache error → passthrough to TensorZero; Cipher unavailable → skip Layer 0; Hi-RAG unavailable → Ollama fallback |
| **Phase 1 effort** | 3-5 days (working MVP with HiRAG + Cipher + tests) |
| **Phase 2 effort** | 2-3 days (BGE-M3 hybrid, circuit breaker, cron eviction, Grafana, TensorZero Layer 2) |
| **Phase 3 effort** | 3-5 days (fleet-wide shared cache + shared Cipher KG, embedding cache) |
