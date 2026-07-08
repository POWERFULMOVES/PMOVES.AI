# Semantic Cache Deployment Guide

## Overview

The **semantic-cache** service (Issue #1427) is a FastAPI proxy that sits between
Agent Zero and TensorZero, intercepting `POST /openai/v1/chat/completions` requests
to provide similarity-based caching via pgvector (Layer 1) and Cipher Memory
(Layer 0). On cache hit, the cached response is returned with near-zero latency;
on miss, the request forwards to TensorZero and the response is stored in both
cache layers for future retrieval.

## Architecture

```
Agent Zero ──► Semantic Cache Proxy ──► TensorZero Gateway ──► LLM Provider
                    │    :8100               :3000
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
  Cipher Memory            Supabase pgvector
  (Layer 0)                (Layer 1)
  Qdrant/KG                HNSW index
```

## Deployment Steps

### 1. Prerequisites

Ensure the following services are healthy before starting semantic-cache:

| Service | Network | Purpose |
|---------|---------|---------|
| `nats` | pmoves_bus | CHIT bus for cross-instance cache invalidation |
| `supabase-kong` | pmoves_api | PostgREST gateway → pgvector for cache storage |
| `tensorzero-gateway` | pmoves_api | LLM inference on cache miss |
| `hi-rag-gateway-v2` | pmoves_api | Embedding generation (BGE-M3) |
| `cipher-api` | pmoves_app | Layer 0 knowledge-graph pre-check (optional) |

### 2. Start the service

```bash
# Option A: Start with the orchestration profile (recommended)
docker compose -f docker-compose.yml -f docker-compose.cache.yml up -d semantic-cache

# Option B: Start via cache profile only
docker compose -f docker-compose.yml -f docker-compose.cache.yml --profile cache up -d
```

### 3. Verify health

```bash
# Health check endpoint
curl http://127.0.0.1:8107/health

# Expected response:
# {
#   "status": "ok",
#   "version": "2.0.0",
#   "cache_entries": 0,
#   "components": { ... }
# }

# Prometheus metrics
curl http://127.0.0.1:8107/metrics
```

### 4. Verify Prometheus scrape target

Open Prometheus UI at `http://localhost:9090/targets` and confirm the
`semantic-cache` job is in `UP` state.

## Environment Variable Reference

| Variable | Default | Source | Description |
|----------|---------|--------|-------------|
| `SEMANTIC_CACHE_BIND` | `127.0.0.1` | env.shared | Host bind address for published port |
| `SEMANTIC_CACHE_HOST_PORT` | `8107` | env.shared | Host-facing port (avoids conflict with github-branch-cleanup:8100) |
| `SUPABASE_URL` | — | env.shared | Supabase REST endpoint (e.g. `http://supabase-kong:8000`) |
| `SUPABASE_SERVICE_ROLE_KEY` | — | env.tier-supabase | Supabase service-role key for PostgREST |
| `NATS_URL` | — | env.shared | NATS connection URL with credentials |
| `TENSORZERO_URL` | — | env.shared | TensorZero gateway OpenAI-compatible endpoint |
| `HIRAG_GATEWAY_URL` | `http://hi-rag-gateway-v2:8086` | env.shared | Hi-RAG Gateway v2 for embeddings |
| `CIPHER_MCP_URL` | `http://cipher-api:3000/mcp/sse` | env.shared | Cipher MCP SSE endpoint |
| `CIPHER_LAYER_ENABLED` | `true` | env.shared | Enable Cipher Layer 0 pre-check |
| `CACHE_MAX_ENTRIES` | `10000` | env.shared | LRU eviction ceiling |
| `CACHE_SIMILARITY_THRESHOLD` | `0.92` | env.shared | Cosine similarity threshold (0.0–1.0) |
| `CACHE_TTL_CHAT_SECS` | `3600` | env.shared | Chat completion cache TTL (seconds) |
| `CACHE_TTL_EMBED_SECS` | `3600` | env.shared | Embedding cache TTL (seconds) |
| `MAX_CACHEABLE_TEMPERATURE` | `0.5` | env.shared | Max temperature for cacheable requests |
| `CACHE_EMBEDDING_MODEL` | `BAAI/bge-m3` | env.shared | Default embedding model identifier |
| `CACHE_EMBEDDING_DIM` | `1024` | env.shared | Dense vector dimension |

## Troubleshooting

### Service fails to start (port conflict)

```bash
# Check if port 8107 is already in use
lsof -i :8107
# Change SEMANTIC_CACHE_HOST_PORT in env.shared to an available port
```

### Health check returns "degraded"

Inspect the response body — the `components` key indicates which subsystem
is failing:

| Component | Failure Mode | Resolution |
|-----------|-------------|------------|
| `hirag` | model error | Check Hi-RAG Gateway v2 health on :8086 |
| `cipher` | disabled/unreachable | Verify CIPHER_MCP_URL and cipher-api container |
| `cache` | pgvector error | Check Supabase PostgREST health; verify pgvector extension |
| `chit_bus` | disconnected | Verify NATS is healthy on :8222/varz |

### Cache hit rate is zero

1. Verify `CACHE_SIMILARITY_THRESHOLD` is not too strict (try 0.88).
2. Check `cache_entries_total` metric — entries may not be storing.
3. Confirm `SUPABASE_SERVICE_ROLE_KEY` has write access to `llm_semantic_cache`.
4. Review logs for storage errors: `docker logs pmoves-semantic-cache`.

### Prometheus target is down

1. Confirm `semantic-cache` container is on the `pmoves_monitoring` network
   (it is NOT by default — the Prometheus job scrapes via `pmoves_api`).
2. Verify the Prometheus container can reach `semantic-cache:8100`:
   ```bash
   docker exec pmoves-prometheus wget -qO- http://semantic-cache:8100/metrics
   ```
3. Check Prometheus `scrape_configs` includes the semantic-cache job.

## CHIT Bus Integration

The semantic-cache subscribes to NATS JetStream subjects for cross-instance
cache invalidation:

| Subject | Action |
|---------|--------|
| `cache.invalidate.*` | Flush/delete cache entries |
| `model.registry.changed` | Invalidate entries for changed models |
| `embedding.model.changed` | Flush stale entries on dimension change |

Message format:
```json
{
  "event": "cache.invalidate",
  "type": "model|dimension|all|hash",
  "target": "<model_name>|<dim>|<*>|<hash>",
  "source": "model_registry|embedding_gateway|admin",
  "timestamp": "2026-07-09T12:00:00Z"
}
```

## Security

- Container runs as non-root user `65532:65532`
- Root filesystem is read-only (`read_only: true`)
- All Linux capabilities are dropped (`cap_drop: [ALL]`)
- No `env_file` directive exposes `.env` files
- All credentials are injected via `${VAR:?error}` — containers fail-closed
  when required secrets are missing
- Host environment leak guard nullifies Windows Docker Desktop leakage
