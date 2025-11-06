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
  - Brings up Open Notebook attached to `cataclysm-net`. UI http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API :${OPEN_NOTEBOOK_API_PORT:-5055}.
- `make down-open-notebook`
  - Stops Open Notebook.
- `make mindmap-notebook-sync`
  - Wrapper around `python pmoves/scripts/mindmap_to_notebook.py`; reads `/mindmap/{constellation_id}` and mirrors those points into Open Notebook via `/api/sources/json`. Requires `MINDMAP_BASE`, `MINDMAP_CONSTELLATION_ID`, `MINDMAP_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN`.
- `make hirag-notebook-sync`
  - Calls `python pmoves/scripts/hirag_search_to_notebook.py` to run `/hirag/query` for one or more queries and push the hits into Open Notebook. Configure `HIRAG_URL`, `INDEXER_NAMESPACE`, `HIRAG_NOTEBOOK_ID` (or reuse the mindmap notebook), and `OPEN_NOTEBOOK_API_TOKEN`.

## Supabase
- `make supa-start`
  - Wraps `supabase start --network-id pmoves-net` (Supabase CLI runtime). Uses the port overrides from `supabase/config.toml` (65421/65432/etc.).
- `make supa-stop`
  - Calls `supabase stop` to shut down the CLI stack.
- `make supabase-up`
  - Only relevant when `SUPABASE_RUNTIME=compose`; starts the GoTrue/Realtime/Storage shim defined in `docker-compose.supabase.yml`.
- `make supabase-bootstrap`
  - Replays `supabase/initdb/*.sql` + `supabase/migrations/*.sql` into whichever Postgres is active (CLI or compose) and re-seeds geometry/persona fixtures.
- `make supabase-boot-user`
  - Provisions (or rotates) the Supabase dashboard operator, waits for the auth endpoint, and updates `env.shared`, `.env.local`, and `pmoves/.env.local` with the latest password and JWT. `make first-run` runs this automatically.

## Console (UI)
- `make ui-dev-start`
  - Starts the Next.js console on port 3001 using the project env loader; when `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` is present, the console auto‑auths and skips `/login`.
- `make ui-dev-stop`
  - Stops the background dev server started by `ui-dev-start`.
- `make ui-dev-logs`
  - Tails the console dev log for quick debugging.

## Agents, Media, and YT
- `make up-agents`
  - Starts NATS, Agent Zero, Archon, Mesh Agent, and publisher-discord.
- `make up-media`
  - Starts optional media analyzers (`media-video`, `media-audio`).
- `make up-yt`
  - Starts the ingest stack (`bgutil-pot-provider`, `ffmpeg-whisper`, `pmoves-yt`).
- `make vendor-httpx`
  - Rebuilds `pmoves/vendor/python/` with `uv` so the Jellyfin backfill script has an offline `httpx` bundle. Requires `uv` in your PATH.
- `make up-cloudflare`
  - Brings up the Cloudflare tunnel connector (needs `CLOUDFLARE_TUNNEL_TOKEN` or `CLOUDFLARE_TUNNEL_NAME` + `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_CERT`/`CLOUDFLARE_CRED_FILE` in `env.shared`/`.env.local`). Pair with `make cloudflare-url` to print the latest published endpoint and `make down-cloudflare` to stop it.
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
- `make smoke-wger`
  - Hits the nginx proxy on `http://localhost:8000` (override via `WGER_ROOT_URL`) plus `/static/images/logos/logo-font.svg` to ensure collectstatic artifacts and the Django backend are available.
- `make smoke-firefly`
  - Pings the Firefly III login landing page and `/api/v1/about` (using `FIREFLY_ACCESS_TOKEN` from your shell or `env.shared`) to confirm the finance stack and API token are wired up. Override `FIREFLY_ROOT_URL` / `FIREFLY_PORT` when testing remote hosts.

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
- Core services remain on external network `pmoves-net`; the branded integrations bundle publishes onto `cataclysm-net` for shared access across Cataclysm stacks.

## External Integrations
- `make up-external` – start Wger, Firefly III, Open Notebook, and Jellyfin from published images on `cataclysm-net`.
- `make up-external-wger` / `up-external-firefly` / `up-external-on` / `up-external-jellyfin` – bring up individually.
- `make wger-brand-defaults` – idempotently updates the Django `Site`, default admin profile, and seed gym name using `WGER_BRAND_*` env vars (this runs automatically after `up-external-wger`; run it again if you wipe the SQLite volume).
- Images are configurable via env: `WGER_IMAGE`, `FIREFLY_IMAGE`, `OPEN_NOTEBOOK_IMAGE` (default `ghcr.io/lfnovo/open-notebook:v1-latest`), `JELLYFIN_IMAGE`.
- See `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md` for linking your forks and publishing to GHCR.

## Integrations Compose (local dev)
- `make integrations-up-core` – start the n8n automation stack with integrations-ready configuration.
- `make integrations-up-wger` / `make integrations-up-firefly` – layer Wger or Firefly profiles on top of the core stack.
- `make integrations-up-all` – bring up n8n, both integrations, and the flows watcher sidecar for live JSON imports.
- `make integrations-import-flows` – run the REST helper once to import all JSON from `pmoves/integrations/**/n8n/flows`.
- `make integrations-logs` / `make integrations-down` – tail logs or tear the stack down (volumes removed on down).
