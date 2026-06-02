# Meilisearch Pipeline Damage Report
**Date:** 2026-04-29
**Scope:** Pipeline alignment, injection points, cascading damage assessment
**Auditor:** Agent Zero (security-auditor subordinate) + BMad Master synthesis

## Pipeline Trace

```
MinIO (object storage)          [pmoves_data]  ✅ Healthy
    │
    ▼
extract-worker /ingest          [pmoves_data]  depends: minio ✅
    │
    ▼
hi-rag-gateway-v2 /ingest       [pmoves_api + pmoves_data]  depends: qdrant ✅, neo4j ✅
    │                                                       depends: meilisearch ❌ NOT LISTED
    ├──→ Qdrant upsert           [fail-closed → 503 on error]
    └──→ Meilisearch index       [fail-open → exception swallowed, lexical_indexed: 0]
    │
    ▼
Query path: /hirag/query
    ├──→ embed (blocking)
    ├──→ qdrant search (fail-closed)
    └──→ meili_lexical() → TCP connect to :7700 → 10s timeout per request
         ↓
    Under concurrency: N requests × 10s = uvicorn worker pool exhaustion
    ↓
ALL requests queue (including health checks) → service appears unhealthy
    ↓
Downstream services blocked (condition: service_healthy)
```

## Root Cause Chain

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| 1 | ~~**env.tier-data MISSING**~~ **FALSE POSITIVE** — populated by `make brand-defaults` (see AGNOTE4482 docs). Not a root cause. | ~~CRITICAL~~ N/A | ~~`pmoves/env.tier-data`~~ N/A |
| 2 | **MEILI_MASTER_KEY → MEILI_API_KEY name mismatch** — compose sends one name, code reads another. Key IS present after `make brand-defaults`, but code never sees it. | CRITICAL | `docker-compose.agents.yml:329` vs `config.py:229` |
| 3 | **Phantom default credential** — `os.environ.get("MEILI_API_KEY", "master_key")` sends literal string as auth | CRITICAL | `config.py:229` |
| 4 | **USE_MEILI hardcoded true** — no escape hatch when meilisearch isn't deployed | CRITICAL | `docker-compose.agents.yml:328` |
| 5 | **No depends_on meilisearch** — gateway starts without waiting for meilisearch | HIGH | `docker-compose.agents.yml:368-372` |
| 6 | **Healthcheck masks degradation** — root endpoint returns `{ok: true}` unconditionally | HIGH | `routes/health.py:102-104` |
| 7 | **Silent index divergence** — qdrant gets data, meilisearch doesn't, no alert | HIGH | `routes/query.py:218-251` |
| 8 | **ZERO circuit breakers** — no retry logic AND no circuit breaking anywhere | HIGH | Service-wide |
| 9 | **wait-for-deps.sh is a no-op** — prints message then exits immediately | MEDIUM | `scripts/wait-for-deps.sh` |

## Damage Pattern Analysis

### What the damage IS:
- **Timeout multiplication, not retry storms.** Each request blocks 10s on TCP connect to dead meilisearch. Under concurrency, this starves the uvicorn worker pool.
- **Silent data divergence.** Qdrant and meilisearch indexes drift apart over time. No alert fires.
- **False healthy signal.** Healthcheck reports healthy while the service is degraded.

### What the damage IS NOT:
- Not a retry loop problem (there are NO retries anywhere in the service)
- Not a MinIO problem (gateway has no MinIO integration — that's in `presign`)
- Not an injection attack (no external input reaches meilisearch unvalidated)

### The Circuit-Breaker Gap
The service has exactly zero resilience patterns:
- No retry with backoff
- No circuit breaker (pybreaker, etc.)
- No degraded mode signaling
- No dependency health in liveness probe

This means a single unhealthy dependency creates unbounded damage proportional to request concurrency.

## Priority Fixes

### P0 — Block Deploy
1. Create `env.tier-data` with real MEILI_MASTER_KEY, or change `:?` to `:-` (optional)
2. Fix env var name: `config.py` should read `MEILI_MASTER_KEY` as fallback
3. Remove phantom default: change `"master_key"` to `""` in `config.py:229`

### P1 — Before Next Release
4. Change `USE_MEILI=${USE_MEILI:-false}` — meilisearch should be opt-in
5. Add startup probe: if `USE_MEILI=true` and meilisearch unreachable, auto-disable with warning
6. Add circuit breaker for meilisearch (pybreaker or flag-based): after N failures, skip for T seconds

### P2 — Current Sprint
7. Add `/hirag/healthz` with dependency connectivity checks (qdrant, neo4j, meilisearch)
8. Point Docker HEALTHCHECK at `/hirag/healthz`
9. Remove or implement `wait-for-deps.sh`

### P3 — Next Sprint
10. Add tenacity retries for qdrant upsert (the only fail-closed external call)
11. Add retry to seed scripts (seed_local.py, load_csv.py)
12. Make meilisearch indexing fail-closed when `USE_MEILI=true` (no silent half-state)

## "Three Times the Charm = Stop" — Circuit-Breaker Principle

> The damage from persistence is not linear — it's multiplicative.
> When a dependency fails, each additional attempt doesn't just waste
> one request's worth of resources. Under concurrency, blocked workers
> accumulate, starving ALL requests including health checks.
> The third attempt doesn't fail gracefully — it fails catastrophically
> by taking down the observer.
>
> The principle: fail fast, fail open, fail observable.
> One clean failure beats three escalating ones.
> The model should stop after the first clear signal, reflect,
> and preserve context for both itself and everyone who follows.

This principle applies equally to:
- Service retry logic (circuit breakers)
- Agent retry loops (tool call failures)
- Human-AI interaction (stop, don't spiral)

## Pipeline Funnel Alignment Status

| Segment | Aligned | Notes |
|---------|---------|-------|
| MinIO → extract-worker | ✅ | Correct depends_on, same network |
| extract-worker → hi-rag-gateway-v2 | ✅ | Correct URL wiring, worker depends on gateway |
| hi-rag-gateway-v2 → Qdrant | ✅ | Fail-closed, correct depends_on |
| hi-rag-gateway-v2 → Meilisearch | ❌ | No depends_on, no auth key, no circuit breaker |
| hi-rag-gateway-v2 → Neo4j | ✅ | Correct depends_on, credentials present |
| Healthcheck → Reality | ❌ | Reports healthy when degraded |

**Overall: 4/6 aligned. Meilisearch integration is architecturally broken.**
