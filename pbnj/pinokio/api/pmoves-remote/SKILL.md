---
name: PMOVES Remote Services
description: Remote service discovery and cross-machine routing for PMOVES.AI via Pinokio
keywords: remote, discovery, tailscale, mesh, cross-machine
version: 1.0.0
category: Infrastructure/Discovery
---

# PMOVES Remote Services

**Category**: Infrastructure/Discovery
**Version**: 1.0.0
**Status**: Active

## Overview

Pinokio launcher for discovering and connecting to PMOVES.AI services running on remote machines in the Tailscale mesh. Enables cross-machine service access between z890, 5090, and 4090 nodes.

## Capabilities

- Discover remote PMOVES services via Tailscale mesh
- Route requests to remote GPU services (TTS, Hi-RAG GPU, ComfyUI)
- Display remote service health and availability
- Install Tailscale and configure mesh connectivity

## Scripts

| Script | Purpose |
|--------|---------|
| `install.js` | Install Tailscale, configure mesh auth |
| `start.js` | Start remote service discovery and health polling |
| `status.js` | Display remote node and service status |
| `pinokio.js` | Dynamic UI with remote service links |

## Node Topology

| Node | Role | Key Services |
|------|------|-------------|
| z890 | Dev/GPU primary | Agent Zero, Hi-RAG, Supabase |
| 5090 | GPU compute | TTS, ComfyUI, NeMo |
| 4090 | Portable dev | Analysis, theming, codespace |

## Integration Points

- **Tailscale**: Mesh networking for cross-machine routing
- **NATS**: WebSocket at port 9222 (standalone) / 9223 (docked)
- **Health**: Remote `/healthz` polling

## See Also

- [pmoves-services](../pmoves-services/SKILL.md) — Local service launcher
- [Topology docs](../../../../pmoves/docs/operations/TOPOLOGY.md) — Network topology
