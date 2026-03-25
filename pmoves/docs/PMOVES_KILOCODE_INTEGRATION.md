# PMOVES KiloCode Integration — VPS Multi-Claw Architecture

## Overview

PMOVES.AI deploys **Kilo Code (OpenClaw)** as the AI coding IDE across its infrastructure fleet. Each node runs a scoped claw instance with permissions matched to its role in the topology. This document covers VPS configuration, agent modes, and fleet deployment.

## Architecture

```
                      PMOVES Multi-Claw Fleet
                      ========================

    Z890 (dev)              KVM4-1 (api-gw)          KVM4-2 (data)
    ┌──────────┐            ┌──────────┐             ┌──────────┐
    │ Kilo Code│            │ Kilo Code│             │ Kilo Code│
    │ full     │            │ restricted│            │ restricted│
    │ opus-4   │            │ sonnet-4  │            │ sonnet-4  │
    │ all MCP  │            │ curl,gh,  │            │ psql,mc,  │
    │ docker+  │            │ nats,dig  │            │ curl,py   │
    └────┬─────┘            └────┬──────┘            └────┬──────┘
         │                       │                        │
    ─────┴───────────────────────┴────────────────────────┴────────
                         Tailscale Mesh (100.x.x.x)
    ─────┬───────────────────────┬────────────────────────┬────────
         │                       │                        │
    ┌────┴─────┐            ┌────┴──────┐           ┌────┴───────┐
    │ KVM2     │            │ Jetson #1 │           │ Jetson #2  │
    │ exit-prxy│            │ NemoClaw  │           │ NemoClaw   │
    │ haiku    │            │ nemotron  │           │ nemotron   │
    │ net tools│            │ GPU + NATS│           │ GPU + NATS │
    └──────────┘            └───────────┘           └────────────┘
```

## Node Roles & Scope Profiles

| Node | Hostinger VPS | Role | Model | Tools Profile | Ask Mode | Key Permissions |
|------|--------------|------|-------|--------------|----------|----------------|
| Z890 | — (local) | Full infra | claude-opus-4 | full | off | Everything |
| KVM4-1 | VPS #1 | API gateway | claude-sonnet-4 | restricted | auto | curl, gh, nats, dig, systemctl |
| KVM4-2 | VPS #2 | Data/storage | claude-sonnet-4 | restricted | auto | psql, mc, curl, python |
| KVM2 | VPS #3 | Exit proxy | claude-haiku-4-5 | restricted | confirm | tailscale, wg, cloudflared, dig |
| Jetson | — (edge) | NemoClaw | nemotron (local) | restricted | auto | nvidia-smi, tegrastats, trtexec, ollama |

**Scope files:** `pmoves/configs/claws/scopes/{node}.json`

## VPS Configuration

### Kilo Code Config Path

On VPS nodes, Kilo Code stores config at:
```
/root/.config/kilo/
├── opencode.json        ← Main config (MCP servers, modes, model routing)
└── ...
```

On the Fly.io reference instance, OpenClaw stores config at:
```
/root/.openclaw/
├── openclaw.json        ← Main config
├── exec-approvals.json  ← Permission allowlists
└── ...
```

Both paths are supported — `deploy-claw.sh` detects which is in use.

### opencode.json Structure (VPS Standard)

The `opencode.json` configures MCP servers and agent modes per node:

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "sse",
      "url": "http://cipher-memory:8096/sse"
    }
  },
  "modes": {
    "default": "pmoves-code",
    "available": ["pmoves-code", "pmoves-architect", "pmoves-debug", "pmoves-review"]
  },
  "modelOverrides": {
    "primary": "claude-sonnet-4"
  }
}
```

See `pmoves/configs/claws/opencode-{node}.json` for per-node configs.

## Agent Modes (8 Custom Modes)

Defined in `.kilocodemodes` at repo root. Each mode maps to PMOVES service tiers:

| Mode | Slug | Purpose | Tiers | VPS Availability |
|------|------|---------|-------|-----------------|
| PMOVES Code | pmoves-code | Service implementation | 3-4 | All nodes |
| PMOVES Architect | pmoves-architect | System design | 6+3 | Z890, KVM4-1 |
| PMOVES Ask | pmoves-ask | Research & retrieval | 1-2 | All nodes |
| PMOVES Debug | pmoves-debug | Diagnostics | 4+1 | All nodes |
| PMOVES Review | pmoves-review | Security audit | 6 | Z890, KVM4-1 |
| PMOVES Frontend | pmoves-frontend | UI development | 7 | Z890 only |
| PMOVES Portal | pmoves-portal | CHIT/geometry | 6+L2.5 | Z890 only |
| PMOVES Crush | pmoves-crush | User experience | 7+6 | Z890 only |

**VPS nodes get a subset of modes** matching their role. Gateway nodes get architect + review; data nodes get code + debug; edge nodes get code + debug only.

## NemoClaw (Hybrid Agent)

NemoClaw runs on Jetson Orin Nano devices as both:

1. **Kilo Code CLI** — local AI coding IDE with NVIDIA-scoped permissions
2. **Agent Zero subordinate** — NATS-connected GPU agent for model lifecycle

### Kilo Code on Jetson
- Model: Nemotron via local Ollama (`http://localhost:11434`)
- Allowed: nvidia-smi, tegrastats, jetson_clocks, python3, trtexec, ollama
- No remote API calls — all inference is local

