# PMOVES.AI Hybrid Runner Strategy

**Status**: Production-ready
**Last Updated**: 2025-12-08

## Executive Summary

PMOVES.AI uses a **hybrid runner strategy** combining self-hosted infrastructure with cloud runners and Cloudflare Workers orchestration to achieve:

- **88% cost savings** vs GitHub-hosted only (~$35/mo vs $300/mo)
- **GPU-accelerated builds** (CUDA, model inference) via AI Lab
- **Zero-downtime deployments** to staging/production VPS environments
- **Intelligent routing** via Cloudflare edge workers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Repository                         │
│                     (Push/PR Event)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Worker (Edge)                        │
│  • Receives webhook                                          │
│  • Analyzes changed files                                    │
│  • Determines requirements (GPU/Docker/lightweight)          │
│  • Routes to optimal runner                                  │
│  • Tracks build state in KV                                  │
│  • Sends notifications                                       │
└────────┬────────────────┬───────────────┬────────────────────┘
         │                │               │
         │                │               │
    ┌────▼─────┐    ┌─────▼──────┐  ┌────▼────────┐
    │ AI Lab   │    │ VPS Fleet  │  │ GitHub      │
    │ (GPU)    │    │ (CPU)      │  │ Hosted      │
    └──────────┘    └────────────┘  └─────────────┘
    • RTX 5090       • cloudstartup   • ubuntu-latest
    • CUDA builds    • kvm4 (prod)    • Lightweight
    • Hi-RAG GPU     • kvm2 (backup)  • No cache req
    • Ollama         • Docker cache   • Fast spin-up
                     • Deployments
```

## Runner Fleet

### Self-Hosted Infrastructure

| Runner | Labels | Role | Hardware | Monthly Cost |
|--------|--------|------|----------|-------------|
| **AI Lab** | `self-hosted, ai-lab, gpu, cuda` | GPU builds, model inference | RTX 5090/4090/3090Ti, 128GB RAM | $0 (electricity ~$20) |
| **cloudstartup** | `self-hosted, vps, cloudstartup, staging` | Staging deploys, CPU builds | 8 vCPU, 16GB RAM, Hostinger VPS | $10/mo |
| **kvm4** | `self-hosted, vps, kvm4, production` | Production deploys | 8 vCPU, 16GB RAM, Hostinger VPS | $10/mo |
| **kvm2** | `self-hosted, vps, kvm2, backup` | Overflow/backup | 4 vCPU, 8GB RAM, Hostinger VPS | $10/mo |

**Self-hosted Total**: $30/mo (VPS) + electricity

### Cloud Infrastructure

| Runner | Labels | Role | Cost |
|--------|--------|------|------|
| **GitHub hosted** | `ubuntu-latest` | Lightweight tasks, fallback | $0.008/min (~$0.05-0.20/build) |
| **Cloudflare Workers** | N/A (orchestration only) | Webhook handler, routing logic | $0 (free tier: 100K req/day) |

## Decision Matrix

### When to Use Each Runner Type

#### 1. AI Lab (Self-Hosted GPU) ← **GPU Required**

**Use for**:
- Ollama CUDA builds (`services/ollama/Dockerfile.cuda`)
- Hi-RAG GPU builds (`services/hirag-gateway/Dockerfile.gpu`)
- Model fine-tuning, inference testing
- Any workflow with `gpu-build` label

**Workflow example**:
```yaml
jobs:
  build-gpu:
    runs-on: [self-hosted, ai-lab, gpu]
    steps:
      - name: Verify GPU
        run: nvidia-smi
      - name: Build CUDA image
        run: docker build -f Dockerfile.cuda .
```

**Why self-hosted**:
- GitHub Actions doesn't provide GPU runners
- ~$12/run on cloud GPU services (AWS g4dn.xlarge)
- AI Lab provides $0 cost + faster builds (local cache)

**Average build time**: 20-30 minutes (CUDA compilation)

---

#### 2. VPS Fleet (Self-Hosted CPU) ← **Docker Builds, Deployments**

**Use for**:
- Multi-stage Docker builds with layer cache
- Service deployments to staging/production
- Integration tests requiring database access
- Long-running builds (>10 minutes)

**Workflow example**:
```yaml
jobs:
  build-cpu:
    runs-on: [self-hosted, vps]
    steps:
      - name: Build Docker image
        run: docker build -t pmoves-agent-zero .
```

**Why self-hosted**:
- Persistent Docker layer cache (5-10x faster rebuilds)
- Direct access to deployment environments
- No egress costs for large images
- Fixed VPS cost vs per-minute GitHub billing

**Average build time**: 5-15 minutes (with cache)

---

#### 3. GitHub Hosted ← **Lightweight, No Cache Benefit**

**Use for**:
- Linting, formatting checks
- Documentation builds (Markdown → HTML)
- Unit tests (<2 minutes)
- JSON schema validation
- SQL policy linting
- Workflows without Docker or GPU

**Workflow example**:
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Lint Python
        run: ruff check .
```

