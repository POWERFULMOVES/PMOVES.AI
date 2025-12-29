# Self-Hosted Runners Configuration

## Overview

PMOVES.AI uses GitHub Actions self-hosted runners for CI/CD pipelines. This document covers runner configuration, deployment, and maintenance.

## Runner Hosts

| Host | Label | Purpose | Hardware |
|------|-------|---------|----------|
| ai-lab | `self-hosted,ai-lab,gpu,Linux,X64` | GPU builds, TTS, media processing | NVIDIA GPU, 64GB+ RAM |
| vps | `self-hosted,vps,Linux,X64` | General CPU builds, testing | 8+ cores, 16GB+ RAM |
| cloudstartup | `self-hosted,cloudstartup,staging,Linux,X64` | Staging deployments | Cloud VM |
| kvm4 | `self-hosted,kvm4,production,Linux,X64` | Production deployments | Production server |

## Quick Deployment

### Using Setup Script

```bash
# Copy script to target host
scp .claude/scripts/setup-runner.sh user@host:~/

# SSH and run with host type
ssh user@host
./setup-runner.sh ai-lab  # or vps, cloudstartup, kvm4
```

### Manual Registration

```bash
# 1. Generate registration token (valid 1 hour)
TOKEN=$(gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token -X POST --jq '.token')

# 2. Download runner
mkdir ~/actions-runner && cd ~/actions-runner
curl -sL -o runner.tar.gz https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf runner.tar.gz && rm runner.tar.gz

# 3. Configure
./config.sh --url https://github.com/POWERFULMOVES/PMOVES.AI \
  --token $TOKEN \
  --name "pmoves-<host>-runner" \
  --labels "self-hosted,<host>,Linux,X64" \
  --work "_work" \
  --replace

# 4. Install as service
sudo ./svc.sh install
sudo ./svc.sh start
```

## Workflow Configuration

### Example Workflow Using Self-Hosted Runners

```yaml
name: Build and Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: [self-hosted, vps]
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: docker compose build

  gpu-tests:
    runs-on: [self-hosted, ai-lab, gpu]
    needs: build
    steps:
      - uses: actions/checkout@v4
      - name: Run GPU tests
        run: pytest tests/gpu/

  deploy-staging:
    runs-on: [self-hosted, cloudstartup, staging]
    needs: build
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: ./deploy.sh staging

  deploy-production:
    runs-on: [self-hosted, kvm4, production]
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to production
        run: ./deploy.sh production
```

## Runner Management

### Check Runner Status

```bash
# List runners via GitHub API
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners --jq '.runners[] | "\(.name): \(.status)"'

# On runner host
sudo ./svc.sh status
```

### Restart Runner

```bash
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Remove Runner

```bash
# On runner host
sudo ./svc.sh uninstall
./config.sh remove --token <REMOVE_TOKEN>

# Generate remove token
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/remove-token -X POST --jq '.token'
```

### Update Runner

```bash
sudo ./svc.sh stop
# Download new version
curl -sL -o runner.tar.gz https://github.com/actions/runner/releases/download/v<VERSION>/actions-runner-linux-x64-<VERSION>.tar.gz
tar xzf runner.tar.gz
sudo ./svc.sh start
```

## Labels Reference

### Standard Labels

| Label | Description |
|-------|-------------|
| `self-hosted` | All self-hosted runners (required) |
| `Linux` | Linux-based runners |
| `X64` | x86_64 architecture |

### PMOVES-Specific Labels

| Label | Description | Typical Jobs |
|-------|-------------|--------------|
| `ai-lab` | AI development workstation | GPU builds, TTS, media |
| `gpu` | Has NVIDIA GPU | CUDA builds, ML training |
| `vps` | Virtual private server | General builds, tests |
| `staging` | Staging environment | Pre-production deployment |
| `production` | Production environment | Production deployment |
| `cloudstartup` | Cloud VM | Testing, staging |
| `kvm4` | KVM host 4 | Production workloads |

## Workflow Files

| File | Purpose | Runner Labels |
|------|---------|---------------|
| `.github/workflows/self-hosted-builds-hardened.yml` | Main CI/CD pipeline | Various |
| `.github/workflows/docker-multiarch.yml` | Multi-arch Docker builds | `vps` |
| `.github/workflows/gpu-tests.yml` | GPU-specific tests | `ai-lab, gpu` |

## Security Considerations

1. **Runner Isolation**
   - Each runner runs in isolated `_work` directory
   - Sensitive env vars configured per-workflow

2. **Token Management**
   - Registration tokens expire after 1 hour
   - Store tokens securely, never commit

3. **Network Access**
   - Runners need outbound HTTPS to github.com
   - May need internal network access for deployment

4. **Secrets**
   - Use GitHub Secrets for sensitive data
   - Never hardcode credentials in workflows

## Troubleshooting

### Runner Offline

```bash
# Check service status
sudo ./svc.sh status

# Check logs
journalctl -u actions.runner.<repo>.<name>.service -f

# Verify network connectivity
curl -I https://github.com
```

### Job Stuck

```bash
# Check runner logs
tail -f ~/actions-runner/_diag/Runner_*.log

# Force restart
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Permission Issues

```bash
# Ensure runner user owns work directory
chown -R $USER:$USER ~/actions-runner/_work

# Check Docker access
docker info
```

## Token Generation Commands

```bash
# Registration token (for adding runners)
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token -X POST --jq '.token'

# Remove token (for removing runners)
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/remove-token -X POST --jq '.token'

# List runners
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners
```

## Related Files

- `.claude/scripts/setup-runner.sh` - Automated setup script
- `.github/workflows/` - Workflow definitions
- `.claude/learnings/session5-infrastructure-audit-2025-12.md` - Setup history
