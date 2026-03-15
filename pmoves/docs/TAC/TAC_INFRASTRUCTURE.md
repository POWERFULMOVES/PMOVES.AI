# TAC Tree: Infrastructure & Networking

> Technology-Architecture-Context tree for the PMOVES.AI infrastructure layer — mesh VPN, node topology, CI runner fleet, and DNS routing that enables all 62 agents to discover and communicate with each other.

## Service Identity

| Field | Value |
|-------|-------|
| **Team** | infra |
| **Agents** | mesh_agent, headscale, vps_fleet_manager |
| **Node Affinity** | kvm4-1, kvm2 (production); z890, powerfulmoves (dev) |
| **CI Runner** | vps (production); ai-lab (GPU) |
| **Tier** | api (cross-cutting) |
| **Class** | Utility |
| **Evolution** | Base (foundational, stable) |

## Node Topology

| Node | Tailscale Hostname | Role | GPU | Runner Labels |
|------|--------------------|------|-----|---------------|
| Z890 (Windows 11) | `100.113.38.37` | Dev, GPU | RTX 3090 Ti | `self-hosted, ai-lab, gpu, cuda` |
| POWERFULMOVES (Windows 11) | `pmoves-powerfulmoves` | Dev, GPU (secondary) | — | — |
| 5090 PC | (pending onboarding) | Primary GPU | RTX 5090 | (future: `ai-lab`) |
| KVM4-1 | `pmoves-kvm4-1` | API Gateway | — | `self-hosted, vps, kvm4, production` |
| KVM4-2 | `pmoves-kvm4-2` | Data / Storage | — | `self-hosted, vps, kvm4, production` |
| KVM2 | `pmoves-kvm2` | Exit Node / Proxy | — | `self-hosted, vps, kvm2, backup` |
| Cloudflare Edge | — | DNS, Worker routing | — | — |
| GitHub Cloud | — | Lightweight CI | — | `ubuntu-latest` |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| Docker Engine (all nodes) | Container runtime | Yes |
| NATS (4222) | Mesh node announcements | Yes |
| Tailscale Cloud / Headscale | VPN control plane | Yes |
| Cloudflare | DNS and edge routing | Yes (production) |
| Supabase (3010) | Node metadata storage | Optional |
| Prometheus (9090) | Metrics collection | Optional |

## Downstream Consumers

| Consumer | Dependency | Description |
|----------|-----------|-------------|
| All 62 agents | Tailscale mesh | Inter-node connectivity |
| Agent Zero (8080) | `mesh.node.announce.v1` | Host discovery via NATS |
| Model Registry | `mesh.gpu.model.*` | GPU model lifecycle events |
| CI/CD Workflows (19) | Runner fleet | Workflow execution |
| Grafana (3002) | Prometheus | Infrastructure dashboards |

## NATS Mesh Subjects

| Subject | Publisher | Direction | Interval |
|---------|-----------|-----------|----------|
| `mesh.node.announce.v1` | mesh_agent | Publishes | 15s heartbeat |
| `mesh.gpu.status.v1` | gpu-orchestrator | Publishes | 5s heartbeat |
| `mesh.gpu.model.loaded.v1` | gpu-orchestrator | Publishes | on-event |
| `mesh.gpu.model.unloaded.v1` | gpu-orchestrator | Publishes | on-event |
| `mesh.gpu.command.v1` | agent-zero | Publishes | on-demand |
| `mesh.gpu.command.result.v1` | gpu-orchestrator | Publishes | on-event |
| `model.registry.updated.v1` | model-registry | Publishes | on-event |

## Mesh Networking Audit

- [ ] All nodes reachable via Tailscale (`tailscale ping <hostname>`)
- [ ] POWERFULMOVES registered on tailnet (Docker userspace mode)
- [ ] Z890 registered on tailnet (bare-metal install)
- [ ] KVM2 advertising exit node (`--advertise-exit-node`)
- [ ] KVM4-1 and KVM4-2 accepting routes (`--accept-routes`)
- [ ] Magic DNS resolution working across all nodes
- [ ] Headscale self-hosted deployment planned (replaces Tailscale Cloud)

