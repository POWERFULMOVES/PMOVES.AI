# PMOVES.AI KVM Exit Nodes, Hostinger Hosting & Network Infrastructure

> **Version:** 1.0 | **Date:** 2026-04-17 | **Classification:** Internal Architecture
> **Sources:** 25+ config files, OpenAPI spec, provisioning scripts, Terraform IaC

---

## Executive Summary

PMOVES.AI operates a hybrid infrastructure spanning 3 Hostinger KVM VPS nodes (US-East datacenter), physical GPU workstations (Z890/5090), and an NVIDIA DGX Spark superchip. All nodes interconnect via Tailscale WireGuard VPN, forming a private overlay network that compensates for Hostinger's lack of VPC/private networking.

The architecture follows a strict 3-tier separation: **KVM2** (network edge/exit proxy), **KVM4-1** (API/agent tier), **KVM4-2** (data/storage tier). GPU compute remains on-premises. A Tailscale exit node on KVM2 addresses the home ISP upload bottleneck through multi-strategy bypass (staging, GHCR, MinIO, rsync-over-Tailscale).

**Critical findings requiring immediate action:**

| Priority | Finding | Impact |
|----------|---------|--------|
| P0 | Tailscale exit node consume ACL rule missing | Exit node will not route any traffic despite being advertised |
| P0 | Provisioning script uses `tag:exit-node` but ACL defines `tag:exit` | Tag mismatch prevents exit node approval |
| P0 | No KVM has `tag:exit` assigned in production | Exit node infrastructure exists in config but is non-functional |
| P1 | KVM4-1 agent tier exceeds 16GB RAM budget (10.2GB needed, ~6GB realistic) | Risk of OOM under burst load |
| P1 | DGX Spark has zero Tailscale configuration | Cannot participate in mesh NATS or monitoring |
| P1 | Network inventory missing all 3 KVM nodes | Audit gap for infrastructure documentation |
| P2 | Root Makefile doesn't include `nvidia-dgx-spark.mk` | `make spark-*` targets unavailable from project root |

**Monthly cost:** ~$30/mo (3x Hostinger KVM) + home electricity for GPU workstations.

---

## 1. KVM Topology — Node Roles, Services, Tailscale Tags

### 1.1 Node Inventory

| Node | Hostname | Role | Hostinger Plan | vCPU | RAM | Disk | DC | Cost/mo |
|------|----------|------|----------------|------|-----|------|----|---------|
| **KVM2** | `pmoves-kvm2` | Exit Proxy / VPN Edge | kvm2-usd-4m | 8 | 8 GB | 200 GB SSD | US-East (id=13) | ~$10 |
| **KVM4-1** | `pmoves-kvm4-1` | API Gateway / Agent Tier | kvm4-usd-4m | ~16 | ~16 GB | ~400 GB SSD | US-East (id=13) | ~$10 |
| **KVM4-2** | `pmoves-kvm4-2` | Data / Storage Tier | kvm4-usd-4m | ~16 | ~16 GB | ~400 GB SSD | US-East (id=13) | ~$10 |

> KVM4 specs are inferred from tier naming. Verify via `GET /api/vps/v1/virtual-machines`.

### 1.2 Per-Node Service Maps

#### KVM2 — Exit Proxy (source: `claws/scopes/kvm2.json`, `claude-md/kvm2.md`)

| Service | Port | RAM | Status | Notes |
|---------|------|-----|--------|-------|
| Headscale (Tailscale control plane) | 8181 | ~100 MB | Running | Self-hosted TS control plane |
| Cloudflared (tunnel daemon) | — | ~50 MB | Running | Cloudflare tunnel to KVM2 |
| Tailscale client | — | ~30 MB | Running | Mesh networking |
| RustDesk hbbs (signaling) | 21115-21117 | ~30 MB | Running | Remote desktop signaling |
| RustDesk hbbr (relay) | 21117, 21119 | ~50 MB | Running | Remote desktop relay |
| Tailscale Exit Node | — | ~30 MB | **Not configured** | IPTables NAT + route advertising |
| Nginx (reverse proxy) | 80/443 | ~64 MB | **Planned** | TLS termination for PBNJ web UI |
| PBNJ Web Dashboard | 3001 | ~128 MB | **Planned** | Remote deployment dashboard |
| **Total used** | | ~260 MB | | **~7.7 GB free** |

**CLAW scope:** Restricted profile, `claude-haiku-4-5` model, manual confirm required. Only network diagnostics allowed (tailscale, wg, cloudflared, dig, traceroute, curl, ss, ip). No docker, no database access.

#### KVM4-1 — API Gateway (source: `claws/scopes/kvm4-1.json`, `claude-md/kvm4-1.md`)

