# Make Targets — PMOVES Stack

This file summarizes the most-used targets and maps them to what they do under docker compose.

## Bring-up / Down
- `make up`
  - Starts core data plane (qdrant, neo4j, meilisearch, minio) + workers (presign, render-webhook, langextract, extract-worker), v2 gateway, retrieval-eval.
  - Uses the shared network `pmoves-net` (external).
- `make down`
  - Stops the compose project containers.

## GPU / Gateways
- `make up-gpu-gateways`
  - Soft-starts qdrant + neo4j, then brings up `hi-rag-gateway-v2-gpu` (and v1-gpu if profile enabled).
  - v2‑GPU defaults: `RERANK_MODEL=Qwen/Qwen3-Reranker-4B`, `USE_MEILI=true`.
- `make up-both-gateways`
  - Ensures v2 CPU and v2‑GPU are up.
- `make recreate-v2`
  - Force-recreate v2 CPU container without dependencies.
- `make recreate-v2-gpu`
  - Force-recreate v2‑GPU container without dependencies.

## Open Notebook
- `make up-open-notebook`
  - Brings up Open Notebook attached to `pmoves-net`. UI http://localhost:8503, API :5056.
- `make down-open-notebook`
  - Stops Open Notebook.

## Smokes
- `make smoke`
  - Full 12‑step baseline including geometry checks.
- `make smoke-gpu`
  - Validates v2‑GPU availability and rerank path.
- `make smoke-qwen-rerank`
  - Confirms v2‑GPU reports a Qwen reranker in stats and uses it on a test query.
- `make smoke-geometry-db`
  - Verifies seeded geometry rows via PostgREST.

## Realtime / Admin Notes
- v2 derives Realtime WS URL from `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` if `SUPABASE_REALTIME_URL` host is not resolvable in-container.
- For local smokes, set `SMOKE_ALLOW_ADMIN_STATS=true` so `/hirag/admin/stats` is readable.
- Optional: `POST /hirag/admin/reranker/model/label {"label":"Qwen/Qwen3-Reranker-4B"}` to override the reported model name without reloading.

## Networks
- The stack uses external network `pmoves-net` to allow side stacks (e.g., Open Notebook) to attach.

