---
name: PMOVES Services Control Center
description: |
  One-click Docker Compose orchestrator for 40+ PMOVES.AI microservices.
  Start/stop/status for 4 service profiles: core agents, voice pipeline,
  monitoring stack, and external integrations. Manages the entire PMOVES
  infrastructure from a single Pinokio launcher.
keywords: docker, compose, services, agents, voice, monitoring, infrastructure, start, stop, status, reset
version: 1.0.0
category: Infrastructure/Orchestration
tier: 1
agent_class: Standard
agent_id: pmoves_services_ctl
---

# PMOVES Services Control Center

**Agent Class**: `Standard (Pmoves-)`
**Category**: Infrastructure/Orchestration
**Version**: 1.0.0
**Tier**: 1 (Core Infrastructure)
**Status**: Active — 4 service profiles, 40+ containers

---

## Capabilities

| Command | What It Does |
|---------|-------------|
| `start-core` | Launch Agent Zero, Archon, Mesh Agent, Extract Worker, media analyzers |
| `start-voice` | Launch Flute-Gateway, Ultimate-TTS-Studio, Cast, media pipeline |
| `start-monitoring` | Launch Prometheus, Grafana, Loki, Promtail, cAdvisor |
| `start-external` | Launch Wger, Firefly III, Jellyfin (external integrations) |
| `status` | Show running containers across all compose files |
| `stop` | Gracefully stop all services (volumes preserved) |
| `reset` | Stop all services AND delete volumes (full reset) |
| `update` | Git pull + submodule update + re-bootstrap env |

---

## Trigger Phrases (Pinokio 7 Interpreter)

| Phrase | Action | Script |
|--------|--------|--------|
| `"start the agents"` | Launch core agent stack | `start-core.js` |
| `"start voice services"` | Launch TTS + Flute pipeline | `start-voice.js` |
| `"start monitoring"` | Launch Prometheus + Grafana | `start-monitoring.js` |
| `"show service status"` | Display all running containers | `status.js` |
| `"stop all services"` | Graceful shutdown | `stop.js` |
| `"reset everything"` | Full reset with volume deletion | `reset.js` |
| `"update pmoves"` | Pull latest + rebuild env | `update.js` |
| `"start external apps"` | Launch Wger + Firefly + Jellyfin | `start-external.js` |

---

## Service Profiles

### Core (Agents + Workers)
- **Agent Zero** — `http://localhost:8080` (orchestrator, MCP API)
- **Archon** — `http://localhost:8091` (Supabase agent service)
- **Mesh Agent** — Node announcer (NATS every 15s)
- **Extract Worker** — `http://localhost:8083` (text embedding + indexing)
- **Hi-RAG v2** — `http://localhost:8086` (hybrid retrieval)

### Voice
- **Flute-Gateway** — `http://localhost:8055` (prosodic voice synthesis)
- **Ultimate-TTS-Studio** — `http://localhost:7860` (14-engine TTS)
- **Cast-TTS** — `http://localhost:8060` (Chromecast/Nest speaker TTS)

### Monitoring
- **Prometheus** — `http://localhost:9090` (metrics)
- **Grafana** — `http://localhost:3000` (dashboards)
- **Loki** — `http://localhost:3100` (log aggregation)

### External
- **Wger (Health)** — `http://localhost:8000` (fitness tracking)
- **Firefly III (Wealth)** — `http://localhost:8075` (finance management)
- **Jellyfin** — Media server

---

## Health Checks

```bash
# Quick check all core services
curl http://localhost:8080/healthz   # Agent Zero
curl http://localhost:8086/          # Hi-RAG v2
curl http://localhost:8094/healthz   # Publisher-Discord
curl http://localhost:8055/healthz   # Flute-Gateway

# Full verification
make -C pmoves verify-all
```

---

## Prerequisites

- Docker Desktop running with Docker Compose v2+
- `pmoves/env.shared` bootstrapped (Install step handles this)
- NATS message bus accessible at port 4222