| Service | Port | RAM | Status | Notes |
|---------|------|-----|--------|-------|
| Claude Code CLI | — | ~200 MB | Running | AI coding agent v2.1.83 |
| Ollama (qwen2.5-coder:3b) | 11434 | ~1.5 GB | Running | CPU-optimized coding model |
| GitHub Actions runner | — | ~100 MB | Running | Self-hosted CI/CD |
| Z890 service proxies (via Tailscale) | Various | Passive | Running | Proxy references to Z890 |
| Agent Zero (planned) | 8080, 8081 | ~2 GB | **Planned** | Core orchestrator |
| Archon (planned) | 8091 | ~512 MB | **Planned** | Supabase agent |
| TensorZero Gateway (planned) | 3030 | ~512 MB | **Planned** | LLM routing |
| Hi-RAG v2 (planned) | 8086 | ~1 GB | **Planned** | Hybrid search |
| NATS JetStream (planned) | 4222 | ~256 MB | **Planned** | Message bus |
| **Total existing** | | ~1.8 GB | | **~14 GB free** |
| **Total planned** | | ~8.8 GB | | **~7 GB free** |

**CLAW scope:** Restricted profile, `claude-sonnet-4` model, auto-confirm. Can manage GitHub PRs (gh), NATS messages, systemctl, journalctl, git, ollama, claude, wrangler. No docker, no make, no SSH to other nodes.

**MCP servers configured:** `pmoves-cipher` (SSE at `${TS_Z890}:8105`), `agent-zero` (HTTP at `${TS_Z890}:8080/mcp`).

#### KVM4-2 — Data Storage (source: `claws/scopes/kvm4-2.json`, `claude-md/kvm4-2.md`)

| Service | Port | RAM | Status | Notes |
|---------|------|-----|--------|-------|
| Supabase (Kong API gateway) | 8000 | ~500 MB | Running | PostgREST gateway |
| PostgreSQL | 5432 | ~1 GB | Running | Primary database |
| MinIO (object storage) | 9000/9001 | ~500 MB | Running | S3-compatible storage |
| Qdrant (vector DB) | 6333 | ~1 GB | Running | Embeddings store |
| Meilisearch (full-text search) | 7700 | ~300 MB | Running | Search engine |
| Neo4j (graph DB) | 7474/7687 | ~1 GB | Running | Knowledge graph |
| Cipher Memory | 8105 | ~200 MB | Running | Agent memory persistence |
| GitHub Actions runner | — | ~100 MB | Running | Self-hosted CI/CD |
| **Total** | | ~4.6 GB | | **~11.4 GB free** |

**CLAW scope:** Restricted profile, `claude-sonnet-4` model, auto-confirm. Only data operations: psql, mc (MinIO), curl to data endpoints, python3, git. No docker, no make, no SSH.

**MCP servers configured:** `pmoves-cipher` (SSE at `cipher-memory:8105`).

### 1.3 Tailscale Tags (Current vs. Required)

| Node | Current Tags | Required Tags | Gap |
|------|-------------|---------------|-----|
| pmoves-kvm2 | `tag:pmoves` | `tag:pmoves`, `tag:exit` | Missing `tag:exit` |
| pmoves-kvm4-1 | `tag:pmoves` | `tag:pmoves` | None |
| pmoves-kvm4-2 | `tag:pmoves` | `tag:pmoves` | None |
| pmoves-dgx-spark | (none) | `tag:pmoves`, `tag:dgx-spark` | Fully missing |

**Bug in provisioning script:** `hostinger-kvm-setup.sh` line for KVM2 tags uses `--tag=tag:exit-node` but the ACL policy defines `tag:exit`. This mismatch means the provisioning script will fail to get exit node approved.

---

## 2. Hostinger Integration

### 2.1 API Overview

Full OpenAPI 3.x specification at `docs/Hostingerapi/api-1.json`. Base URL: `https://developers.hostinger.com/api`. Auth: `Authorization: Bearer $TOKEN`.

**VPS API endpoints (57 endpoints):**

| Category | Count | Key Operations |
|----------|-------|----------------|
| Virtual Machines | 12 | Create, start, stop, restart, recreate, recovery, setup, hostname, root-password |
| Snapshots | 4 | Create, get, restore, delete |
| Backups | 3 | List, restore |
| Firewall | 10 | CRUD groups + rules, activate/deactivate/sync per VM |
| DNS | 8 | Full zone CRUD, snapshots, validation, reset |
| SSH Keys | 4 | Create, list, delete, attach to VM |
| Post-Install Scripts | 4 | Create, update, delete (attached during provisioning) |
| Metrics | 1 | CPU%, RAM, disk, traffic, uptime per VM |
| Docker Manager | 9 | Compose project CRUD, start/stop/update/logs/restart (EXPERIMENTAL) |
| PTR Records | 2 | Create/delete reverse DNS |
| IP Addresses | 1 | List all VM IPs |
| Malware Scanner (Monarx) | 3 | Get metrics, install, uninstall |
| Data Centers | 1 | List available DCs |
| OS Templates | 2 | List templates, get details |
| Nameservers | 1 | Set nameservers per VM |
| Panel Password | 1 | Set hPanel password |

