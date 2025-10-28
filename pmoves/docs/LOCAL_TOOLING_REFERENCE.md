# Local Tooling & Automation Reference
Note: See consolidated index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md for cross-links.
_Last updated: 2025-10-26_

This guide aggregates the entry points that keep local environments consistent across Windows, WSL, and Linux hosts. Use it alongside `pmoves/docs/LOCAL_DEV.md` (service ports, networking) and `pmoves/docs/SMOKETESTS.md` (verification flows) when onboarding new contributors or refreshing a workstation.

## Environment & Secrets
- `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` → wraps the
  registry-driven env bootstrap and then stages
  `pmoves/pmoves_provisioning_pr_pack/` into
  `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/` (override with `--output`). Use
  `--registry`/`--service` when you need to scope the env refresh to a subset of
  services.
- `python3 -m pmoves.tools.mini_cli deps check` → confirm host tooling like
  `make`, `jq`, and `pytest` are available. `deps install` can automatically
  install missing binaries via your package manager (auto-detects `apt`,
  `dnf`, `brew`, `choco`, etc.) or, with `--use-container`, run the installs
  inside a disposable container (`python:3.11-slim` by default) so the host
  environment stays untouched.
- `make env-setup` → runs `python3 -m pmoves.tools.secrets_sync generate` to materialize `.env.generated` / `env.shared.generated` from `pmoves/chit/secrets_manifest.yaml`, then calls `scripts/env_setup.{sh,ps1}` to merge `.env.example` with the optional `env.*.additions`. Use `make env-setup -- --yes` to accept defaults non-interactively.
- `make bootstrap` → interactive secret capture (still writes overrides to `env.shared`, which now layers on top of the generated secrets for Supabase, provider tokens, Wger/Firefly/Open Notebook, Discord/Jellyfin). Re-run after `supabase start --network-id pmoves-net` or whenever external credentials change. Supports `BOOTSTRAP_FLAGS="--service supabase"` and `--accept-defaults` for targeted updates.
- `make supabase-bootstrap` → replays `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and `db/v5_12_grounded_personas.sql` into the Supabase CLI Postgres container. Run it once after `make supa-start` (and again whenever schema changes land) to keep the local CLI stack in sync.
- UI ingestion security: the Next.js dashboard now requires a Supabase session. `upload_events` rows are stamped with `owner_id` and the UI only presigns keys in `namespace/users/<owner-id>/uploads/…`. Anonymous or cross-user presign attempts will fail with `401/403`.
- `python3 -m pmoves.tools.onboarding_helper status` → summarize manifest coverage and highlight missing CGP labels before generating env files (`… generate` writes the files directly).
- `make manifest-audit` → scans `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/inventory/nodes.yaml` (and optional Supabase exports) for unsupported 32-bit hardware. Use it ahead of Jellyfin 10.11 upgrades to ensure all nodes are x86_64 or aarch64.
- `python3 -m pmoves.tools.mini_cli crush setup` → write a PMOVES-aware `~/.config/crush/crush.json` (providers, MCP stubs, context paths). After running, launch `crush` from the repo root. See `CRUSH.md` for the day-to-day flow.
  - Set `TENSORZERO_BASE_URL` (and optional `TENSORZERO_API_KEY`) before running this command to auto-register the TensorZero gateway. The generator wires the Authorization header automatically and prefers the TensorZero models when both large/small defaults are present.
- `make env-check` → calls `scripts/env_check.{sh,ps1}` for dependency checks, port collisions, and `.env` completeness.
  - CI runs the PowerShell preflight on Windows runners only; Linux contributors should run `scripts/env_check.sh` locally if they bypass Make.
- `scripts/create_venv*.{sh,ps1}` → optional helpers to create/activate Python virtualenvs outside of Conda. Pass the environment name as the first argument on Bash, or `-Name` in PowerShell.
- `scripts/codex_bootstrap*.{sh,ps1}` → standardizes editor/agent prerequisites inside Codex or WSL sessions (installs `jq`, configures Make, syncs Python deps).
- `scripts/install_all_requirements*.{sh,ps1}` → one-shot installs for every Python requirement file when you need parity with CI or remote hosts.
  - Optional TensorZero gateway: copy `pmoves/tensorzero/config/tensorzero.toml.example` to `pmoves/tensorzero/config/tensorzero.toml`, then set `TENSORZERO_BASE_URL=http://localhost:3030` (and `TENSORZERO_API_KEY` if the gateway enforces auth). LangExtract will honour `LANGEXTRACT_PROVIDER=tensorzero` and forward `LANGEXTRACT_REQUEST_ID` / `LANGEXTRACT_FEEDBACK_*` metadata tags when these variables are present.
  - Advanced toggles: set `TENSORZERO_MODEL` for alternative chat backends, `TENSORZERO_TIMEOUT_SECONDS` to raise or lower the request timeout, and `TENSORZERO_STATIC_TAGS` (JSON or comma-separated `key=value` pairs) to annotate requests with deployment metadata.
