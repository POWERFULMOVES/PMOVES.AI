# PMOVES.AI Master Topology

> Single source of truth for all physical/virtual nodes, service assignments, agent teams, route flows, and runner strategy.
>
> Last updated: 2026-04-13

---

## Node Inventory

| Node | LAN IP | Tailscale IP | Tailscale Hostname | Role | Runner Labels | vCPU / RAM | Cost |
|------|--------|-------------|--------------------|----- |---------------|------------|------|
| Z890 (Windows 11) | LAN (dual NIC) | `ts:<z890>` | pmoves-z890 | Dev, GPU (RTX 3090 Ti) | `self-hosted, ai-lab` (secondary) | 32C / 128GB | electricity |
| POWERFULMOVES (5090) | LAN (dual NIC) | `ts:<5090-linux>`, `ts:<5090-win>` | pmoves-powerfulmoves, powerfulmoves-1 | Primary GPU (RTX 5090) | `self-hosted, ai-lab, gpu, cuda` | 24C / 64GB | electricity |
| 4090 Laptop (Windows) | LAN | `ts:<laptop>` | pmoves-4090 | Control Plane, Edge Orchestration, Agent Zero + Claws | — | RTX 4090 | electricity |
| DGX Spark | LAN | `ts:<dgx-spark>` | pmoves-dgx-spark | Heavyweight Inference (Gemma 4 31B, Nemotron Super 49B, Qwen3-Coder 480B) | `self-hosted, ai-lab, gpu, cuda, spark` (pending) | 20C Arm / 128GB unified LPDDR5X | electricity |
| Jetson Orin #1 | LAN (RustDesk + SSH) | `ts:<nano>` | pmoves-nano (rename to pmoves-nano-1 pending) | Edge Inference (Nemotron/NemoClaw), Claws | — | Orin (sm_87) | electricity |
| Jetson Orin #2 | LAN (RustDesk + SSH) | TBD | TBD | Edge Inference (Nemotron/NemoClaw), Claws | — | Orin (sm_87) | electricity |
| KVM4-1 | — | — | pmoves-kvm4-1 | API Gateway | `self-hosted, vps, kvm4, production` | 8C / 16GB | $10/mo |
| KVM4-2 | — | — | pmoves-kvm4-2 | Data / Storage | `self-hosted, vps, kvm4, production` | 8C / 16GB | $10/mo |
| KVM2 | — | — | pmoves-kvm2 | Exit Node / Proxy | `self-hosted, vps, kvm2, backup` | 4C / 8GB | $10/mo |
| Cloudflare Edge | — | — | — | DNS, Worker routing | — | Edge | Free plan |
| GitHub Cloud | — | — | — | Lightweight CI | `ubuntu-latest` | 2C / 7GB | $0.008/min |

### Mobile & IoT Devices

| Device | LAN IP | Tailscale IP | Notes |
|--------|--------|-------------|-------|
| Pixel 10 Pro XL | — | `ts:<pixel>` | Mobile agent (Discord/Openclaw) |
| Nest Audio (x2) | LAN | — | Cast speakers, voice output |
| Nest Mini | LAN | — | Den speaker near 5090 |
| TCL 75QM850G TV | LAN | — | Chromecast built-in |
| Creality 3DMax | LAN | — | 3D printer — future Danger Room fabrication |

### Jetson Orin Status

Both Jetson Orin Nanos have SSH configured (`pmovesnvme@.110`, `pmovesnvme@.144`) and are accessible via **RustDesk** relay through KVM2. Both registered on KVM2 RustDesk server with root + user config deployed via `restart-jetson-rustdesk.sh`.

**Completed:**
- SSH key-only auth (password disabled)
- RustDesk config: KVM2 relay, both root and user paths
- pmoves-claw SSH key injected to root

**Remaining:**
1. Jetson #1: Tailscale active (pmoves-nano, 100.x), pending rename to pmoves-nano-1
2. Jetson #2: Fresh Tailscale install needed
3. JetPack version check and potential update
4. Registration in `agent-teams.yaml` and `node-agent-specialization.yaml`
5. Agent Zero + Claws deployment

**Total VPS cost:** $30/mo + electricity for local nodes.

### DGX Spark — Heavyweight Inference Node (Pending)

NVIDIA DGX Spark (GB10 Grace-Blackwell Superchip) on Tailscale. Purpose-built for 200B-param-class inference via unified memory:

