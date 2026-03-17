# TAC Tree: CI/CD Runner Fleet

> Technology-Architecture-Context tree for the PMOVES.AI CI/CD runner infrastructure — containerized GitHub Actions runners, workflow-to-runner routing, phase policy, and certificate management.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | GitHub Actions Self-Hosted Runners |
| **Management Tool** | `local_cert_runners.py` |
| **Runner Image** | `myoung34/github-runner` |
| **Ports** | — (outbound HTTPS to GitHub only) |
| **Health** | Runner registration status via `gh api` |
| **Metrics** | Container health via cAdvisor (8080) |
| **Tier** | api (cross-cutting) |
| **Class** | Utility |
| **Evolution** | Base |

## Runner Fleet

| Runner | Labels | Node | vCPU / RAM | Restart Policy |
|--------|--------|------|------------|----------------|
| ai-lab | `self-hosted, ai-lab, gpu, cuda` | Z890 | 32C / 128GB | `unless-stopped` |
| cloudstartup | `self-hosted, cloudstartup` | KVM4-1 | 8C / 16GB | `unless-stopped` |
| kvm4 | `self-hosted, kvm4, production` | KVM4-2 | 8C / 16GB | `unless-stopped` |
| kvm2 | `self-hosted, kvm2, backup` | KVM2 | 4C / 8GB | `unless-stopped` |
| (GitHub hosted) | `ubuntu-latest` | GitHub Cloud | 2C / 7GB | — |

**Management:** `make ci-runners-local-cert-up` starts Docker-containerized Linux runners. Containers auto-restart via `unless-stopped` policy.

## Workflow-to-Runner Map

19 GitHub Actions workflows mapped to runners (from `WORKFLOW_RUNNER_MAP.md`):

| Category | Workflows | Primary Runner | Fallback |
|----------|-----------|----------------|----------|
| GPU builds | Docker multi-arch, model training | `ai-lab` | — |
| Docker builds | Service images, Dockerfile lint | `kvm4` | `cloudstartup` |
| Tests | Python tests, smoke tests, CodeQL | `cloudstartup` | `ubuntu-latest` |
| Docs/Lint | SQL lint, CHIT contract check | `ubuntu-latest` | — |
| Deploy | Production deploy, secrets sync | `kvm4` | `kvm2` |

**Routing logic:** Cloudflare Worker (`deploy/cloudflare/worker.js`) analyzes changed files to select appropriate runner.

## Runner Phase Policy

**File:** `runner_phase_policy.json`

Defines which runner labels are allowed per deployment phase:

| Phase | Allowed Labels | Purpose |
|-------|---------------|---------|
| `local-certification` | `ai-lab` | Local Docker container runners (both on Z890) |
| `staging` | `cloudstartup`, `kvm4` | VPS runners for staging validation |
| `production` | `kvm4`, `kvm2` | Production deployment runners |
| `lightweight` | `ubuntu-latest` | GitHub-hosted for non-sensitive tasks |

## Runner Configuration

**Lane hosts:** `lane_hosts.json` defines containerized topology:

```json
{
  "ai-lab": {"host": "localhost", "type": "docker-container"},
  "cloudstartup": {"host": "kvm4-1.internal", "type": "docker-container"},
  "kvm4": {"host": "kvm4-2.internal", "type": "docker-container"},
  "kvm2": {"host": "kvm2.internal", "type": "docker-container"}
}
```

## Docker-in-Docker Security

| Concern | Mitigation |
|---------|-----------|
| Container escape | Runners use `--security-opt=no-new-privileges` |
| Volume access | Bind-mounted work directories only |
| Network access | Host network for Tailscale connectivity |
| Secrets exposure | GitHub Actions secrets injected at runtime, not stored |
| Image trust | `myoung34/github-runner` from Docker Hub (verified publisher) |

## Certificate Management

| Certificate | Location | Rotation | Status |
|-------------|----------|----------|--------|
| Runner registration token | GitHub API | Per-registration | Auto |
| GitHub PAT (for runner API) | `env.shared` | Manual (90 day) | Tracked |
| TLS certs (VPS nodes) | Let's Encrypt on KVM2 | Auto-renewal (certbot) | GREEN |
| Docker TLS | Docker daemon | Manual | Tracked |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| GitHub API | Runner registration, workflow dispatch | Yes |
| Docker Engine | Container runtime for runners | Yes |
| Tailscale mesh | Inter-node connectivity for distributed runners | Yes |
| `local_cert_runners.py` | Runner lifecycle management | Yes |
| `myoung34/github-runner` | Runner container image | Yes |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| All runners online | Partial | 3/4 online after `make ci-runners-local-cert-up`; KVM runners need VPS access |
| Runner labels match workflows | GREEN | Validated via `runner_phase_policy.json` |
| Docker-in-Docker security | Partial | `no-new-privileges` set; full audit pending |
| Certificate rotation | Partial | Let's Encrypt auto-renews; Docker TLS manual |
| Monitoring | GREEN | cAdvisor + Prometheus scraping container metrics |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| Runner containers run as root | P2 | Tracked — `myoung34` image requires root for Docker socket |
| `apt-get` needs `sudo` on self-hosted runners | P3 | Documented — non-root runners can't install system deps |
| Docker Bench CI fails on Windows runner | P3 | Fixed (PR #846) — `if: runner.os == 'Linux'` guard |
| GitHub PAT rotation not automated | P3 | Tracked |

## Cross-Links

- **Infrastructure TAC:** [`TAC_INFRASTRUCTURE.md`](./TAC_INFRASTRUCTURE.md)
- **Workflow Runner Map:** `pmoves/docs/operations/WORKFLOW_RUNNER_MAP.md`
- **Hybrid Runner Strategy:** `deploy/HYBRID_RUNNER_STRATEGY.md`
- **Runner Topology:** `.claude/context/runner-topology.md`
- **Lane Hosts Config:** `lane_hosts.json`
- **Phase Policy:** `runner_phase_policy.json`
- **Local Runner Script:** `local_cert_runners.py`
- **VPS Provisioning:** `deploy/provision/hostinger-kvm-setup.sh`

## Open Items

- Automate GitHub PAT rotation (currently manual 90-day cycle)
- Non-root runner image evaluation (security improvement)
- Runner health monitoring via NATS (currently no NATS integration)
- KVM runner cert rotation automation
- Runner auto-scaling for burst CI load (currently fixed fleet)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-RUNNERS::2026-03-15 -->
