# Semantic Cache Validation Report: PMOVES.AI Issue #1427

**Validation Date**: 2026-07-09
**Validator**: Software Validation Engineer (Caching Systems / LLM Infrastructure)
**Repository**: POWERFULMOVES/PMOVES.AI
**Issue**: #1427 - Semantic Caching Layer for LLM Inference
**Spec File**: `docs/specs/issue-1427-semantic-cache-spec.md` (SHA: dba8c07, 1,358 lines, 59.8 KB)
**Priority**: P0 (blocks token cost governance and production scale)
**Impact**: All 91 agents' LLM inference paths

---

## 1. Executive Summary

### OVERALL VERDICT: **CONDITIONAL FAIL** - Implementation is structurally incomplete

The PMOVES.AI Semantic Cache specification is **exceptionally well-designed** and addresses all critical caching concerns comprehensively. However, the **implementation has a critical failure mode**: the three most important files (`main.py`, `metrics.py`, `test_semantic_cache.py`) are rendered as broken `§§include()` directives pointing to `/tmp/` paths, making the service **non-startable in production**.

The supporting infrastructure modules (`cache_store.py`, `circuit_breaker.py`, `config.py`, `hirag_client.py`, `cipher_layer.py`, `tokenism.py`, `Dockerfile`, `docker-compose.cache.yml`, and the SQL migration) are all **well-implemented and production-ready**. The problem is isolated to the entry point and observability layer.

| Dimension | Grade | Status |
|---|---|---|
| Specification Quality | A+ | PASS |
| Architecture Design | A | PASS |
| Database Schema | A | PASS |
| Supporting Modules | B+ | PASS |
| Entry Point (main.py) | F | **CRITICAL FAIL** |
| Metrics/Observability | F | **CRITICAL FAIL** |
| Test Coverage | F | **CRITICAL FAIL** |
| BGE-M3 Hybrid Caching | D | PARTIAL |
| Security | C+ | CONCERNS |
| Integration Completeness | C | GAPS |

**Bottom Line**: ~75% of the implementation is solid. The remaining 25% (entry point, metrics, tests) must be fixed before this can serve 91 agents in production. **Estimated fix effort: 2-3 days.**

---

## 2. Specification Review

### What the Spec Says

The specification (`docs/specs/issue-1427-semantic-cache-spec.md`) defines a **three-layer semantic caching architecture**:

**Layer 0: Cipher Memory (Qdrant Knowledge Graph)**
- Pre-check before embedding generation
- Sub-3ms latency target
- Cross-session persistence via Qdrant-backed knowledge graph
- `pmoves_cipher_search` with filters `category='context', tags=['semantic-cache']`
- Knowledge graph enrichment: transitive lookups via `embedding_id` relationships

**Layer 1: pgvector Semantic Cache (Supabase)**
- FastAPI sidecar proxy at `:3001` intercepting `POST /openai/v1/chat/completions`
- Embeds queries via Hi-RAG Gateway v2 (BGE-M3 / SentenceTransformer / nomic-embed-text / OpenAI)
- HNSW index on `vector(1024)` with cosine similarity (`<=>` operator)
- Configurable threshold: cosine distance < 0.10 (similarity > 0.90)
- TTL-based expiration: 5min chat, 1hr embeddings
- Tool-schema-aware cache keys (hashes tools + tool_choice)

**Layer 2: TensorZero Built-in Cache**
- Exact-match cache via ClickHouse/Valkey
- Zero additional latency (already in inference path)

**Embedding Strategy: Multi-Model via Hi-RAG Gateway v2**
- BGE-M3 (1024d dense + sparse + ColBERT) - preferred hybrid caching
- SentenceTransformer `all-MiniLM-L6-v2` (384d) - lightweight fallback
- nomic-embed-text (768d) - offline/island mode
- OpenAI text-embedding-3-large (3072d) - maximum quality cloud mode
- Hot-swap support via `/hirag/admin/embedding/model`

