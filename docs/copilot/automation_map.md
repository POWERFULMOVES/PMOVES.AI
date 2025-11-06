# Copilot Agent Automation Map

## Provisioning Steward
- **Make targets**: `make env-setup`, `make supa-start`, `make up`, `make up-external`, `make bootstrap-data`, `make smoke`, `make preflight`
- **Codex tasks**: `codex run db_all_in_one`, `codex run pmoves_all_install`
- **Scripts**: `python3 -m pmoves.tools.mini_cli bootstrap`, `python3 -m pmoves.tools.mini_cli crush setup`
- **Docs**: `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/`, `pmoves/docs/pmoves_all_in_one_v10/docs/README.md`, `pmoves/docs/LOCAL_TOOLING_REFERENCE.md`

## Website & UI Maintainer
- **Node targets**: `npm install`, `npm run lint`, `npm run test`, `npm run build`, `npm run dev`
- **Playwright**: `npx playwright test`, scripts under `pmoves/docs/scripts/`
- **Hostinger/Dart**: MCP commands (Hostinger) plus scripts in `pmoves/tools/integrations/hostinger/` and Dart MCP utilities.
- **Docs**: `pmoves/ui/README.md`, `docs/PMOVES_MINI_CLI_SPEC.md`, UI sections in `pmoves/docs/pmoves_all_in_one_v10/docs/`

## Integrations & VPS Ops
- **Make targets**: `make up-external`, `make up-external-jellyfin`, `make up-invidious`, `make yt-jellyfin-smoke`, `make jellyfin-smoke`, `make smoke-wger`, `make smoke-presign-put`, `make preflight`
- **Hi-RAG geometry**: ensure `HIRAG_URL` / `HIRAG_GPU_URL` aim at `http://hi-rag-gateway-v2-gpu:8086` (host port 8087) so CGPs hydrate the GPU ShapeStore; keep `HIRAG_CPU_URL` available for CPU-only runs.
- **Docker logs**: `docker compose logs <service>`, `make logs-core`
- **n8n/automation scripts**: `docs/n8n/*.json`, `pmoves/tools/integrations/*.sh`
- **Docs**: `pmoves/docs/services/<service>/README.md`, `pmoves/docs/SMOKETESTS.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`

Use this map when crafting Copilot instructions or extending MCP catalogs so each agent exposes the correct commands and documentation entry points.
