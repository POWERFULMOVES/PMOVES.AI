# Open Notebook - Service Guide

Status: optional external integration (UI + API), with PMOVES automation hooks.

Last verified: 2026-03-06.

## Official documentation references
- Upstream repo: `https://github.com/lfnovo/open-notebook`
- API reference (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/7-DEVELOPMENT/api-reference.md`
- Environment reference (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/5-CONFIGURATION/environment-reference.md`
- Docker install guide (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/1-INSTALLATION/docker-compose.md`

## Image policy for PMOVES
- Default in PMOVES compose/env templates: `ghcr.io/lfnovo/open-notebook:1.8.0`
- PMOVES-branded image exists: `ghcr.io/powerfulmoves/pmoves-open-notebook:pmoves-latest`
- Current version state (verified 2026-03-06):
  - Upstream latest release: `v1.8.0` (published 2026-02-27)
  - PMOVES image package version: `1.6.2`

Recommendation:
- Keep production defaults on upstream `1.8.0` until PMOVES fork is rebuilt on `1.8.x`.
- Use `OPEN_NOTEBOOK_IMAGE` override when validating PMOVES-specific image updates.

## Compose wiring
- File: `pmoves/docker-compose.open-notebook.yml`
- Service: `open-notebook`
- Ports (host -> container):
  - UI `${OPEN_NOTEBOOK_UI_PORT:-8503}:8502` (Next.js UI)
  - API `${OPEN_NOTEBOOK_API_PORT:-5055}:5055` (FastAPI backend)
- Network: shared `cataclysm-net` plus PMOVES compatibility aliases.

## PMOVES integration compatibility
The following PMOVES paths are compatible with both upstream `1.8.0` and PMOVES `1.6.2`:
- `pmoves/scripts/yt_transcripts_to_notebook.py`
- `pmoves/scripts/mindmap_to_notebook.py`
- `pmoves/scripts/hirag_search_to_notebook.py`
- `pmoves/services/notebook-sync/sync.py`
- `pmoves/services/deepresearch/worker.py`
- `pmoves/services/agent-zero/mcp_server.py`
- `pmoves/ui/app/api/notebook/sources/route.ts`

Compatibility expectations:
- API base must include port `5055`.
- Source creation endpoint `/api/sources/json` is supported.
- API auth is bearer password (`Authorization: Bearer <OPEN_NOTEBOOK_PASSWORD>`).
- PMOVES keeps `OPEN_NOTEBOOK_API_TOKEN` and `OPEN_NOTEBOOK_PASSWORD` aligned by default to avoid credential drift.

SurrealDB env note:
- Upstream docs use `SURREAL_PASSWORD`.
- PMOVES compose uses `SURREAL_PASS`, and PMOVES Open Notebook code supports fallback (`SURREAL_PASSWORD` or `SURREAL_PASS`).

## Make targets
- `make up-open-notebook`
- `make down-open-notebook`
- `make notebook-up`
- `make notebook-down`
- `make notebook-logs`
- `make notebook-set-password PASSWORD="pmoves4482"`
- `make notebook-seed-models`
- `make yt-notebook-sync ARGS="--limit 25 --dry-run"`

## PMOVES.YT transcript sync
`scripts/yt_transcripts_to_notebook.py` mirrors unsynced transcripts into Open Notebook and writes back:
- `notebook_source_id`
- `notebook_synced_at`

Required env:
- `SUPA_REST_URL` or `SUPABASE_REST_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPEN_NOTEBOOK_API_URL`
- `OPEN_NOTEBOOK_API_TOKEN`
- `YOUTUBE_NOTEBOOK_ID` (or `MINDMAP_NOTEBOOK_ID`)

Run:
```bash
make yt-notebook-sync ARGS="--limit 5 --dry-run"
make yt-notebook-sync ARGS="--limit 25"
```

## Quick validation commands
```bash
# health
curl -s http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/health

# auth + source list
curl -s -H "Authorization: Bearer ${OPEN_NOTEBOOK_API_TOKEN}" \
  "http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/api/sources?limit=1"

# provider catalog after seeding
curl -s -H "Authorization: Bearer ${OPEN_NOTEBOOK_API_TOKEN}" \
  "http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}/api/models/providers"
```

## Troubleshooting
- Port conflict: adjust `OPEN_NOTEBOOK_UI_PORT` and/or `OPEN_NOTEBOOK_API_PORT`.
- Auth failures (401): ensure `OPEN_NOTEBOOK_API_TOKEN` matches `OPEN_NOTEBOOK_PASSWORD`.
- Missing embeddings provider: run sync helpers with `--no-embed`, or configure local provider (`OLLAMA_API_BASE`) and rerun `make notebook-seed-models`.
- Missing notebook-sync updates: confirm `NOTEBOOK_SYNC_MODE=live`, then restart worker:
  `docker compose -f pmoves/docker-compose.yml --profile workers restart notebook-sync`
