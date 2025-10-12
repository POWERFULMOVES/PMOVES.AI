**Make Targets (Quick Guide)**

### Core stack lifecycle

- `make up`
  - Brings up the core data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`, plus Postgres/PostgREST when `SUPA_PROVIDER=compose`) and all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`).
  - Also launches pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When running with the compose Supabase provider the target automatically chains to `make supabase-up` so GoTrue/Realtime/Storage/Studio come online.
  - Defaults to `SUPA_PROVIDER=cli`, which skips the compose Postgres/PostgREST pair so that the Supabase CLI database can own those ports.
  - If the Supabase CLI stack is detected (`supabase_db_pmoves`), the target also runs `supabase-bootstrap` to replay `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and the v5.12 schema/seed SQL under `db/`.

- `make up-cli` / `make up-compose`
  - Convenience shims that force a single run of `make up` with `SUPA_PROVIDER=cli` or `SUPA_PROVIDER=compose` respectively.

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
  - Boots the YouTube ingest stack (`ffmpeg-whisper`, `pmoves-yt`) with the required profiles.

- `make up-media`
  - Adds the optional GPU media analyzers (`media-video`, `media-audio`).

- `make up-jellyfin`
  - Launches the Jellyfin bridge in isolation.

- `make up-nats`
  - Starts the NATS broker (`agents` profile) and rewrites `.env.local` so `YT_NATS_ENABLE=true` with `NATS_URL=nats://nats:4222`.
  - Use this before opting into the agents profile (Agent Zero, Archon, mesh-agent, Discord publisher).

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
  - Idempotently applies all SQL under `supabase/initdb/`, `supabase/migrations/`, and the v5.12 schema/seed files in `db/` against the Supabase CLI database (expects the `supabase_db_pmoves` container to be running). This target runs automatically at the end of `make up`, but you can invoke it manually after rotating credentials or pulling new migrations.
- `make neo4j-bootstrap`
  - Copies `neo4j/datasets/person_aliases_seed.csv` into the running container and executes `neo4j/cypher/001_init.cypher` + `002_load_person_aliases.cypher` via `cypher-shell`. Useful after refreshing the aliases CSV or wiping the graph.

### Notes

- `.env.local` overlays `.env` for services that declare `env_file: [.env, .env.local]`. Run one of the Supabase switch helpers above when Compose warns about a missing `.env.local`.
- pmoves.yt ships without NATS by default. Run `make up-nats` to enable event publishing or to unlock the agents profile.
- See `pmoves/README.md` for full startup decision trees and profile walkthroughs.