## CI Runner Fleet

| Runner | Label | Node | Mode | Start Command |
|--------|-------|------|------|---------------|
| ai-lab | `self-hosted, ai-lab` | Z890 | Docker container | `make ci-runners-local-cert-up` |
| cloudstartup | `self-hosted, cloudstartup` | KVM4-1 | Docker container | Provisioned via `hostinger-kvm-setup.sh` |
| kvm4 | `self-hosted, kvm4` | KVM4-2 | Docker container | Provisioned via `hostinger-kvm-setup.sh` |
| kvm2 | `self-hosted, kvm2` | KVM2 | Docker container | Provisioned via `hostinger-kvm-setup.sh` |

Runner management: `local_cert_runners.py` with `myoung34/github-runner` image.

## Submodule Alignment Checklist

| Submodule | Branch | CLAUDE.md | CHIT Stanza | .gitmodules |
|-----------|--------|-----------|-------------|-------------|
| PMOVES-Tailscale | PMOVES.AI-Edition-Hardened | Pending | Pending | Tracked |
| PMOVES-Headscale | PMOVES.AI-Edition-Hardened | Present | Pending | Tracked |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| Headscale not deployed (using Tailscale Cloud) | P2 | Planned |
| NATS mesh traffic unencrypted between nodes | P2 | Tracked (TLS planned) |
| Runner containers need cert rotation | P2 | Tracked |
| VPS provisioning scripts use reusable auth keys | P3 | Acceptable (tagged keys) |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| Mesh agent heartbeat | GREEN | 15s NATS announcements |
| Tailscale connectivity | Partial | Z890 + KVM nodes connected; POWERFULMOVES pending |
| Runner fleet | GREEN | 4 containerized runners via `local_cert_runners.py` |
| Prometheus scraping | GREEN | All `/metrics` endpoints configured |
| DNS zone | Partial | Registered at Hostinger; Cloudflare migration pending |
| VPN auth | GREEN | Tailscale Cloud manages auth keys |

## Make Targets

| Target | Description |
|--------|-------------|
| `make -C pmoves tailscale-docker-up` | Start Tailscale Docker container and join tailnet |
| `make -C pmoves tailscale-docker-down` | Stop Tailscale Docker container |
| `make -C pmoves tailscale-docker-status` | Show Tailscale Docker container connection status |
| `make -C pmoves tailscale-docker-ip` | Show Tailscale Docker container's IP |
| `make ci-runners-local-cert-up` | Start Docker-containerized CI runners |

## Cross-Links

- **Master Topology:** `pmoves/docs/operations/TOPOLOGY.md`
- **Runner Map:** `pmoves/docs/operations/WORKFLOW_RUNNER_MAP.md`
- **Runner Strategy:** `deploy/HYBRID_RUNNER_STRATEGY.md`
- **Provisioning:** `deploy/provision/hostinger-kvm-setup.sh`
- **Agent Teams:** `pmoves/configs/agent-teams.yaml` → `infra`
- **Agent Registry:** `pmoves/config/agent_registry.yaml`
- **Tailscale TAC:** [`TAC_TAILSCALE.md`](./TAC_TAILSCALE.md)
- **Runners TAC:** [`TAC_RUNNERS.md`](./TAC_RUNNERS.md)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)

## Open Items

- Register POWERFULMOVES on tailnet (Docker userspace mode)
- Deploy Headscale self-hosted (replaces Tailscale Cloud console)
- 5090 node onboarding (blocked on Tailscale + OpenSSH setup)
- Runner certificate rotation automation
- NATS TLS between nodes (P2 security finding)
- Network segmentation per node tier

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-INFRA::2026-03-15 -->