**Additional APIs in spec (non-VPS):** Domains (15+ endpoints), Billing/Subscriptions (6 endpoints).

**Critical limitations:**
- No VPC or private networking between VMs
- No GPU instances
- No in-place resize (must recreate — data loss risk)
- No floating IPs
- No custom images (OS templates only)
- Docker Manager is marked EXPERIMENTAL

### 2.2 Python SDK

Referenced in strategy doc. Key operations:

```python
client = hostinger_api.Client(token="YOUR_API_TOKEN")
client.vps.list_virtual_machines()          # List all KVMs
client.vps.get_metrics(vm_id)               # CPU/RAM/disk/traffic
client.vps.create_snapshot(vm_id)           # Named snapshot
client.vps.restore_snapshot(snapshot_id)    # Restore from snapshot
client.vps.update_firewall(fw_id, rules=[]) # Update + sync firewall
```

### 2.3 MCP Server Integration

Hostinger provides `hostinger/api-mcp-server` (npx package). Can be added to CLAW scopes:

```json
{
  "mcpServers": {
    "hostinger": {
      "args": ["-y", "hostinger-api-mcp-server"],
      "env": { "HOSTINGER_API_TOKEN": "${HOSTINGER_API_TOKEN}" }
    }
  }
}
```

Not yet configured in any CLAW scope JSON.

### 2.4 Available SDKs/Tools

Python, Node.js, Terraform (provider v0.1.22), Ansible, MCP Server, n8n Node, CLI (`hapi`).

### 2.5 COS Workflows

`docs/Hostingerapi/COS/` contains Content Automation OS workflows (blog post triggers, AI image generation, social scheduling) — these are for content operations, not infrastructure. Separate concern from VPS management.

---

## 3. Cloudflare Integration

### 3.1 Cloudflare Worker — CI/CD Orchestrator

Located at `deploy/cloudflare/`. This is NOT a tunnel configuration — it's an intelligent build router.

**Purpose:** Receives GitHub webhooks, analyzes changed files, and routes builds to optimal runners.

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check (returns mode + timestamp) |
| `/webhook/github` | POST | GitHub webhook receiver (signature-verified) |
| `/status?build_id=X` | GET | Build state from KV store |
| `/metrics` | GET | Prometheus-compatible metrics |

**Runner routing decision tree:**

```
Is GPU required? → YES → AI Lab (self-hosted, RTX 5090, $0)
                    → NO → Is Docker build with cache benefit?
                              → YES → VPS (self-hosted, $0)
                              → NO → Is deployment to specific env?
                                        → YES → KVM4 (self-hosted, $0)
                                        → NO → Lightweight (<2min)?
                                                  → YES → GitHub hosted (~$0.05)
                                                  → NO → VPS (default)
```

**State storage:** Cloudflare KV namespace `CI_STATE`. Optional R2 bucket for artifacts.

**Planned routes** (commented out in `wrangler.toml`):
- `ci.pmoves.ai/webhook/*`
- `ci.pmoves.ai/health`
- `ci.pmoves.ai/status`
- `ci.pmoves.ai/metrics`

**Environments:** `production` (hybrid mode), `staging` (cloudflare-only mode).

### 3.2 Cloudflare Tunnel (on KVM2)

Cloudflared runs as a daemon on KVM2 for tunneling public traffic to internal services. No dedicated config files found — likely configured via `cloudflared tunnel list` CLI or Cloudflare dashboard. This is separate from the CI/CD Worker.

---

## 4. Tailscale ACL Policy Analysis

### 4.1 Current Policy (`pmoves/configs/tailscale-acl-policy.json`)

**7 tags defined:**

| Tag | Owner | Used In ACL | Notes |
|-----|-------|-------------|-------|
| `tag:pmoves` | autogroup:admin | Yes (full mesh) | All PMOVES nodes |
| `tag:gpu` | autogroup:admin | Yes (dst for lab/partner/guest) | GPU workstations |
| `tag:vps` | autogroup:admin | **NO** | Defined but unused — dead tag |
| `tag:lab` | autogroup:admin | Yes (→gpu:*) | Jetson Nano etc. |
| `tag:exit` | autogroup:admin | Yes (autoApprovers) | Exit node capability |
| `tag:partner` | autogroup:admin | Yes (→gpu:3030,8080,8081) | External collaborators |
| `tag:guest` | autogroup:admin | Yes (→gpu:8081) | Demo access |

**5 standard ACL rules:**

```
tag:pmoves       → tag:pmoves:*          (all ports, full mesh)
tag:lab          → tag:gpu:*             (all ports, inference access)
tag:partner      → tag:gpu:3030,8080,8081 (Agent Zero API + TensorZero + UI)
tag:guest        → tag:gpu:8081          (Agent Zero UI only)
autogroup:admin  → *:*                   (full access)
```

**2 SSH rules:**

```
tag:pmoves       → tag:pmoves            (non-root only)
autogroup:admin  → *                     (root + non-root)
```

