# PMOVES.AI — Orchestration Mesh (Starter)

## Quickstart

### 1. Prepare environment files
- Windows (no Make): `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`
- Or use Make targets: `make env-setup` then `make env-check` to interactively generate and verify `.env`.
- Copy `.env.example` → `.env`. This is the base configuration shared across every compose service.
- Layer in secrets and provider credentials from the `*.additions` helpers (copy/paste the values into your `.env`). Common entries:
  - `env.presign.additions`
  - `env.render_webhook.additions`
  - `env.hirag.reranker.additions` and `env.hirag.reranker.providers.additions`
  - `env.publisher.enrich.additions` (if using the Discord publisher or enrichment flows)
- Optional overlay: copy `.env.local.example` → `.env.local` for per-machine overrides. Supabase helper targets keep this file fresh when you toggle between providers (see below).
- Additional Supabase templates live at `.env.supa.local.example` and `.env.supa.remote.example`. They are swapped into `.env.local` via `make supa-use-local` / `make supa-use-remote`.

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
- `make up` — default entry point. Brings up the data profile (`qdrant`, `neo4j`, `minio`, `meilisearch`, `presign`), all default workers (`hi-rag-gateway-v2`, `retrieval-eval`, `render-webhook`, `langextract`, `extract-worker`), plus pmoves.yt (`ffmpeg-whisper`, `pmoves-yt`) and the Jellyfin bridge. When `SUPA_PROVIDER=compose` it automatically chains to `make supabase-up`.
- `make up-cli` / `make up-compose` — one-shot shims that force CLI vs. compose Supabase for a single `make up` run.
- `make up-workers` — only the worker layer (assumes data profile is already running).
- `make up-media` — opt-in GPU analyzers (`media-video`, `media-audio`).
- `make up-jellyfin` — Jellyfin bridge in isolation.
- `make up-yt` — YouTube ingest stack if you want to start it separately.
- `make up-nats` — spins up the NATS broker and updates `.env.local` with `YT_NATS_ENABLE=true` and the default connection URL. Required before enabling the agents profile.
- Additional helpers: `make ps`, `make down`, `make clean`. See `docs/MAKE_TARGETS.md` for the full catalogue.

### Dev Environment (Conda + Windows/macOS/Linux)

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
- `retrieval-eval` (8090): Dashboard/tests; points to `hi-rag-gateway-v2`.
- `presign` (8088): MinIO presign API for ComfyUI uploads. See `docs/COMFYUI_MINIO_PRESIGN.md`.
- `render-webhook` (8085): ComfyUI completion → Supabase Studio. See `docs/RENDER_COMPLETION_WEBHOOK.md`.
- `langextract` (8084): Core extraction service (text/XML → chunks, errors). See `docs/LANGEXTRACT.md`.
- `extract-worker` (8083): Ingests LangExtract output to Qdrant/Meili and Supabase.
- Agents (profile `agents`): `nats`, `agent-zero` (8080), `archon` (8091) — opt-in.

Notes
- Legacy `hi-rag-gateway` remains available. Use `make up-legacy` to start it with `retrieval-eval` targeting the legacy gateway.
- Compose snippets for services are already merged in `docker-compose.yml` for ease-of-use.

### Tests

- Smoke tests stub external dependencies and can run offline: `pytest pmoves/tests`.

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
