**Make Targets (Quick Guide)**

- `make up`
  - Starts core data (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`, and Postgres/PostgREST when SUPA_PROVIDER=compose) and workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`).
  - Also starts pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`), Jellyfin bridge, and (in Compose mode) Supabase lite (gotrue/realtime/storage/studio).
  - Default provider is `SUPA_PROVIDER=cli`, so Compose Postgres/PostgREST are skipped to avoid conflicts with Supabase CLI.

- `make down`
  - Stops and removes the pmoves stack (volumes kept). Does not affect Supabase CLI.

- `make clean`
  - Down + remove volumes + orphans for the pmoves stack. Useful after compose layout changes.

- `make ps`
  - Shows status for the pmoves project.

- `make up-workers`
  - Starts only worker services while ensuring data profile is active.

- `make up-yt`
  - Starts `ffmpeg-whisper` and `pmoves-yt` (YouTube ingest) with data+workers profiles.

- `make up-media`
  - Starts optional media analyzers: `media-video`, `media-audio`.

- `make up-jellyfin`
  - Starts `jellyfin-bridge` only.

- `make up-nats` (new)
  - Starts a local NATS broker (`nats` service, profile `agents`).
  - Writes/updates `.env.local` with `YT_NATS_ENABLE=true` and `NATS_URL=nats://nats:4222` so services emit events.

- `make supa-init | supa-start | supa-stop | supa-status`
  - Supabase CLI wrappers for full local Supabase (recommended for feature parity). Requires the `supabase` CLI installed.

- `make supa-use-local`
  - Copies `.env.supa.local.example` → `.env.local`. Edit keys from `make supa-status` output.

- `make supa-use-remote`
  - Copies `.env.supa.remote` (or the example) → `.env.local` to point services at your self‑hosted instance.

- `make supa-extract-remote`
  - Parses `supa.md` and writes `.env.supa.remote` with endpoints (and keys if present in `supa.md`). Keys are ignored by Git.

- `make up-cli | make up-compose`
  - Force one‑shot provider mode for pmoves stack (`SUPA_PROVIDER=cli` or `compose`).

Notes
- `.env.local` overlays `.env` for all services and is ignored by Git. Use it to switch between local CLI Supabase and self‑hosted.
- If you see a missing `.env.local` error from Compose, run either `make supa-use-local` or `make supa-use-remote`.
- pmoves.yt no longer requires NATS by default. To enable event publishing, run `make up-nats`.

