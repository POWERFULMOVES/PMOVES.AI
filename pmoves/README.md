# PMOVES.AI — Orchestration Mesh (Starter)

## Quickstart

### 1. Prepare environment files
- Copy `.env.example` → `.env` once; it holds the base compose settings shared by every service.
- Run the interactive bootstrapper to populate machine-specific secrets and overlays:
  - `make bootstrap` (uses `python -m pmoves.scripts.bootstrap_env` under the hood)
  - Copy `env.shared.example` → `env.shared` (or let `make` auto-seed it) before adding secrets.
  - Pass `BOOTSTRAP_FLAGS="--service supabase"` to scope the prompts, or `--accept-defaults` to reuse existing values without prompting.
- The bootstrap writes `env.shared`, `.env.local`, `env.jellyfin-ai`, and the `env.*.additions` helpers with branded PMOVES defaults, Supabase pointers, and generated secrets. Re-run the command any time you change Supabase endpoints or want to regenerate credentials.
- Manual edits are still supported; re-run `make bootstrap` afterwards to validate and persist updates.

### 2. Choose your Supabase backend
- **Supabase CLI (full feature parity, default path)**
  - Install the `supabase` CLI and run `make supa-init` once per repo.
  - Start/stop with `make supa-start` / `make supa-stop`, inspect endpoints with `make supa-status`, then `make supa-use-local` to copy the CLI defaults into `.env.local` before starting the stack.
  - Deep dive: `docs/SUPABASE_FULL.md` (CLI bootstrap) and `docs/SUPABASE_SWITCH.md` (switching between CLI vs. remote).
- **Compose-backed Supabase (lightweight alt.)**
  - Run `make up-compose` to boot the core stack with compose Postgres/PostgREST enabled, then `make supabase-up` to add GoTrue/Realtime/Storage/Studio from `docker-compose.supabase.yml`.
  - Stop the Supabase sidecars with `make supabase-stop` (or `make down` for everything) and clear data with `make supabase-clean`.
- **Remote/self-hosted Supabase**
  - Populate `.env.supa.remote` with your endpoints/keys (generate from `supa.md` via `make supa-extract-remote` if provided).
  - Apply the remote profile with `make supa-use-remote` before running the main stack.

### 3. Start the PMOVES stack
- `make up` — default entry point. Brings up the data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`), all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`), plus pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When `SUPABASE_RUNTIME=compose` it automatically chains to `make supabase-up`.
- `make preflight` — run the bootstrap validator without starting containers. `make up` runs this check automatically and exits early if required secrets are missing.
- `make up-cli` / `make up-compose` — one-shot shims that force CLI vs. compose Supabase for a single `make up` run.
- `make up-workers` — only the worker layer (assumes data profile is already running).
- `make up-media` — opt-in GPU analyzers (`media-video`, `media-audio`).
- `make up-jellyfin` — Jellyfin bridge in isolation.
- `make jellyfin-folders` — provision `pmoves/data/jellyfin/{config,cache,transcode,media/...}` so the external Jellyfin service launches with Movies/TV/Music folders ready to scan.
- `make up-yt` — YouTube ingest stack if you want to start it separately.
- `make up-nats` — spins up the NATS broker and updates `.env.local` with `YT_NATS_ENABLE=true` and the default connection URL. Required before enabling the agents profile.
- Additional helpers: `make ps`, `make down`, `make clean`. See `docs/MAKE_TARGETS.md` for the full catalogue.
- Open Notebook workspace: `make notebook-up` starts the Streamlit UI (8502) and REST API (5055) defined in `docker-compose.open-notebook.yml`. Populate `env.shared` with `OPEN_NOTEBOOK_API_URL` (defaults to `http://cataclysm-open-notebook:5055`) plus either `OPEN_NOTEBOOK_PASSWORD` or `OPEN_NOTEBOOK_API_TOKEN` before launching. Once your provider keys (`OPENAI_API_KEY`, `GROQ_API_KEY`, etc.) live in `env.shared`, run `make notebook-seed-models` to register models/defaults in SurrealDB so the UI drop-downs are pre-populated. Use `make notebook-logs` for live output and `make notebook-down` to stop the container while preserving data in `pmoves/data/open-notebook/`.

