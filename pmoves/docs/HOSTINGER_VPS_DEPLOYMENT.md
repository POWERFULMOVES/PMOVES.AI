# Hostinger VPS Deployment Guide

**Last Updated:** 2026-02-04
**Phase:** Phase 2.5 - Container Hardening Complete

## Overview

This guide covers deploying PMOVES.AI to Hostinger VPS instances with the hardened container configuration.

## Prerequisites

### Hostinger VPS Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8GB | 16GB+ |
| CPU | 4 cores | 8 cores |
| Storage | 80GB SSD | 160GB SSD |
| Bandwidth | 1TB | Unmetered |

### Local Requirements

- Docker with BuildKit enabled
- GitHub CLI (`gh`)
- SSH access to VPS
- Tailscale account (for VPN)

## Deployment Architecture

### Single VPS Deployment

```
┌─────────────────────────────────────────┐
│          Hostinger VPS                  │
│  ┌─────────────────────────────────────┐ │
│  │  PMOVES.AI Stack (Docker Compose)  │ │
│  │  - Observability (Prometheus)       │ │
│  │  - Data Tier (Qdrant, Neo4j, etc.)  │ │
│  │  - Message Bus (NATS)               │ │
│  │  - Services (Hi-RAG, Agents, etc.)  │ │
│  └─────────────────────────────────────┘ │
│              │                           │
│         Tailscale VPN                    │
│              │                           │
└──────────────┼───────────────────────────┘
               │
        ┌──────┴──────┐
        │ Local       │ Other
        │ Machine     │ Locations
└────────┴────────────┴─────────────┘
```

### Multi-VPS Deployment

For larger deployments, consider:
- **VPS 1** - Observability + Data Tier (8GB+)
- **VPS 2** - Services + Agents (16GB+)
- **VPS 3** - GPU/ML Workloads (32GB+)

## Quick Start

### 1. Provision VPS

```bash
# Via Hostinger Control Panel
# - Choose Ubuntu 22.04 or 24.04
# - Enable SSH key authentication
# - Configure firewall (allow 22, 80, 443, 4482)
```

### 2. Install Docker on VPS

```bash
ssh root@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com/rootless | sh
export DOCKER_HOST=unix:///run/user/$UID/docker.sock
echo 'export DOCKER_HOST=unix:///run/user/$UID/docker.sock' >> ~/.bashrc

# Install Docker Compose
curl -SL https://github.com/docker/compose/releases/download/v2.30.3/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 3. Install Tailscale

```bash
# Add Tailscale GPG key and repo
curl -fsSL https://tailscale.com/gpg-keys/tailscale-archive-keyring.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://tailscale.com/tailscale-setup.sh | sh

# Connect to your Tailnet
sudo tailscale up
```

### 4. Deploy PMOVES.AI

**Option A: Build Locally, Push to Registry**

```bash
# On local machine
cd /path/to/PMOVES.AI

# Build images incrementally (see INCREMENTAL_BUILD_PLAN.md)
# Build wave 1: Core infrastructure
docker compose build qdrant neo4j meilisearch nats

# Tag for registry
docker tag pmoves-qdrant:latest ghcr.io/powerfulmoves/pmoves-qdrant:hardened
docker tag pmoves-neo4j:latest ghcr.io/powerfulmoves/pmoves-neo4j:hardened
docker tag pmoves-meilisearch:latest ghcr.io/powerfulmoves/pmoves-meilisearch:hardened
docker tag pmoves-nats:latest ghcr.io/powerfulmoves/pmoves-nats:hardened

# Push to registry
docker push ghcr.io/powerfulmoves/pmoves-qdrant:hardened
docker push ghcr.io/powerfulmoves/pmoves-neo4j:hardened
docker push ghcr.io/powerfulmoves/pmoves-meilisearch:hardened
docker push ghcr.io/powerfulmoves/pmoves-nats:hardened
```

**Option B: Build Directly on VPS**

```bash
# On VPS (requires more resources)
git clone https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI/pmoves

# Build incrementally
docker compose build qdrant neo4j meilisearch nats
```

### 5. Configure Environment

```bash
# On VPS
cd PMOVES.AI/pmoves

# Bootstrap environment
python3 -m pmoves.scripts.bootstrap_env

# Or use defaults
cp env.shared.example env.shared
cp env.tier-data.example env.tier-data
# ... copy other env files
```

### 6. Start Services

```bash
# Start observability first
make up-obs

# Start data tier
docker compose up -d qdrant neo4j meilisearch minio

# Start message bus
docker compose up -d nats

