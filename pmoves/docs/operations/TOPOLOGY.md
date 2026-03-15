# PMOVES.AI Master Topology

> Single source of truth for all physical/virtual nodes, service assignments, agent teams, route flows, and runner strategy.
>
> Last updated: 2026-03-14

---

## Node Inventory

| Node | LAN IP | Tailscale Hostname | Public IP | Role | Runner Labels | vCPU / RAM | Cost |
|------|--------|--------------------|-----------|------|---------------|------------|------|
| Z890 (Windows 11) | 192.168.1.92 / .94 | 100.113.38.37 | — | Dev, GPU (RTX 3090 Ti) | `self-hosted, ai-lab, gpu, cuda` | 32C / 128GB | electricity |
| 5090 PC | 192.168.1.65 / .66 | (pending onboarding) | — | Primary GPU (RTX 5090) | (future: `ai-lab`) | TBD | electricity |
| KVM4-1 | — | pmoves-kvm4-1 | Hostinger (TBD) | API Gateway | `self-hosted, vps, kvm4, production` | 8C / 16GB | $10/mo |
| KVM4-2 | — | pmoves-kvm4-2 | Hostinger (TBD) | Data / Storage | `self-hosted, vps, kvm4, production` | 8C / 16GB | $10/mo |
| KVM2 | — | pmoves-kvm2 | Hostinger (TBD) | Exit Node / Proxy | `self-hosted, vps, kvm2, backup` | 4C / 8GB | $10/mo |
| Cloudflare Edge | — | — | Anycast | DNS, Worker routing | — | Edge | Free plan |
| GitHub Cloud | — | — | — | Lightweight CI | `ubuntu-latest` | 2C / 7GB | $0.008/min |

**Total VPS cost:** $30/mo + electricity for local nodes.

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

### KVM2 — Exit Node / Reverse Proxy

| Service | Port | Health | Notes |
|---------|------|--------|-------|
| nginx | 80 / 443 | `nginx -t` | SSL termination via Let's Encrypt |

### Z890 — Development (Local)

All services can run locally via Docker Compose profiles. Primary use: development, GPU inference (3090 Ti), self-hosted GitHub Actions runner (`ai-lab`).

### 5090 PC — Primary GPU (Pending)

Future primary inference node. Blocked on: Tailscale onboarding, OpenSSH setup.

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

Z890 ←→ KVM4-1 ←→ KVM4-2
  ↕         ↕
5090      KVM2
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
| AI Lab | `self-hosted, ai-lab, gpu, cuda` | Z890 (→ 5090) | RTX 3090Ti/5090, 128GB | GPU builds, CUDA, inference | $0 (electricity) |
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
| 5090 Tailscale join | OpenSSH not installed on 5090 | User installs OpenSSH |
| DNS records creation | pmoves.ai zone not in Cloudflare | User adds zone + updates NS at Hostinger |
| KVM public IPs | Not retrieved yet | Hostinger MCP or dashboard |
| Cloudflare Worker deploy | Config ready, needs manual `wrangler deploy` | Zone active |
| Hostinger MCP | `HOSTINGER_API_KEY` not local | Run `sync-secrets-local.yml` or copy manually |

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
