# Repository Guidelines

## Project Structure & Module Organization
- `services/`: Python microservices (FastAPI workers, utilities). Examples: `agent-zero/`, `hi-rag-gateway/`, `retrieval-eval/`, `graph-linker/`, `publisher/`.
- `contracts/`: Event contracts (`schemas/`) and `topics.json` mapping topics → schema paths.
- `schemas/`: Shared domain models used across services.
- `supabase/`, `neo4j/`, `services/*/migrations/`: DB migrations and Cypher/SQL.
- `n8n/`, `comfyui/`: Workflow exports and ComfyUI assets.
- `datasets/`, `docs/`: Sample data and documentation.
- Root: `docker-compose.yml`, `Makefile`, `env.shared.example`.

## Planning & Documentation Expectations
- **Mandatory context before changes:** read `docs/ROADMAP.md` and `docs/NEXT_STEPS.md` to align with the current sprint focus (M2 — Creator & Publishing). These documents spell out the active priorities, including Jellyfin refresh polish, Discord embeds, and Supabase→Discord automation; confirm your work reinforces or explicitly updates those targets before you start coding.
- **Maintainer cadence:** when significant features ship, priorities move between columns, or we start a new sprint, refresh both `docs/ROADMAP.md` and `docs/NEXT_STEPS.md` (and adjust their `_Last updated` timestamps) so contributors always land on the latest plan.
- **Supporting references:**
  - `docs/MAKE_TARGETS.md` — authoritative Make targets, smoke checks, and automation entry points.
  - `docs/README_DOCS_INDEX.md` — high-level index of the documentation set and where to find service-specific guides.
  - Jellyfin integration runbooks live under `pmoves/docs/PMOVES.AI PLANS/` (see `JELLYFIN_BRIDGE_INTEGRATION.md`, `JELLYFIN_BACKFILL_PLAN.md`, and `Enhanced Media Stack with Advanced AudioVideo Analysis/`).
  - Additional operational primers live alongside services (e.g., `services/**/README.md`) and should be consulted when touching those areas.

## Build, Test, and Development Commands
- `make up`: Starts core data services and workers (qdrant, neo4j, minio, meilisearch, hi-rag-gateway, retrieval-eval) via Docker Compose profiles.
- `make down`: Stops all containers.
- `make clean`: Stops and removes volumes (destructive for local data).
- Run a service locally (example): `python services/agent-zero/main.py` (installs deps first: `pip install -r services/agent-zero/requirements.txt`).
- Logs: `docker compose logs -f <service>`.

## Coding Style & Naming Conventions
- Python 3.11+, 4‑space indentation, prefer type hints.
- FastAPI routes: snake_case function names; path names kebab-case only in URLs.
- Event contracts: keep `v{n}` suffix in filenames (e.g., `*.v1.schema.json`) and update `contracts/topics.json` when adding topics.
- Keep modules small and single‑purpose; share helpers in `services/common/`.

## Testing Guidelines
- Current repo has minimal automated tests. When adding tests, use `pytest` with `tests/` per service (e.g., `services/<name>/tests/test_*.py`).
- Mock external systems (NATS, MinIO, Neo4j) and validate envelope/schema with sample payloads.
- Suggested commands: `pip install -r services/<name>/requirements.txt pytest` then `pytest -q`.
- Before pushing, mirror the GitHub Actions checks documented in `docs/LOCAL_CI_CHECKS.md` (pytest suites, `make chit-contract-check`, `make jellyfin-verify` when the publisher is affected, SQL policy lint, env preflight). Capture each command/output in the PR template’s Testing section.
- If you intentionally skip one of those checks (docs-only change, etc.), record the rationale in the PR Reviewer Notes so reviewers know the risk envelope.
- UI updates: run `make -C pmoves notebook-workbench-smoke ARGS="--thread=<uuid>"` to lint the Next.js bundle and validate Supabase connectivity. Reference `pmoves/docs/UI_NOTEBOOK_WORKBENCH.md` when collecting smoke evidence.
- Hi-RAG gateway: after touching reranker or embedding code, run `make -C pmoves smoke-gpu`. The target now pipes the validation query through `docker compose exec` so FlagEmbedding/Qwen rerankers that only accept batch size 1 still report `"used_rerank": true` (first run downloads the 4B checkpoint).

