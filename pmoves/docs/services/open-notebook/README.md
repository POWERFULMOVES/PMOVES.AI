# Open Notebook — Service Guide

Status: Compose add‑on (external image), attached to shared network.

Overview
- Lightweight notebook UI + API for local workflows. Lives on the shared `pmoves-net` so it can talk to services if needed.

Compose
- File: `pmoves/docker-compose.open-notebook.yml`
- Service: `open-notebook`
- Ports (host → container): UI `8503:8502`, API `5056:5055`
- Network: external `pmoves-net` (shared with the main stack)

Make targets
- `make up-open-notebook` — bring up ON on `pmoves-net` (UI http://localhost:8503, API :5056)
- `make down-open-notebook` — stop ON

Troubleshooting
- If port conflicts occur, adjust the host ports in `docker-compose.open-notebook.yml` (e.g., `8504:8502`, `5057:5055`).
- Ensure the shared network exists: `docker network create pmoves-net` (Make and Compose create/attach automatically when needed).

Notes
- ON is optional and does not participate in core smokes.