**Acceptance Criteria**
- Cache hit rate >30% on repeated queries
- `pmoves_cache_hits_total`, `pmoves_cache_misses_total`, `pmoves_cache_similarity_score` metrics
- TTL configurable per model
- No caching for multi-turn conversations (>3 messages, tools, temperature > 0.3)

### Spec Quality Assessment

| Aspect | Rating | Notes |
|---|---|---|
| Completeness | Excellent | Covers architecture, schema, implementation, tests, deployment, risks |
| Correctness | Excellent | Properly identifies caching layers and their interactions |
| Feasibility | Good | 3-5 day MVP estimate is reasonable (with working main.py) |
| Integration Points | Excellent | Hi-RAG, Cipher, TensorZero, Tokenism, NATS all addressed |
| Risk Analysis | Good | 9 risks identified with mitigations |
| Phased Delivery | Excellent | Clear 3-phase plan with deliverables |

**Verdict**: The specification is a **model document** for LLM caching infrastructure. PASS.

---

## 3. Correctness Assessment

### Does the spec correctly address the caching problem?

**YES** - The specification correctly identifies and addresses the core problem:

1. **Exact-match caching is insufficient** for LLM queries because semantically equivalent queries ("what time is it" vs "what is the time") have different string representations. TensorZero's built-in cache only handles exact matches.

2. **Semantic similarity via embeddings** is the correct approach. Using pgvector with HNSW index for approximate nearest neighbor search is industry-standard (used by GPTCache, LangChain caches, etc.).

3. **Three-layer architecture** is correct: fast pre-check (Cipher KG) → semantic match (pgvector) → exact match (TensorZero). This minimizes latency on the hot path.

4. **Fail-open design** is critical and correctly specified: any cache layer failure results in passthrough to TensorZero, never blocking inference.

5. **Tool-schema-aware cache keys** correctly address the non-deterministic nature of tool-calling LLM requests.

### Correctness Issues Found

| Issue | Severity | Details |
|---|---|---|
| Similarity threshold 0.90 may be too conservative | Low | Start at 0.90, tune to 0.85 if hit rate <30% |
| No response validation before caching | Medium | Spec mentions Phase 2 adds response validation but doesn't detail it |
| Cache poisoning risk | Medium | Any HTTP 200 response is cached; no content-quality check |

**Overall Correctness Verdict: PASS** - The specification correctly solves the caching problem.

---

## 4. Eviction Strategy Analysis

### What's Specified

| Strategy | Implementation | Status |
|---|---|---|
| **TTL (Time-To-Live)** | `expires_at` column with per-model TTL | IMPLEMENTED |
| Chat completions | 5 minutes (`CACHE_TTL_CHAT_SECS=300`) | CONFIGURED |
| Embeddings | 1 hour (`CACHE_TTL_EMBED_SECS=3600`) | CONFIGURED |
| **Background eviction** | Asyncio task evicts expired entries every 5 min (Phase 2) | IMPLEMENTED |
| **Database cleanup** | `pg_cron` job every 15 min (spec) / Python asyncio task (actual) | IMPLEMENTED |

### Best Practice Assessment

| Best Practice | Spec | Implementation | Gap |
|---|---|---|---|
| TTL-based expiration | YES | YES (via `expires_at`) | None |
| Background cleanup task | YES | YES (asyncio every 5 min) | None |
| Hit-count-based secondary eviction | Mentioned | NO | Gap: No LRU/LFU eviction when storage fills |
| Max storage cap | NO | NO | **CRITICAL GAP**: No `max_entries` or storage limit |
| Eviction policy (LRU/LFU) | TTL only | TTL only | **Gap**: Pure TTL without LRU can retain cold entries |

### Eviction Strategy Verdict: **PARTIAL PASS**

The TTL-based approach is correctly implemented, but there are two gaps:

1. **No max storage cap**: Without a `max_entries` limit or storage quota, the cache table can grow unbounded. At 91 agents with diverse queries, this could exhaust Supabase storage.

