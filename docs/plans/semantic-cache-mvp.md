# Implementation Plan: Semantic Cache MVP (#1427)

## Overview

A pgvector-powered semantic cache that intercepts LLM inference calls between agents and TensorZero, catching paraphrased queries via embedding similarity. Three-layer architecture with Cipher KG pre-check, pgvector HNSW semantic match, and TensorZero exact-match fallback.

## Architecture Decisions

- **Sidecar proxy at :3001** — TensorZero has no native hook/middleware for interception. The cache MUST be a proxy.
- **Embedding via Hi-RAG Gateway** — delegate to `/hirag/embeddings` with Ollama fallback. Inherits whatever model Hi-RAG uses via hot-swap.
- **Tool-schema-aware cache keys** — Archon sends heavy tool-calling requests. Cache key must include `tools` + `tool_choice` hash, not just messages.
- **SSE streaming passthrough** — Archon streams via SSE. Cache either passes `stream: true` through uncached or buffers full response. MVP: passthrough (no stream caching).
- **Tokenism attribution** — cache hits publish to `tokenism.attribution.recorded.v1` for cost-savings metering.
- **Longbow-ready** — cache sits at agent→inference boundary. Longbow (if built) inserts between cache-miss and TensorZero. No current code needed.
- **Fail-open** — all layers degrade gracefully (Circuit Breaker principle).

## Task List

### Phase 1: Foundation

- [ ] Task 1: Create pgvector migration (`20260702000000_semantic_cache.sql`) with HNSW index, TTL columns, model/dimension metadata
- [ ] Task 2: Create `config.py` — pydantic settings (thresholds, TTLs, Hi-RAG URL, Cipher toggle, Tokenism toggle)
- [ ] Task 3: Create `Dockerfile` — slim Python image with pgvector deps

### Checkpoint: Foundation
- [ ] Migration runs clean
- [ ] Config validates

### Phase 2: Core Proxy

- [ ] Task 4: Create `hirag_client.py` — embedding delegation to Hi-RAG Gateway with Ollama fallback
- [ ] Task 5: Create `cache_store.py` — pgvector CRUD (store, lookup, TTL eviction) + cache key builder (messages + model + tools hash)
- [ ] Task 6: Create `main.py` — FastAPI proxy: intercept `/openai/v1/chat/completions`, SSE passthrough for stream=true, cache filter (≤3 msgs, no tools, temp ≤0.3)
- [ ] Task 7: Create `metrics.py` — Prometheus metrics (hits, misses, similarity scores, latency)

### Checkpoint: Core Proxy
- [ ] Proxy starts and forwards requests
- [ ] Cache miss → TensorZero path works
- [ ] Metrics endpoint returns data

### Phase 3: Integration Layers

- [ ] Task 8: Create `cipher_layer.py` — Layer 0 KG pre-check via pmoves_cipher_search; store misses via pmoves_cipher_store
- [ ] Task 9: Add Tokenism attribution — publish cost-savings to `tokenism.attribution.recorded.v1` on cache hit
- [ ] Task 10: Create `docker-compose.cache.yml` overlay + Makefile targets

### Checkpoint: Integration
- [ ] Cipher pre-check works (graceful skip if unavailable)
- [ ] Tokenism attribution fires on hits
- [ ] Compose overlay valid

### Phase 4: Tests & Docs

- [ ] Task 11: Create `test_semantic_cache.py` — unit tests (cache key, filter, store/lookup, SSE passthrough, fail-open)
- [ ] Task 12: Update CATALOG.md + Makefile targets

### Checkpoint: Complete
- [ ] All tests pass
- [ ] Compose overlay valid
- [ ] Fail-open verified

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE streaming breaks cache | High | MVP: passthrough stream=true uncached |
| Tool-schema mismatch | Medium | Cache key includes tools hash |
| pgvector not available | Medium | Fail-open passthrough (Circuit Breaker) |
| Hi-RAG Gateway down | Low | Ollama fallback for embeddings |
| Tokenism NATS unavailable | Low | Fire-and-forget (no blocking) |

## Open Questions

- Port: spec says :3001, TensorZero investigation says :3031. Using **:3001** per spec.
- TensorZero internal port is :3000 (host :3030). Cache forwards to `http://tensorzero-gateway:3000/openai/v1`.
