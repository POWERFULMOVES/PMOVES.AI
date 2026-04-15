# Open Notebook - Service Guide

Status: optional external integration (UI + API), with PMOVES automation hooks.

Last verified: 2026-03-06.

## Official documentation references
- Upstream repo: `https://github.com/lfnovo/open-notebook`
- API reference (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/7-DEVELOPMENT/api-reference.md`
- Environment reference (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/5-CONFIGURATION/environment-reference.md`
- Docker install guide (v1.8.0): `https://github.com/lfnovo/open-notebook/blob/v1.8.0/docs/1-INSTALLATION/docker-compose.md`

## Image policy for PMOVES
- **Default in PMOVES compose/env templates: `ghcr.io/powerfulmoves/pmoves-open-notebook:pmoves-latest`** (Phase 9L, 2026-04-15)
- Upstream reference image: `ghcr.io/lfnovo/open-notebook:1.8.0` (use only as a comparison/escape hatch)
- Current version state (verified 2026-04-15):
  - Upstream latest release: `v1.8.0` (published 2026-02-27)
  - PMOVES fork base: upstream 1.8 + 70 upstream commits merged via `5cc0ba4`, plus
    TensorZero provider mode, fail-closed auth, USER directive, /healthz + /metrics,
    Fernet credential encryption, Phase C hardening (NATS auth, no root SurrealDB defaults)
  - Fork commit tracked by submodule gitlink at `PMOVES-Open-Notebook @ 0533c8a`

Recommendation:
- Use the PMOVES fork image as the default. The `OPEN_NOTEBOOK_IMAGE` env var still exists as
  an override for pinning to a specific SHA tag or testing an upstream build.
- When bumping the PMOVES fork, bump the gitlink on `PMOVES.AI-Edition-Hardened`
  and let the GHCR build workflow publish a fresh `:pmoves-latest` + `:YYYYMMDD-sha7` tag.

## Compose wiring
- File: `pmoves/docker-compose.open-notebook.yml`
- Service: `open-notebook`
- Container name: `pmoves-open-notebook` (since Phase 9L, 2026-04-15)
- Network aliases: `pmoves-open-notebook` (canonical), `open-notebook` (short), and
  `cataclysm-open-notebook` (legacy alias retained per migration-safe topology policy,
  see `pmoves/docs/ARC/network_fabric.md` and `pmoves/tools/topology_chit_gate.py`).
- Ports (host -> container):
  - UI `${OPEN_NOTEBOOK_UI_PORT:-8503}:8502` (Next.js UI)
  - API `${OPEN_NOTEBOOK_API_PORT:-5055}:5055` (FastAPI backend)
- Networks: `pmoves-net`, `cataclysm-net`, `pmoves_api`, `pmoves_app` (all compatibility-mapped).

## PMOVES expected compatibility (with evidence level)
The following paths are expected to work against upstream `1.8.0` and PMOVES `1.6.2`.
- `pmoves/scripts/yt_transcripts_to_notebook.py` (manual dry-run verification)
- `pmoves/scripts/mindmap_to_notebook.py` (docs-verified API contract)
- `pmoves/scripts/hirag_search_to_notebook.py` (docs-verified API contract)
- `pmoves/services/notebook-sync/sync.py` (runtime integration via `notebook-sync`)
- `pmoves/services/deepresearch/worker.py` (runtime integration via `OPEN_NOTEBOOK_API_URL`)
- `pmoves/services/agent-zero/mcp_server.py` (contract-level compatibility)
- `pmoves/ui/app/api/notebook/sources/route.ts` (live probe through Notebook Workbench API route)

Compatibility expectations:
- API base must include port `5055`.
- Search API for v1.8 uses `POST /api/search` (legacy fallback remains `POST /api/v1/notebooks/search` for older deployments).
- Source creation endpoint `/api/sources/json` is supported.
- API auth is bearer token (`Authorization: Bearer <OPEN_NOTEBOOK_API_TOKEN>`).
- PMOVES keeps `OPEN_NOTEBOOK_API_TOKEN` and `OPEN_NOTEBOOK_PASSWORD` aligned by default to avoid credential drift.

Supporting operator checks:
- `make -C pmoves notebook-workbench-smoke`
- `curl -s http://localhost:5055/health`
- `curl -s http://localhost:4482/api/notebook/sources`

SurrealDB env note:
- Upstream docs use `SURREAL_PASSWORD`.
- PMOVES compose uses `SURREAL_PASS`, and PMOVES Open Notebook code supports fallback (`SURREAL_PASSWORD` or `SURREAL_PASS`).

## Make targets
- `make up-open-notebook`
- `make down-open-notebook`
- `make notebook-up`
- `make notebook-down`
- `make notebook-logs`
- `make notebook-set-password PASSWORD="<your-secret>"` (reuse the generated Open Notebook credential from your install/bootstrap flow)
- `make notebook-seed-models`

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
python pmoves/scripts/yt_transcripts_to_notebook.py --limit 5 --dry-run
python pmoves/scripts/yt_transcripts_to_notebook.py --limit 25
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
