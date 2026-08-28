# Runner & Topology Context (Condensed)

> Quick-reference for agents. Full details: `pmoves/docs/operations/TOPOLOGY.md`
> "Runner" means TWO fabrics — keep them distinct:
> **(A) CI runner fabric** — GitHub Actions self-hosted runners executing workflows.
> **(B) Model runner fabric** — inference endpoints (Ollama / llama.cpp / vLLM) that agents execute against, routed by TensorZero and announced via `mesh.node.announce.v1` → `node-registry` (:8115, Supabase-backed).

## Nodes

| Node | Role | Key Services | CI Runner | Model Runner |
|------|------|-------------|-----------|--------------|
| **B850 "Knuckles"** | Primary dev host (Claude Code shell) + heavyweight ROCm inference; 9850X3D / dual AMD R9700 (RDNA4 gfx1201) 64GB VRAM / ROCm 7.1 / Ubuntu 24.04 / hostname `pmoves-b850-ai-top` | All (local Docker Compose; data tier live) | `self-hosted, ai-lab` (target: `+gpu, rocm, rdna4`) | `llama-server` :8090 (llama.cpp-HIP fork `tlee933/llama.cpp-rdna4-gfx1201` — stock Ollama lacks gfx1201 kernels) + Ollama :11434 |
| **SPARK (DGX GB10)** | ARM64 CI + 70B+/NVFP4 inference; Grace-Blackwell 128GB unified; only NVFP4-capable node | Agent Zero sidecar, shape-worker | `pmoves-spark-runner`: `self-hosted, spark, Linux, ARM64` at `/opt/actions-runner-spark` | Ollama ARM64-CUDA :11434 (`ollama_spark` TZ provider) |
| **Z890** | Windows workstation, ai-lab lane (GTX 1650 4GB per 2026-06-04 live scan — earlier "3090 Ti" spec was wrong) | Local Docker Compose | `self-hosted, ai-lab, gpu, cuda` | hermes3:8b-class small models only |
| **5090** | Primary GPU (pending standup) | Future inference | (pending) | (pending) |
| **4090 Laptop (PMOVES-4090)** | Mobile relay / PR triage; Claude Code dev shell | Docker Desktop (WSL2) | `pmoves-ai-lab-win`: `self-hosted, X64, ai-lab, Windows, 4090` (native) + `pmoves-4090-runner-*`: `self-hosted, ai-lab, Linux, X64` (2× containers via `make gha-runner-4090-up`) | Ollama Cloud backend (no heavy local VRAM budget) |
| **KVM4-1** | API Gateway + Tailscale Egress Exit Node (Phase 9Q) | TensorZero, Agent Zero, Hi-RAG, Archon, Gateway Agent (:8111) | `self-hosted, vps, kvm4, production` | TensorZero routing plane |
| **KVM4-2** | Data/Storage | Supabase, NATS, Qdrant, Neo4j, Meilisearch, MinIO, monitoring | `self-hosted, vps, kvm4, production` | — |
| **KVM2** | Reverse Proxy / RustDesk Relay | nginx (SSL), RustDesk hbbs/hbbr | `self-hosted, vps, kvm2, backup` | — |
| **cloudstartup** | Staging deploys | staging stack | `self-hosted, cloudstartup, staging` | — |
| **Cloudflare** | Edge — DNS, tunnel, R2, CI-orchestration Worker (build ROUTING only, not execution; `ci.pmoves.ai` routes currently commented out in `wrangler.toml`) | `pmoves-ci-orchestrator` Worker | — | Workers AI = **planned** fallback inference tier, not wired |

**Container-managed CI lanes** (`pmoves/tools/local_cert_runners.py`, `myoung34/github-runner` images, `RUNNER_ALLOW_RUNNER_REUSE=true`): `pmoves-ai-lab-runner` (ai-lab,gpu), `pmoves-vps-runner` (vps), `pmoves-hotfix-runner` (hotfix). Token cascade: `GITHUB_PAT` → `gh auth token` (never `GH_PAT_PUBLISH` — wrong scope).