**nodeAttrs:** `tag:exit` gets `funnel` attribute (public ingress capability).

**autoApprovers:**

```json
{
  "exitNode": ["tag:exit"],
  "routes": { "0.0.0.0/0": ["tag:exit"], "::/0": ["tag:exit"] }
}
```

### 4.2 P0 Gap: Exit Node Non-Functional

The autoApprovers grant `tag:exit` nodes permission to **advertise** as exit nodes with default routes. However, **no ACL rule exists that allows any source to consume (use) the exit node**.

Without this consume rule, Tailscale will not route any client traffic through the exit node, even if the node correctly advertises routes. Required fix:

```json
{"action": "accept", "src": ["tag:pmoves"], "dst": ["autogroup:internet:*"]}
{"action": "accept", "src": ["tag:lab"], "dst": ["autogroup:internet:*"]}
```

### 4.3 Proposed ACL Updates (from strategy doc)

1. Add 2 exit node consume rules (pmoves→internet, lab→internet)
2. Add SSH rule: `tag:lab` → `tag:gpu` (non-root)
3. Remove dead `tag:vps`
4. Add `tag:dgx-spark` for DGX Spark integration

---

## 5. Network Inventory

### 5.1 Registered Nodes (`pmoves/configs/pinokio-network-inventory.yaml`)

| Hostname | Tailscale Host | Role | LWW | Services |
|----------|---------------|------|-----|----------|
| POWERFULMOVES | powerfulmoves-1 | Primary GPU/TTS | Yes | 9 intentional + 6 noise |
| pmoves-z890 | pmoves-z890 | Infra Coordinator | Yes | 8 intentional + 1 noise |
| pmoves-laptop | pmoves-laptop | Mobile Relay | No | 0 (consumer node) |

**Gap:** All 3 KVM nodes and DGX Spark are missing from the network inventory. This file tracks Pinokio LAN-Wide-Web services but should also register Tailscale-only nodes for completeness.

### 5.2 POWERFULMOVES (5090) Services

Intentional: Ultimate-TTS-Studio (:7860), Qwen3-TTS, VibeVoice-Realtime, VoxForge-Pro, Ollama (:11434), N8N, SillyTavern, ACE-Step (music), WAN (video).

Noise (auto-discovered, non-PMOVES): Steam, Chrome DevTools (:9222), Razer Synapse, Logitech GHub, Surfshark VPN.

System: Docker Desktop, NVIDIA Container.

### 5.3 pmoves-z890 Services

NATS (:4222), Agent Zero (:8080), TensorZero (:3030), Grafana (:3000), Prometheus (:9090), Supabase-Kong (:8000), Flute-Gateway (:8055), Pinokio UI (:42000).

Note: TTS apps (OpenAudio/Fish Speech, Qwen3-TTS, Ultimate-TTS SUP3R) were removed 2026-03-22 and delegated to 5090.

### 5.4 Full Fleet (Including Unregistered)

| Node | Type | Location | Tailscale | Registered in Inventory |
|------|------|----------|-----------|------------------------|
| POWERFULMOVES | Physical (RTX 5090) | Home LAN | Yes | Yes |
| pmoves-z890 | Physical (RTX 4090) | Home LAN | Yes | Yes |
| pmoves-laptop | Physical (RTX 4090 mobile) | Mobile | Yes | Yes |
| pmoves-kvm2 | Hostinger KVM VPS | US-East DC | Yes | **NO** |
| pmoves-kvm4-1 | Hostinger KVM VPS | US-East DC | Yes | **NO** |
| pmoves-kvm4-2 | Hostinger KVM VPS | US-East DC | Yes | **NO** |
| pmoves-dgx-spark | NVIDIA DGX Spark | Tailscale | Yes (via ollama_spark) | **NO** |
| pmoves-nano | Jetson Nano | Home LAN | Yes | **NO** |

---

## 6. DGX Spark Integration

### 6.1 Hardware

NVIDIA DGX Spark with GB10 Grace-Blackwell superchip, 128GB unified LPDDR5X, 1 petaFLOP FP4. Unified memory eliminates CPU↔VRAM copies — models up to ~200B params can run without traditional VRAM constraints.

### 6.2 Agent Profile (`pmoves/configs/agent-profiles/spark_claw.yaml`)

- **Name:** spark_claw
- **Role:** dgx-spark-heavyweight-claw
- **Model:** ollama_spark/gemma4:31b (fallback: tensorzero)
- **Endpoint:** `http://pmoves-dgx-spark:11434/v1`
- **Capabilities:** heavyweight_llm_inference, unified_memory_200b, multimodal_any_to_any, gemma4_support, nemotron_support, qwen3_coder_large_support, agentic_reasoning, gpu_monitoring
- **NATS integration:** Subscribes to `mesh.gpu.command.v1`, `pinokio.agent.session.v1`. Publishes to `mesh.gpu.status.v1`, `mesh.gpu.model.loaded.v1`, `mesh.gpu.model.unloaded.v1`, `mesh.gpu.command.result.v1`, `pinokio.telemetry.v1`
- **Health:** `http://pmoves-dgx-spark:11434/api/tags`, heartbeat every 10s on `mesh.gpu.status.v1`
- **Agent Zero:** Subordinate agent, reports to main Agent Zero