## Stabilization Snapshot (Nov 6, 2025)
- Storage unified to Supabase Storage S3 endpoint. Ensure in `pmoves/env.shared`:
  - `MINIO_ENDPOINT=http://host.docker.internal:65421/storage/v1/s3`
  - `MINIO_REGION=local`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` from `make -C pmoves supa-status`.
- Invidious bound to `127.0.0.1:3005` (stats 200). Companion/HMAC keys stamped in `pmoves/.env`.
- Hi‑RAG v2: GPU on `:8087`, CPU on `:8086`. Health path is `/hirag/admin/stats`.
- Core smoke: PASS. GPU smoke: rerank temporarily disabled (`RERANK_ENABLE=false`) while model/runtime is validated.
- Jellyfin: server 8096 OK; bridge 8093 OK.
- Monitoring: Prometheus/Grafana OK; Loki config upgrade pending.

### Operator quick links
- Supabase Studio: http://127.0.0.1:65433  • REST: http://127.0.0.1:65421/rest/v1
- Hi‑RAG v2 GPU: http://localhost:8087/hirag/admin/stats
- Invidious: http://127.0.0.1:3005
- Jellyfin: http://localhost:8096 • Bridge API: http://localhost:8093
- Grafana: http://localhost:3002 • Prometheus: http://localhost:9090

### Next actions
- Finish Loki config and confirm `/ready` 200.
- Re‑enable GPU rerank and add an integration smoke.
- Force offline transcript provider (`YT_TRANSCRIPT_PROVIDER=qwen2-audio`) in smoketest IDs; broaden fallback detection.

### Console & Personas
- Console dev helpers: `make -C pmoves ui-dev-start` (port 3001, auto-loads env and boot JWT), `ui-dev-stop`, and `ui-dev-logs`.
- Personas (v5.12): `pmoves_core.personas` is created and seeded with the `Archon` persona. To reapply schema/seeds: `make -C pmoves supabase-bootstrap`. Verify with:
  ```bash
  supadb=$(docker ps --format '{{.Names}}' | grep -m1 '^supabase_db_');
  docker exec -it "$supadb" psql -U postgres -d postgres -c "select name,version from pmoves_core.personas;"
  ```
- JetStream drift can surface as `nats: JetStream.Error cannot create queue subscription…` in the Agent Zero container logs. Rebuild with `docker compose build agent-zero && docker compose up -d agent-zero` so the pull-subscribe controller code ships and the consumer metadata is recreated automatically.

#### Health badges and custom endpoints

The console Quick Links probe Agent Zero and Archon using `/healthz` by default. If your forks expose different health endpoints, set:

- `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`)
- `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`)

Personas page fallback when Supabase CLI REST hides `pmoves_core`:

- Start a PostgREST bound to the CLI DB: `docker compose -p pmoves up -d postgrest-cli` (host `http://localhost:3011`).
- Personas page now uses Supabase REST by default. Ensure the Supabase CLI stack is running (REST on `http://host.docker.internal:65421/rest/v1`). Only set `POSTGREST_URL=http://localhost:3011` if you explicitly bring up the legacy compose PostgREST fallback.

See also: `pmoves/docs/SERVICE_HEALTH_ENDPOINTS.md`.

### Agents UIs one‑click bring‑up

- Published images (default):
  - `make -C pmoves up-agents-ui` — starts NATS, Agent Zero API, Archon API, and the Archon UI. Open the UIs:
    - Agent Zero UI: `${NEXT_PUBLIC_AGENT_ZERO_UI_URL:-http://localhost:8081}`
    - Archon UI: `${NEXT_PUBLIC_ARCHON_UI_URL:-http://localhost:3737}`