**Why GitHub hosted**:
- Faster startup (<30s vs 2-3min self-hosted)
- No cache advantage for single-file tasks
- Cheaper than idle self-hosted runner for infrequent tasks
- No maintenance burden

**Average build time**: 1-3 minutes

**Cost**: $0.008/min × 2min = $0.016/build

---

#### 4. Cloudflare Workers ← **Orchestration, Not Execution**

**Use for**:
- GitHub webhook ingestion
- Build metadata tracking (KV storage)
- Runner selection logic (analyze commits → route to optimal runner)
- Discord notifications
- Cost analytics

**Why Cloudflare**:
- Edge deployment (ultra-low latency)
- Free tier covers 100% of PMOVES.AI traffic
- Global availability (99.99% uptime SLA)
- No cold starts

**Important**: Cloudflare Workers **cannot** run GitHub Actions jobs directly. They orchestrate and monitor builds, not execute them.

---

## Routing Logic

### Implemented in Cloudflare Worker

```javascript
function determineRunnerStrategy(changedFiles) {
  // 1. GPU requirement check
  if (changedFiles.some(f =>
      f.includes('ollama') ||
      f.includes('Dockerfile.cuda') ||
      f.includes('Dockerfile.gpu'))) {
    return { runner: 'ai-lab', labels: ['self-hosted', 'ai-lab', 'gpu'] };
  }

  // 2. Docker build with cache benefit
  if (changedFiles.some(f =>
      f.includes('Dockerfile') ||
      f.startsWith('pmoves/services/'))) {
    return { runner: 'vps', labels: ['self-hosted', 'vps'] };
  }

  // 3. Deployment to specific environment
  if (branch === 'develop') {
    return { runner: 'cloudstartup', labels: ['self-hosted', 'cloudstartup', 'staging'] };
  }
  if (branch === 'main') {
    return { runner: 'kvm4', labels: ['self-hosted', 'kvm4', 'production'] };
  }

  // 4. Lightweight tasks (docs, lint, tests)
  if (changedFiles.every(f =>
      f.endsWith('.md') ||
      f.includes('docs/') ||
      f.includes('.github/'))) {
    return { runner: 'ubuntu-latest', labels: ['ubuntu-latest'] };
  }

  // 5. Default to VPS (safe fallback)
  return { runner: 'vps', labels: ['self-hosted', 'vps'] };
}
```

### Routing Examples

| Commit | Changed Files | Analysis | Runner | Reason |
|--------|--------------|----------|--------|--------|
| `feat(ollama)` | `services/ollama/Dockerfile.cuda` | GPU required | **ai-lab** | CUDA compilation |
| `fix(agent-zero)` | `services/agent-zero/Dockerfile` | Docker build | **vps** | Layer cache benefit |
| `docs: update README` | `README.md`, `docs/*.md` | Lightweight | **ubuntu-latest** | No cache, fast spin-up |
| `ci: update workflows` | `.github/workflows/*.yml` | CI config | **ubuntu-latest** | No build artifacts |
| Push to `main` | `(any)` | Production deploy | **kvm4** | Target environment |
| Push to `develop` | `(any)` | Staging deploy | **cloudstartup** | Target environment |

## Cost Optimization Strategies

### 1. Persistent Docker Cache

**Problem**: Rebuilding Docker images from scratch is expensive (time + CPU).

**Solution**: Self-hosted VPS runners maintain layer cache.

**Savings**:
- First build: 15 minutes
- Subsequent builds: 2-3 minutes (5x faster)
- Cost: $0 (vs $0.12 GitHub hosted per rebuild)

### 2. GPU Workload Localization

**Problem**: Cloud GPU instances cost $1-2/hour minimum.

**Solution**: AI Lab provides dedicated GPU hardware.

**Savings**:
- AWS g4dn.xlarge: $0.526/hour × 0.5hr = $0.26/build
- AI Lab: $0/build (electricity only)
- 50 GPU builds/month: **$13/mo savings**

### 3. Intelligent Fallback

**Problem**: Self-hosted runners may be busy or offline.

**Solution**: Cloudflare Worker detects runner availability, falls back to GitHub hosted.

**Implementation**:
```yaml
jobs:
  build:
    runs-on: [self-hosted, vps]
    timeout-minutes: 5  # If no runner available
    continue-on-error: true

  build-fallback:
    runs-on: ubuntu-latest
    needs: build
    if: failure()  # Trigger if self-hosted unavailable
```

### 4. Scheduled Cleanup

**Problem**: Docker disk usage grows over time on VPS.

**Solution**: Weekly cron job prunes unused images/volumes.

```bash
# /etc/cron.weekly/docker-prune
docker system prune -af --volumes
docker builder prune -af
```

**Savings**: Prevents runner failures, reduces manual intervention.

## Failover Patterns

### Pattern 1: Primary + Backup Runners

```yaml
jobs:
  build-primary:
    runs-on: [self-hosted, vps]
    timeout-minutes: 5

  build-backup:
    runs-on: [self-hosted, kvm2, backup]
    needs: build-primary
    if: failure()
```