### 6.3 Make Targets (`pmoves/mk/nvidia-dgx-spark.mk`)

7 targets, all SSH-based via Tailscale hostname `pmoves-dgx-spark`:

| Target | Description |
|--------|-------------|
| `spark-ssh` | SSH to DGX Spark |
| `spark-ollama-status` | Check Ollama service (`ollama list`) |
| `spark-gpu-status` | GB10 GPU utilization via `nvidia-smi` |
| `spark-ollama-ls` | List local Ollama models |
| `spark-ollama-pull MODEL=X` | Pull specific model |
| `spark-gemma4-pull` | Pull all 4 Gemma 4 variants (E2B, E4B, 26B, 31B) |
| `spark-health` | HTTP health check at :11434/api/tags |

**Gap:** Root `Makefile` only has `update-service-docs` target — does not include `pmoves/mk/nvidia-dgx-spark.mk`. Must run `make -C pmoves spark-*` or fix the include.

### 6.4 Integration Gaps (7 of 8 remaining)

1. Root Makefile doesn't include nvidia-dgx-spark.mk
2. Tailscale ACL has no dgx-spark entries (no `tag:dgx-spark`)
3. Network inventory missing DGX Spark
4. NATS `mesh.gpu.*` subjects referenced but not defined in any NATS config
5. Flare model namespace has TODO for dgx-spark nodes enum
6. ~~No ollama_spark provider~~ **FIXED** — added to model_providers.yaml
7. No AGNOTE docs reference DGX Spark
8. No TAC tree for DGX Spark

### 6.5 How DGX Spark Fits the Network Mesh

DGX Spark is accessed via Agent Zero's `ollama_spark` provider (HTTP at `pmoves-dgx-spark:11434`), not direct Tailscale CLI. It's designed as a subordinate agent that receives commands via NATS (`mesh.gpu.command.v1`) and reports status back (`mesh.gpu.status.v1`). However, without Tailscale tags and ACL rules, it has no formal identity in the tailnet — just an Ollama endpoint reachable over Tailscale IP.

**Recommended integration:** Add `tag:dgx-spark` to ACL, tag the node, add SSH rule for `tag:pmoves` → `tag:dgx-spark`, add to network inventory.

---

## 7. PBnJ/Pinokio Launcher

### 7.1 Architecture

PBnJ (Pinokio-Based N-tier) is a one-click deployment interface running on the operator's machine via Pinokio desktop app. It does NOT run on KVMs — it orchestrates deployments TO KVMs via kubectl and docker compose commands.

### 7.2 Pinokio Apps (6 apps in `pbnj/pinokio/api/`)

| App | Purpose | Key Workflows |
|-----|---------|---------------|
| `pmoves-pbnj` | Main deployment dashboard | lab-up/down, kvm4-up/down, local-up/down, status, vps-status, kvm2-deploy, kvm4-1-deploy, kvm4-2-deploy, 4090-deploy/status/models |
| `pmoves-services` | Service management | start-core, start-external, start-voice, start-monitoring, stop, reset, update, status |
| `pmoves-agent-zero` | Agent Zero control | install, start, status, reset, update |
| `pmoves-remote` | Remote KVM deployment | install, start, status |
| `pmoves-discord-bot` | Discord bot management | setup, install, start (Node.js app with channel-structure.yaml) |
| `pmoves-model-registry` | Model registry | SKILL.md only (planned) |

### 7.3 KVM Deploy Workflows

PBnJ has dedicated JSON workflows for each KVM:

- `kvm2-deploy.json` — Deploy to KVM2 exit node
- `kvm4-1-deploy.json` — Deploy to KVM4-1 API tier
- `kvm4-2-deploy.json` — Deploy to KVM4-2 data tier

These execute `deploy-k8s.sh` or `deploy-compose.sh` with KVM-specific parameters via Tailscale SSH.

### 7.4 API Endpoints

No REST API — PBnJ uses Pinokio's `shell.run` method to execute commands. The planned PBNJ Web Dashboard on KVM2 (:3001) would provide a web UI for remote triggering, but this is Phase 6 (optional, Days 19-21).

---

## 8. Deploy Configurations

### 8.1 Directory Structure

