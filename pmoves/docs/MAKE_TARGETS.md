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
  - Brings up Open Notebook attached to `pmoves-net`. UI http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API :${OPEN_NOTEBOOK_API_PORT:-5055}.
- `make down-open-notebook`
  - Stops Open Notebook.

## Supabase
- `make supa-start`
  - Wraps `supabase start --network-id pmoves-net` (Supabase CLI runtime). Uses the port overrides from `supabase/config.toml` (65421/65432/etc.).
- `make supa-stop`
  - Calls `supabase stop` to shut down the CLI stack.
- `make supabase-up`
  - Only relevant when `SUPABASE_RUNTIME=compose`; starts the GoTrue/Realtime/Storage shim defined in `docker-compose.supabase.yml`.
- `make supabase-bootstrap`
  - Replays `supabase/initdb/*.sql` + `supabase/migrations/*.sql` into whichever Postgres is active (CLI or compose) and re-seeds geometry/persona fixtures.

## Agents, Media, and YT
- `make up-agents`
  - Starts NATS, Agent Zero, Archon, Mesh Agent, and publisher-discord.
- `make up-media`
  - Starts optional media analyzers (`media-video`, `media-audio`).
- `make up-yt`
  - Starts `ffmpeg-whisper` and `pmoves-yt` for ingest.
- `make up-jellyfin`
  - Starts the Jellyfin bridge only.
- `make up-n8n`
  - Launches the n8n automation UI (`http://localhost:5678`).

## Logs and Single-Service Bring-up
- Pattern for logs: `docker compose logs -f <service>`
- Pattern to bring up one service: `docker compose up -d <service>`
- Common services: `hi-rag-gateway-v2`, `hi-rag-gateway-v2-gpu`, `presign`, `render-webhook`, `langextract`, `extract-worker`, `publisher`, `publisher-discord`, `pmoves-yt`.

## Smokes
- `make smoke`
  - Full 12‑step baseline including geometry checks.
- `make smoke-gpu`
  - Validates v2‑GPU availability and rerank path.
- `make smoke-qwen-rerank`
  - Confirms v2‑GPU reports a Qwen reranker in stats and uses it on a test query.
- `make smoke-geometry-db`
  - Verifies seeded geometry rows via PostgREST.

## CHIT Demo Mappers
- `make demo-health-cgp`
  - Converts `contracts/samples/health.weekly.summary.v1.sample.json` to a CGP and posts it to `HIRAG_URL/geometry/event`.
- `make demo-finance-cgp`
  - Converts `contracts/samples/finance.monthly.summary.v1.sample.json` to a CGP and posts it to `HIRAG_URL/geometry/event`.

## Realtime / Admin Notes
- v2 derives Realtime WS URL from `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` if `SUPABASE_REALTIME_URL` host is not resolvable in-container.
- For local smokes, set `SMOKE_ALLOW_ADMIN_STATS=true` so `/hirag/admin/stats` is readable.
- Optional: `POST /hirag/admin/reranker/model/label {"label":"Qwen/Qwen3-Reranker-4B"}` to override the reported model name without reloading.

## Networks
- The stack uses external network `pmoves-net` to allow side stacks (e.g., Open Notebook) to attach.

## External Integrations
- `make up-external` – start Wger, Firefly III, Open Notebook, and Jellyfin from published images on `pmoves-net`.
- `make up-external-wger` / `up-external-firefly` / `up-external-on` / `up-external-jellyfin` – bring up individually.
- Images are configurable via env: `WGER_IMAGE`, `FIREFLY_IMAGE`, `OPEN_NOTEBOOK_IMAGE`, `JELLYFIN_IMAGE`.
- See `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md` for linking your forks and publishing to GHCR.

## Integrations Compose (local dev)
- `make integrations-up-core` – start the n8n automation stack with integrations-ready configuration.
- `make integrations-up-wger` / `make integrations-up-firefly` – layer Wger or Firefly profiles on top of the core stack.
- `make integrations-up-all` – bring up n8n, both integrations, and the flows watcher sidecar for live JSON imports.
- `make integrations-import-flows` – run the REST helper once to import all JSON from `pmoves/integrations/**/n8n/flows`.
- `make integrations-logs` / `make integrations-down` – tail logs or tear the stack down (volumes removed on down).
