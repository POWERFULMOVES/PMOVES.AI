---
name: PMOVES Remote Access
description: |
  One-click Headscale VPN mesh + RustDesk remote desktop for PMOVES.AI
  multi-node deployment. Connects Z890, 5090, 4090, Jetson edge nodes
  into a secure mesh for cross-machine agent routing and remote access.
keywords: headscale, rustdesk, vpn, mesh, tailscale, remote, desktop, ssh, multi-node
version: 1.0.0
category: Infrastructure/Networking
tier: 1
agent_class: Standard
agent_id: pmoves_remote_access
---

# PMOVES Remote Access

**Agent Class**: `Standard (Pmoves-)`
**Category**: Infrastructure/Networking
**Version**: 1.0.0
**Tier**: 1 (Core Infrastructure)
**Status**: Active — Headscale VPN + RustDesk remote desktop

---

## Capabilities

| Command | What It Does |
|---------|-------------|
| `mesh-status` | Show Tailscale/Headscale mesh node status |
| `connect` | RustDesk remote desktop to a specified node |
| `nodes` | List all PMOVES fleet nodes and their IPs |

---

## Trigger Phrases (Pinokio 7 Interpreter)

| Phrase | Action |
|--------|--------|
| `"show mesh status"` | Display Tailscale node connectivity |
| `"connect to 5090"` | Open RustDesk to POWERFULMOVES node |
| `"connect to z890"` | Open RustDesk to Z890 node |
| `"list all nodes"` | Display fleet inventory |
| `"check vpn health"` | Verify Headscale control plane |

---

## Fleet Nodes

| Node | Role | Services |
|------|------|----------|
| Z890 | Infrastructure coordinator | Docker, CI runner, NATS, data stores |
| 5090 (POWERFULMOVES) | GPU compute, voice | TTS, Flute, model training |
| 4090 Laptop | Field agent, mobile | Terminal, monitoring, edge testing |
| Jetson Orin #1 | Edge inference | Whisper, Ollama, YOLO |
| Jetson Orin #2 | Edge inference | TensorRT, mesh agent |

---

## Prerequisites

- Tailscale or Headscale client installed on each node
- RustDesk server running (self-hosted or relay)
- Headscale control plane at port 8096
