# mesh-agent — Service Guide

Status: Implemented (compose)

Overview
- NATS-connected helper that announces capabilities to the mesh.

Compose
- Service: `mesh-agent`
- Profiles: `agents`
- Depends on: `nats`

Environment
- `NATS_URL` (default `nats://nats:4222`)
- `HIRAG_URL` (default `http://hi-rag-gateway-v2-gpu:8086`)
- `ANNOUNCE_SEC` (default `15`)

Smoke
```
docker compose --profile agents up -d nats mesh-agent
docker compose ps mesh-agent
docker compose logs -n 100 mesh-agent | rg -i "connected|NATS|announce" || true
```