### Dev Environment (Conda + Windows/macOS/Linux)

- Baseline interpreter: Python 3.11 (installed via the provided Conda environment).
- Conda: create the env and install deps once:
  - Windows (PowerShell 7+):
    - (Admin) `choco install make -y` to get GNU Make
    - `conda env create -f environment.yml -n PMOVES.AI`
    - `pwsh -File scripts/install_all_requirements.ps1 -CondaEnvName PMOVES.AI`
  - Linux/macOS:
    - `conda env create -f environment.yml -n pmoves-ai`
    - `bash scripts/install_all_requirements.sh pmoves-ai`

Activate your env before running local services (example):
- Windows: `conda activate PMOVES.AI`
- Linux/macOS: `conda activate pmoves-ai`

Services
- `hi-rag-gateway-v2` (8087→8086 in-container): Hybrid RAG with reranker providers (Flag/Qwen/Cohere/Azure). See `docs/HI_RAG_RERANKER.md` and `docs/HI_RAG_RERANK_PROVIDERS.md`.
  - Realtime: v2 now auto-derives a websocket URL from `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` when a host-only DNS is detected. Prefer `pmoves/.env.local`:
    - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
    - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:65421/rest/v1`
    - `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`
  - Lexical: set `USE_MEILI=true` in `pmoves/.env.local` to enable Meilisearch (enabled by default in this repo’s `.env.local`).
  - GPU variant default reranker: Qwen/Qwen3-Reranker-4B (overridable via `RERANK_MODEL`).
- `retrieval-eval` (8090): Dashboard/tests; points to `hi-rag-gateway-v2`.
- `presign` (8088): MinIO presign API for ComfyUI uploads. See `docs/COMFYUI_MINIO_PRESIGN.md`.
- `render-webhook` (8085): ComfyUI completion → Supabase Studio. See `docs/RENDER_COMPLETION_WEBHOOK.md`.
- `langextract` (8084): Core extraction service (text/XML → chunks, errors). See `docs/LANGEXTRACT.md`.
- `extract-worker` (8083): Ingests LangExtract output to Qdrant/Meili and Supabase.
- `notebook-sync` (8095): Polls the Open Notebook REST API, normalizes payloads, and pushes them through LangExtract + extrac
t-worker to keep Qdrant/Meili/Supabase aligned.
- Agents (profile `agents`): `nats`, `agent-zero` (8080), `archon` (8091) — opt-in.

Notes
- Legacy `hi-rag-gateway` remains available. Use `make up-legacy` to start it with `retrieval-eval` targeting the legacy gateway.
- Compose snippets for services are already merged in `docker-compose.yml` for ease-of-use.
- Persistent bind mounts live under `pmoves/data/`; see `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` for how Agent Zero knowledge/logs are pre-seeded there and tips on keeping them synced with upstream docs.

### Tests

- Smoke tests stub external dependencies and can run offline: `pytest pmoves/tests`.
- Verify the external Wger stack after `make up-external`: `make smoke-wger` checks the nginx proxy plus static bundle.citeturn0search0

Agents Profile
- Run `make up-nats` first to ensure the broker and `.env.local` flags are ready.
- Start: `docker compose --profile agents up -d nats agent-zero archon mesh-agent publisher-discord`
- Defaults: agents read `NATS_URL=nats://nats:4222`; override via `.env`/`.env.local` if you are targeting an external broker.
- Explore architecture and workflows in `docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md`.

Supabase (Full)
- Recommended: Supabase CLI (see `docs/SUPABASE_FULL.md`). Or use `docker-compose.supabase.yml` with `./scripts/pmoves.ps1 up-fullsupabase`.
- Realtime demo: `http://localhost:8090/static/realtime.html` (subscribe to `studio_board`, `it_errors`; upload avatar and assign to a row).

## Codex VM Bootstrap

- Recommended profile: auto-approve with full access when you need maximum autonomy; otherwise use a safer `workspace-write` profile for day-to-day.
- When the project loads in Codex, run:
  - Windows: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName PMOVES.AI`
  - Linux/macOS: `bash scripts/codex_bootstrap.sh PMOVES.AI`
- Full Codex config examples live in `docs/codex_full_config_bundle/README-Codex-MCP-Full.md`.
