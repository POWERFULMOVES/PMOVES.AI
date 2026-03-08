#!/bin/bash
# PMOVES.AI VPS Bootstrap Script (Terraform-templated)
# WARNING: This file is a Terraform template — DO NOT execute directly.
# Variables like ${project_name} are interpolated by templatefile() at plan time.
# Injected variables: project_name, git_repo_url, git_branch, etc.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "=== PMOVES.AI VPS Bootstrap ==="
echo "Project: ${project_name}"
echo "Branch:  ${git_branch}"
echo "Node:    $(hostname)"

# ============================================================================
# 1. System Updates & Prerequisites
# ============================================================================
apt-get update -y
apt-get install -y \
    apt-transport-https ca-certificates curl gnupg lsb-release \
    git jq unzip htop tmux fail2ban ufw

# ============================================================================
# 2. Docker Installation
# ============================================================================
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Docker Compose plugin (V2)
if ! docker compose version &>/dev/null; then
    echo "Installing Docker Compose V2..."
    apt-get install -y docker-compose-plugin
fi

# ============================================================================
# 3. Tailscale Installation
# ============================================================================
if ! command -v tailscale &>/dev/null; then
    echo "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# ============================================================================
# 4. Firewall Configuration
# ============================================================================
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
# SSH exposed publicly for initial provisioning (before Tailscale is up).
# Secured by key-only auth + fail2ban. Post-Tailscale, consider restricting
# to tailscale0 interface: ufw allow in on tailscale0 && ufw delete allow 22/tcp
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw allow 41641/udp  # Tailscale WireGuard
ufw --force enable

# ============================================================================
# 5. Clone Repository
# ============================================================================
DEPLOY_DIR="/opt/${project_name}"
if [[ ! -d "$DEPLOY_DIR" ]]; then
    git clone --branch "${git_branch}" "${git_repo_url}" "$DEPLOY_DIR"
fi

cd "$DEPLOY_DIR"

%{ if submodule_init ~}
git submodule update --init --depth 1
%{ endif ~}

# ============================================================================
# 6. Environment Configuration
# ============================================================================
cd "$DEPLOY_DIR/pmoves"

cat > .env.vps <<'ENVEOF'
NATS_URL=${nats_url}
SUPABASE_URL=${supabase_url}
SUPABASE_SERVICE_KEY=${supabase_service_key}
OPEN_NOTEBOOK_API_URL=${open_notebook_api_url}
OPEN_NOTEBOOK_API_TOKEN=${open_notebook_api_token}
HIRAG_URL=${hirag_url}
COMFYUI_WEBHOOK_URL=${comfyui_webhook_url}
YOUTUBE_API_KEY=${youtube_api_key}
DOMAIN_NAME=${domain_name}
ENVEOF

chmod 600 .env.vps

# ============================================================================
# 7. Start Services
# ============================================================================
%{ if docker_compose_profile == "full" ~}
docker compose -f docker-compose.yml -f docker-compose.vps.override.yml up -d
%{ else ~}
docker compose -f docker-compose.yml -f docker-compose.vps.override.yml --profile ${docker_compose_profile} up -d
%{ endif ~}

# ============================================================================
# 8. Monitoring Retention
# ============================================================================
%{ if monitoring_retention_days > 0 ~}
# Set Prometheus retention (applied via command-line flag in compose)
echo "Prometheus retention: ${monitoring_retention_days} days"
%{ endif ~}

echo "=== PMOVES.AI Bootstrap Complete ==="
echo "Services: docker compose ps"
echo "Logs:     docker compose logs -f"