```
deploy/
├── scripts/
│   ├── deploy-k8s.sh          # K8s orchestration (apply/delete/status per target)
│   ├── deploy-compose.sh      # Docker Compose wrapper (up/down/logs)
│   ├── deploy-vps.sh          # VPS-specific deployment
│   └── verify-services.sh     # Service health verification
├── k8s/
│   ├── base/                  # Base Kustomize manifests (namespace, deployment, service, ingress)
│   ├── ai-lab/                # AI Lab overlay (5 replicas, lab-hardened image)
│   ├── kvm4/                  # KVM4 gateway overlay (2 replicas, kvm4-hardened image)
│   ├── local/                 # Local dev overlay (dev-local tag)
│   └── networkpolicies/       # 6 NetworkPolicy manifests (default-deny, allow-dns, allow-ingress, allow-nats-mesh, allow-monitoring, allow-external-api)
├── runners/
│   ├── vps/install.sh         # VPS runner install (standard)
│   ├── vps/install-hardened.sh # VPS runner install (hardened)
│   ├── ailab/install.sh       # AI Lab GPU runner install
│   ├── README.md              # Runner fleet documentation
│   ├── IMPLEMENTATION-SUMMARY.md
│   ├── HARDENING-ANALYSIS.md
│   └── QUICK-START.md
├── provision/
│   └── hostinger-kvm-setup.sh # Full KVM provisioning (6-step, 4 node types)
├── cloudflare/                # CI/CD Worker orchestrator
├── HYBRID_RUNNER_STRATEGY.md  # Runner routing architecture
└── README.md
```

### 8.2 K8s Deployment Strategy

**3 targets via Kustomize overlays:**

| Target | Image | Replicas | Hostname | Context Env Var |
|--------|-------|----------|----------|----------------|
| AI Lab | `pmoves-core:v1.0.0-lab-hardened` | 5 | `pmoves.lab.local` | `PMOVES_K8S_CONTEXT_AI_LAB` |
| KVM4 | `pmoves-core:v1.0.0-kvm4-hardened` | 2 | `pmoves.kvm4.yourdomain.tld` | `PMOVES_K8S_CONTEXT_KVM4` |
| Local | dev-local | 1 | localhost | `PMOVES_K8S_CONTEXT_LOCAL` |

**Network policies:** Default deny-all, then allow DNS, ingress, NATS mesh, monitoring, external API. Defense-in-depth approach.

### 8.3 Runner Fleet

| Runner | Labels | Role | Hardware |
|--------|--------|------|----------|
| AI Lab | `self-hosted,ai-lab,gpu` | GPU builds (CUDA, Ollama) | RTX 5090/4090/3090Ti |
| cloudstartup | `self-hosted,cloudstartup,staging` | Staging deploys | Hostinger VPS (8 vCPU) |
| kvm4 | `self-hosted,kvm4,production` | Production deploys | Hostinger VPS (8 vCPU) |
| kvm2 | `self-hosted,kvm2,backup` | Overflow/backup | Hostinger VPS (4 vCPU) |
| GitHub hosted | `ubuntu-latest` | Lightweight tasks | Cloud (on-demand) |

**Cost:** ~$35/month vs ~$300/month GitHub-hosted only (88% savings).

### 8.4 Provisioning Script (`deploy/provision/hostinger-kvm-setup.sh`)

6-step automated provisioning for fresh Ubuntu 22.04+ KVM:

1. **System hardening:** apt update, ufw (per-node rules), fail2ban (5-attempt/1hr ban), SSH hardening (key-only, MaxAuthTries 3)
2. **Docker + Compose v2:** get.docker.com, docker-compose plugin
3. **Tailscale mesh join:** Install, tag per node type, KVM2 gets `--advertise-exit-node`
4. **GitHub Actions runner:** Uses hardened install script, per-node labels
5. **Work directory:** `/opt/pmoves` with git clone and `.node-config` marker
6. **Flare config:** `MODEL_NAMESPACE=pmoves`, vLLM endpoint routing (local for gpu-5090, Tailscale for others)

**Per-node UFW rules:**

- KVM4-1: 8080 (Agent Zero), 8086 (Hi-RAG), 3030 (TensorZero), 8091 (Archon), 8100 (Gateway)
- KVM4-2: 4222 (NATS), 6333 (Qdrant), 7474/7687 (Neo4j), 7700 (Meilisearch), 9090 (Prometheus), 3000 (Grafana)
- KVM2: 80/443 (HTTP/HTTPS)
- GPU-5090: 8200 (GPU Orchestrator), 11434 (Ollama), 8100-8160 (vLLM)

---

## 9. Makefile Analysis

### 9.1 Root Makefile

Minimal — single target that delegates:

```makefile
PYTHON ?= python3
.PHONY: update-service-docs
update-service-docs:
	@$(MAKE) -C pmoves update-service-docs ARGS="$(ARGS)"
```

Does NOT include `pmoves/mk/nvidia-dgx-spark.mk`. To use DGX Spark targets, must run `make -C pmoves spark-health` etc.

### 9.2 Missing Includes

The `pmoves/mk/` directory contains `nvidia-dgx-spark.mk` but it's not included by the root or pmoves Makefile. This means `make spark-*` is unavailable from standard build workflow.

---

## 10. Terraform Infrastructure-as-Code

### 10.1 Files

