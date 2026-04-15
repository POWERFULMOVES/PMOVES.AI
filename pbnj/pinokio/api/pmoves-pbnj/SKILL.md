---
name: PBnJ | PMOVES + Pinokio Bridge
description: |
  Multi-target deployment bridge for PMOVES.AI infrastructure.
  Manages local Docker Compose, Kubernetes AI Lab, KVM4 production,
  VPS fleet deployment, and network diagnostics from a single
  Pinokio control panel. Covers Z890, 5090, 4090, KVM4-1/4-2, KVM2 nodes.
keywords: deploy, infrastructure, docker, kubernetes, kvm4, vps, tailscale, glances, network, diagnostics, fleet
version: 1.0.0
category: Infrastructure/Deployment
tier: 1
agent_class: Standard
agent_id: pmoves_pbnj_bridge
---

# PBnJ | PMOVES + Pinokio Bridge

**Agent Class**: `Standard (Pmoves-)`
**Category**: Infrastructure/Deployment
**Version**: 1.0.0
**Tier**: 1 (Core Infrastructure)
**Status**: Active — 3 deployment targets, 5 VPS nodes, network tools

---

## Capabilities

| Command | What It Does |
|---------|-------------|
| `local-up` | Start local Docker Compose stack (Z890 dev) |
| `local-down` | Stop local Docker Compose stack |
| `local-logs` | Stream logs from local services |
| `lab-up` | Apply AI Lab manifests to Kubernetes |
| `lab-down` | Delete AI Lab from Kubernetes |
| `kvm4-up` | Deploy KVM4 production stack |
| `kvm4-down` | Stop KVM4 production stack |
| `kvm4-1-deploy` | Deploy API services to KVM4-1 (Agent Zero, TZ, Hi-RAG) |
| `kvm4-2-deploy` | Deploy data services to KVM4-2 (Supabase, Qdrant, Neo4j) |
| `kvm2-deploy` | Deploy exit proxy to KVM2 (Nginx) |
| `4090-deploy` | Deploy coding workstation to 4090 laptop |
| `4090-models` | Pull models to 4090 (~50GB) |
| `4090-status` | Check 4090 node status |
| `status` | Kubernetes deployment status |
| `vps-status` | Tailscale ping + runner status for all VPS nodes |

---

## Trigger Phrases (Pinokio 7 Interpreter)

| Phrase | Action | Script |
|--------|--------|--------|
| `"start local dev"` | Launch Docker Compose | `local-up.json` |
| `"stop local dev"` | Stop Docker Compose | `local-down.json` |
| `"show logs"` | Stream local service logs | `local-logs.json` |
| `"deploy to lab"` | Apply K8s manifests | `lab-up.json` |
| `"deploy to production"` | Apply KVM4 K8s stack | `kvm4-up.json` |
| `"deploy kvm4-1"` | API services to KVM4-1 | `kvm4-1-deploy.json` |
| `"deploy kvm4-2"` | Data services to KVM4-2 | `kvm4-2-deploy.json` |
| `"deploy kvm2"` | Exit proxy to KVM2 | `kvm2-deploy.json` |
| `"deploy 4090"` | Coding workstation to 4090 | `4090-deploy.json` |
| `"check cluster status"` | K8s status | `status.json` |
| `"check vps fleet"` | All VPS node health | `vps-status.json` |
| `"stop everything"` | Stop all stacks | `lab-down.json` → `kvm4-down.json` → `local-down.json` |

---

## Fleet Nodes

| Node | Role | Deploy Script |
|------|------|---------------|
| Z890 | Infrastructure coordinator, Docker, CI | `local-up.json` |
| 5090 | GPU compute, voice, model training | (via pmoves-services) |
| 4090 Laptop | Field agent, mobile | `4090-deploy.json` |
| KVM4-1 | API gateway (TZ, A0, Hi-RAG, Archon) | `kvm4-1-deploy.json` |
| KVM4-2 | Data/storage (Supabase, Qdrant, Neo4j) | `kvm4-2-deploy.json` |
| KVM2 | Exit proxy (Nginx) | `kvm2-deploy.json` |

---

## Network Tools (Optional)

When network tools are installed (`app/env` exists):
- **Glances** — System monitor (venv or Docker mode)
- **Network Diagnostics** — Connectivity checks
- **DNS Flush** — Clear DNS cache
- **Winsock Reset** — Reset network stack
- **Firewall Rules** — Add PMOVES service rules
- **Docker Network Cleanup** — Prune stale networks

---

## Prerequisites

- Docker Desktop with Compose v2+
- Tailscale client (for VPS deployments)
- kubectl (for Kubernetes targets)
- `pmoves/env.shared` bootstrapped
