# Open Notebook — Service Guide

Status: Compose add‑on (external image), attached to shared network.

Overview
- Lightweight notebook UI + API for local workflows. Lives on the shared `cataclysm-net` so it can talk to services if needed. Host ports are overridable so the UI/API can coexist with other stacks.

Compose
- Image (default): `ghcr.io/lfnovo/open-notebook:v1-latest` — tracked from the integration workspace fork (Open Notebook 1.x, React/Next.js build). Override via `OPEN_NOTEBOOK_IMAGE` to pin a specific tag (for example `ghcr.io/lfnovo/open-notebook:1.2.0`). Run `make docker-login-ghcr` (uses `DOCKER_USERNAME` / `DOCKER_PASS`) before pulling or pushing images.
- Migration reference: `integrations-workspace/Pmoves-open-notebook/MIGRATION.md` captures upstream breaking changes between the legacy Streamlit build and v1+.
- File: `pmoves/docker-compose.open-notebook.yml`
- Service: `open-notebook`
- Ports (host → container):
  - UI `${OPEN_NOTEBOOK_UI_PORT:-8503}:8502`
  - API `${OPEN_NOTEBOOK_API_PORT:-5055}:5055`
- Network: external `cataclysm-net` (shared with the branded integrations stack)
- Upstream defaults (per the Open Notebook README, Oct 20 2025) expose the Next.js UI on container port **8502** and the FastAPI backend on **5055**. We map the host UI port to **8503** by default to avoid clashes with other PMOVES services; override the host binding via `.env.local` if you prefer the upstream 8502. Always expose **5055** so API clients stay functional (this is enforced in v1+).

Make targets
- `make up-open-notebook` — bring up ON on `cataclysm-net` (UI http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API :${OPEN_NOTEBOOK_API_PORT:-5055})
- `make down-open-notebook` — stop ON
- `make notebook-set-password PASSWORD="pmoves4482"` — update `OPEN_NOTEBOOK_PASSWORD` / `OPEN_NOTEBOOK_API_TOKEN` (add `TOKEN=...` if you want a distinct bearer, `NOTEBOOK_ID=notebook:...` to rewrite `MINDMAP_NOTEBOOK_ID`, `YOUTUBE_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_NOTEBOOK_ID`); rerun `make down-open-notebook && make up-open-notebook` afterwards.
- `make -C pmoves up-external` — starts the packaged image alongside Wger/Firefly/Jellyfin (ensure `docker network create cataclysm-net` first)
- `make notebook-seed-models` — auto-register provider models/default selections via `scripts/open_notebook_seed.py` after `env.shared` contains your API keys
- `make yt-notebook-sync ARGS="--limit 10"` — mirror unsynced PMOVES.YT transcripts from Supabase into an Open Notebook notebook (set `YOUTUBE_NOTEBOOK_ID`, `SUPABASE_SERVICE_ROLE_KEY`, and `OPEN_NOTEBOOK_API_TOKEN` first)
  - The sync helper now submits sources with `async_processing=true` so Open Notebook queues ingestion instead of running blocking calls inside the request loop. Only pass `--sync-processing` for debugging if you can tolerate the `asyncio.run()` error when the request loop is already running.

### Sync control

- `NOTEBOOK_SYNC_MODE` — set to `live` (default) to allow automation, or `offline` to keep the notebook local-only. The notebook-sync worker honours this flag and Supabase Studio exposes it via `env.shared`.
- `NOTEBOOK_SYNC_INTERVAL_SECONDS` — polling cadence for the worker (0 disables polling; you can still trigger `/sync` manually or via n8n).
- `NOTEBOOK_SYNC_SOURCES` — comma list of resources (`notebooks`, `notes`, `sources`) that the worker should process. Use this to stage only specific feeds.
- To apply changes: edit the values in `pmoves/env.shared` (or directly in Supabase Studio), then `docker compose -f pmoves/docker-compose.yml --profile workers restart notebook-sync`.
- n8n / cron triggers: POST `http://notebook-sync:8095/sync` with the same bearer token (`OPEN_NOTEBOOK_API_TOKEN`) to run an on-demand sync.

## Sync PMOVES.YT transcripts into Open Notebook

The `scripts/yt_transcripts_to_notebook.py` helper pulls transcripts created by the pmoves-yt service,
creates Notebook sources for each video, and records the resulting source IDs back into Supabase so
future runs skip previously-synced items.

