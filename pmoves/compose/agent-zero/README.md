# Agent Zero (GPU) — Compose & Images

## Images & Tags
- Multi-arch (desktop RTX + Jetson) under one tag:
  - `yourorg/agent-zero:latest` (default)
  - `yourorg/agent-zero:vX.Y.Z` (pinned)
- Build multi-arch manifests with Buildx:
  - Linux/Mac: `REGISTRY=docker.io/yourorg VERSION=v1.0.0 ./scripts/buildx-agent-zero.sh`
  - Windows: `./scripts/buildx-agent-zero.ps1 -Registry docker.io/yourorg -Version v1.0.0`

## Run (Desktop RTX)
- `docker compose -f compose/agent-zero/docker-compose.gpu.optimized.yml up -d`

## Run (High-end 5090)
- `docker compose -f compose/agent-zero/docker-compose.gpu5090.optimized.yml up -d`

## Run (Profiles)
- Desktop profile: `docker compose -f compose/agent-zero/compose.profiles.yml --profile gpu-desktop up -d`
- Jetson profile: `docker compose -f compose/agent-zero/compose.profiles.yml --profile gpu-jetson up -d`

Notes
- Use `gpus: all` (modern Compose) with NVIDIA Container Toolkit installed.
- For older setups, you can fall back to `runtime: nvidia`.
- PMOVES core stack does not include NATS yet — Agent Zero is kept separate. When adding NATS, wire `NATS_URL` and/or add a `nats` service.