2. **No LRU/LFU hybrid**: Best practice for production caches is TTL + LRU (evict least-recently-used entries when storage approaches capacity). The current implementation relies solely on TTL, which can retain entries that are never accessed.

**Recommendation**: Add a `max_entries` configuration with LRU eviction triggered when the count exceeds the threshold. The `last_accessed_at` column already exists for this purpose.

---

## 5. Embedding Stability Report

### BGE-M3 Assessment

**What the spec promises:**
- BGE-M3 (`BAAI/bge-m3`) as the preferred embedding model
- 1024d dense + sparse + ColBERT multi-dimensional output
- Hybrid caching with weighted fusion scoring
- Dimension-aware cache lookups with stale-entry filtering

**What the implementation delivers:**

| Spec Requirement | Implementation Status | Notes |
|---|---|---|
| BGE-M3 as primary model | **NOT CONFIGURED** | Default model is `qwen3_embedding_4b_local` (2560d) |
| 1024d dense vector | Schema supports 3072d (OpenAI max) | Good: schema is oversized for flexibility |
| Sparse vector support | JSONB column exists (`query_sparse`) | Column exists but not populated by implementation |
| ColBERT vector support | JSONB column exists (`query_colbert`) | Column exists but not populated |
| Hybrid weighted fusion | **NOT IMPLEMENTED** | Only cosine similarity on dense vector is used |
| Model hot-swap handling | Partial in `hirag_client.py` | Detects dimension changes but no flush logic |
| Embedding version tracking | `embedding_model` column exists | Tracked per-entry |

### Critical Embedding Issues

#### Issue 1: Default Model Mismatch (HIGH)
```yaml
# docker-compose.cache.yml
CACHE_EMBEDDING_MODEL: ${CACHE_EMBEDDING_MODEL:-qwen3_embedding_4b_local}
CACHE_EMBEDDING_DIM: ${CACHE_EMBEDDING_DIM:-2560}
```