- Offline Python deps: `pmoves/vendor/python/` ships a bundled copy of `httpx` + dependencies for the Jellyfin backfill path. Run `make vendor-httpx` after installing [uv](https://github.com/astral-sh/uv) to refresh the bundle—it rehydrates the vendor directory from `services/pmoves-yt/requirements.txt` without touching your global Python. The backfill script automatically prepends the directory to `sys.path`, so subsequent invocations work even when pip/Internet access is unavailable. Open Notebook also exposes a default login (`changeme`) in `.env.shared`/`.env.local`; rotate it immediately after confirming access.
- UI testing: `npm run test` executes Jest + Testing Library unit suites; `npm run test:e2e` drives Playwright E2E checks (run `npx playwright install` once to fetch browsers).

## Stack Orchestration (Make Targets)
- `make up` → main compose profile (data + workers). Overrides: `make up-cli`, `make up-compose`, `make up-workers`, `make up-media`, `make up-jellyfin`, `make up-yt`.
- `make channel-monitor-up` / `make channel-monitor-smoke` → start the YouTube channel monitor service and trigger a one-off RSS pass. Uses `CHANNEL_MONITOR_*` env vars defined in `.env`, `.env.local`, and `env.shared`. Set `CHANNEL_MONITOR_SECRET` (channel monitor) + `CHANNEL_MONITOR_STATUS_URL`/`CHANNEL_MONITOR_STATUS_SECRET` (pmoves-yt) so ingestion callbacks can mark rows `completed`/`failed` once downloads finish. Tune yt-dlp with `YT_ARCHIVE_DIR`/`YT_ENABLE_DOWNLOAD_ARCHIVE`, `YT_SUBTITLE_LANGS`/`YT_SUBTITLE_AUTO`, and `YT_POSTPROCESSORS_JSON` when you need richer outputs (captions, metadata embedding) during ingest. For Hi-RAG pacing, adjust `YT_UPSERT_BATCH_SIZE`, `YT_ASYNC_UPSERT_MIN_CHUNKS`, and `YT_INDEX_LEXICAL_DISABLE_THRESHOLD`; poll `/yt/emit/status/{job_id}` for async progress.
- `python -m pmoves.tools.register_media_source` → append sources (YouTube channels, playlists, SoundCloud users, etc.) to the channel monitor config without editing JSON manually. Supports per-source namespaces, formats, cookies, and inline `yt_options` JSON.
- `make notebook-up` → launches the optional Open Notebook research workspace (Streamlit UI on 8502, REST API on 5055). Pair with `make notebook-logs` for tailing output and `make notebook-down` to stop it without removing data under `pmoves/data/open-notebook/`. Once `env.shared` has your API token/password and provider keys, run `make notebook-seed-models` to auto-register the default model catalogue upstream so the UI can save settings without manual SurrealDB edits.
- `make up-cloudflare` → runs the Cloudflare tunnel connector so remote collaborators can hit local services. Requires either `CLOUDFLARE_TUNNEL_TOKEN` or the set `CLOUDFLARE_TUNNEL_NAME` / `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_CERT` (or `CLOUDFLARE_CRED_FILE`) defined in `env.shared`/`.env.local`. Optional knobs: `CLOUDFLARE_TUNNEL_INGRESS` to map multiple services (`hi-rag=http://hi-rag-gateway-v2:8086,publisher=http://publisher-discord:8092`), `CLOUDFLARE_TUNNEL_HOSTNAMES` for explicit hostname creation, and `CLOUDFLARE_TUNNEL_METRICS_PORT` to expose connector metrics. Use `make cloudflare-url` to print the active hostname and `make logs-cloudflare` for tunnel diagnostics.
- `make up-agents` → launches NATS, Agent Zero, Archon, Mesh Agent, and the Discord publisher. Run `make up-nats` first if `NATS_URL` is not configured.
- `make ps`, `make down`, `make clean` → quick status, stop, and tear-down helpers pinned to the `pmoves` compose project.
- `make flight-check` / `make flight-check-retro` → fast readiness sweep (Docker, env vars, contracts) via `tools/flightcheck/retro_flightcheck.py`. The checklist now verifies:
  - Supabase CLI stack (PostgREST + **Realtime**) reachable on `pmoves-net`
  - External integration env (`WGER_API_TOKEN`, `FIREFLY_ACCESS_TOKEN`, Open Notebook tokens)
  - Geometry assets (`supabase/migrations/2025-10-20_geometry_cgp_views.sql` applied) and hi-rag gateway ports
  - Optional bundles (Open Notebook bind mounts, Jellyfin bridge) with actionable warnings
- `python pmoves/tools/youtube_po_token_capture.py` → headless Playwright helper to capture the authenticated `youtubei/v1/player` request (headers, body, PO token) for a given video using your exported cookies. Use it to refresh `YT_PO_TOKEN_VALUE` or to pre-seed request payloads when yt-dlp hits SABR restrictions.
- Windows without GNU Make: `scripts/pmoves.ps1` replicates the same targets (`./scripts/pmoves.ps1 up`, `./scripts/pmoves.ps1 smoke`, etc.).
- `make jellyfin-folders` → prepares `pmoves/data/jellyfin/{config,cache,transcode,media/...}` so Jellyfin launches with a categorized library tree (Movies/TV/Music/Audiobooks/Podcasts/Photos/HomeVideos) owned by the host user.
- `FIREFLY_PORT` in `env.shared` defaults to `8082` to avoid colliding with the Agent Zero API on 8080; adjust before running `make up-external` if that port is taken on your host.
- TensorZero gateway (optional): `docker compose --profile tensorzero up tensorzero-clickhouse tensorzero-gateway tensorzero-ui` boots the ClickHouse backing store, gateway, and UI (http://localhost:4000). Point `TENSORZERO_BASE_URL` at `http://localhost:3030` so LangExtract and the Crush configurator detect the gateway automatically.

## Supabase Workflows
- CLI parity (default):
  - `make supa-init` → initializes the Supabase CLI project.
- `make supa-start` / `make supa-stop` / `make supa-status` → lifecycle management for the CLI stack.
- `make supa-use-local` → copies `.env.supa.local.example` into `.env.local` so services reference the CLI hostnames/ports.
- TIP: to share networking with the compose services, run `supabase start --network-id pmoves-net` from `pmoves/`. Afterwards, update `.env.local` with the CLI-issued keys (`supabase status -o json`) and reapply `supabase/initdb/*.sql` so PostgREST, GoTrue, and Realtime expose the expected tables.
- Supabase SQL lives under `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and the v5.12 schema/seed files under `db/`; run `make supabase-bootstrap` (or the aggregate `make bootstrap-data`) whenever you reset the CLI stack or land new SQL.
- Manual refresh: run `make supabase-bootstrap` after bumping SQL files or resetting the CLI stack. Expect output showing each init/migration file (“Init …”, “Migration …”, “Seed …”) and a final `✔ Supabase CLI schema + seeds applied.`.
- One-shot data bring-up: `make bootstrap-data` chains the Supabase bootstrap, Neo4j seed, and Qdrant/Meili demo seed so a fresh workstation lands with all backing stores populated.
- `make neo4j-bootstrap` copies the seed CSV (`neo4j/datasets/person_aliases_seed.csv`) into the live container and runs the Cypher scripts under `neo4j/cypher/` so the CHIT/mindmap graph always has baseline data. `make up` runs this helper after the Supabase bootstrap when `pmoves-neo4j-1` is online. After seeding, query the gateway via `python pmoves/scripts/mindmap_query.py --base http://localhost:8086 --cid 8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111 --limit 25 --offset 0` to inspect the enriched JSON (contains media URLs and Open Notebook payloads); the CLI now prints summary stats (`returned`, `total`, `remaining`, `has_more`) on stderr for quick paging.
- `make neo4j-bootstrap` copies the seed CSV (`neo4j/datasets/person_aliases_seed.csv`) into the live container and runs the Cypher scripts under `neo4j/cypher/` so the CHIT/mindmap graph always has baseline data. `make up` runs this helper after the Supabase bootstrap when `pmoves-neo4j-1` is online. After seeding, query the gateway via `python pmoves/scripts/mindmap_query.py --base http://localhost:8086 --cid 8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111 --limit 25 --offset 0` to inspect the enriched JSON (contains media URLs and Open Notebook payloads); the CLI now prints summary stats (`returned`, `total`, `remaining`, `has_more`) on stderr for quick paging. Use `python pmoves/scripts/mindmap_to_notebook.py` or `make mindmap-notebook-sync ARGS="--dry-run"` to push nodes into Open Notebook once `OPEN_NOTEBOOK_API_TOKEN` and `MINDMAP_NOTEBOOK_ID` are configured. When you need to mirror PMOVES.YT transcripts into the research workspace, run `make yt-notebook-sync ARGS="--limit 25"` after setting `SUPABASE_SERVICE_ROLE_KEY`, `OPEN_NOTEBOOK_API_TOKEN`, and `YOUTUBE_NOTEBOOK_ID`. Rotate the Open Notebook bearer with `make notebook-set-password PASSWORD="super-strong-pass"` (add `TOKEN=...` for a distinct API secret and/or `NOTEBOOK_ID=notebook:...` to rewrite the ingest targets) and restart the service so the new credentials load.
- Notebook sync toggles live in `NOTEBOOK_SYNC_MODE` (`live` / `offline`), `NOTEBOOK_SYNC_INTERVAL_SECONDS` (polling cadence; 0 disables), and `NOTEBOOK_SYNC_SOURCES` (comma list of `notebooks`, `notes`, `sources`). Update them in `env.shared`, then `docker compose -f pmoves/docker-compose.yml --profile workers restart notebook-sync` to apply. Supabase Studio exposes the env row so you can flip the switches without editing the repo; n8n or Cron flows can call `http://notebook-sync:8095/sync` for on-demand runs.
- Extract worker embeddings: set `EMBEDDING_BACKEND=tensorzero` (default `sentence-transformers`) to route chunk embeddings through the TensorZero gateway, honouring `TENSORZERO_BASE_URL` and `TENSORZERO_EMBED_MODEL` (`gemma_embed_local`, backed by Ollama's `embeddinggemma:300m`). Restart `extract-worker` after changes.
- `supabase/migrations/2025-10-26_transcripts_video_fk.sql` adds the `transcripts.video_id → videos.video_id` foreign key that PostgREST uses for `videos:` joins; pull latest SQL and re-run `make supabase-bootstrap` (or `supabase db reset`) if your stack predates Oct 26 2025.
- `make hirag-notebook-sync` drives `pmoves/scripts/hirag_search_to_notebook.py`, which runs `/hirag/query` for the provided `--query` strings and mirrors those hits into Open Notebook. Set `HIRAG_URL`, `INDEXER_NAMESPACE`, `HIRAG_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN` first; pass `ARGS="--query 'my topic' --k 20 --dry-run"` while testing.
- Qdrant/Meili demo corpus: `make seed-data` rebuilds `hi-rag-gateway-v2` (so the loader ships with the latest code) and executes `/app/scripts/seed_local.py`, reporting the number of vectors upserted (`Qdrant upserted: 3`, `Meili indexed: True` on the stock dataset). Useful after wiping volumes or onboarding a new machine. `make bootstrap-data` runs this automatically after Supabase/Neo4j.
- New in October 2025: containers now honour `SUPA_REST_INTERNAL_URL` (defaults to `http://host.docker.internal:65421/rest/v1`) so compose services call the Supabase CLI stack directly. Host-side scripts continue to rely on `SUPA_REST_URL` (`http://127.0.0.1:65421/rest/v1`); keep both values in sync when rotating credentials.
- December 2025 update: services that publish to Supabase (pmoves-yt, ffmpeg-whisper, hi-rag-gateway-v2) now also read `SUPABASE_URL` and `SUPABASE_KEY`. When you run `supabase start --network-id pmoves-net`, copy the CLI-issued service role key into both `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY`, and set `SUPABASE_URL=http://api.supabase.internal:8000` inside `.env.local` so in-network containers hit the CLI proxy directly.
- Compose alternative:
  - `SUPABASE_RUNTIME=compose make up` → start core stack with compose Postgres/PostgREST.
  - `make supabase-up` / `make supabase-stop` / `make supabase-clean` → manage GoTrue, Realtime, Storage, Studio sidecars.
- Remote handoff:
  - `make supa-extract-remote` → pulls documented endpoints/keys into Markdown when you have remote Supabase credentials.
  - `make supa-use-remote` → swaps `.env.local` to target a self-hosted Supabase instance.
- Schema & seeds:
  - SQL bootstrap lives in `supabase/initdb/00_pmoves_schema.sql` → `06_media_analysis.sql`. Apply with the Supabase CLI (`supabase db reset`) or the Docker-friendly runners (`scripts/apply_migrations_docker.{sh,ps1}`).

## Data, Agents, & Utilities
- `make seed-data` → loads demo vectors into Qdrant/Meilisearch.
- `scripts/discord_ping.{sh,ps1}` → manual Discord webhook validation before enabling automation loops.
- `scripts/buildx-agent-zero.{sh,ps1}` → bake custom Agent Zero images that include PMOVES wrappers.
- `curl -X POST http://localhost:8080/mcp/execute \\
    -H 'Content-Type: application/json' \\
    -d '{"cmd":"notebook.search","arguments":{"query":"<keywords>","limit":5}}'` → invoke the Open Notebook search MCP command once `OPEN_NOTEBOOK_API_URL` and `OPEN_NOTEBOOK_API_TOKEN` are configured. Use `notebook_id`, `tags`, or `source_ids` filters to scope the results surfaced back to Agent Zero operators.
- `scripts/proxmox/pmoves-bootstrap.sh` & `CATACLYSM_STUDIOS_INC/**` → unattended provisioning bundles (refer to the Proxmox or Coolify docs before running on remote hosts).
- `scripts/install/wizard.{sh,ps1}` → interactive bootstrap that chains env setup, dependency installs, and smoke prompts for greenfield machines.
- `make smoke` (Bash) / `scripts/smoke.ps1` (PowerShell) → end-to-end health check of data services, render webhook, Agent Zero, and geometry bus. See `docs/SMOKETESTS.md` for expected output.

## Persistent Data Layout (`pmoves/data/`)
The repository keeps opinionated `gitkeep` stubs so local volumes land in predictable places when Docker mounts bind into the workspace. Buckets and databases still live in Docker volumes; this hierarchy houses agent-specific state that benefits from git-backed defaults:

- `pmoves/data/agent-zero/knowledge/` → upstream Agent Zero documentation mirror used to seed the PMOVES wrapper. `default/main/about/github_readme.md`, `installation.md`, and siblings ship as quick references when the container boots without internet access. Update these mirrors when upstream docs change so our offline knowledge stays fresh.
- `pmoves/data/agent-zero/instruments/` → placeholder for runtime tool manifests; expect JetStream/NATS watchers to drop JSON instrumentation here after smoke runs.
- `pmoves/data/agent-zero/memory/` → conversation and task memory snapshots captured by the PMOVES controller. Clean this directory if you need a cold start (the `gitkeep` preserves the folder).
- `pmoves/data/agent-zero/logs/` → HTML logs from local Agent Zero sessions. Rotate or prune after debugging; the stack writes timestamped files automatically.
- `pmoves/data/open-notebook/notebook_data/` → bind mount backing the Open Notebook UI exports and uploaded research assets.
- `pmoves/data/open-notebook/surreal_data/` → SurrealDB state used by Open Notebook. Keep this directory on fast storage so embeddings and indexes remain responsive between restarts.

When provisioning remote hosts, ensure these directories map to persistent storage (bind mounts or volume mounts). For WSL/Windows users, keep the repo inside the Linux filesystem (`\\wsl$`) to avoid Docker latency when Agent Zero streams logs and knowledge documents.

## Where to Look Next
- Service port map & networking: `pmoves/docs/LOCAL_DEV.md`
- Smoke harness walkthrough: `pmoves/docs/SMOKETESTS.md`
- Supabase deep dives: `docs/SUPABASE_FULL.md`, `docs/SUPABASE_SWITCH.md`
- Agent Zero & Archon integration: `pmoves/services/agent-zero/README.md`, `pmoves/services/archon/README.md`
- Roadmap alignment & evidence logging: `pmoves/docs/NEXT_STEPS.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`
- Local CI workflow mirror (pytest, CHIT grep, SQL policy lint, env preflight): `docs/LOCAL_CI_CHECKS.md`

## Verification & Smokes
- `make smoke-wger` → runs HTTP checks against `http://localhost:8000` and `/static/images/logos/logo-font.svg` through the nginx sidecar so Wger matches the upstream static-serving deployment guidance.citeturn0search0
- `make smoke-firefly` → pings the Firefly III UI (`http://localhost:8082` by default) and `/api/v1/about` using `FIREFLY_ACCESS_TOKEN`. Use `FIREFLY_ROOT_URL`/`FIREFLY_PORT` overrides if you reverse-proxy the finance stack.
