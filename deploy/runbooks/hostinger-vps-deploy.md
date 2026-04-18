# Hostinger VPS Deployment Runbook

## Overview
Deploy PMOVES.AI services to a Hostinger VPS with Tailscale networking, Docker runtime, and submodule initialization.

## Prerequisites

- Hostinger VPS credentials (API key or SSH access)
- Tailscale auth key with appropriate ACL tags
- GitHub SSH key with repo access (`POWERFULMOVES/PMOVES.AI`)
- DNS records configured (optional, can use Tailscale MagicDNS)

## Steps

### 1. Provision via Terraform

```bash
cd pmoves/terraform/
terraform init
terraform plan -var-file=hostinger.tfvars
terraform apply -var-file=hostinger.tfvars
```

Alternatively, use the Python SDK at `docs/Hostingerapi/`:
```bash
python3 docs/Hostingerapi/provision_vps.py --plan=vc2-4c-8gb --region=us-east
```

### 2. Install Tailscale

```bash
ssh root@<vps-ip>
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey=$TS_AUTHKEY --tag=hostinger
```

Verify: `tailscale status` should show the node with `tag:hostinger`.

### 3. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
usermod -aG docker $USER
```

### 4. Clone Repository

```bash
git clone git@github.com:POWERFULMOVES/PMOVES.AI.git /opt/pmoves
cd /opt/pmoves
git submodule update --init --recursive
```

### 5. Configure Environment

```bash
cp pmoves/env.tier-api.example pmoves/env.tier-api
cp pmoves/env.tier-data.example pmoves/env.tier-data
# Edit each file with actual secrets (see vault runbook for future improvement)
```

### 6. Launch Services

```bash
cd /opt/pmoves
docker compose -f pmoves/docker/docker-compose.yml up -d
```

### 7. Verify

```bash
# Health checks
curl http://localhost:8080/healthz  # Gateway
curl http://localhost:5432/healthz  # Postgres
curl http://localhost:9000/minio/health/live  # MinIO

# Tailscale connectivity
tailscale ping pmoves-dgx-spark
tailscale ping kvm2
```

## Rollback

```bash
cd /opt/pmoves
git pull --ff-only
git submodule update --init --recursive
docker compose -f pmoves/docker/docker-compose.yml up -d --force-recreate
```

## TODO

- [ ] Test Terraform plan on clean VPS
- [ ] Configure Tailscale ACL for hostinger tag (add to tailscale-acl-policy.json)
- [ ] Pinokio PBNJ launcher installation (see pinokio-pbnj-install.md)
- [ ] n8n workflow deployment
- [ ] Let's Encrypt HTTPS for public endpoints
- [ ] Prometheus + Grafana monitoring

## References

- Terraform configs: `pmoves/terraform/`
- Python SDK: `docs/Hostingerapi/`
- MCP server: available via mcp2cli plugin
- Network ACL: `pmoves/configs/tailscale-acl-policy.json`

Added: 2026-04-17