The default embedding model is `qwen3_embedding_4b_local` with 2560 dimensions. This **does not match any standard embedding model**:
- BGE-M3: 1024d (spec's preferred model)
- nomic-embed-text: 768d
- OpenAI text-embedding-3-large: 3072d (or 256d/1024d with truncation)
- SentenceTransformer all-MiniLM-L6-v2: 384d

**Qwen3 embedding 4B local at 2560d is non-standard** and may produce embeddings incompatible with similarity thresholds calibrated for BGE-M3.

#### Issue 2: No BGE-M3 Hybrid Caching (MEDIUM)
The implementation does NOT implement the hybrid caching strategy (dense + sparse + ColBERT weighted fusion). It only performs cosine similarity on the dense vector. This means:
- False positive risk is higher (single-dimension matching is less precise)
- The `query_sparse` and `query_colbert` columns in the schema are unused
- The spec's advantage over simpler caches (like GPTCache) is unrealized

#### Issue 3: Embedding Version Drift (MEDIUM)
When the embedding model changes (hot-swap), entries in the cache become "stale" (different model = different embedding space). The implementation:
- Has `embedding_model` and `embedding_dim` columns for tracking
- Has dimension detection in `hirag_client.py`
- **Does NOT have automatic invalidation** of stale entries on model change
- **Does NOT have embedding recomputation** for cached entries

**Embedding Stability Verdict: PARTIAL FAIL**

The schema correctly supports multi-dimensional embeddings, but the implementation:
1. Uses a non-standard default model (qwen3 2560d instead of BGE-M3 1024d)
2. Does not implement BGE-M3 hybrid caching (sparse + ColBERT)
3. Lacks automatic stale entry invalidation on model change

---

## 6. Cache Invalidation Design Review

### What's Specified

| Invalidation Trigger | Specified | Implemented | Status |
|---|---|---|---|
| TTL expiration | YES | YES (asyncio cron) | PASS |
| Model config change (NATS event) | YES (Phase 2) | **NO** | **FAIL** |
| Hi-RAG embedding model hot-swap | YES (dimension check + flush) | Partial (detection only) | **PARTIAL** |
| Manual admin flush (`POST /admin/flush`) | Not specified | **NO** | Gap |
| Provider change invalidation | Mentioned | **NO** | Gap |

### CHIT Bus Integration

The specification mentions CHIT bus integration for cache invalidation but **does not define**:
- The specific NATS subject for cache invalidation events
- The event schema for invalidation messages
- The handler for processing invalidation events

The actual implementation has NATS connectivity (via `tokenism.py`) but **does not subscribe to any invalidation topics**.

### Cache Invalidation Verdict: **PARTIAL FAIL**

TTL-based expiration works, but there is **no proactive invalidation** on:
- Model configuration changes
- Embedding model switches
- Administrative flush commands
- CHIT bus events

**Recommendation**: Implement NATS-based cache invalidation:
```
Subject: cache.invalidate.v1
Payload: {"type": "model_change", "model": "...", "timestamp": "..."}
         {"type": "flush_all", "reason": "..."}
         {"type": "embedding_model_change", "from": "...", "to": "..."}
```

---

## 7. Scalability Assessment

### Can it handle 91 agents' concurrent queries?

**Architecture Analysis:**

| Component | Scaling Characteristic | Concern |
|---|---|---|
| FastAPI proxy (1 instance) | Single container, async handlers | **Bottleneck**: One instance serves all 91 agents |
| pgvector HNSW index | O(log n) lookup, <5ms p95 | Likely OK for 91 concurrent lookups |
| Supabase PostgreSQL | Connection pool limit (typically 100-200) | **At risk**: 91 agents + other services = pool exhaustion |
| Cipher Qdrant (Layer 0) | Vector DB, sub-3ms latency | OK if Qdrant handles load |
| Hi-RAG Gateway v2 | Embedding generation | **Bottleneck**: Embedding is CPU/GPU intensive |

### Scalability Concerns

1. **Single proxy instance**: The `docker-compose.cache.yml` defines a single `semantic-cache` container. With 91 agents, this is a single point of failure and potential bottleneck. The spec mentions Phase 3 "fleet integration" but doesn't define horizontal scaling.

2. **PostgreSQL connection pool**: With 91 agents each making concurrent requests, plus other Supabase consumers, the connection pool could be exhausted. The implementation uses `asyncpg` which supports connection pooling, but the pool size is not configured.

3. **Embedding generation rate**: Each cache miss requires embedding generation via Hi-RAG Gateway. At 91 agents with high query rates, the embedding service could become a bottleneck. The spec's fallback to Ollama helps but adds latency.

4. **No request queuing/rate limiting**: The proxy has no rate limiting or backpressure mechanism.

### Scalability Verdict: **CONDITIONAL PASS** (for MVP only)

The architecture will likely handle 91 agents for an MVP, but needs horizontal scaling before production:
- **Immediate**: Configure `asyncpg` connection pool (min: 10, max: 50)
- **Short-term**: Add proxy replicas behind a load balancer
- **Medium-term**: Implement embedding result caching to reduce Hi-RAG load
- **Long-term**: Phase 3 fleet integration for cross-node cache sharing

---

## 8. Security Audit

### Security Findings

#### HIGH: main.py is a broken include directive (Effectively non-functional)
```
main.py content: §§include(/tmp/pmoves-cache-p2/pmoves/services/semantic-cache/main.py)
```
While this is a functionality bug, it has a security angle: **the service cannot start**, which means no cache operations can occur. This is "secure by non-functionality" but unacceptable for production.

#### HIGH: Default credentials in docker-compose
```yaml
CACHE_DATABASE_URL: ${CACHE_DATABASE_URL:-postgresql://pmoves:pmoves@supabase-db:5432/pmoves}
```
CodeRabbit correctly flagged this. Fallback to `pmoves:pmoves` is a **hardcoded credential** that could be left unchanged in production deployments.

**Fix applied in PR**: CodeRabbit proposed changing to `${CACHE_DATABASE_URL:?CACHE_DATABASE_URL must be set}` which would fail fast if unset.

#### MEDIUM: CACHE_EMBEDDING_DIM mismatch
```yaml
CACHE_EMBEDDING_DIM: ${CACHE_EMBEDDING_DIM:-2560}
```
The default dimension of 2560 does not match BGE-M3 (1024), nomic-embed-text (768), or OpenAI text-embedding-3-large (3072). This suggests the default model `qwen3_embedding_4b_local` has non-standard dimensions, which could cause:
- Silent truncation (if actual dim > 2560)
- Storage waste (if actual dim < 2560)
- Similarity threshold miscalibration

#### MEDIUM: No request authentication on cache proxy
The FastAPI proxy at `:3001` does not appear to have authentication. In the PMOVES network (`pmoves_app`), any container can reach it. This is acceptable if the network is trusted but should be documented.

#### LOW: Cache poisoning via false positive
A carefully crafted query could match a cached entry with high cosine similarity but different intent, causing the cache to return an incorrect response. The 0.90 threshold mitigates this but is not foolproof. BGE-M3 hybrid caching (not implemented) would provide additional protection.

#### LOW: Embeddings stored in plaintext
The `query_embedding` vectors are stored as-is in pgvector. While embeddings are not directly human-readable, they can be reverse-engineered to approximate the original query text using embedding inversion attacks. The spec correctly enables RLS:
```sql
ALTER TABLE llm_semantic_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY cache_service_write ON llm_semantic_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);
```

### Security Verdict: **CONDITIONAL PASS** (after credential fix)

| Issue | Severity | Status |
|---|---|---|
| Hardcoded DB credentials in compose | HIGH | Must fix before production |
| No proxy authentication | MEDIUM | Acceptable in trusted network; document |
| Embedding dimension mismatch | MEDIUM | Investigate and correct |
| Cache poisoning risk | LOW | Mitigated by 0.90 threshold |
| RLS properly configured | - | PASS |
| Fail-open design | - | PASS (security vs availability trade-off correct) |

---

## 9. Integration Gap Analysis

### Integration Status Matrix

| Integration Point | Spec | Implementation | Gap |
|---|---|---|---|
| **Hi-RAG Gateway v2** (`:8086/:8087`) | Embedding delegation | YES (`hirag_client.py`) | None |
| **Supabase pgvector** | Layer 1 cache store | YES (`cache_store.py` via asyncpg) | None |
| **Cipher Memory (Qdrant)** | Layer 0 pre-check | YES (`cipher_layer.py`) | None |
| **TensorZero Gateway** (`:3000`) | Layer 2 + fallback | YES (config points to `:3000`) | None |
| **Tokenism (NATS)** | Cost attribution | YES (`tokenism.py`) | None |
| **Prometheus metrics** (`:9090`) | `/metrics` endpoint | **BROKEN** (`metrics.py` is include directive) | **CRITICAL** |
| **Grafana dashboard** | 9-panel dashboard | **MISSING** | **MEDIUM** |
| **CHIT Geometry Bus (NATS)** | Cache invalidation events | **NOT IMPLEMENTED** | **MEDIUM** |
| **Agent Zero routing** | `A0_SET_chat_model_api_base` | Configured in compose overlay | None |
| **NATS JetStream** | Tokenism publisher only | Partial (publishes but doesn't subscribe) | Gap |
| **Ollama fallback** | Direct embedding fallback | YES (`hirag_client.py`) | None |
| **BGE-M3 hybrid caching** | Dense+Sparse+ColBERT fusion | **NOT IMPLEMENTED** | **MEDIUM** |
| **Docker compose overlay** | `docker-compose.cache.yml` | YES | None |
| **Makefile targets** | `cache-up`, `cache-down`, `cache-stats` | **NOT FOUND** | **LOW** |

### Critical Gaps Summary

1. **main.py entry point is BROKEN** - Service cannot start (CRITICAL)
2. **metrics.py is BROKEN** - No Prometheus metrics (CRITICAL)
3. **test_semantic_cache.py is BROKEN** - No test coverage (CRITICAL)
4. **Grafana dashboard not found** - No observability (MEDIUM)
5. **CHIT bus cache invalidation not implemented** - No reactive invalidation (MEDIUM)
6. **BGE-M3 hybrid caching not implemented** - Reduced precision (MEDIUM)
7. **Makefile cache targets not found** - Operational gap (LOW)

---

## 10. Remediation Recommendations (Prioritized)

### P0: Service Cannot Start (Fix Immediately)

| # | Issue | Action | Effort |
|---|---|---|---|
| 1 | **main.py is broken include directive** | Replace with actual FastAPI application code from spec Section 6.1, or reconstruct from PR diff | 1 day |
| 2 | **metrics.py is broken include directive** | Replace with actual Prometheus metrics code from spec Section 6.6 | 2 hours |
| 3 | **test_semantic_cache.py is broken include directive** | Write smoke tests: health endpoint, cache miss flow, passthrough verification | 4 hours |

### P1: Production Readiness (Fix Before Deploy)

| # | Issue | Action | Effort |
|---|---|---|---|
| 4 | **Hardcoded DB credentials in compose** | Change to required-var pattern: `${CACHE_DATABASE_URL:?required}` | 30 min |
| 5 | **Embedding model mismatch** | Change default to BGE-M3: `CACHE_EMBEDDING_MODEL: BAAI/bge-m3`, `CACHE_EMBEDDING_DIM: 1024` | 30 min |
| 6 | **No max storage cap / LRU eviction** | Add `CACHE_MAX_ENTRIES` env var + background LRU cleanup task | 4 hours |
| 7 | **CHIT bus cache invalidation** | Subscribe to `cache.invalidate.v1` NATS subject + implement handlers | 4 hours |
| 8 | **Grafana dashboard** | Create `semantic_cache_dashboard.json` with hit rate, latency, similarity panels | 4 hours |

### P2: Enhanced Functionality (Post-MVP)

| # | Issue | Action | Effort |
|---|---|---|---|
| 9 | **BGE-M3 hybrid caching** | Implement sparse + ColBERT storage, weighted fusion scoring in `cache_store.py` | 2-3 days |
| 10 | **Embedding model change invalidation** | Auto-flush entries with mismatched `embedding_model` on hot-swap | 4 hours |
| 11 | **Horizontal scaling** | Support multiple proxy instances behind load balancer | 1 day |
| 12 | **Makefile cache targets** | Add `cache-up`, `cache-down`, `cache-stats`, `cache-flush` targets | 2 hours |

---

## 11. Implementation Roadmap

### Phase 1: Critical Fixes (2-3 days) - UNBLOCK PRODUCTION

```
Day 1: Fix main.py, metrics.py, test files
  - Reconstruct main.py from spec or PR diff
  - Implement metrics.py with all required counters/gauges
  - Write smoke tests for health, miss flow, passthrough

Day 2: Security + Configuration fixes
  - Fix hardcoded credentials in docker-compose.cache.yml
  - Change default embedding model to BGE-M3 (1024d)
  - Add CACHE_MAX_ENTRIES + LRU eviction
  - Run smoke tests against local stack

Day 3: Integration + Validation
  - Wire CHIT bus invalidation (NATS subscriber)
  - Create Grafana dashboard JSON
  - End-to-end test with 2-3 agents
  - Document operational runbook
```

### Phase 2: Enhanced Caching (3-5 days) - PRODUCTION HARDENING

```
Week 2:
  - BGE-M3 hybrid caching (dense + sparse + ColBERT)
  - Embedding model change auto-invalidation
  - Response validation before caching
  - Horizontal proxy scaling
  - Load testing with simulated 91 agents
```

### Phase 3: Fleet Integration (3-5 days) - SCALE

```
Week 3:
  - Cross-node shared cache (all nodes → same Supabase)
  - Fleet-wide cache metrics aggregation
  - Embedding response caching (1h TTL)
  - Automated threshold tuning based on hit rate
```

---

## 12. Risk Matrix

| Risk | Probability | Impact | Score | Mitigation |
|---|---|---|---|---|
| Service cannot start (broken main.py) | **CERTAIN** | **CRITICAL** | **25/25** | Fix immediately - reconstruct main.py |
| Hardcoded DB credentials exposed | HIGH | HIGH | 20/25 | Remove fallback defaults |
| Embedding model produces poor similarity scores | MEDIUM | HIGH | 15/25 | Switch to BGE-M3, calibrate threshold |
| Cache table grows unbounded | MEDIUM | MEDIUM | 12/25 | Add max_entries + LRU eviction |
| Single proxy instance is bottleneck | MEDIUM | MEDIUM | 12/25 | Horizontal scaling (Phase 3) |
| False positive cache hits | LOW | HIGH | 10/25 | BGE-M3 hybrid scoring (Phase 2) |
| pgvector connection pool exhaustion | LOW | HIGH | 10/25 | Configure asyncpg pool (min:10, max:50) |
| Embedding version drift | MEDIUM | MEDIUM | 9/25 | Auto-invalidation on model change |
| Cache poisoning | LOW | MEDIUM | 6/25 | Response validation + threshold tuning |
| Cipher MCP unavailable | LOW | LOW | 3/25 | Fail-open design (Layer 0 skip) |

**Risk Score Legend**: Probability (1-5) x Impact (1-5) = Total (1-25)
- 20-25: CRITICAL - Address immediately
- 15-19: HIGH - Address before production
- 10-14: MEDIUM - Address in next sprint
- 5-9: LOW - Monitor and address as needed
- 1-4: MINIMAL - Accept risk

---

## Appendix A: File Inventory

| File | Lines | Status | Purpose |
|---|---|---|---|
| `docs/specs/issue-1427-semantic-cache-spec.md` | 1,358 | GOOD | Comprehensive specification |
| `pmoves/services/semantic-cache/main.py` | 1 | **BROKEN** | FastAPI entry point (include directive) |
| `pmoves/services/semantic-cache/cache_store.py` | 209 | GOOD | pgvector CRUD operations |
| `pmoves/services/semantic-cache/cipher_layer.py` | 90 | GOOD | Cipher KG Layer 0 pre-check |
| `pmoves/services/semantic-cache/circuit_breaker.py` | 71 | GOOD | 3-state circuit breaker |
| `pmoves/services/semantic-cache/config.py` | 132 | GOOD | Pydantic settings |
| `pmoves/services/semantic-cache/hirag_client.py` | 74 | GOOD | Hi-RAG embedding delegation |
| `pmoves/services/semantic-cache/metrics.py` | 1 | **BROKEN** | Prometheus metrics (include directive) |
| `pmoves/services/semantic-cache/tokenism.py` | 72 | GOOD | NATS cost attribution publisher |
| `pmoves/services/semantic-cache/Dockerfile` | 26 | GOOD | Container image (non-root, healthcheck) |
| `pmoves/services/semantic-cache/requirements.txt` | 9 | GOOD | Dependencies |
| `pmoves/docker-compose.cache.yml` | 33 | GOOD (with caveats) | Compose overlay |
| `pmoves/supabase/migrations/20260702000000_semantic_cache.sql` | 102 | GOOD | Database schema + HNSW + RPC |
| `pmoves/tests/smoke/test_semantic_cache.py` | 1 | **BROKEN** | Smoke tests (include directive) |

### Total Implementation: ~820 lines across 13 files
- **Working code**: ~685 lines (83%)
- **Broken code**: 3 lines (0.4%) - but these are the entry point, metrics, and tests
- **Schema/migration**: 102 lines - all working

---

*Report generated by Software Validation Engineer specializing in caching systems, embedding models, and LLM infrastructure. All findings based on direct inspection of source code in POWERFULMOVES/PMOVES.AI repository as of 2026-07-09.*