- From your forks (integrations workspace):
  - `make -C pmoves agents-integrations-clone` (once)
  - `make -C pmoves build-agents-integrations`
  - `make -C pmoves up-agents-integrations`

### Reproducible integration images (GHCR)

The GHCR workflow (`.github/workflows/integrations-ghcr.yml`) builds/publishes multi‑arch images nightly and on demand for:

- Agent Zero API (`pmoves-agent-zero`)
- Archon API (`pmoves-archon`)
- Archon UI (`pmoves-archon-ui`)
- Open Notebook (`pmoves-open-notebook`)
- Jellyfin (`pmoves-jellyfin`)
- Firefly III (`pmoves-firefly-iii`)
- Wger (`pmoves-health-wger`)
- PMOVES.YT (`pmoves-yt`)

Pin images by setting `AGENT_ZERO_IMAGE`, `ARCHON_IMAGE`, `ARCHON_UI_IMAGE`, and `PMOVES_YT_IMAGE` in `pmoves/env.shared`.

## Bring-Up Sequence
- Prefer `make first-run` to bootstrap secrets, start the Supabase CLI stack, launch core/agent/external services, seed Supabase + Neo4j + Qdrant, and run the smoketests in one shot (see `docs/FIRST_RUN.md`).
- Manual flow: `make bootstrap` → `make supabase-boot-user` → `make supa-start` → `make up` → `make bootstrap-data` → `make up-agents` → `make up-external` → `make smoke`.

## Smoketests & Diagnostics
- Full harness: `make smoke`
- Discord publisher: `make discord-smoke` (requires `DISCORD_WEBHOOK_URL` in `env.shared`/`.env.local`; host port 8094).
- Geometry web UI: `make web-geometry`
- Health checks: `make health-agent-zero`, `make health-publisher-discord`, `make health-jellyfin-bridge`
- External integrations: `make smoke-wger`, `make smoke-presign-put`, `make yt-jellyfin-smoke` (pmoves.yt ingest + Jellyfin playback; ensure `make up`, `make up-yt`, `make up-invidious`, and `make up-jellyfin` are running, and keep the overlay `JELLYFIN_API_KEY` in sync so the bridge can mint playback URLs) or `make jellyfin-smoke` (playback-only; the target now attempts `/jellyfin/map-by-title` first and, if that misses, links the newest Jellyfin library item through `/jellyfin/link` before requesting a playback URL). Keep `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` pointed at the active Supabase REST host — `http://host.docker.internal:65421/rest/v1` when the CLI stack is running, and set `HIRAG_URL`/`HIRAG_GPU_URL` to `http://hi-rag-gateway-v2-gpu:8086` so CGPs land in the GPU ShapeStore before falling back to `HIRAG_CPU_URL`.
- Creative CGP demos: `make demo-health-cgp`, `make demo-finance-cgp`, plus manual WAN/Qwen/VibeVoice webhook triggers (see `pmoves/creator/README.md`).
- Environment sanity: `make preflight` (tooling) and `make flight-check` (runtime)

### UI Quickstart & Links
- Supabase Studio → http://127.0.0.1:65433 (`make -C pmoves supa-start`; status via `make -C pmoves supa-status`).
- Notebook Workbench → http://localhost:3000/notebook-workbench (`npm run dev` in `pmoves/ui`; the launcher now layers `env.shared` + `.env.local` automatically; smoke with `make -C pmoves notebook-workbench-smoke`).
- TensorZero Playground → http://localhost:4000 (`make -C pmoves up-tensorzero`; this target now launches ClickHouse, the gateway/UI, and `pmoves-ollama` so embeddings resolve on http://localhost:3030). If you’re on Jetson/arm64 or delegating inference, point `TENSORZERO_BASE_URL` at a remote gateway instead.
- Firefly Finance → http://localhost:8082 (`make -C pmoves up-external-firefly`; configure `FIREFLY_*` secrets).
- Wger Coach Portal → http://localhost:8000 (`make -C pmoves up-external-wger`; brand defaults apply automatically).
- Jellyfin Media Hub → http://localhost:8096 (`make -C pmoves up-external-jellyfin`; run `make -C pmoves jellyfin-folders` and drop media into `pmoves/data/jellyfin` if you need the legacy stack).
- Jellyfin AI Overlay → http://localhost:9096 (`make -C pmoves up-jellyfin-ai`; exposes API gateway on http://localhost:8300 and dashboard on http://localhost:8400; seed a sample asset with `python scripts/seed_jellyfin_media.py` so smoketests have something to link).
- Invidious + Companion → http://127.0.0.1:3000 / http://127.0.0.1:8282 (`make -C pmoves up-invidious`; provides YouTube fallback for pmoves.yt).
- Open Notebook UI → http://localhost:8503 (`docker start cataclysm-open-notebook` or `make -C pmoves notebook-up`; keep password/token aligned).
- n8n Automation → http://localhost:5678 (`make -C pmoves up-n8n`; flows sync from `pmoves/integrations`).

