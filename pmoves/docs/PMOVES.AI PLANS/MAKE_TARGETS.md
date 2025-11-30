**Make Targets (Quick Guide)**

### Core stack lifecycle

- `make up`
  - Brings up the core data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`, plus Postgres/PostgREST when `SUPABASE_RUNTIME=compose`) and all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`).
  - Also launches pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When running with the compose Supabase provider the target automatically chains to `make supabase-up` so GoTrue/Realtime/Storage/Studio come online.
  - Defaults to `SUPABASE_RUNTIME=cli`, which skips the compose Postgres/PostgREST pair so that the Supabase CLI database can own those ports.
- Follow `make up` with `make bootstrap-data` (or the granular `make supabase-bootstrap` / `make neo4j-bootstrap` / `make seed-data`) to apply SQL, seed Neo4j, and load demo vectors on fresh installs.

- `make up-cli` / `make up-compose`
  - Convenience shims that force a single run of `make up` with `SUPABASE_RUNTIME=cli` or `SUPABASE_RUNTIME=compose` respectively.

- `make down`
  - Stops and removes the pmoves Docker Compose project while leaving Supabase CLI services untouched.

- `make clean`
  - `down` + remove volumes/orphans for a fresh reset. Helpful after compose file changes.

- `make ps`
  - Shortcut for `docker compose -p pmoves ps` to inspect service status.

### New convenience targets
- `make update` — pull repo + images, reconcile containers.
- `make backup` — best-effort dumps (Postgres, Qdrant snapshot, MinIO mirror, Meili dump) into `backups/<timestamp>/`.
- `make restore` — see **LOCAL_DEV.md** for step-by-step restore instructions.
- `make up-gpu` — start with `docker-compose.gpu.yml` overrides (GPU/VAAPI). See **LOCAL_DEV.md** for driver/toolkit notes.

### External-mode
Set `EXTERNAL_NEO4J|MEILI|QDRANT|SUPABASE=true` in `.env.local` to skip local infra services and point the stack at your existing instances.

### Optional stacks

- `make up-workers`
  - Starts only the worker layer while ensuring the data profile is active.

- `make up-yt`
  - Boots the YouTube ingest stack (`bgutil-pot-provider`, `ffmpeg-whisper`, `pmoves-yt`) with the required profiles.
- `make vendor-httpx`
  - Rebuilds `pmoves/vendor/python/` using `uv` so the Jellyfin backfill helper keeps an offline `httpx` bundle. Run this after updating `services/pmoves-yt/requirements.txt`.

- `make up-cloudflare`
  - Starts the Cloudflare tunnel connector for remote reviewers. Requires either `CLOUDFLARE_TUNNEL_TOKEN` or the trio `CLOUDFLARE_TUNNEL_NAME` + `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_CERT`/`CLOUDFLARE_CRED_FILE` in your env overrides; follow with `make cloudflare-url` to capture the issued hostname and `make down-cloudflare` when finished.

- `make up-media`
  - Adds the optional GPU media analyzers (`media-video`, `media-audio`).

- `make up-jellyfin`
  - Launches the Jellyfin bridge in isolation.

- `make up-nats`
  - Starts the NATS broker (`agents` profile) and rewrites `.env.local` so `YT_NATS_ENABLE=true` with `NATS_URL=nats://nats:4222`.
  - Use this before opting into the agents profile (Agent Zero, Archon, mesh-agent, Discord publisher).
- `make mindmap-notebook-sync`
  - Runs `python pmoves/scripts/mindmap_to_notebook.py` to pull `/mindmap/{constellation_id}` entries out of `hi-rag-gateway-v2` and mirror them into Open Notebook via `/api/sources/json`. Requires `MINDMAP_BASE`, `MINDMAP_CONSTELLATION_ID`, `MINDMAP_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN`.
- `make hirag-notebook-sync`
  - Runs `python pmoves/scripts/hirag_search_to_notebook.py` to execute `/hirag/query` for one or more `--query` arguments and ingest those hits into the configured Notebook. Configure `HIRAG_URL`, `INDEXER_NAMESPACE`, `HIRAG_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN` (pass CLI flags via `ARGS="--query 'topic' --k 20"`).

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

- `make supabase-bootstrap`
  - Idempotently applies all SQL under `supabase/initdb/` (including the CHIT demo fixture in `12_geometry_fixture.sql`), `supabase/migrations/`, and the v5.12 schema/seed files in `db/` against the Supabase CLI database (expects the `supabase_db_pmoves` container to be running). Run directly after you edit migrations or reset the CLI stack, or let `make bootstrap-data` call it for you.
- `make neo4j-bootstrap`
  - Copies `neo4j/datasets/person_aliases_seed.csv` into the running container and executes the curated Cypher set (`neo4j/cypher/001_init.cypher`, `002_load_person_aliases.cypher`, `010_chit_geometry_fixture.cypher`, `011_chit_geometry_smoke.cypher`) via `cypher-shell`. Useful after refreshing the aliases CSV, replaying the CHIT constellation, or wiping the graph.
- `make bootstrap-data`
  - Convenience umbrella that runs `supabase-bootstrap`, `neo4j-bootstrap`, and `seed-data` so Supabase, Neo4j, and Qdrant/Meili land in a known-good state on a new workstation.

### Notes

- `.env.local` overlays `.env` for services that declare `env_file: [.env, .env.local]`. Run one of the Supabase switch helpers above when Compose warns about a missing `.env.local`.
- pmoves.yt ships without NATS by default. Run `make up-nats` to enable event publishing or to unlock the agents profile.
- See `pmoves/README.md` for full startup decision trees and profile walkthroughs.