1. Ensure the following environment variables are populated (usually via `pmoves/env.shared`):
   - `SUPA_REST_URL` / `SUPABASE_REST_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `OPEN_NOTEBOOK_API_URL`
   - `OPEN_NOTEBOOK_API_TOKEN`
   - `YOUTUBE_NOTEBOOK_ID` (or reuse `MINDMAP_NOTEBOOK_ID` if you want to co-mingle assets)
   - Supabase migration `2025-10-26_transcripts_video_fk.sql` applied so `transcripts.video_id`
     has a foreign key to `videos.video_id` (required for PostgREST joins); run `supabase db reset`
     or apply the migration manually if you provisioned the stack before Oct 26 2025.
2. Run the sync (dry run first):

   ```bash
   make yt-notebook-sync ARGS="--limit 5 --dry-run"
   make yt-notebook-sync ARGS="--limit 25"
   ```

   The script dedupes using Notebook titles/URLs, creates text sources containing the transcript plus
   a link to the original video, and updates both `transcripts.meta` and `youtube_transcripts.meta`
   with `notebook_source_id` / `notebook_synced_at` timestamps.

Use `--namespace` or `--language` flags to narrow the sync to a specific pmoves-yt namespace or language,
and `--include-synced` if you need to reprocess existing entries.

Troubleshooting
- If port conflicts occur, set `OPEN_NOTEBOOK_UI_PORT` / `OPEN_NOTEBOOK_API_PORT` in `.env.local` (or export inline) before running Make/Compose.
- Ensure the shared network exists: `docker network create cataclysm-net` (Make and Compose create/attach automatically when needed).
- Set credentials in `pmoves/env.shared` before starting (either edit by hand or run `make notebook-set-password PASSWORD="yours" NOTEBOOK_ID=notebook:xyz"` right after the first login so operators can set their own secret and target notebook):
  ```
  OPEN_NOTEBOOK_API_URL=http://cataclysm-open-notebook:5055
  OPEN_NOTEBOOK_API_TOKEN=<generated-token>
  OPEN_NOTEBOOK_SURREAL_URL=ws://cataclysm-open-notebook-surrealdb:8000/rpc
  OPEN_NOTEBOOK_SURREAL_ADDRESS=cataclysm-open-notebook-surrealdb
  ```
- The password that unlocks the UI also serves as the API bearer. Keep `OPEN_NOTEBOOK_API_TOKEN` identical to `OPEN_NOTEBOOK_PASSWORD` (branded defaults ship this way) so CLI helpers and agents reuse the same secret.
- The `OPEN_NOTEBOOK_SURREAL_*` variables drive both the local SurrealDB container and any external Surreal endpoint; `SURREAL_*` aliases remain for legacy agents/Make targets that still read the older names.
- If embeddings are not configured (no `OPENAI_API_KEY`, `GROQ_API_KEY`, etc.), run the ingestion helpers with `--no-embed` so `/api/sources/json` doesn’t attempt to call EsperanTO’s provider chain and fail with `ValueError("OpenAI API key not found")`.
- Local-only embeddings: point `OLLAMA_API_BASE` (or another self-hosted provider endpoint) at your Compose service, then rerun `make notebook-seed-models`. The seeder already registers `ollama` models (`llama3.1`, `mxbai-embed-large`) whenever the base URL is present, letting Open Notebook stay inside the PMOVES stack without touching external APIs.
- Health checks:
  - UI: `curl -I http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}` (expect HTTP 200/307)
  - API: `curl http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/health` (returns `{ "status": "healthy" }`)
- Rotate credentials:
  1. Choose a new passphrase and run `make notebook-set-password PASSWORD="new-strong-pass"` (add `TOKEN=...` only if you want the API bearer to differ).
  2. Restart the service: `make down-open-notebook && make up-open-notebook`.
  3. Verify `curl -H "Authorization: Bearer new-strong-pass" http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/api/sources?limit=1`.
- Migrating older stacks: if `2025-10-26_transcripts_video_fk.sql` fails because of duplicate `videos.video_id` rows or orphan transcripts, run
- Migrating older stacks: if `2025-10-26_transcripts_video_fk.sql` fails because of duplicate `videos.video_id` rows or orphan transcripts, run
  ```
  delete from public.videos v using public.videos v2 where v.video_id = v2.video_id and v.id > v2.id;
  insert into public.videos (video_id, namespace, source_url)
    select distinct t.video_id, coalesce(t.meta->>'namespace', 'default'), 'https://youtube.com/watch?v=' || t.video_id
    from public.transcripts t
    left join public.videos v on v.video_id = t.video_id
    where v.video_id is null;
  ```
  before reapplying the migration (adjust namespace if you track multiple brands).
- If PMOVES logs complain that Open Notebook is missing, re-run `make bootstrap` after the service is up so the env loader captures the API URL/token. Restart `notebook-sync` with `docker compose --profile orchestration up -d notebook-sync`.

Notes
- ON is optional and does not participate in core smokes.
- Data stores live under `pmoves/data/open-notebook/`; remove the SQLite or SurrealDB files there if you want a clean reset.
- The bundled image runs the frontend with `next start`, which logs a warning for `output: standalone`. Upstream mirrors this behaviour; if you need a silent boot, replace the command with `node .next/standalone/server.js` in a custom supervisor override.
- After seeding models, the `/api/models/providers` endpoint should list your enabled providers (curl `http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/api/models/providers | jq`). The UI surfaces these under **Settings → Models**.
- Upgrading from the legacy Streamlit build (`lfnovo/open_notebook:latest-single`) requires pulling the new v1 image and clearing any stale containers: `make down-open-notebook && docker compose -f pmoves/docker-compose.open-notebook.yml pull open-notebook && make up-open-notebook`. Expect the first boot to rebuild caches because the Next.js frontend lives in the new bundle.
