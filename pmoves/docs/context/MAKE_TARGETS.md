**Make Targets (Quick Guide)**

### Core stack lifecycle

- `make up`
  - Brings up the core data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`, plus Postgres/PostgREST when `SUPA_PROVIDER=compose`) and all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`).
  - Also launches pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When running with the compose Supabase provider the target automatically chains to `make supabase-up` so GoTrue/Realtime/Storage/Studio come online.
  - Defaults to `SUPA_PROVIDER=cli`, which skips the compose Postgres/PostgREST pair so that the Supabase CLI database can own those ports.

- `make up-cli` / `make up-compose`
  - Convenience shims that force a single run of `make up` with `SUPA_PROVIDER=cli` or `SUPA_PROVIDER=compose` respectively.
  - Brings up the core data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`, plus Postgres/PostgREST when `SUPABASE_RUNTIME=compose`) and all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`).
  - Also launches pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When running with the compose Supabase provider the target automatically chains to `make supabase-up` so GoTrue/Realtime/Storage/Studio come online.
  - Defaults to `SUPABASE_RUNTIME=cli`, which skips the compose Postgres/PostgREST pair so that the Supabase CLI database can own those ports.

- `make up-cli` / `make up-compose`
  - Convenience shims that force a single run of `make up` with `SUPABASE_RUNTIME=cli` or `SUPABASE_RUNTIME=compose` respectively.

- `make down`
  - Stops and removes the pmoves Docker Compose project while leaving Supabase CLI services untouched.

- `make clean`
  - `down` + remove volumes/orphans for a fresh reset. Helpful after compose file changes.

- `make ps`
  - Shortcut for `docker compose -p pmoves ps` to inspect service status.

### Optional stacks

- `make up-workers`
  - Starts only the worker layer while ensuring the data profile is active.

- `make up-yt`
  - Boots the YouTube ingest stack (`ffmpeg-whisper`, `pmoves-yt`) with the required profiles.
  - Boots the YouTube ingest stack (`bgutil-pot-provider`, `ffmpeg-whisper`, `pmoves-yt`) with the required profiles.
- `make vendor-httpx`
  - Uses `uv` to refresh the offline `pmoves/vendor/python/` bundle so Jellyfin backfill scripts can import `httpx` without pip.

- `make up-cloudflare`
  - Launches the Cloudflare tunnel connector once `CLOUDFLARE_TUNNEL_TOKEN` **or** (`CLOUDFLARE_TUNNEL_NAME`, `CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_CERT`/`CLOUDFLARE_CRED_FILE`) are set. Use `make cloudflare-url` to print the latest tunneled hostname and `make down-cloudflare` to stop it.

- `make up-media`
  - Adds the optional GPU media analyzers (`media-video`, `media-audio`).

- `make up-jellyfin`
  - Launches the Jellyfin bridge in isolation.

- `make up-nats`
  - Starts the NATS broker (`agents` profile) and rewrites `.env.local` so `YT_NATS_ENABLE=true` with `NATS_URL=nats://nats:4222`.
  - Use this before opting into the agents profile (Agent Zero, Archon, mesh-agent, Discord publisher).
- `make notebook-up` / `make notebook-down`
  - Bring the Open Notebook UI/API online (Streamlit on host `:${OPEN_NOTEBOOK_UI_PORT:-8503}`, FastAPI on `:${OPEN_NOTEBOOK_API_PORT:-5055}`) or stop it while leaving data in `pmoves/data/open-notebook/`.
- `make notebook-seed-models`
  - Calls `scripts/open_notebook_seed.py` to register provider models/defaults once `env.shared` contains `OPEN_NOTEBOOK_API_TOKEN` (or password) and any desired provider keys (`OPENAI_API_KEY`, `GROQ_API_KEY`, etc.). Run this after starting the container so the UI drop-downs populate automatically.