**Use case**: Primary VPS runner is busy/offline.

### Pattern 2: Self-Hosted → GitHub Hosted Fallback

```yaml
jobs:
  build-self-hosted:
    runs-on: [self-hosted, vps]
    timeout-minutes: 5

  build-github:
    runs-on: ubuntu-latest
    needs: build-self-hosted
    if: failure()
```

**Use case**: All self-hosted runners unavailable (network outage).

### Pattern 3: Environment-Specific + Cloud Fallback

```yaml
jobs:
  deploy-prod:
    runs-on: [self-hosted, kvm4, production]
    timeout-minutes: 10

  deploy-remote:
    runs-on: ubuntu-latest
    needs: deploy-prod
    if: failure()
    steps:
      - name: Deploy via SSH
        run: |
          ssh deploy@kvm4 './deploy/scripts/deploy-compose.sh production'
```

**Use case**: kvm4 runner down, deploy remotely via SSH.

## Monitoring & Observability

### Prometheus Metrics (Exposed by Cloudflare Worker)

```prometheus
# Runner assignment counts
pmoves_ci_runner_assignments{runner="ai-lab"} 42
pmoves_ci_runner_assignments{runner="vps"} 156
pmoves_ci_runner_assignments{runner="github-hosted"} 23

# Build duration by runner type
pmoves_ci_build_duration_seconds{runner="ai-lab",quantile="0.5"} 1200
pmoves_ci_build_duration_seconds{runner="vps",quantile="0.5"} 300

# Cost tracking (estimated)
pmoves_ci_estimated_cost_dollars{runner="github-hosted"} 1.84
pmoves_ci_estimated_cost_dollars{runner="self-hosted"} 0.00
```

### Grafana Dashboard

**Panels**:
1. Runner utilization (AI Lab GPU, VPS CPU)
2. Build success rate by runner type
3. Cost savings vs GitHub-hosted baseline
4. Avg build duration trends
5. Failover event frequency

### Discord Notifications

**Triggered by Cloudflare Worker**:
- ✅ Production deployments
- ❌ Build failures on main branch
- ⚠️ Fallback to GitHub hosted (capacity warning)
- 📊 Weekly cost/usage summary

## Migration Guide

### Existing Workflows → Hybrid Strategy

#### Before: All GitHub-Hosted
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
```

#### After: Intelligent Routing
```yaml
jobs:
  build-gpu:
    runs-on: [self-hosted, ai-lab, gpu]
    if: contains(github.event.head_commit.message, 'gpu') || contains(github.event.pull_request.labels.*.name, 'gpu-build')

  build-cpu:
    runs-on: [self-hosted, vps]
    if: contains(github.event.head_commit.modified, 'Dockerfile')

  build-lightweight:
    runs-on: ubuntu-latest
    if: contains(github.event.head_commit.modified, '.md')
```

### Steps to Adopt

1. **Install self-hosted runners** (see `/deploy/runners/README.md`)
2. **Deploy Cloudflare Worker** (see `/deploy/cloudflare/README.md`)
3. **Update workflows** to use `runs-on: [self-hosted, ...]`
4. **Monitor costs** via Grafana dashboard
5. **Tune routing logic** based on actual build patterns

## Security Considerations

### Self-Hosted Runner Risks

1. **Docker socket access** - Runners mount `/var/run/docker.sock`
   - **Mitigation**: Use trusted repos only, no public forks
   - **Alternative**: Rootless Docker + gVisor sandboxing

2. **Network exposure** - VPS runners have public IPs
   - **Mitigation**: Firewall rules (allow GitHub IPs only)
   - **Tool**: `ufw` configured to block all except GitHub Actions IP ranges

3. **Secrets in environment** - `.env` files on VPS
   - **Mitigation**: GitHub Secrets + encrypted vault (SOPS)
   - **Never** commit secrets to repo

### Cloudflare Worker Security

1. **Webhook signature validation** - Verify `X-Hub-Signature-256`
2. **Secrets in env vars** - Never hardcode in `worker.js`
3. **Rate limiting** - Cloudflare automatic DDoS protection
4. **CORS policy** - Restrict origins for API endpoints

## Future Roadmap

### Phase 2 (Q1 2025)

- [ ] **ML-based routing** - Learn optimal runner per repo/branch
- [ ] **Auto-scaling** - Spin up VPS runners on demand (Hetzner Cloud API)
- [ ] **Cost dashboards** - Real-time spend tracking in Grafana

### Phase 3 (Q2 2025)

- [ ] **Multi-region runners** - US West (AI Lab) + EU (VPS)
- [ ] **Kubernetes integration** - Replace VPS with k3s cluster
- [ ] **Build queue management** - Distribute load across runner pool

## References

- [Self-Hosted Runners Setup](/home/pmoves/PMOVES.AI/deploy/runners/README.md)
- [Cloudflare Worker Setup](/home/pmoves/PMOVES.AI/deploy/cloudflare/README.md)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)

---

**Questions?** Tag @frostbytten in PMOVES.AI Discord or open an issue on GitHub.
