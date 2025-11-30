# PMOVES Integration – Open Notebook Docker + GHCR

Adds GHCR publish workflow and pmoves-net compose. Runs UI on :8503 and API on :5055 by default (override with `OPEN_NOTEBOOK_UI_PORT` / `OPEN_NOTEBOOK_API_PORT`).

Usage:
```bash
docker network create pmoves-net || true
docker compose -f docker-compose.pmoves-net.yml up -d
# UI: http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API: http://localhost:${OPEN_NOTEBOOK_API_PORT:-5055}
```

Image: `ghcr.io/POWERFULMOVES/Pmoves-open-notebook:main`.
