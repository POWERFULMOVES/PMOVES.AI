# PMOVES.AI — Orchestration Mesh (Starter)

## Quickstart

### One command, full stack

```bash
make first-run
```

This aggregates the entire onboarding sequence: env bootstrap, Supabase CLI bring-up, core + agent + external compose profiles, Supabase/Neo4j/Qdrant seeding, and the smoketest harness. A full breakdown lives in [docs/FIRST_RUN.md](docs/FIRST_RUN.md).

### Manual path

#### 1. Prepare environment files
- Copy `pmoves/env.shared.example` → `pmoves/env.shared` so every container ships with the branded defaults (Supabase CLI endpoints, Discord/Jellyfin tokens, MinIO buckets, etc.).
- Run the interactive bootstrapper to layer machine-specific secrets on top:
  - `make bootstrap` (wraps `python -m pmoves.scripts.bootstrap_env`) or `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults`
  - Pass `BOOTSTRAP_FLAGS="--service supabase"` to scope the prompts when needed.
- The bootstrap now writes `env.shared`, `.env.generated`, `.env.local`, `env.jellyfin-ai`, and the `env.*.additions` helpers so Docker Compose, Supabase CLI, and the UI all read the same values. Compose loads them in order (`env.shared.generated` → `env.shared` → `.env.generated` → `.env.local`), and the UI launcher mirrors that stack via `scripts/with-env.mjs`.
- Manual edits remain supported—adjust `env.shared` for shared defaults or `.env.local` for host-specific overrides, then rerun `make bootstrap` (or `make env-check`) to validate.

#### 2. Choose your Supabase backend
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

#### 3. Start the PMOVES stack
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

### Model selection (Ollama / TensorZero / OpenAI-compatible)

- List profiles: `make -C pmoves model-profiles`
- Apply defaults for Hi‑RAG/Archon: `make -C pmoves model-apply PROFILE=archon HOST=workstation_5090`
- Apply defaults for Agent Zero: `make -C pmoves model-apply PROFILE=agent-zero HOST=workstation_5090`
- Pre‑pull local models: `make -C pmoves models-seed-ollama`
- Restart gateways after changes: `make -C pmoves recreate-v2` (and `recreate-v2-gpu` if using GPU)

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

## Dashboards & UIs
- Supabase Studio (CLI): http://127.0.0.1:65433 — `make supa-start`.
- Agent Zero UI: http://localhost:8080 — `make up-agents`.
- Archon Health: http://localhost:8091/healthz — `make up-agents`.
- Hi‑RAG v2 Geometry Console (GPU): http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/geometry/ — `make up`.
- TensorZero UI: http://localhost:4000; Gateway: http://localhost:3030 — `make up-tensorzero`.
- Jellyfin: http://localhost:8096 — `make -C pmoves up-jellyfin-ai`.
- Jellyfin API Dashboard: http://localhost:8400; Gateway: http://localhost:8300 — `make -C pmoves up-jellyfin-ai`.
- Open Notebook: http://localhost:8503 — `make -C pmoves notebook-up`.
- Invidious: http://127.0.0.1:3000 (companion http://127.0.0.1:8282) — `make -C pmoves up-invidious`.
- n8n: http://localhost:5678 — `make -C pmoves up-n8n`.

### Default access and operator credentials
- Supabase boot operator is provisioned by `make supabase-boot-user` and written to `pmoves/env.shared` / `pmoves/.env.local`:
  - `SUPABASE_BOOT_USER_EMAIL`, `SUPABASE_BOOT_USER_PASSWORD`, `SUPABASE_BOOT_USER_JWT`.
  - The console auto‑auths via `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT`; to sign in manually, copy the email/password from your env files.
- Jellyfin admin/API: confirm user and key in the Jellyfin UI; keep `JELLYFIN_API_KEY` and `JELLYFIN_USER_ID` in sync in `pmoves/env.shared` or `pmoves/env.jellyfin-ai` if rotated.

Supabase (Full)
- Recommended: Supabase CLI (see `docs/SUPABASE_FULL.md`). Or use `docker-compose.supabase.yml` with `./scripts/pmoves.ps1 up-fullsupabase`.
- Realtime demo: `http://localhost:8090/static/realtime.html` (subscribe to `studio_board`, `it_errors`; upload avatar and assign to a row).

## Codex VM Bootstrap

- Recommended profile: auto-approve with full access when you need maximum autonomy; otherwise use a safer `workspace-write` profile for day-to-day.
- When the project loads in Codex, run:
  - Windows: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName PMOVES.AI`
  - Linux/macOS: `bash scripts/codex_bootstrap.sh PMOVES.AI`
- Full Codex config examples live in `docs/codex_full_config_bundle/README-Codex-MCP-Full.md`.
