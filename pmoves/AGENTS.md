# Repository Guidelines

## Project Structure & Module Organization
- `services/`: Python microservices (FastAPI workers, utilities). Examples: `agent-zero/`, `hi-rag-gateway/`, `retrieval-eval/`, `graph-linker/`, `publisher/`.
- `contracts/`: Event contracts (`schemas/`) and `topics.json` mapping topics → schema paths.
- `schemas/`: Shared domain models used across services.
- `supabase/`, `neo4j/`, `services/*/migrations/`: DB migrations and Cypher/SQL.
- `n8n/`, `comfyui/`: Workflow exports and ComfyUI assets.
- `datasets/`, `docs/`: Sample data and documentation.
- Root: `docker-compose.yml`, `Makefile`, `.env.example`.

## Planning & Documentation Expectations
- **Mandatory context before changes:** read `docs/ROADMAP.md` and `docs/NEXT_STEPS.md` to align with the current sprint focus (M2 — Creator & Publishing). These documents spell out the active priorities, including Jellyfin refresh polish, Discord embeds, and Supabase→Discord automation; confirm your work reinforces or explicitly updates those targets before you start coding.
- **Maintainer cadence:** when significant features ship, priorities move between columns, or we start a new sprint, refresh both `docs/ROADMAP.md` and `docs/NEXT_STEPS.md` (and adjust their `_Last updated` timestamps) so contributors always land on the latest plan.
- **Supporting references:**
  - `docs/MAKE_TARGETS.md` — authoritative Make targets, smoke checks, and automation entry points.
  - `docs/README_DOCS_INDEX.md` — high-level index of the documentation set and where to find service-specific guides.
  - Additional operational primers live alongside services (e.g., `services/**/README.md`) and should be consulted when touching those areas.

## Build, Test, and Development Commands
- `make up`: Starts core data services and workers (qdrant, neo4j, minio, meilisearch, hi-rag-gateway, retrieval-eval) via Docker Compose profiles.
- `make down`: Stops all containers.
- `make clean`: Stops and removes volumes (destructive for local data).
- Run a service locally (example): `python services/agent-zero/main.py` (installs deps first: `pip install -r services/agent-zero/requirements.txt`).
- Logs: `docker compose logs -f <service>`.

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indentation, prefer type hints.
- FastAPI routes: snake_case function names; path names kebab-case only in URLs.
- Event contracts: keep `v{n}` suffix in filenames (e.g., `*.v1.schema.json`) and update `contracts/topics.json` when adding topics.
- Keep modules small and single‑purpose; share helpers in `services/common/`.

## Testing Guidelines
- Current repo has minimal automated tests. When adding tests, use `pytest` with `tests/` per service (e.g., `services/<name>/tests/test_*.py`).
- Mock external systems (NATS, MinIO, Neo4j) and validate envelope/schema with sample payloads.
- Suggested commands: `pip install -r services/<name>/requirements.txt pytest` then `pytest -q`.
- Before pushing, mirror the GitHub Actions checks documented in `docs/LOCAL_CI_CHECKS.md` (pytest suites, `make chit-contract-check`, `make jellyfin-verify` when the publisher is affected, SQL policy lint, env preflight). Capture each command/output in the PR template’s Testing section.
- If you intentionally skip one of those checks (docs-only change, etc.), record the rationale in the PR Reviewer Notes so reviewers know the risk envelope.
- JetStream drift can surface as `nats: JetStream.Error cannot create queue subscription…` in the Agent Zero container logs. Rebuild with `docker compose build agent-zero && docker compose up -d agent-zero` so the pull-subscribe controller code ships and the consumer metadata is recreated automatically.

## Commit & Pull Request Guidelines
- Prefer Conventional Commits (e.g., `feat(hi-rag): hybrid search option`).
- PRs should include: clear description, linked issues, affected services, run/rollback notes, and screenshots for UI/flows (e.g., retrieval-eval dashboard).
- Keep changes atomic; update docs/schemas when interfaces change.

## Security & Configuration Tips
- Copy `.env.example` → `.env`; never commit secrets. Key envs: `PMOVES_CONTRACTS_DIR` for schema resolution.
- Use Compose profiles (`data`, `workers`) to scope what runs locally.
- Validate payloads against schemas before publishing events (`services/common/events.py`).


## Environment Bootstrap (Codex + Local)

- Preferred Python: Conda 3.10+ (env name: `PMOVES.AI` or `pmoves-ai`). A ready-to-use `environment.yml` is at the repo root.
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