| File | Purpose |
|------|---------|
| `pmoves/terraform/mcp-integration.tf` | Main Terraform config with Hostinger provider, multi-node fleet, Docker provider |
| `pmoves/terraform/bootstrap-script.sh` | Terraform-templated bootstrap script (variable interpolation) |
| `pmoves/terraform/variables.auto.tfvars.example` | Example variables (never commit actual .tfvars) |

### 10.2 Provider Configuration

```hcl
terraform {
  required_providers {
    hostinger = { source = "hostinger/hostinger", version = "0.1.22" }
    docker    = { source = "kreuzwerker/docker", version = "~> 3.0" }
    local     = { source = "hashicorp/local", version = "~> 2.5" }
  }
}
```

### 10.3 Multi-Node Fleet Definition

```hcl
variable "kvm_nodes" {
  default = {
    "kvm4-1" = { plan = "kvm4-usd-4m", role = "api-gateway",    hostname = "pmoves-kvm4-1", profile = "agents" }
    "kvm4-2" = { plan = "kvm4-usd-4m", role = "data-services",  hostname = "pmoves-kvm4-2", profile = "knowledge" }
    "kvm2"   = { plan = "kvm2-usd-4m", role = "exit-node",      hostname = "pmoves-kvm2",   profile = "monitoring" }
  }
}
```

Default VPS plan is `kvm2-usd-4m` (8GB/8vCPU/200GB). KVM4 nodes use `kvm4-usd-4m`. Data center defaults to 13 (US-East).

### 10.4 Bootstrap Script Template

Terraform-templated shell script with `${variable}` interpolation via `templatefile()`. Steps: system update, Docker install, Tailscale install, UFW firewall (22, 80, 443, 41641/udp), git clone, environment file generation, Docker Compose up (full or partial profile).

**Gap:** Bootstrap script is simpler than `hostinger-kvm-setup.sh` — doesn't include per-node UFW rules, fail2ban, GitHub runner install, or exit node IP forwarding. These two scripts serve different purposes but should be unified.

### 10.5 Status

Terraform configs exist but are not yet applied to existing KVMs. `terraform import` needed to bring existing infrastructure under state management.

---

## Cross-Cutting Analysis

### A. How KVM Exit Nodes Bypass Slow Upload

The home ISP upload bottleneck (typically 10-50 Mbps) is addressed through a **layered strategy** — not just exit nodes:

