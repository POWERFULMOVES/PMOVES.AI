# PMOVES.AI — Orchestration Mesh (Starter)

## Quickstart
- Create `.env` (copy values as needed from the `*.additions` files):
  - `env.presign.additions`
  - `env.render_webhook.additions`
  - `env.hirag.reranker.additions` and `env.hirag.reranker.providers.additions`
- Start data + workers (v2 gateway by default):
  - `make up`
  - Or directly: `docker compose --profile data --profile workers up -d qdrant neo4j minio meilisearch presign hi-rag-gateway-v2 retrieval-eval render-webhook`

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

Agents Profile
- Start: `docker compose --profile agents up -d nats agent-zero archon`
- Defaults: both use `NATS_URL=nats://nats:4222`; change via `.env` if external broker is used.

Supabase (Full)
- Recommended: Supabase CLI (see `docs/SUPABASE_FULL.md`). Or use `docker-compose.supabase.yml` with `./scripts/pmoves.ps1 up-fullsupabase`.
- Realtime demo: `http://localhost:8090/static/realtime.html` (subscribe to `studio_board`, `it_errors`; upload avatar and assign to a row).

## Codex VM Bootstrap

- Recommended profile: auto-approve with full access when you need maximum autonomy; otherwise use a safer `workspace-write` profile for day-to-day.
- When the project loads in Codex, run:
  - Windows: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName PMOVES.AI`
  - Linux/macOS: `bash scripts/codex_bootstrap.sh PMOVES.AI`
- Full Codex config examples live in `docs/codex_full_config_bundle/README-Codex-MCP-Full.md`.
