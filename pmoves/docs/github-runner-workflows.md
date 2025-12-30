# GitHub Actions Runner Labels

**PMOVES.AI CI/CD Workload Distribution Guide**

This document defines the runner label conventions for distributing GitHub Actions workflows across the PMOVES hybrid runner fleet.

---

## Runner Overview

| Runner | Location | Labels | Hardware | Best For |
|--------|----------|--------|----------|----------|
| **ai-lab** | Local | `self-hosted`, `ai-lab`, `gpu`, `Linux`, `X64` | NVIDIA GPU, 64GB RAM, 200GB | Research, LLM training, GPU builds |
| **vps** | Remote VPS | `self-hosted`, `vps`, `Linux`, `X64` | 8 CPU, 16GB RAM, 50GB, Docker | Docker builds, CPU tests, CI pipelines |
| **cloudstartup** | Cloud VM | `self-hosted`, `cloudstartup`, `Linux`, `X64` | 4 CPU, 8GB RAM | Unit tests, overflow, staging |
| **kvm4** | Production | `self-hosted`, `kvm4`, `production`, `Linux`, `X64` | Production spec | Production deployments only |

---

## Workflow Label Selection Guide

### Research & AI/ML Workflows
Use `ai-lab` for:
- Model training (PyTorch, TensorFlow, JAX)
- GPU-accelerated tests
- Large language model operations
- Computer vision workloads
- Long-running experiments (>30 minutes)

```yaml
runs-on: [self-hosted, ai-lab, gpu]
```

### Docker Builds
Use `vps` for:
- Docker image builds (>2GB)
- Multi-stage Dockerfiles
- Container registry pushes
- Docker Compose tests

```yaml
runs-on: [self-hosted, vps]
```

### Unit Tests
Use `cloudstartup` for:
- Fast unit tests (<5 minutes)
- Linting and formatting checks
- Type checking (mypy, tsc)
- Small package installations

```yaml
runs-on: [self-hosted, cloudstartup]
```

### Integration Tests
Use `vps` for:
- Full-stack tests requiring services
- Database migrations
- API integration tests
- End-to-end workflows

```yaml
runs-on: [self-hosted, vps]
```

### Security Scanning
Use `vps` for:
- SAST/SCA scans
- Dependency audits
- Container image scanning
- License compliance checks

```yaml
runs-on: [self-hosted, vps]
```

### Production Deployments
Use `kvm4` for:
- Production deployments
- Database migrations on production
- Configured production secrets access

```yaml
runs-on: [self-hosted, kvm4, production]
```

---

## Workload Routing Matrix

| Workload Type | Primary Runner | Fallback Runner | Rationale |
|---------------|----------------|-----------------|-----------|
| LLM Training | ai-lab | - | Requires GPU |
| GPU Build | ai-lab | - | CUDA dependency |
| Docker Build (large) | vps | cloudstartup | Disk space requirement |
| Docker Build (small) | cloudstartup | vps | Load balancing |
| Unit Tests | cloudstartup | - | Fast, parallelizable |
| Integration Tests | vps | - | Full stack required |
| Security Scan | vps | - | CPU intensive |
| Production Deploy | kvm4 | - | Isolated environment |
| Documentation | cloudstartup | - | Minimal resources |

---

## Workflow Examples

### GPU-Accelerated Test
```yaml
name: GPU Tests

on: [push, pull_request]

jobs:
  test-gpu:
    runs-on: [self-hosted, ai-lab, gpu]
    steps:
      - uses: actions/checkout@v4
      - name: Run GPU tests
        run: |
          pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
          pytest tests/gpu/
```

### Docker Build
```yaml
name: Docker Build

on: [push]

jobs:
  build-image:
    runs-on: [self-hosted, vps]
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: |
          docker build -t myapp:${{ github.sha }} .
          docker push registry.example.com/myapp:${{ github.sha }}
```

### Fast Unit Tests
```yaml
name: Unit Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: [self-hosted, cloudstartup]
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install pytest
          pytest tests/unit/
```

---

## Monitoring Runner Status

### Via API
```bash
# List all runners
curl http://localhost:8100/runners

# Get specific runner status
curl http://localhost:8100/runners/ai-lab

# Get queue status
curl http://localhost:8100/queue/POWERFULMOVES/PMOVES.AI
```

### Via Grafana
Access the GitHub Runners dashboard at:
`http://localhost:3000/d/github-runners`

### Prometheus Metrics
```bash
# Runner availability
curl http://localhost:9090/api/v1/query?query=github_runner_up

# Queue depth
curl http://localhost:9090/api/v1/query?query=github_runner_queue_depth

# Job completion rate
curl http://localhost:9090/api/v1/query?query=sum(rate(github_runner_jobs_total[5m])) by (runner)
```

---

## Troubleshooting

### Workflow Not Picking Up Expected Runner
1. Check labels in workflow YAML match runner labels exactly
2. Verify runner is online: `curl http://localhost:8100/runners`
3. Check runner is not busy: `curl http://localhost:8100/runners/{runner_name}`

### High Queue Depth on Runner
1. Check Grafana for queue trends
2. Consider increasing parallel jobs in workflow
3. If persistent, add capacity or route workloads elsewhere

### Runner Offline
1. Check runner machine is running
2. Verify GitHub Actions runner service is active
3. Check NATS connectivity for status events

---

## Alert Thresholds

| Alert | Trigger | Severity | Action |
|-------|---------|----------|--------|
| RunnerQueueBacklog | Queue depth > 10 for 10m | Warning | Monitor closely |
| RunnerQueueCritical | Queue depth > 20 for 5m | Critical | Add capacity |
| RunnerDiskLow | Disk < 10GB | Critical | Clear disk space |
| RunnerOffline | Runner unreachable for 5m | Warning | Check runner health |
| GitHubAPIRateLimitLow | API calls < 100 | Warning | Wait for reset |

---

## NATS Event Subjects

Runner lifecycle events are published on these subjects for integration:

```text
github.runner.registered.v1      # New runner registered
github.runner.removed.v1         # Runner decommissioned
github.runner.enabled.v1         # Runner brought online
github.runner.disabled.v1        # Runner taken offline
github.runner.unreachable.v1     # Runner health check failed
github.runner.cpu_high.v1        # CPU usage above threshold
github.runner.memory_high.v1     # Memory usage above threshold
github.runner.disk_low.v1        # Disk space below threshold

github.job.queued.v1             # Job queued for runner
github.job.started.v1            # Job started on runner
github.job.completed.v1          # Job completed successfully
github.job.failed.v1             # Job failed
```

---

## See Also

- [PMOVES Monitoring Stack](./PMOVES_Infrastructure_Documentation.md)
- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
