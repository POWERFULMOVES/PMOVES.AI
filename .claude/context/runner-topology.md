# Runner & Topology Context (Condensed)

> Quick-reference for agents. Full details: `pmoves/docs/operations/TOPOLOGY.md`

## Nodes

| Node | Role | Key Services | Runner |
|------|------|-------------|--------|
| **Z890** | Dev + GPU (3090Ti) | All (local Docker Compose) | `ai-lab, gpu, cuda` |
| **5090** | Primary GPU (pending) | Future inference | (pending) |
| **KVM4-1** | API Gateway | TensorZero, Agent Zero, Hi-RAG, Archon, Gateway Agent | `kvm4, production` |
| **KVM4-2** | Data/Storage | Supabase, NATS, Qdrant, Neo4j, Meilisearch, MinIO, monitoring | `kvm4, production` |
| **KVM2** | Exit Node | nginx (SSL termination) | `kvm2, backup` |
| **Cloudflare** | Edge | DNS, CI Worker | — |

## Route: Public → Services

```
Internet → Cloudflare DNS → KVM2 (nginx/SSL) → KVM4-1 (API) or KVM4-2 (data)
```

## Route: CI/CD

```
GitHub event → CF Worker (analyzes files) → ai-lab (GPU) / vps (Docker) / ubuntu-latest (light)
```

## Agent Teams (11 teams, 61 agents)

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
- `pmoves/config/agent_registry.yaml` — Full 61-agent registry
- `deploy/cloudflare/worker.js` — CI routing logic
- `deploy/scripts/deploy-vps.sh` — VPS deployment
- `pmoves/docs/operations/WORKFLOW_RUNNER_MAP.md` — All 19 workflows mapped
