# BoTZ Gateway Deployment Plan — KVM4-1 VPS

> **For:** VPS operators and fleet coordinators.
> **Status:** READY — VPS inventory retrieved via Hostinger MCP, IPs confirmed.
> **Date:** 2026-07-14
> **VPS:** KVM4-1 (`PMOVES.AI.CLOUD1.KVMIV`) — IP `31.97.42.207`, 4C/16GB/200GB, Ubuntu 24.04

## VPS Fleet Inventory (verified 2026-07-14 via Hostinger API)

| VPS | Hostname | IP | Plan | CPU/RAM/Disk | Role |
|-----|----------|-----|------|--------------|------|
| KVM4-1 | PMOVES.AI.CLOUD1.KVMIV | 31.97.42.207 | KVM 4 | 4C/16GB/200GB | **BoTZ Gateway** (target) |
| KVM4-2 | PMOVES.AI.CLOUD2.KVMIV | 167.88.39.80 | KVM 4 | 4C/16GB/200GB | Data/storage tier |
| KVM2 | PMOVES.AI.CLOUD.KVMII | 167.88.38.57 | KVM 2 | 2C/8GB/100GB | Exit proxy, RustDesk relay |

All three VPS are **running**, co-located in datacenter 17, Ubuntu 24.04 LTS.

## Architecture

```
+-------------------+     Tailscale     +-------------------+
|   KVM4-1 (VPS)    | ←---------------→ |   All PMOVES Nodes |
|                   |                   |                   |
|  +-------------+  |                   |  Elder-Melchor    |
|  | BoTZ Gateway|  |                   |  5090             |
|  | :8054      |  |                   |  4090             |
|  +------+------+  |                   |  Z890             |
|         |         |                   |  SPARK            |
|  +------|------+ |                   |  B850             |
|  | NATS :4222  | |                   |                   |
|  +-------------+ |                   |                   |
|  | Cipher :8105| |                   |                   |
|  +-------------+ |                   |                   |
|  | Agent Zero  | |                   |                   |
|  | :8080      | |                   |                   |
|  +-------------+ |                   |                   |
|  | Supabase    | |                   |                   |
|  | :8000      | |                   |                   |
|  +-------------+ |                   |                   |
|  | Hi-RAG :8086| |                   |                   |
|  +-------------+ |                   |                   |
|  | GitHub MCP  | |                   |                   |
|  +-------------+ |                   |                   |
+-------------------+                   +-------------------+
```

## Deployment Steps

### Phase 1: Prerequisites
1. Verify KVM4-1 is accessible via Tailscale: `tailscale ping kvm4-1`
2. Verify Docker is installed on KVM4-1: `docker --version`
3. Create `pmoves-net` on KVM4-1: `docker network create pmoves-net`
4. Clone PMOVES.AI on KVM4-1: `git clone --recurse-submodules https://github.com/POWERFULMOVES/PMOVES.AI.git`
5. Copy `pmoves/env.shared.example` → `pmoves/env.shared` and fill in credentials

### Phase 2: Start Core Services
```bash
# On KVM4-1:
cd PMOVES.AI
# Start NATS + Neo4j (for Cipher)
docker compose -f pmoves/docker-compose.yml --profile agents up -d nats neo4j
# Start BoTZ Gateway
docker compose -f pmoves/docker-compose.yml --profile botz up -d botz-gateway
# Start Hi-RAG (CPU mode, no GPU on VPS)
docker compose -f pmoves/docker-compose.yml --profile agents up -d hi-rag-gateway-v2
```

### Phase 3: Verify Gateway
```bash
# BoTZ Gateway health
curl http://localhost:8054/health
# NATS health
curl http://localhost:8222/varz
# Verify from another node via Tailscale
curl http://${TS_KVM4}:8054/health
```

### Phase 4: Update Fleet MCP Configs
Each node's MCP config should point to BoTZ Gateway instead of direct service connections:

| MCP Server | Current (Direct) | After (BoTZ Gateway) |
|------------|-------------------|----------------------|
| Cipher | `${TS_Z890}:8105/mcp/sse` | `${TS_KVM4}:8054/cipher/sse` |
| Agent Zero | `${TS_Z890}:8080/mcp` | `${TS_KVM4}:8054/agent-zero` |
| Hi-RAG | `${TS_Z890}:8086/hirag` | `${TS_KVM4}:8054/hirag` |
| GitHub | (per-node Docker MCP) | `${TS_KVM4}:8054/github` |

### Phase 5: NATS Leaf Node Mesh
Configure each node's NATS as a leaf node to KVM4-1:
```conf
leafnodes {
  remotes = [
    { url: "nats://nats:pmoves@${TS_KVM4}:4222" }
  ]
}
```

## MCP Server Aggregation

BoTZ Gateway should expose all MCP servers through a single endpoint. This requires adding MCP proxy routes to the BoTZ Gateway service:

| Route | Backend | Protocol |
|-------|---------|----------|
| `/cipher/sse` | `http://cipher-api:8105/mcp/sse` | SSE |
| `/agent-zero` | `http://agent-zero:8080/mcp` | HTTP |
| `/hirag` | `http://hi-rag-gateway-v2:8086/hirag` | HTTP |
| `/github` | (BoTZ native — GitHub App token minting) | stdio |

## Security
- All inter-node traffic via Tailscale (encrypted WireGuard)
- BoTZ Gateway requires Bearer auth (`CIPHER_API_TOKEN`)
- GitHub MCP uses GitHub App credentials (minted per-session by BoTZ)
- No ports exposed to public internet — Tailscale-only

## Failover
If KVM4-1 goes down, nodes fall back to direct Tailscale connections:
- Elder-Melchor: local Cipher (stdio) — already working
- 5090: direct `${TS_Z890}:8105/mcp/sse` — already configured
- Z890: local services — already running