### Agent Zero Integration
- Profile: `pmoves/configs/agent-profiles/nemoclaw.yaml`
- NATS subscribe: `mesh.gpu.command.v1`
- NATS publish: `mesh.gpu.status.v1`, `mesh.gpu.model.loaded.v1`
- Node affinity: jetson

## Deployment

### Prerequisites

1. **SSH access** — Keys in GitHub Secrets (`HOSTINGER_KVM*_IP`, `HOSTINGER_KVM*_USER`)
2. **Tailscale** — Must be installed on each VPS for mesh networking
3. **RustDesk** — Self-hosted instance for remote desktop fallback

### Deploy Single VPS

```bash
# Migrate a single VPS from scratch
pmoves/scripts/claws/migrate-vps.sh --node kvm4-1 --target root@<KVM4_1_IP>

# Or via make target
make -C pmoves claw-deploy SCOPE=kvm4-1
```

### Deploy Entire Cluster

```bash
# Deploy to all 3 KVM nodes
pmoves/scripts/claws/deploy-vps-cluster.sh

# Or via make target
make -C pmoves claws-status
```

### Verify

```bash
# Single node
make -C pmoves claw-verify SCOPE=kvm4-1

# All nodes
make -C pmoves claws-status
```

### Rotate Tokens

```bash
make -C pmoves claw-rotate SCOPE=kvm4-1
```

## Security Model

### Permission Scoping

Each claw's `exec-approvals.json` resolves commands to **full binary paths**:
```json
{ "pattern": "/usr/bin/curl", "note": "Health checks only" }
```

This prevents PATH hijacking — the exact binary is whitelisted, not just the command name.

### Trust Levels

| Ask Mode | Trust Level | Use Case |
|----------|------------|----------|
| `off` | Full trust | Z890 dev workstation (your machine) |
| `auto` | Moderate | KVM4-1/4-2 (auto-approve known patterns) |
| `confirm` | Low trust | KVM2 exit proxy (confirm every command) |

### Token Management

Each node gets unique tokens for:
- Gateway auth (port 3001)
- Hooks webhook
- Exec-approvals socket

Tokens are generated at deploy time and rotated via `rotate-tokens.sh`.

## MCP Server Configuration

### Standard MCP Servers (all nodes)

| Server | Transport | Endpoint | Purpose |
|--------|-----------|----------|---------|
| pmoves-cipher | SSE | `http://cipher-memory:8096/sse` | Agent memory (Neo4j) |

### Z890-Only MCP Servers

| Server | Transport | Purpose |
|--------|-----------|---------|
| docker | stdio | Docker container management |
| web-reader | stdio | Web content fetching |
| web-search-prime | stdio | Web search |
| claude-in-chrome | stdio | Browser automation |

### VPS MCP Availability

VPS nodes connect to Cipher Memory via Tailscale. No Docker MCP on VPS (no Docker socket exposure).

## File Reference

| Path | Purpose |
|------|---------|
| `pmoves/configs/claws/base-openclaw.json` | Base config template |
| `pmoves/configs/claws/base-exec-approvals.json` | Base permission scaffold |
| `pmoves/configs/claws/scopes/*.json` | Per-node scope profiles |
| `pmoves/configs/claws/claude-md/*.md` | Per-node CLAUDE.md |
| `pmoves/configs/agent-profiles/nemoclaw.yaml` | NemoClaw Agent Zero profile |
| `pmoves/scripts/claws/deploy-claw.sh` | Single node deployment |
| `pmoves/scripts/claws/verify-claw.sh` | Single node verification |
| `pmoves/scripts/claws/rotate-tokens.sh` | Token rotation |
| `pmoves/scripts/claws/migrate-vps.sh` | Full VPS migration |
| `pmoves/scripts/claws/deploy-vps-cluster.sh` | Cluster deployment |
| `.kilocodemodes` | Mode definitions (8 modes) |
| `.kilocode/rules/kilorules.md` | KiloCode integration rules |
| `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md` | Full architecture plan |

## Operational Commands

```bash
# Fleet status
make -C pmoves claws-status

# Deploy single node
make -C pmoves claw-deploy SCOPE=kvm4-1

# Deploy cluster
pmoves/scripts/claws/deploy-vps-cluster.sh

# Verify single node
make -C pmoves claw-verify SCOPE=kvm4-1

# Rotate tokens
make -C pmoves claw-rotate SCOPE=kvm4-1

# Dry-run deployment
make -C pmoves claw-deploy SCOPE=kvm4-1 DRY_RUN=1
```
