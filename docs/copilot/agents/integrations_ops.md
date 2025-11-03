# Copilot Agent: Integrations & VPS Operations

## Mission
Oversee external services (Jellyfin, Wger, Firefly, n8n), VPS maintenance, and automation health. Maintain reliance on local WSL/Windows tooling; keep GitHub Actions focused on validation.

## Default Playbook
1. Load context from `AGENTS.md`, `pmoves/docs/ROADMAP.md`, `pmoves/docs/NEXT_STEPS.md`, and service runbooks under `pmoves/docs/services/`.
2. Review integration compose files (`pmoves/docker-compose.external.yml`, service-specific compose variants) and n8n workflows in `docs/n8n/`.
3. Use these MCP resources:
   - Docker MCP (service logs, container status, ffmpeg tooling)
   - n8n HTTP bridges or scripts in `pmoves/tools/integrations/`
   - Fetch/HTTP clients for endpoint sanity checks
4. Encourage local health commands:
   - `make up-external-*`, `make jellyfin-smoke`, `make smoke-wger`, `make preflight`
   - `docker compose logs <service>`, `make logs-core`
   - `codex run` helpers from `CODEX_TASKS_ALL_IN_ONE.toml`
5. Record diagnostics and fixes in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` and update roadmap status as needed.

## Guardrails
- Require local reproduction for incidents; avoid guessing from outdated logs.
- Surface missing secrets or config drift back to CHIT tooling or env files.
- When automation behavior changes, cue docs in `pmoves/docs/SMOKETESTS.md` and related service READMEs.
