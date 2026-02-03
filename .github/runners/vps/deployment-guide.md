# VPS Self-Hosted Runner Deployment Guide

**Purpose:** Deploy production GitHub Actions runners on your VPS for PMOVES.AI CI/CD.

**Last Updated:** 2026-01-31

---

## Overview

Self-hosted runners on your VPS provide:
- **Faster builds** - No queue time for CI/CD
- **GPU access** - AI Lab runners with NVIDIA GPU support
- **Cost control** - Use your own infrastructure
- **Data privacy** - Code never leaves your infrastructure

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| RAM | 2GB | 4GB+ |
| CPU | 2 cores | 4+ cores |
| Storage | 20GB | 50GB+ SSD |
| Network | Stable connection | 1Gbps preferred |

### For GPU Runners (AI Lab)

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| GPU | NVIDIA GTX 1660 | NVIDIA RTX 3090/4090 |
| VRAM | 6GB | 24GB |
| CUDA | 11.8 | 12.4 |
| RAM | 8GB | 32GB |

---

## Deployment Steps

### 1. System Preparation

Connect to your VPS:
```bash
ssh user@your-vps-ip
```

Update the system:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl jq wget tar docker.io
```

Add user for runner (optional but recommended):
```bash
sudo useradd -m -s /bin/bash runner
sudo usermod -aG docker runner
sudo -u runner bash
```

### 2. Docker Installation

Install Docker:
```bash
# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker
```

Verify Docker:
```bash
docker --version
sudo docker run --rm hello-world
```

### 3. Runner Installation

Create runner directory:
```bash
cd /home/runner
mkdir -p actions-runner
cd actions-runner
```

Download the runner:
```bash
RUNNER_VERSION="2.319.1"
curl -o actions-runner.tar.gz -L \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"

tar xzf ./actions-runner.tar.gz
rm actions-runner.tar.gz
```

### 4. Get Runner Token

1. Go to: https://github.com/POWERFULMOVES/PMOVES.AI/settings/actions/runners
2. Click "New self-hosted runner"
3. Select "Linux" and "x64"
4. Copy the token

### 5. Configure Runner

Replace `<TOKEN>` with your actual token:
```bash
./config.sh \
  --url https://github.com/POWERFULMOVES/PMOVES.AI \
  --token <TOKEN> \
  --name vps-production \
  --labels "self-hosted,vps,production,linux,x64" \
  --work /home/runner/_work \
  --replace
```

### 6. Install as Service

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

Check status:
```bash
sudo ./svc.sh status
```

---

## GPU Runner Setup (AI Lab)

### Install NVIDIA Drivers

```bash
# Add NVIDIA repository
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update

# Install NVIDIA driver (535 is stable)
sudo apt install -y nvidia-driver-535

# Reboot required
sudo reboot
```

Verify driver:
```bash
nvidia-smi
```

### Install NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Configure GPU Runner with GPU Label

```bash
./config.sh \
  --url https://github.com/POWERFULMOVES/PMOVES.AI \
  --token <TOKEN> \
  --name vps-gpu-ailab \
  --labels "self-hosted,gpu,ai-lab,linux,x64,nvidia" \
  --work /home/runner/_work \
  --replace
```

---

## Runner Management

### Start/Stop Runner

```bash
# Start
sudo ./svc.sh start

# Stop
sudo ./svc.sh stop

# Restart
sudo ./svc.sh restart

# Status
sudo ./svc.sh status
```

### Remove Runner

```bash
./config.sh remove --token <TOKEN>
sudo ./svc.sh uninstall
```

### Update Runner

```bash
# Stop service
sudo ./svc.sh stop

# Download new version
RUNNER_VERSION="2.319.1"
curl -o actions-runner.tar.gz -L \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"

# Extract (overwrite)
tar xzf ./actions-runner.tar.gz --overwrite

# Start service
sudo ./svc.sh start
```

---

## Firewall Configuration

Allow GitHub to reach your runner:

```bash
# GitHub Actions IP ranges (may change - check official docs)
sudo ufw allow from 185.199.108.0/24 to any port 80,443
sudo ufw allow from 140.82.112.0/20 to any port 80,443

# Or allow HTTPS outbound (runner connects to GitHub)
sudo ufw allow out 443/tcp

# Enable firewall
sudo ufw enable
```

---

## Monitoring

### Check Runner Logs

```bash
# Service logs
sudo journalctl -u actions.runner.* -f

# Runner diagnostics
./bin/Runner.Diagnostics.exe
```

### Monitor Runner Activity

Visit: https://github.com/POWERFULMOVES/PMOVES.AI/settings/actions/runners

You'll see:
- Runner status (online/idle/busy)
- Current job (if any)
- Job history
- Runner version

---

## Troubleshooting

### Runner Not Connecting

```bash
# Check service status
sudo systemctl status actions.runner.*

# Check logs
sudo journalctl -u actions.runner.* -n 50

# Verify network
curl -I https://github.com
curl -I https://github.com/POWERFULMOVES/PMOVES.AI
```

### Docker Permission Issues

```bash
# Verify user is in docker group
groups runner

# Fix if needed
sudo usermod -aG docker runner

# Re-login required
newgrp docker
```

### GPU Not Available in Container

```bash
# Verify NVIDIA runtime
docker info | grep nvidia

# Test GPU container
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

### Out of Memory

Add swap space:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Security Hardening

### 1. Runner User Isolation

Run as non-root user:
```bash
sudo -u runner ./config.sh ...
```

### 2. Resource Limits

Create `/etc/systemd/system/actions.runner.*.service.d/override.conf`:
```ini
[Service]
MemoryMax=4G
CPUQuota=200%
```

### 3. Network Segmentation

Place runner in isolated subnet, only allow:
- Outbound HTTPS (to GitHub, Docker Hub, GHCR)
- Inbound SSH (for management)

### 4. Auto-Updates

Configure unattended upgrades:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Runner Labels Reference

| Label | Purpose | Runner Type |
|-------|---------|-------------|
| `self-hosted` | All self-hosted runners | All |
| `vps` | VPS-based runners | Production |
| `production` | Production environment | Production |
| `local` | Local dev runner | Local |
| `gpu` | GPU-enabled | AI Lab |
| `ai-lab` | AI/ML workloads | AI Lab |
| `nvidia` | NVIDIA GPU specific | AI Lab |
| `linux` | Linux OS | All |
| `x64` | x86_64 architecture | All |

---

## Workflow Configuration

Use the runner in your GitHub Actions:

```yaml
jobs:
  build:
    runs-on: [self-hosted, vps]
    steps:
      - uses: actions/checkout@v6

  gpu-job:
    runs-on: [self-hosted, gpu, ai-lab]
    steps:
      - uses: actions/checkout@v6
      - name: Test GPU
        run: nvidia-smi
```

---

## Related Documentation

- Local Runner Setup: `.github/runners/local/setup.sh`
- Hardening Validation: `pmoves/scripts/validate-hardening.sh`
- CI/CD Workflows: `.github/workflows/`
