# extract-worker — Service Guide

Status: Implemented (compose)

Overview
- Indexes extracted content to Qdrant/Meili and Supabase.

Compose
- Service: `extract-worker`
- Port: `${EXTRACT_WORKER_HOST_PORT:-8083}:8083`
- Profiles: `workers`, `orchestration`
- Depends on: (none explicit) — expects `qdrant`, `meilisearch`, `postgrest` reachable

Environment
- `QDRANT_URL` (default `http://qdrant:6333`)
- `QDRANT_COLLECTION` (default `pmoves_chunks_qwen3`)
- `SENTENCE_MODEL` (default `all-MiniLM-L6-v2`)
- `EMBEDDING_BACKEND` (default `tensorzero`)
- `TENSORZERO_BASE_URL` (default `http://tensorzero-gateway:3000`)
- `TENSORZERO_EMBED_MODEL` (default `tensorzero::embedding_model_name::qwen3_embedding_4b_local`)
- `MEILI_URL` (default `http://meilisearch:7700`)
- `MEILI_API_KEY`
- `SUPA_REST_URL` (default `http://host.docker.internal:65421/rest/v1`)

Smoke
```bash
docker compose up -d qdrant meilisearch postgrest extract-worker
docker compose ps extract-worker
curl -sS "http://localhost:${EXTRACT_WORKER_HOST_PORT:-8083}/healthz" | head -c 200 || true
docker compose logs -n 50 extract-worker
```
Ops Quicklinks
- Smoke: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next Steps: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)
