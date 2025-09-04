# Repository Guidelines

## Project Structure & Module Organization
- `services/`: Python microservices (FastAPI workers, utilities). Examples: `agent-zero/`, `hi-rag-gateway/`, `retrieval-eval/`, `graph-linker/`, `publisher/`.
- `contracts/`: Event contracts (`schemas/`) and `topics.json` mapping topics → schema paths.
- `schemas/`: Shared domain models used across services.
- `supabase/`, `neo4j/`, `services/*/migrations/`: DB migrations and Cypher/SQL.
- `n8n/`, `comfyui/`: Workflow exports and ComfyUI assets.
- `datasets/`, `docs/`: Sample data and documentation.
- Root: `docker-compose.yml`, `Makefile`, `.env.example`.

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

## Commit & Pull Request Guidelines
- Prefer Conventional Commits (e.g., `feat(hi-rag): hybrid search option`).
- PRs should include: clear description, linked issues, affected services, run/rollback notes, and screenshots for UI/flows (e.g., retrieval-eval dashboard).
- Keep changes atomic; update docs/schemas when interfaces change.

## Security & Configuration Tips
- Copy `.env.example` → `.env`; never commit secrets. Key envs: `PMOVES_CONTRACTS_DIR` for schema resolution.
- Use Compose profiles (`data`, `workers`) to scope what runs locally.
- Validate payloads against schemas before publishing events (`services/common/events.py`).