# Start services incrementally
docker compose up -d agent-zero archon
docker compose up -d hi-rag-gateway-v2
```

## VPS-Specific Configuration

### CPU Optimization

Create `docker-compose.vps.override.yml`:

```yaml
# VPS resource limits for CPU-constrained environments
services:
  hi-rag-gateway-v2:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

  agent-zero:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

  extract-worker:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

### Use with:

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.vps.override.yml
docker compose up -d
```

## Monitoring

### Access from Local Machine

```bash
# Via Tailscale
ssh root@your-vps-node.tailnet-name

# Port forwarding via SSH
ssh -L 3000:localhost:3000 root@your-vps-ip

# Or access services directly via Tailscale
# - Grafana: http://your-vps-node:3000
# - Prometheus: http://your-vps-node:9090
```

### Health Checks

```bash
# On VPS
cd PMOVES.AI/pmoves

# Run smoke tests
make verify-all

# Check service health
curl http://localhost:8080/healthz  # Agent Zero
curl http://localhost:8086/healthz  # Hi-RAG v2
curl http://localhost:9090/-/healthy  # Prometheus
```

## Hardening Considerations

### VPS Security

1. **Firewall Rules:**
   ```bash
   # Allow only necessary ports
   ufw allow 22    # SSH
   ufw allow 80    # HTTP
   ufw allow 443   # HTTPS
   ufw allow 4482  # PMOVES UI
   ufw enable
   ```

2. **SSH Hardening:**
   ```bash
   # Disable password authentication
   sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
   systemctl restart sshd
   ```

3. **Docker Hardening:**
   - Already applied via docker-compose.yml
   - All services use appropriate templates
   - 6-tier network isolation enabled

### Data Persistence

```bash
# Ensure data is persisted across restarts
ls -la pmoves/data/

# Backup key directories
tar -czf pmoves-backup-$(date +%Y%m%d).tar.gz pmoves/data/
```

## Troubleshooting

### Out of Memory

```bash
# Check memory usage
free -h

# Check container memory
docker stats --no-stream

# Reduce parallel builds
# See INCREMENTAL_BUILD_PLAN.md
```

### Build Failures

```bash
# Clean build cache
docker builder prune -a -f

# Rebuild specific service
docker compose build --no-cache qdrant
```

### Network Issues

```bash
# Verify Tailscale connection
tailscale status

# Check Docker networks
docker network ls
docker network inspect pmoves_data

# Test connectivity
docker compose exec agent-zero ping qdrant
```

## Scaling

### Vertical Scaling (Upgrade VPS)

1. Create snapshot of current VPS
2. Upgrade to larger plan
3. Restore from snapshot
4. Adjust resource limits in docker-compose.vps.override.yml

### Horizontal Scaling (Add VPS)

1. Provision new VPS
2. Install Docker + Tailscale
3. Join Tailnet
4. Deploy specific service tiers
5. Update network configuration

## Backup Strategy

### Automated Backups

```bash
# Add to crontab (crontab -e)
# Daily backup at 2 AM
0 2 * * * /root/backup-pmoves.sh
```

### Backup Script

```bash
#!/bin/bash
# /root/backup-pmoves.sh
BACKUP_DIR="/backup/pmoves"
DATE=$(date +%Y%m%d)
cd /root/PMOVES.AI/pmoves

# Stop services before backup
docker compose stop

# Backup data
tar -czf $BACKUP_DIR/pmoves-$DATE.tar.gz data/

# Restart services
docker compose start
```

## Cost Optimization

### Resource Monitoring

```bash
# Monitor resource usage
docker stats --no-stream

# Identify resource-heavy services
for svc in $(docker compose ps --services); do
  echo "$svc:"
  docker stats --no-stream $svc --format "table {{.CPUPerc}}\t{{.MemUsage}}"
done
```

### Recommendations

1. **Stop unused services**
2. **Scale down non-critical workers**
3. **Use scheduled start/stop**
4. **Optimize GPU service usage**

## Next Steps

1. Review [Production Documentation](../docs/PRODUCTION_SINGLE_HOST.md)
2. Set up CI/CD for automated deployments
3. Configure monitoring alerts
4. Implement automated backups
5. Review [Incremental Build Plan](../docs/INCREMENTAL_BUILD_PLAN.md)

## Support

- **Documentation:** [docs/INDEX.md](../docs/INDEX.md)
- **Troubleshooting:** [docs/PRODUCTION_TROUBLESHOOTING.md](../docs/PRODUCTION_TROUBLESHOOTING.md)
- **GitHub Issues:** https://github.com/POWERFULMOVES/PMOVES.AI/issues