## Commit & Pull Request Guidelines
- Prefer Conventional Commits (e.g., `feat(hi-rag): hybrid search option`).
- PRs should include: clear description, linked issues, affected services, run/rollback notes, and screenshots for UI/flows (e.g., retrieval-eval dashboard).
- Keep changes atomic; update docs/schemas when interfaces change.

## Security & Configuration Tips
- Copy `env.shared.example` → `env.shared`; never commit secrets. Keep shared defaults in `env.shared` and machine-specific overrides in `.env.local`. Key envs: `PMOVES_CONTRACTS_DIR` for schema resolution.
- Branded Open Notebook deployments reuse the UI password as the API bearer token; keep `OPEN_NOTEBOOK_API_TOKEN` aligned with `OPEN_NOTEBOOK_PASSWORD` so ingestion helpers and agents authenticate successfully.
- When working with Open Notebook, populate `OPEN_NOTEBOOK_SURREAL_URL` / `OPEN_NOTEBOOK_SURREAL_ADDRESS` (or the legacy `SURREAL_*` aliases) so the Streamlit UI can reach SurrealDB inside Compose.
- To keep embeddings local, launch your provider (e.g., `ollama`) and set `OLLAMA_API_BASE` before running `make notebook-seed-models`; the seeder will add `ollama`-backed models so Notebook never calls external APIs unless you want it to.
- Use Compose profiles (`data`, `workers`) to scope what runs locally.
- Validate payloads against schemas before publishing events (`services/common/events.py`).


## Environment Bootstrap (Codex + Local)

- Preferred Python: Conda 3.11+ (env name: `PMOVES.AI` or `pmoves-ai`). A ready-to-use `environment.yml` is at the repo root.
- One‑time setup on Windows (PowerShell 7+):
  - Install GNU Make (Chocolatey): `choco install make -y` (requires admin PowerShell).
  - Create/refresh Conda env: `conda env create -f environment.yml -n PMOVES.AI` (or use the default name inside the file).
  - Install service deps: `pwsh -File scripts/install_all_requirements.ps1 -CondaEnvName PMOVES.AI`.
- Linux/macOS:
  - `conda env create -f environment.yml -n pmoves-ai`
  - `bash scripts/install_all_requirements.sh pmoves-ai`

### Codex VM / Profiles

- For maximum autonomy, use a Codex profile with:
  - `approval_policy = "never"` (auto-approve),
  - `sandbox_mode = "danger-full-access"`,
  - `network_access = true`.
- When opening this repo, run the bootstrap:
  - Windows: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName PMOVES.AI`
  - Linux/macOS: `bash scripts/codex_bootstrap.sh PMOVES.AI`
- See `docs/codex_full_config_bundle/README-Codex-MCP-Full.md` for a complete `config.toml` with sensible profiles.

### Notes

- The bootstrap prefers `uv pip` if available (faster); otherwise falls back to `python -m pip`.
- The scripts install requirements from `services/*/requirements.txt` and `tools/*/requirements.txt`. Pass `-IncludeDocs` (PowerShell) or `INCLUDE_DOCS=1` (Bash) to include `docs/**/requirements.txt`.
