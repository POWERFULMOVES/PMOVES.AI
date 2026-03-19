---
name: PMOVES Services
description: Docker Compose profile controls for PMOVES.AI infrastructure services
keywords: docker, compose, services, infrastructure, start, stop, status, monitoring, voice
version: 1.0.0
category: Infrastructure/Orchestration
---

# PMOVES Services

**Category**: Infrastructure/Orchestration
**Version**: 1.0.0
**Status**: Stable

## Overview

Controls PMOVES.AI Docker Compose service profiles from Pinokio. Start, stop, and monitor core infrastructure, voice pipeline, monitoring stack, and external integrations without touching the terminal.

## Capabilities

- Start/stop Docker Compose profiles (core, voice, monitoring, external)
- Check running service status across all profiles
- Reset and reinstall service dependencies
- Update launcher scripts and service images

## Trigger Phrases

| Natural Language Phrase | Action | Script |
|-------------------------|--------|--------|
| "start PMOVES services" | Launch core profile | start-core.js |
| "start voice pipeline" | Launch voice services | start-voice.js |
| "start monitoring" | Launch Prometheus/Grafana/Loki | start-monitoring.js |
| "start external services" | Launch external integrations | start-external.js |
| "check service status" | Show running containers | status.js |
| "stop all services" | Stop all profiles | stop.js |
| "reset services" | Reset dependencies | reset.js |
| "update services" | Pull latest images | update.js |

## Service Profiles

### Core (`start-core.js`)
Agent Zero, NATS, Supabase, Neo4j, Qdrant, Meilisearch, MinIO, TensorZero

### Voice (`start-voice.js`)
Flute-Gateway, Ultimate-TTS-Studio, Cast TTS, Voice Relay

### Monitoring (`start-monitoring.js`)
Prometheus, Grafana, Loki, Promtail, cAdvisor

### External (`start-external.js`)
PMOVES.YT, Channel Monitor, Jellyfin Bridge, Publisher-Discord

## API Endpoints (When Running)

| Service | Endpoint | Health |
|---------|----------|--------|
| Agent Zero | `http://localhost:8080` | `GET /healthz` |
| NATS | `nats://localhost:4222` | `GET /healthz` on 8222 |
| TensorZero | `http://localhost:3030` | `GET /health` |
| Grafana | `http://localhost:3000` | `GET /api/health` |
| Hi-RAG v2 | `http://localhost:8086` | `GET /health` |
| Flute-Gateway | `http://localhost:8055` | `GET /healthz` |
| Ultimate TTS | `http://localhost:7861` | `GET /gradio_api/info` |

## Cross-Machine Access

Services bound to `0.0.0.0` (mesh-accessible tier) are reachable from any Tailscale node:
```text
http://100.x.x.x:8080   # Agent Zero from remote machine
http://100.x.x.x:3030   # TensorZero from remote machine
```

Services bound to `127.0.0.1` (localhost-only tier) require Pinokio Caddy proxy for remote access via `42XXX` ports.

## Integration Points

- **NATS Subject**: `ops.services.status.v1` (future)
- **Prometheus**: All services expose `/metrics`
- **Docker Networks**: `pmoves_api`, `pmoves_data`, `pmoves_bus`

## See Also

- [PORT_BINDING_MODEL.md](../../../../pmoves/docs/security/PORT_BINDING_MODEL.md)
- [TOPOLOGY.md](../../../../pmoves/docs/operations/TOPOLOGY.md)
