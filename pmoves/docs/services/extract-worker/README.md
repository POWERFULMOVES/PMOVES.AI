# extract-worker — Service Guide

Status: Implemented (compose)

Overview
- Indexes extracted content to Qdrant/Meili and Supabase.

Compose
- Service: `extract-worker`
- Port: `8083:8083`
- Profiles: `workers`, `orchestration`
- Depends on: (none explicit) — expects `qdrant`, `meilisearch`, `postgrest` reachable

Environment
- `QDRANT_URL` (default `http://qdrant:6333`)
- `QDRANT_COLLECTION` (default `pmoves_chunks`)
- `SENTENCE_MODEL` (default `all-MiniLM-L6-v2`)
- `MEILI_URL` (default `http://meilisearch:7700`)
- `MEILI_API_KEY`
- `SUPA_REST_URL` (default `http://postgrest:3000`)

Smoke
```
docker compose up -d qdrant meilisearch postgrest extract-worker
docker compose ps extract-worker
curl -sS http://localhost:8083/ | head -c 200 || true
docker compose logs -n 50 extract-worker
```
Ops Quicklinks
- Smoke: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next Steps: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)
