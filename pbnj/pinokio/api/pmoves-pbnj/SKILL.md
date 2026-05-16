---
name: PBnJ | PMOVES + Pinokio Bridge
description: |
  Multi-target deployment bridge for PMOVES.AI infrastructure.
  Manages local Docker Compose, Kubernetes AI Lab, KVM4 production,
  VPS fleet deployment, homelab bare-metal, and edge (Jetson) nodes
  from a single Pinokio control panel. Built-in gepeto + pinokio skills.
  Covers: Z890, 5090, 4090, SPARK, R9700, JONS×3, KVM4-1/4-2, KVM2.
keywords: deploy, infrastructure, docker, kubernetes, kvm4, vps, tailscale, glances, network, diagnostics, fleet, jetson, spark, rdna4, edge, gepeto, pinokio
version: 1.1.0
category: Infrastructure/Deployment
tier: 1
agent_class: Standard
agent_id: pmoves_pbnj_bridge
pinokio_skills:
  native:
    - pinokio          # Built-in app discovery + launch
    - gepeto           # Built-in code assistant (~/.agents/skills/gepeto)
  pmoves:
    - pmoves-services  # Docker Compose profile controls
    - pmoves-remote    # Headscale/RustDesk remote access
    - pmoves-agent-zero
    - pmoves-model-registry
---

# PBnJ | PMOVES + Pinokio Bridge

**Agent Class**: `Standard (Pmoves-)`
**Category**: Infrastructure/Deployment
**Version**: 1.1.0
**Tier**: 1 (Core Infrastructure)
**Status**: Active — homelab + VPS + edge fleet, gepeto + pinokio native skills

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
| `spark-deploy` | Bootstrap DGX Spark (GB10 Grace-Blackwell, 128GB) |
| `spark-models` | Pull models to SPARK (Gemma 4 31B FP16, Nemotron-Super-49B) |
| `spark-status` | Check SPARK node health (Tailscale + Ollama) |
| `rdna4-deploy` | Bootstrap RDNA4 workstation (dual R9700, ROCm 7.1) |
| `rdna4-status` | Check RDNA4 node health (llama-server + rocm-smi) |
| `jons-deploy` | Bootstrap all 3 Jetson Orin Nano Super units (JetPack 6.x) |
| `jons-status` | Check Jetson edge fleet health (mesh-agent + ollama) |
| `fleet-status` | Full fleet: all nodes Tailscale ping + service health |
| `status` | Kubernetes deployment status |
| `vps-status` | Tailscale ping + runner status for all VPS nodes |

---

## Trigger Phrases (Pinokio 7 Interpreter)

Uses built-in `gepeto` and `pinokio` skills for natural language routing.

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
| `"deploy spark"` | Bootstrap DGX SPARK node | `spark-deploy.json` |
| `"deploy rdna4"` | Bootstrap RDNA4 workstation | `rdna4-deploy.json` |
| `"deploy jetsons"` | Bootstrap all 3 Jetson JONS | `jons-deploy.json` |
| `"check cluster status"` | K8s status | `status.json` |
| `"check vps fleet"` | All VPS node health | `vps-status.json` |
| `"check fleet"` | Full fleet health (all nodes) | `fleet-status.json` |
| `"stop everything"` | Stop all stacks | `lab-down.json` → `kvm4-down.json` → `local-down.json` |

---

## Fleet Nodes

### Homelab (Bare Metal)
| Node | Role | Deploy Script |
|------|------|---------------|
| Z890 (`pmoves-z890`) | Infrastructure coordinator, Docker, CI | `local-up.json` |
| 5090 (`pmoves-5090`) | GPU compute, voice, model training | (via pmoves-services) |
| SPARK (`pmoves-gb10-spark`) | DGX Grace-Blackwell, 128GB unified, ARM64 inference | `spark-deploy.json` |
| RDNA4 (`pmoves-rdna4`) | Dual R9700 workstation, ROCm 7.1, 64GB VRAM | `rdna4-deploy.json` |
| 4090 Laptop (`pmoves-4090`) | Field agent, mobile | `4090-deploy.json` |

### Edge Nodes (Jetson Orin Nano Super × 3)
| Node | Role | Deploy Script |
|------|------|---------------|
| JONS-1 (`pmoves-jons-1`) | Edge inference, Whisper, YOLOv8 | `jons-deploy.json` |
| JONS-2 (`pmoves-jons-2`) | Edge inference, Whisper, YOLOv8 | `jons-deploy.json` |
| JONS-3 (`pmoves-jons-3`) | Edge inference, Whisper, YOLOv8 | `jons-deploy.json` |

**Jetson specs**: 6-core Cortex-A78AE, Ampere SM_87 1024 CUDA cores, 8GB LPDDR5 (102 GB/s), 67 TOPS.
JetPack 6.x (L4T 36.x). Built-in Pinokio `gepeto` + `pinokio` skills.

### VPS (Hostinger)
| Node | Role | Deploy Script |
|------|------|---------------|
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
