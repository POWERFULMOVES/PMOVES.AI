---
name: PMOVES Services Launcher
description: Docker Compose profile controller for PMOVES.AI services via Pinokio
keywords: docker, compose, services, launcher, profiles
version: 1.0.0
category: Infrastructure/Launcher
---

# PMOVES Services Launcher

**Category**: Infrastructure/Launcher
**Version**: 1.0.0
**Status**: Active

## Overview

Pinokio launcher for the PMOVES.AI Docker Compose service stack. Provides one-click install, start, stop, reset, and update for core services, monitoring, voice, and external integrations.

## Capabilities

- Start/stop Docker Compose profiles (core, monitoring, voice, external)
- Install prerequisites (Docker, env setup, brand defaults)
- Reset service state and volumes
- Update launcher scripts and service images
- Real-time service status display

## Scripts

| Script | Purpose |
|--------|---------|
| `install.js` | Bootstrap Docker, env-setup, brand-defaults |
| `start-core.js` | Start core services (Agent Zero, NATS, Supabase, Hi-RAG) |
| `start-monitoring.js` | Start Prometheus, Grafana, Loki stack |
| `start-voice.js` | Start Flute-Gateway, Ultimate-TTS-Studio |
| `start-external.js` | Start external integrations (Discord, Jellyfin, etc.) |
| `status.js` | Display service health status |
| `stop.js` | Stop all running services |
| `reset.js` | Reset dependencies and volumes |
| `update.js` | Pull latest images and scripts |
| `pinokio.js` | Dynamic UI generator (sidebar menu) |

## Docker Compose Profiles

| Profile | Services | Ports |
|---------|----------|-------|
| `agents` | Agent Zero, Archon, Mesh Agent | 8080, 8091 |
| `workers` | Extract, LangExtract, media analyzers | 8083, 8084 |
| `monitoring` | Prometheus, Grafana, Loki | 9090, 3000, 3100 |
| `gpu` | GPU-enabled services | varies |
| `yt` | PMOVES.YT ingestion | 8077 |

## Integration Points

- **Make targets**: `make -C pmoves up`, `make -C pmoves verify-all`
- **Health checks**: All services expose `/healthz`
- **NATS**: Event bus at port 4222

## See Also

- [pmoves-remote](../pmoves-remote/SKILL.md) — Remote service discovery
- [PMOVES.AI CLAUDE.md](../../../../.claude/CLAUDE.md) — Full architecture context