- **CPU+GPU:** 20-core Arm (10x Cortex-X925 + 10x Cortex-A725) + GB10 Grace-Blackwell
- **Memory:** 128GB unified LPDDR5X (CPU+GPU coherent, no VRAM↔RAM copies)
- **Throughput:** 1 petaFLOP FP4
- **Target models:** Gemma 4 31B (FP16), Gemma 4 26B-A4B, Nemotron Super 49B, Qwen3-Coder 480B
- **Runtime:** Ollama (CUDA) primary; NVIDIA NIM optional
- **Ports:** 11434 (Ollama), 8200 (NIM if deployed — same default as 5090)
- **Tailscale hostname:** `pmoves-dgx-spark`

**Pending setup:**
1. Tailscale join + tag assignment (`tag:spark`)
2. Ollama install + `gemma4:31b`, `gemma4:26b-a4b`, `nemotron:49b` model pulls
3. Registration in `agent-teams.yaml` under `agents/gpu-inference` tier
4. TensorZero `ollama_spark` provider points at `http://pmoves-dgx-spark:11434/v1`
5. `spark_claw` agent profile activates after first heartbeat on `mesh.gpu.status.v1`

---

## Node Agent Cognitive Specialization

Each GPU node runs a Claude Code CLI agent with a declared cognitive specialization.
Config: `pmoves/configs/node-agent-specialization.yaml`

| Node Agent | Specialization | Strength | Default Work | NATS Subject |
|------------|---------------|----------|-------------|-------------|
| z890-claude | Infrastructure Coordinator | Docker, NATS, secrets, compose | Commit hygiene, service wiring | `mesh.agent.z890.capabilities.v1` |
| 5090-claude | GPU Inference Specialist | Voice, TTS, models, media | Pipeline design, model evaluation | `mesh.agent.5090.capabilities.v1` |
| 4090-claude | Noise Reducer (Jewel Finder) | PR triage, patterns, docs | Review threads, submodule audit | `mesh.agent.4090.capabilities.v1` |

**Routing:** PR review threads are keyword-scored and routed to the best-fit agent.
The 4090 is the default handler — its "noise reducer" role catches anything unmatched.
See `suggest_reviewer()` in `pmoves/tools/pr_hedge_trim.py`.

**Insight Sharing:** Agents publish `ops.pr.insight.shared.v1` to share cross-PR
patterns, blockers, and learnings for validation by peer agents.

---

## Service-to-Node Assignments

### KVM4-1 — API Gateway Node

Services deployed via `docker-compose.vps.override.yml`:

| Service | Port | Health | Compose Profile |
|---------|------|--------|-----------------|
| TensorZero Gateway | 3030 | `/healthz` | — |
| Agent Zero | 8080 | `/healthz` | agents |
| Hi-RAG v2 (CPU) | 8086 | `/healthz` | — |
| Archon | 8091 | `/healthz` | agents |
| Mesh Agent | — | — | agents |
| Gateway Agent | 8100 | `/healthz` | tier-agent |
| Extract Worker | 8083 | `/healthz` | workers |

### KVM4-2 — Data / Storage Node

| Service | Port | Health | Compose Profile |
|---------|------|--------|-----------------|
| Supabase DB (Postgres) | 5432 (int) / 54322 (ext) | — | supabase-local |
| Supabase PostgREST | 3000 (container-internal, via Kong at 8000) | — | supabase-local |
| Kong Gateway | 8000 / 65421 | — | supabase-local |
| Qdrant | 6333 | `/healthz` | — |
| Neo4j | 7474 (HTTP) / 7687 (Bolt) | `/db/neo4j/health` | — |
| Meilisearch | 7700 | `/health` | — |
| NATS | 4222 / 9222 (WS) | `http://nats:8222/varz` | — |
| Prometheus | 9090 | `/-/healthy` | monitoring |
| Grafana | 3002 | `/api/health` | monitoring |
| Loki | 3100 | `/ready` | monitoring |
| MinIO | 9000 (API) / 9001 (Console) | `/minio/health/live` | — |

### KVM2 — Exit Node / Reverse Proxy / RustDesk Relay

| Service | Port | Health | Notes |
|---------|------|--------|-------|
| nginx | 80 / 443 | `nginx -t` | SSL termination via Let's Encrypt |
| RustDesk hbbs | 21115-21116 | `journalctl -u hbbs` | Rendezvous server with `-r` relay flag |
| RustDesk hbbr | 21117-21119 | `journalctl -u hbbr` | Relay server |