**4090 Docker Runner Prerequisites** (for `make gha-runner-4090-up`):
1. `docker login` — Docker Hub auth required to pull `myoung34/github-runner:ubuntu-jammy`
2. Docker Desktop → Settings → Resources → Network → **Use system DNS** — enables Tailscale MagicDNS hostname resolution from containers (`pmoves-kvm4-2`, etc.); required for `NATS_URL_TAILNET` in `branch-trail-emit.yml`
3. Token source (resolved automatically in order):
   - `GITHUB_PAT` from `env.tier-agent` (run `make secrets-funnel` to populate) — correct `repo` scope
   - `gh auth token` fallback — works on any machine with `gh auth status` logged in
   - **Do not** use `GH_PAT_PUBLISH` (GHCR `packages:write` scope only — wrong for runner registration)
4. Validate all three with: `make -C pmoves gha-runner-4090-preflight`

**Phase 9Q — YT egress routing (2026-04-16, PR #1262):** `pmoves-yt`,
`bgutil-pot-provider`, `invidious-companion`, and `invidious` route all
outbound HTTP/HTTPS through a Tailscale sidecar (`tailscale-yt-egress`)
configured with `--exit-node=pmoves-kvm4-1`. See
`pmoves/docs/operations/YT_EGRESS_RUNBOOK.md` for activation/rollback.
The egress path is transparent to event consumers — no new NATS subjects
are introduced. See `.claude/context/nats-subjects.md` for the subject
catalog; `ingest.*.v1` flows through normally when egress is active.

## Model runner announcement plane

```text
node (mesh-agent) → mesh.node.announce.v1 (15s heartbeat) → node-registry :8115 → Supabase
                                                            (REST: POST /api/v1/nodes/query — requires_gpu/min_tier/online_only)
Model catalog: model-registry :8110 (Supabase; signed candidates via /api/model-candidates)
GPU lifecycle: gpu-orchestrator :8200 (load/unload/optimize, VRAM tracking, ollama+vllm clients)
Routing: TensorZero :3030 (cloud coding plans = orchestrator tier; local siblings = worker tier)
```

## Route: Public → Services

```text
Internet → Cloudflare DNS → KVM2 (nginx/SSL) → KVM4-1 (API) or KVM4-2 (data)
```

## Route: CI/CD

```text
GitHub event → CF Worker (analyzes files; routes only, execution stays on runners)
            → ai-lab (GPU) / vps (Docker) / hotfix / spark (ARM64) / cloudstartup (staging) / ubuntu-latest (light)
```

## Agent Teams (13 teams, 91 agents)

_Counts are authoritative from `pmoves/config/agent_registry.yaml` ↔ `pmoves/configs/agent-teams.yaml` (enforced by the pydantic gate `make -C pmoves validate-agents`). Regenerate after roster changes._

| Team | Node Affinity | CI Runner | Count |
|------|--------------|-----------|-------|
| orchestration | kvm4-1, z890, powerfulmoves | ai-lab | 12 |
| research | kvm4-1, kvm4-2, z890 | vps | 11 |
| media | powerfulmoves, z890 | ai-lab | 16 |
| data | kvm4-2, z890 | vps | 9 |
| ui | z890, powerfulmoves | ubuntu-latest | 6 |
| automation | kvm4-1, z890 | vps | 7 |
| evolution | powerfulmoves, z890 | ai-lab | 5 |
| infra | kvm4-1, kvm2, jetson | vps | 5 |
| sandbox | cloud | ubuntu-latest | 8 |
| observability | kvm4-1, z890 | ai-lab | 5 |
| life | z890 | ubuntu-latest | 2 |
| **fordham_community** | kvm4-1, kvm4-2, kvm2, z890, powerfulmoves | vps | 5 |
| external | N/A (CLI) | N/A | 0 agents (human + dev-agent contributors) |

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
| `ci.pmoves.ai` | CF Worker | Yes (routes commented out in `wrangler.toml` — coded, not confirmed live) |

## Key Files

- `pmoves/configs/agent-teams.yaml` — Team definitions
- `pmoves/config/agent_registry.yaml` — Full agent registry
- `pmoves/tools/local_cert_runners.py` — Container CI lanes (ai-lab/vps/hotfix)
- `deploy/cloudflare/worker.js` — CI routing logic
- `deploy/scripts/deploy-vps.sh` — VPS deployment
- `pmoves/docs/operations/WORKFLOW_RUNNER_MAP.md` — All 19 workflows mapped
- `pmoves/docs/infrastructure/DISTRIBUTED_COMPUTE_SERVICES.md` — node-registry / distributed compute
