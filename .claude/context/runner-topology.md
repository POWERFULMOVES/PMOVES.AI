# Runner & Topology Context (Condensed)

> Quick-reference for agents. Full details: `pmoves/docs/operations/TOPOLOGY.md`

## Nodes

| Node | Role | Key Services | Runner |
|------|------|-------------|--------|
| **Z890** | Production ai-lab node, GPU (RTX 3090 Ti); workstation co-located with dev workflow | All (local Docker Compose) | `self-hosted, ai-lab, gpu, cuda` |
| **B850 "Knuckles"** (= R9700 Workstation pre-Phase-C) | Heavyweight ROCm Inference target; **current state: 9850X3D / 32GB / 1× R9700 / Ubuntu 24.04.4 / /dev/kfd present / hostname `pmoves-b850-ai-top`**. Hosts the Claude Code dev shell. | All (local Docker Compose, ROCm install operator-pending) | `self-hosted, ai-lab` (target: `+gpu, rocm, rdna4`) |
| **5090** | Primary GPU (pending) | Future inference | (pending) |
| **KVM4-1** | API Gateway + Tailscale Egress Exit Node (Phase 9Q) | TensorZero, Agent Zero, Hi-RAG, Archon, Gateway Agent; outbound exit for `pmoves-yt` stack | `self-hosted, vps, kvm4, production` |
| **KVM4-2** | Data/Storage | Supabase, NATS, Qdrant, Neo4j, Meilisearch, MinIO, monitoring | `self-hosted, vps, kvm4, production` |
| **KVM2** | Reverse Proxy / RustDesk Relay | nginx (SSL termination), RustDesk hbbs/hbbr | `self-hosted, vps, kvm2, backup` |
| **Cloudflare** | Edge | DNS, CI Worker | — |

**Phase 9Q — YT egress routing (2026-04-16, PR #1262):** `pmoves-yt`,
`bgutil-pot-provider`, `invidious-companion`, and `invidious` route all
outbound HTTP/HTTPS through a Tailscale sidecar (`tailscale-yt-egress`)
configured with `--exit-node=pmoves-kvm4-1`. See
`pmoves/docs/operations/YT_EGRESS_RUNBOOK.md` for activation/rollback.
The egress path is transparent to event consumers — no new NATS subjects
are introduced. See `.claude/context/nats-subjects.md` for the subject
catalog; `ingest.*.v1` flows through normally when egress is active.

## Route: Public → Services

```text
Internet → Cloudflare DNS → KVM2 (nginx/SSL) → KVM4-1 (API) or KVM4-2 (data)
```

## Route: CI/CD

```text
GitHub event → CF Worker (analyzes files) → ai-lab (GPU) / vps (Docker) / ubuntu-latest (light)
```

## Agent Teams (11 teams, 62 agents)

| Team | Node Affinity | CI Runner | Count |
|------|--------------|-----------|-------|
| orchestration | kvm4-1, z890, 5090 | ai-lab | 6 |
| research | kvm4-1, kvm4-2, z890 | vps | 9 |
| media | 5090, z890 | ai-lab | 11 |
| data | kvm4-2, z890 | vps | 9 |
| ui | z890, 5090 | ubuntu-latest | 6 |
| automation | kvm4-1, z890 | vps | 4 |
| evolution | 5090, z890 | ai-lab | 4 |
| infra | kvm4-1, kvm2 | vps | 3 |
| sandbox | cloud | ubuntu-latest | 7 |
| life | z890 | ubuntu-latest | 2 |
| external | N/A (CLI) | N/A | 0 agents (7 human contributors) |

## DNS Subdomains (pmoves.ai)

| Subdomain | Target Node | Proxy |
|-----------|------------|-------|
| `api.pmoves.ai` | KVM4-1 | Yes |
| `agent.pmoves.ai` | KVM4-1 | Yes |
| `rag.pmoves.ai` | KVM4-1 | Yes |
| `tts.pmoves.ai` | Z890 (via Tailscale relay) | Yes |
| `n8n.pmoves.ai` | KVM4-1 | Yes |
| `grafana.pmoves.ai` | KVM4-2 | Yes |
| `search.pmoves.ai` | KVM4-2 | Yes |
| `nats.pmoves.ai` | KVM4-2 | DNS only |
| `minio.pmoves.ai` | KVM4-2 | DNS only |
| `headscale.pmoves.ai` | KVM2 | DNS only |
| `ci.pmoves.ai` | CF Worker | Yes |

## Key Files

- `pmoves/configs/agent-teams.yaml` — Team definitions
- `pmoves/config/agent_registry.yaml` — Full agent registry
- `deploy/cloudflare/worker.js` — CI routing logic
- `deploy/scripts/deploy-vps.sh` — VPS deployment
- `pmoves/docs/operations/WORKFLOW_RUNNER_MAP.md` — All 19 workflows mapped