- `make mindmap-notebook-sync`
  - Invokes `python pmoves/scripts/mindmap_to_notebook.py` to pull `/mindmap/{constellation_id}` entries from `hi-rag-gateway-v2` and mirror them into Open Notebook. Requires `MINDMAP_BASE`, `MINDMAP_CONSTELLATION_ID`, `MINDMAP_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN`.
- `make hirag-notebook-sync`
  - Invokes `python pmoves/scripts/hirag_search_to_notebook.py` to execute `/hirag/query` for supplied `--query` strings and ingest those hits into Notebook sources. Configure `HIRAG_URL`, `INDEXER_NAMESPACE`, `HIRAG_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN` (use `ARGS="--query 'topic' --k 20"`).

### Supabase helpers

- `make supabase-up`
  - Extends the main compose stack with `docker-compose.supabase.yml` to run GoTrue, Realtime, Storage, and Studio against the compose Postgres/PostgREST database.

- `make supabase-stop`
  - Stops the lightweight compose Supabase services without touching the rest of the stack.

- `make supabase-clean`
  - Removes the compose Supabase storage volume (`pmoves_supabase-storage`).

- `make supa-init`
- `make supa-start`
- `make supa-stop`
- `make supa-status`
  - Windows-friendly wrappers around the Supabase CLI for the full local Supabase experience (`supabase init/start/stop/status`). The CLI must already be installed.

- `make supa-use-local`
  - Copies `.env.supa.local.example` → `.env.local`. After running `make supa-status`, paste your anon/service keys into `.env.local`.

- `make supa-use-remote`
  - Copies `.env.supa.remote` (or `.env.supa.remote.example`) → `.env.local` to target a self-hosted Supabase instance.

- `make supa-extract-remote`
  - Parses `supa.md` and produces `.env.supa.remote` (ignored by Git) with the endpoints/keys discovered upstream.

- `make supabase-boot-user`
  - Creates or rotates the Supabase operator account, waits for the auth API to come online, and writes the resulting password/JWT into `env.shared`, `.env.local`, and `pmoves/.env.local`. `make first-run` invokes this automatically; rerun it any time you need to rotate credentials.

### Notes

- `.env.local` overlays `.env` for services that declare `env_file: [.env, .env.local]`. Run one of the Supabase switch helpers above when Compose warns about a missing `.env.local`.
- pmoves.yt ships without NATS by default. Run `make up-nats` to enable event publishing or to unlock the agents profile.
- See `pmoves/README.md` for full startup decision trees and profile walkthroughs.

### Smoke & Diagnostics

- `make smoke-wger`
  - Runs curl checks against the Wger nginx proxy (`http://localhost:8000`) and static bundle (`/static/images/logos/logo-font.svg`) to confirm collectstatic artifacts are mounted and served correctly. Override the target origin with `WGER_ROOT_URL=https://example:port` when testing remote deployments.
- `make smoke-firefly`
  - Calls the Firefly III login landing page plus `/api/v1/about` (using `FIREFLY_ACCESS_TOKEN`) to confirm the finance stack is reachable. Override `FIREFLY_ROOT_URL` / `FIREFLY_PORT` for remote hosts.

## External Integrations
- `make up-external` – start Wger, Firefly III, Open Notebook, and Jellyfin from published images on `cataclysm-net`.
- `make up-external-wger` / `up-external-firefly` / `up-external-on` / `up-external-jellyfin` – bring up individually.
- `make wger-brand-defaults` – reapplies the PMOVES-branded Django `Site`, admin profile, and default gym name using `WGER_BRAND_*` env vars (automatically invoked after `make up-external-wger`).
- Images are configurable via env: `WGER_IMAGE`, `FIREFLY_IMAGE`, `OPEN_NOTEBOOK_IMAGE` (default `ghcr.io/lfnovo/open-notebook:v1-latest`), `JELLYFIN_IMAGE`.
- See `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md` for linking your forks and publishing to GHCR.
