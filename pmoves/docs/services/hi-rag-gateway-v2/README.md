# hi-rag-gateway-v2 — Service Guide

Status: Implemented (compose)

Overview
- Hybrid RAG with rerankers and Neo4j entity boost.

Compose
- Service: `hi-rag-gateway-v2` (and GPU variant `hi-rag-gateway-v2-gpu`).
- Ports: `8086:8086` (v2), `8087:8086` (GPU variant)
- Profiles: `workers`, `gateway` (plus `gpu` for GPU variant)
- Depends on: `qdrant`, `neo4j`

Environment (selected)
- Core: `QDRANT_URL`, `QDRANT_COLLECTION`, `SENTENCE_MODEL`, `INDEXER_NAMESPACE`, `ALPHA`
- Rerank: `RERANK_ENABLE`, `RERANK_MODEL`, `RERANK_TOPN`, `RERANK_K`, `RERANK_FUSION`
- Search: `USE_MEILI`, `MEILI_URL`, `MEILI_API_KEY`
- Graph: `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GRAPH_BOOST`, `ENTITY_CACHE_TTL`, `ENTITY_CACHE_MAX`, `NEO4J_DICT_REFRESH_SEC`, `NEO4J_DICT_LIMIT`
- Optional: `USE_OLLAMA_EMBED`, `OLLAMA_URL`, `TAILSCALE_ONLY`, `TAILSCALE_CIDRS`
- GPU variant adds: `CHIT_DECODE_*`, `CHIT_PERSIST_DB`, `PG*`

Realtime
- Fallback: If `SUPABASE_REALTIME_URL` resolves to a host‑only DNS (e.g., `api.supabase.internal`), v2 auto‑derives `ws://host.docker.internal:54321/realtime/v1/websocket` using `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL`.
- Recommended `.env.local` (host):
  - `SUPA_REST_URL=http://host.docker.internal:54321/rest/v1`
  - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:54321/rest/v1`
  - `SUPABASE_REALTIME_URL=ws://host.docker.internal:54321/realtime/v1/websocket`
- Admin stats guard: stats are Tailscale‑admin only unless `SMOKE_ALLOW_ADMIN_STATS=true` (for local smokes).
- Reranker model label (reporting only): `POST /hirag/admin/reranker/model/label {"label":"Qwen/Qwen3-Reranker-4B"}`

Defaults
- Meilisearch lexical: enabled by default for v2‑GPU (compose sets `USE_MEILI=true`). CPU v2 honors `USE_MEILI` from env.
- v2‑GPU reranker default: `RERANK_MODEL=Qwen/Qwen3-Reranker-4B` (overridable with env).

Smoke
```
docker compose up -d qdrant neo4j hi-rag-gateway-v2
docker compose ps hi-rag-gateway-v2
curl -sS http://localhost:8086/ | head -c 200 || true
docker compose logs -n 50 hi-rag-gateway-v2
```

Make targets
- `make up` — brings up data + v2.
- `make up-gpu-gateways` — ensures v2‑GPU is up (soft‑starts qdrant/neo4j if needed).
- `make recreate-v2` / `make recreate-v2-gpu` — force‑recreate containers (no deps).
- `make smoke` / `make smoke-gpu` / `make smoke-qwen-rerank` — core smokes.

Ops Quicklinks
- Reranker guide: [HI_RAG_RERANKER](../../PMOVES.AI%20PLANS/HI_RAG_RERANKER.md)
- Providers: [HI_RAG_RERANK_PROVIDERS](../../PMOVES.AI%20PLANS/HI_RAG_RERANK_PROVIDERS.md)
