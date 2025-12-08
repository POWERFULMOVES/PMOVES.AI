# PMOVES Self-Hosted GitHub Actions Runners

Self-hosted runner infrastructure for GPU-enabled builds (AI Lab) and cost-effective VPS deployments.

## Runner Fleet

| Host | Labels | Role | Hardware |
|------|--------|------|----------|
| **AI Lab** | `self-hosted,ai-lab,gpu,cuda` | GPU builds, model tests | RTX 5090/4090/3090Ti |
| **cloudstartup** | `self-hosted,vps,cloudstartup,staging` | Staging deploys | Hostinger VPS |
| **kvm4** | `self-hosted,vps,kvm4,production` | Production deploys | Hostinger VPS |
| **kvm2** | `self-hosted,vps,kvm2,backup` | Backup/overflow | Hostinger VPS |

## Installation

### Prerequisites

1. **GitHub PAT** with `repo` scope (or `admin:org` for org-level runners)
   - Create at: https://github.com/settings/tokens/new

2. **AI Lab**: NVIDIA drivers + Docker with NVIDIA Container Toolkit

3. **VPS**: Docker installed (script will install if missing)

### AI Lab (GPU)

```bash
# SSH to AI Lab
ssh ailab

# Set environment
export GITHUB_PAT="ghp_your_token_here"
export RUNNER_NAME="ailab-gpu"

# Run installation
curl -sSL https://raw.githubusercontent.com/frostbytten/PMOVES.AI/main/deploy/runners/ailab/install.sh | bash

# Or clone and run locally
git clone https://github.com/frostbytten/PMOVES.AI.git
cd PMOVES.AI/deploy/runners/ailab
./install.sh
```

### VPS Servers

```bash
# SSH to each VPS
ssh cloudstartup  # or kvm4, kvm2

# Set environment
export GITHUB_PAT="ghp_your_token_here"
export RUNNER_NAME="cloudstartup"  # or "kvm4", "kvm2"

# Run installation
curl -sSL https://raw.githubusercontent.com/frostbytten/PMOVES.AI/main/deploy/runners/vps/install.sh | bash
```

## Workflow Usage

### GPU Builds (AI Lab)

```yaml
jobs:
  build-gpu:
    runs-on: [self-hosted, ai-lab, gpu]
    steps:
      - uses: actions/checkout@v4

      - name: Verify GPU
        run: nvidia-smi

      - name: Build CUDA image
        run: docker build -f services/ollama/Dockerfile.cuda -t pmoves-ollama:cuda .
```

### Staging Deploy (cloudstartup)

```yaml
jobs:
  deploy-staging:
    runs-on: [self-hosted, cloudstartup, staging]
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        run: ./deploy/scripts/deploy-compose.sh staging
```

### Production Deploy (kvm4)

```yaml
jobs:
  deploy-prod:
    runs-on: [self-hosted, kvm4, production]
    needs: [build, test]
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        run: ./deploy/scripts/deploy-compose.sh production
```

### Overflow/Fallback (kvm2)

```yaml
jobs:
  build-overflow:
    runs-on: [self-hosted, kvm2, backup]
    if: github.event.workflow_run.conclusion == 'failure'
    steps:
      - name: Retry build
        run: echo "Running on backup runner"
```

## Service Management

### Check Status

```bash
# AI Lab
sudo systemctl status github-runner-ailab

# VPS
sudo systemctl status github-runner-cloudstartup  # or kvm4, kvm2
```

### View Logs

```bash
sudo journalctl -u github-runner-ailab -f
```

### Restart

```bash
sudo systemctl restart github-runner-ailab
```

### Remove Runner

```bash
cd /opt/actions-runner
./config.sh remove --token <TOKEN>
sudo systemctl stop github-runner-ailab
sudo systemctl disable github-runner-ailab
sudo rm /etc/systemd/system/github-runner-ailab.service
```

## Monitoring

Runners expose metrics via the GitHub API:

```bash
# List all runners
gh api repos/frostbytten/PMOVES.AI/actions/runners

# Get specific runner
gh api repos/frostbytten/PMOVES.AI/actions/runners/{runner_id}
```

## Security Notes

1. **PAT Storage**: Never commit PATs. Use GitHub Secrets or environment variables.

2. **Network**: VPS runners should be behind firewalls, only GitHub IPs allowed.

3. **Docker Socket**: Runners mount Docker socket - use with trusted repos only.

4. **Disk Cleanup**: Weekly cron job prunes Docker resources on VPS.

## Troubleshooting

### Runner Not Appearing

1. Check token validity: `gh auth status`
2. Verify network: `curl -I https://github.com`
3. Check logs: `sudo journalctl -u github-runner-* -n 100`

### GPU Not Detected

1. Verify NVIDIA drivers: `nvidia-smi`
2. Check Docker GPU: `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi`
3. Restart runner: `sudo systemctl restart github-runner-ailab`

### Disk Full

```bash
# Manual cleanup
docker system prune -af --volumes
docker builder prune -af
```

## Cost Analysis

| Deployment | GitHub-Hosted | Self-Hosted |
|------------|---------------|-------------|
| GPU build (30 min) | ~$12/run | $0 (electricity only) |
| CPU build (10 min) | ~$0.80/run | $0 (VPS fixed cost) |
| Monthly (100 builds) | ~$200+ | ~$30 (VPS hosting) |

Self-hosted runners provide:
- **80%+ cost savings** on frequent builds
- **GPU access** for CUDA builds and model testing
- **Air-gapped security** for sensitive workloads
- **Persistent caches** for faster builds