1. **Exit node proxy (limited benefit):** Routing through KVM2 exit node does NOT bypass ISP uplink for the first hop. Traffic still traverses home ISP upload. Exit nodes help for **download speed** (KVM2's 1Gbps port) and **IP masking**, not upload.

2. **KVM2 staging + DC-internal distribution:** Upload once to KVM2 (ISP speed), then KVM2 distributes to KVM4-1/KVM4-2 at ~1 Gbps datacenter-internal speed. This amortizes the ISP upload across multiple targets.

3. **GHCR for Docker images:** Push to GitHub Container Registry (ISP upload once), KVMs pull at datacenter speed. Already in CI/CD pipeline.

4. **MinIO on KVM4-2:** Upload models/media once (ISP), all services read locally at disk speed. MinIO already running.

5. **rsync-over-Tailscale with compression:** For config/scripts < 100MB, direct rsync with `-avz --compress` is sufficient.

6. **Hostinger post-install scripts:** Provision services from scratch via apt/pip instead of uploading binaries.

**Decision matrix:**

| Artifact Type | Strategy | ISP Upload Required |
|--------------|----------|---------------------|
| Docker images | GHCR | Yes (once, to GHCR) |
| LLM models (>10GB) | MinIO + KVM2 staging | Yes (once, to MinIO) |
| Config/scripts (<100MB) | rsync direct | Yes (small) |
| Public assets | Cloudflare R2 | Yes (once, cached globally) |
| Fresh KVM provisioning | Post-install script | No |

### B. How to Deploy PMOVES.AI on Hostinger VPS

**Option A: Automated provisioning (recommended)**

```bash
# On fresh KVM:
GITHUB_PAT=ghp_xxx TAILSCALE_AUTHKEY=tskey-xxx \
  ./deploy/provision/hostinger-kvm-setup.sh kvm4-1

# Then deploy services:
cd /opt/pmoves/pmoves && docker compose -f docker-compose.yml \
  -f docker-compose.vps.override.yml up -d tensorzero agent-zero
```

**Option B: Terraform IaC**

```bash
cd pmoves/terraform
cp variables.auto.tfvars.example variables.auto.tfvars  # Fill in real values
terraform init
terraform plan
terraform apply
```

**Option C: PBnJ one-click (from operator machine)**

Open Pinokio → PMOVES.PBnJ → Click "KVM4-1 Deploy" or "KVM4-2 Deploy"

**Option D: K8s via PBnJ**

Open Pinokio → PMOVES.PBnJ → Click "Start KVM4 Stack (K8s)"

### C. How DGX Spark Fits the Network Mesh

DGX Spark occupies a unique position — it's the most powerful compute node (200B-class inference) but has the weakest infrastructure integration:

- **Access path:** Agent Zero → `ollama_spark` provider → `http://pmoves-dgx-spark:11434/v1` (HTTP over Tailscale)
- **NATS participation:** Defined in agent profile but subjects not configured in NATS server
- **Tailscale identity:** No tags, no ACL rules, no formal tailnet role
- **Monitoring:** `make spark-gpu-status` works via SSH but no Prometheus/Grafana integration
- **Make targets:** Exist but not included in root Makefile

**Integration priority:** Add Tailscale tags + ACL rules (enables SSH rules, Funnel, monitoring), include mk file in Makefile, define NATS subjects, add to network inventory.

---

## Gaps and Recommendations

### P0 — Block Deployments

| # | Gap | Fix | Effort |
|---|-----|-----|--------|
| 1 | Exit node consume ACL rule missing | Add `tag:pmoves → autogroup:internet:*` and `tag:lab → autogroup:internet:*` to ACL | 5 min |
| 2 | Provisioning script tag mismatch (`tag:exit-node` vs `tag:exit`) | Change `--tag=tag:exit-node` to `--tag=tag:exit` in `hostinger-kvm-setup.sh` line ~163 | 2 min |
| 3 | No KVM has `tag:exit` assigned | Re-auth KVM2 with `tailscale up --advertise-tags=tag:pmoves,tag:exit --advertise-routes=0.0.0.0/0,::/0` | 10 min |

### P1 — Block Full Operation

| # | Gap | Fix | Effort |
|---|-----|-----|--------|
| 4 | KVM4-1 RAM budget exceeds 16GB at full load | Defer voice services to Z890, make Ollama on-demand, add 2GB swap | 1 hr |
| 5 | DGX Spark not in Tailscale ACL | Add `tag:dgx-spark`, ACL rules, SSH rules | 30 min |
| 6 | Network inventory missing KVMs + DGX Spark | Add entries to `pinokio-network-inventory.yaml` | 30 min |
| 7 | Root Makefile missing DGX Spark include | Add `include pmoves/mk/nvidia-dgx-spark.mk` | 2 min |
| 8 | KVM4 specs unverified | Run `GET /api/vps/v1/virtual-machines` and confirm RAM/CPU/disk | 5 min |

### P2 — Improve Operations

| # | Gap | Fix | Effort |
|---|-----|-----|--------|
| 9 | `tag:vps` defined but unused | Remove from ACL | 2 min |
| 10 | Terraform not applied to existing KVMs | `terraform import` existing resources | 2 hr |
| 11 | Hostinger MCP not in CLAW scopes | Add to kvm2/kvm4-1 scope JSONs | 15 min |
| 12 | NATS mesh.gpu.* subjects undefined | Define in NATS server config | 1 hr |
| 13 | No AGNOTE/TAC tree for DGX Spark | Create docs | 2 hr |
| 14 | Two provisioning scripts not unified | Merge bootstrap-script.sh into hostinger-kvm-setup.sh or vice versa | 2 hr |
| 15 | Stale Tailscale nodes (3 exceeding 60-day policy) | Remove via admin console | 10 min |

---

## Quick Reference

```bash
# === Tailscale Exit Node ===
tailscale set --exit-node=pmoves-kvm2                    # Enable
tailscale set --exit-node=pmoves-kvm2 --exit-node-allow-lan-access  # + keep LAN
tailscale set --exit-node=                              # Disable
tailscale exit list                                     # List available

# === Upload Strategies ===
rsync -avz --compress ./config/ root@pmoves-kvm4-1:/opt/pmoves/   # Small files
rsync -avz --compress ./large.tar.gz root@pmoves-kvm2:/tmp/staging/ # Stage large
mc cp ./model.gguf pmoves-minio/models/                          # To MinIO

# === Hostinger API ===
curl -H "Authorization: Bearer $TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines          # List KVMs
curl -H "Authorization: Bearer $TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines/$ID/metrics  # Metrics

# === DGX Spark ===
make -C pmoves spark-health          # Health check
make -C pmoves spark-gemma4-pull     # Pull all Gemma 4 variants
make -C pmoves spark-gpu-status      # GPU utilization

# === Provisioning ===
GITHUB_PAT=ghp_xxx TAILSCALE_AUTHKEY=tskey-xxx \
  ./deploy/provision/hostinger-kvm-setup.sh kvm4-1

# === KVM Health Checks ===
tailscale ping pmoves-kvm4-1                           # Connectivity
curl -s http://pmoves-kvm4-1:8080/healthz              # Agent Zero
curl -s http://pmoves-kvm4-2:6333/collections           # Qdrant
curl -s http://pmoves-dgx-spark:11434/api/tags          # DGX Spark Ollama
```

---

*Report generated by Agent Zero Deep Research from 25+ primary source files. All findings cross-referenced against `docs/architecture/kvm-exit-node-hosting-strategy.md` (v1.0, 2026-04-17). KVM4 specs marked "inferred" require Hostinger API verification before production deployment.*