**RustDesk Fleet:** Self-hosted relay on KVM2. All LAN nodes (Z890, 5090, 4090, Jetson #1, Jetson #2) registered. Mobile devices pending QR enrollment. See `docs/operations/RUSTDESK_SELF_HOSTED.md` for details.

### POWERFULMOVES — Primary GPU + AI Lab Runner

Primary GPU inference node (RTX 5090, 32GB VRAM). Runs containerized `ai-lab` GitHub Actions runner via `myoung34/github-runner`. Connected to tailnet as `pmoves-powerfulmoves`.

**Status (2026-03-15):** ONLINE — GPU passthrough operational (NVIDIA Container Toolkit 1.19.0). SoundCloud ingestion pipeline verified end-to-end. ffmpeg-whisper GPU transcription active.

| Service | Port | Status | Profile |
|---------|------|--------|---------|
| Ollama | 11434 | Ready | default |
| ffmpeg-whisper (GPU) | 8078 | Active | gpu |
| GPU Orchestrator | 8200 | Defined | gpu |
| Ultimate-TTS-Studio | 7861 | Defined | gpu |
| Channel Monitor | 8097 | Active | — |
| PMOVES.YT | 8077 | Active | yt |

### Z890 — Development (Local)

All services can run locally via Docker Compose profiles. Secondary GPU (RTX 3090 Ti). Self-hosted runner available as fallback.

---

## Route Flows

### Public Internet → Production Services

```
User (HTTPS)
  → Cloudflare DNS (pmoves.ai zone)
    → KVM2 nginx (SSL termination, reverse proxy)
      → KVM4-1 (API services: Agent Zero, TensorZero, Hi-RAG, etc.)
      → KVM4-2 (Grafana dashboard, search)
```

### GitHub CI/CD → Runner Routing

```
GitHub Push/PR Event
  → Cloudflare Worker (pmoves-ci-orchestrator)
    → Analyze changed files
      ├── GPU required? → AI Lab runner (Z890/5090)
      ├── Docker build? → VPS runner (kvm4)
      └── Lightweight?  → GitHub hosted (ubuntu-latest)
```

### LAN Development

```
Developer (Z890)
  → Docker Compose (all services locally)
  → Tailscale mesh → KVM nodes (for production testing)
```

### NATS Mesh (All Nodes)

```
All nodes interconnected via Tailscale overlay network.
NATS URL: nats://nats:pmoves@nats:4222

POWERFULMOVES ←→ Z890 ←→ KVM4-1 ←→ KVM4-2
                            ↕
                          KVM2
```

---

## DNS Subdomain Map (Cloudflare)

**Zone:** `pmoves.ai` (registered at Hostinger, NS delegated to Cloudflare)

| Subdomain | Record | Target | Proxy | Node | Protocol |
|-----------|--------|--------|-------|------|----------|
| `headscale.pmoves.ai` | A | KVM2 IP | DNS only | KVM2 | HTTPS (Tailscale) |
| `api.pmoves.ai` | A | KVM4-1 IP | Proxied | KVM4-1 | HTTPS |
| `ci.pmoves.ai` | CNAME | CF Worker | Proxied | Edge | HTTPS |
| `grafana.pmoves.ai` | A | KVM4-2 IP | Proxied | KVM4-2 | HTTPS |
| `n8n.pmoves.ai` | A | KVM4-1 IP | Proxied | KVM4-1 | HTTPS |
| `nats.pmoves.ai` | A | KVM4-2 IP | DNS only | KVM4-2 | TCP (4222) |
| `minio.pmoves.ai` | A | KVM4-2 IP | DNS only | KVM4-2 | HTTPS (9000) |
| `rag.pmoves.ai` | A | KVM4-1 IP | Proxied | KVM4-1 | HTTPS |
| `agent.pmoves.ai` | A | KVM4-1 IP | Proxied | KVM4-1 | HTTPS |
| `search.pmoves.ai` | A | KVM4-2 IP | Proxied | KVM4-2 | HTTPS |
| `tts.pmoves.ai` | A | Z890 IP | Proxied | Z890 (via Tailscale relay from KVM4-1) | HTTPS |

**Note:** NATS, MinIO, and Headscale use DNS-only (no Cloudflare proxy) because they use non-HTTP protocols or need direct TCP connections.

---

## Runner Fleet

| Runner | Labels | Node | Hardware | Role | Cost |
|--------|--------|------|----------|------|------|
| AI Lab (Linux) | `self-hosted, ai-lab, gpu, cuda` | POWERFULMOVES | RTX 5090, 64GB | GPU builds, CUDA, inference | $0 (electricity) |
| AI Lab (Windows) | `self-hosted, ai-lab, gpu, Windows` | POWERFULMOVES | RTX 5090, 64GB | Native Windows builds | $0 (electricity) |
| cloudstartup | `self-hosted, vps, cloudstartup, staging` | KVM4-1 | 8C / 16GB | Staging deploys, CPU builds | $10/mo |
| kvm4 | `self-hosted, vps, kvm4, production` | KVM4-1 | 8C / 16GB | Production deploys | (shared) |
| kvm2 | `self-hosted, vps, kvm2, backup` | KVM2 | 4C / 8GB | Overflow, backup | $10/mo |
| ubuntu-latest | GitHub-hosted | Cloud | 2C / 7GB | Lightweight (lint, tests, docs) | $0.008/min |

**Routing logic:** See `deploy/cloudflare/worker.js` for the full decision tree.

**Estimated savings:** 88% vs GitHub-hosted only (per `deploy/HYBRID_RUNNER_STRATEGY.md`).

---

## Docker Compose Profiles

| Profile | Services | Typical Node |
|---------|----------|-------------|
| `agents` | Agent Zero, Archon, Mesh Agent | KVM4-1, Z890 |
| `workers` | Extract, LangExtract, media analyzers | KVM4-1, Z890 |
| `orchestration` | SupaSerch, DeepResearch | KVM4-1, Z890 |
| `yt` | PMOVES.YT ingestion | Z890 |
| `gpu` | Hi-RAG GPU, Ollama, Ultimate-TTS | 5090, Z890 |
| `monitoring` | Prometheus, Grafana, Loki, Promtail | KVM4-2, Z890 |
| `supabase-local` | Full Supabase 13-service stack | KVM4-2, Z890 |
| `tier-agent` | Gateway Agent | KVM4-1 |

**Start services:**
```bash
docker compose --profile agents --profile workers up -d
```

---

## Docker Networks (Segmentation)

| Network | Purpose | Services |
|---------|---------|----------|
| `pmoves-net` | Default cross-service mesh | All services |
| `pmoves_api` | API tier isolation | Kong, PostgREST, Agent Zero, Gateway Agent |
| `pmoves_data` | Data tier isolation | PostgreSQL, internal Supabase stack |

---

## Deployment Order

1. **KVM4-2** (Data first — NATS, Supabase, Qdrant, Neo4j, Meilisearch, MinIO)
2. **KVM4-1** (API second — TensorZero, Agent Zero, Hi-RAG, Archon, Gateway Agent)
3. **KVM2** (Proxy last — nginx with upstream configs pointing to KVM4-1/KVM4-2)

**Script:** `deploy/scripts/deploy-vps.sh [kvm4-1|kvm4-2|kvm2|all|status]`

---

## Credential Flow

```
GitHub Secrets (source of truth)
  → sync-secrets-local.yml (workflow_dispatch) → .env.local
  → deploy-vps.sh → SSH → /opt/pmoves/.env.vps
  → Cloudflare Worker → wrangler secret put (manual)
```

Key secrets:
- `HOSTINGER_KVM4_1_IP`, `HOSTINGER_KVM4_2_IP`, `HOSTINGER_KVM2_IP` — VPS public IPs
- `HOSTINGER_API_KEY` — Hostinger API access
- `TAILSCALE_AUTHKEY` — Tailscale node join
- `WEBHOOK_SECRET` — GitHub → Cloudflare Worker verification
- `GITHUB_TOKEN` — Worker → GitHub API calls

---

## Blocked Items (Requires User Action)

| Item | Blocker | Depends On |
|------|---------|------------|
| ~~5090 Tailscale join~~ | — | **DONE** — dual entry: pmoves-powerfulmoves (Linux) + powerfulmoves-1 (Windows) |
| ~~4090 Laptop Tailscale~~ | — | **DONE** — pmoves-laptop connected |
| Jetson #1 Tailscale reinstall | RustDesk access needed to open terminal | User connects via RustDesk, runs `deploy.sh --role edge` |
| Jetson #2 Tailscale install | Same as #1 | User connects via RustDesk |
| JetPack update (both Jetsons) | Need to check current version first | `cat /etc/nv_tegra_release` via RustDesk terminal |
| GPU Docker passthrough | NVIDIA Container Toolkit on RTX 5090/WSL2 | Update toolkit to latest version |
| DNS records creation | pmoves.ai zone not in Cloudflare | User adds zone + updates NS at Hostinger |
| KVM public IPs | Not retrieved yet | Hostinger MCP or dashboard |
| Cloudflare Worker deploy | Config ready, needs manual `wrangler deploy` | Zone active |

---

## References

- `deploy/HYBRID_RUNNER_STRATEGY.md` — Full runner fleet documentation
- `deploy/cloudflare/worker.js` — CI orchestrator Worker code
- `deploy/cloudflare/wrangler.toml` — Worker configuration
- `deploy/scripts/deploy-vps.sh` — VPS deployment script
- `pmoves/docker-compose.vps.override.yml` — VPS compose overrides
- `pmoves/docs/operations/PORT_REGISTRY.md` — Port allocations
- `pmoves/config/agent_registry.yaml` — Full agent registry
- `pmoves/configs/agent-teams.yaml` — Agent team assignments
- `.claude/context/runner-topology.md` — Condensed topology for agent context
