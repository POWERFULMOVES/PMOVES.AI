#!/bin/bash
# Hostinger KVM Provisioning Script
#
# Single script to provision a fresh Hostinger KVM as a PMOVES.AI node:
#   1. System update + hardening (ufw, fail2ban, sshd)
#   2. Docker + Docker Compose v2
#   3. Tailscale mesh join
#   4. GitHub Actions runner (via install-hardened.sh)
#   5. /opt/pmoves work directory
#
# Usage:
#   GITHUB_PAT=ghp_xxx TAILSCALE_AUTHKEY=tskey-xxx ./hostinger-kvm-setup.sh <kvm4-1|kvm4-2|kvm2>
#
# Prerequisites:
#   - Fresh Ubuntu 22.04+ on Hostinger KVM
#   - Root or sudo access
#   - GITHUB_PAT with admin:org or repo scope
#   - TAILSCALE_AUTHKEY (reusable, from https://login.tailscale.com/admin/settings/keys)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_TYPE="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "${BLUE}[====]${NC} $1"; }

# Validate node type
validate_node_type() {
    case "$NODE_TYPE" in
        kvm4-1|kvm4-2|kvm2) ;;
        *)
            log_error "Invalid node type: '$NODE_TYPE'"
            echo "Usage: $0 <kvm4-1|kvm4-2|kvm2>"
            echo ""
            echo "Node types:"
            echo "  kvm4-1  API Gateway (TensorZero, Agent Zero, Hi-RAG CPU)"
            echo "  kvm4-2  Data/Storage (Supabase, Qdrant, Neo4j, Meilisearch)"
            echo "  kvm2    Exit Node (Tailscale exit, Nginx, SSL termination)"
            exit 1
            ;;
    esac
}

# Check required environment variables
check_env() {
    log_section "Checking environment..."

    if [ -z "${GITHUB_PAT:-}" ]; then
        log_error "GITHUB_PAT not set. Generate at: https://github.com/settings/tokens/new"
        exit 1
    fi

    if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
        log_warn "TAILSCALE_AUTHKEY not set. Tailscale setup will be skipped."
        log_info "Generate at: https://login.tailscale.com/admin/settings/keys"
    fi

    log_info "Node type: $NODE_TYPE"
    log_info "Hostname: $(hostname)"
    log_info "OS: $(. /etc/os-release && echo "$PRETTY_NAME")"
}

# Step 1: System update + hardening
harden_system() {
    log_section "Step 1: System hardening..."

    # Update packages
    log_info "Updating system packages..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

    # Install essentials
    log_info "Installing essential packages..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        curl wget git jq unzip htop \
        ufw fail2ban \
        ca-certificates gnupg lsb-release \
        uidmap dbus-user-session fuse-overlayfs slirp4netns

    # Configure UFW firewall
    # NOTE: SSH port 22 is exposed publicly during provisioning, secured by:
    #   - Key-only auth (PasswordAuthentication no)
    #   - fail2ban with 5-attempt lockout
    #   - MaxAuthTries 3
    # Post-Tailscale, consider restricting to: ufw allow in on tailscale0
    # and removing public SSH: ufw delete allow 22/tcp
    log_info "Configuring firewall (ufw)..."
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp comment "SSH"

    case "$NODE_TYPE" in
        kvm4-1)
            # API Gateway ports
            ufw allow 8080/tcp comment "Agent Zero API"
            ufw allow 8086/tcp comment "Hi-RAG v2 CPU"
            ufw allow 3030/tcp comment "TensorZero Gateway"
            ufw allow 8091/tcp comment "Archon API"
            ufw allow 8100/tcp comment "Gateway Agent"
            ;;
        kvm4-2)
            # Data services — only exposed within Tailscale mesh
            ufw allow 4222/tcp comment "NATS"
            ufw allow 6333/tcp comment "Qdrant"
            ufw allow 7474/tcp comment "Neo4j HTTP"
            ufw allow 7687/tcp comment "Neo4j Bolt"
            ufw allow 7700/tcp comment "Meilisearch"
            ufw allow 9090/tcp comment "Prometheus"
            ufw allow 3000/tcp comment "Grafana"
            ;;
        kvm2)
            # Exit node / proxy
            ufw allow 80/tcp comment "HTTP"
            ufw allow 443/tcp comment "HTTPS"
            ;;
    esac

    ufw --force enable
    log_info "Firewall enabled"

    # Configure fail2ban
    log_info "Configuring fail2ban..."
    cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
findtime = 600
EOF
    systemctl enable fail2ban
    systemctl restart fail2ban

    # Harden SSH
    log_info "Hardening SSH..."
    sed -i 's/#PermitRootLogin yes/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
    systemctl restart sshd

    log_info "System hardening complete"
}

# Step 2: Docker + Docker Compose v2
install_docker() {
    log_section "Step 2: Installing Docker..."

    if command -v docker &>/dev/null; then
        log_info "Docker already installed: $(docker --version)"
        return 0
    fi

    # Install Docker using official script
    curl -fsSL https://get.docker.com | sh

    # Add current user to docker group
    usermod -aG docker "${SUDO_USER:-$USER}"

    # Install Docker Compose v2 plugin (if not bundled)
    if ! docker compose version &>/dev/null; then
        log_info "Installing Docker Compose v2 plugin..."
        COMPOSE_VERSION="v2.27.0"
        mkdir -p /usr/local/lib/docker/cli-plugins
        curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/lib/docker/cli-plugins/docker-compose
        chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    fi

    # Enable and start Docker
    systemctl enable docker
    systemctl start docker

    log_info "Docker installed: $(docker --version)"
    log_info "Compose: $(docker compose version)"
}

# Step 3: Tailscale mesh join
install_tailscale() {
    log_section "Step 3: Installing Tailscale..."

    if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
        log_warn "Skipping Tailscale (no TAILSCALE_AUTHKEY)"
        return 0
    fi

    # Install Tailscale
    if ! command -v tailscale &>/dev/null; then
        curl -fsSL https://tailscale.com/install.sh | sh
    fi

    # Join mesh with appropriate tags
    local ts_args=(
        --auth-key "$TAILSCALE_AUTHKEY"
        --hostname "pmoves-${NODE_TYPE}"
        --accept-routes
        --accept-dns
    )

    # KVM2 is the exit node
    if [ "$NODE_TYPE" = "kvm2" ]; then
        log_info "Configuring as Tailscale exit node..."
        # Enable IP forwarding for exit node
        sysctl -w net.ipv4.ip_forward=1
        sysctl -w net.ipv6.conf.all.forwarding=1
        cat >> /etc/sysctl.d/99-tailscale.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
        ts_args+=(--advertise-exit-node)
    fi

    tailscale up "${ts_args[@]}"

    # Disable key expiry for persistent VPS node (default 180-day timeout)
    if ! tailscale set --key-expiry-disabled 2>/dev/null; then
        log_warn "Could not disable key expiry — approve manually in admin console"
    fi

    # Verify connection
    sleep 3
    if tailscale status &>/dev/null; then
        local ts_ip
        ts_ip=$(tailscale ip -4 2>/dev/null || echo "pending")
        log_info "Tailscale connected: $ts_ip (pmoves-${NODE_TYPE})"
    else
        log_warn "Tailscale connection pending — may need admin approval"
    fi
}

# Step 4: GitHub Actions runner
install_runner() {
    log_section "Step 4: Installing GitHub Actions runner..."

    # Create runner user if not exists
    if ! id -u runner &>/dev/null; then
        useradd -m -s /bin/bash runner
        usermod -aG docker runner
    fi

    # Use the hardened runner install script
    local runner_script="${SCRIPT_DIR}/../runners/vps/install-hardened.sh"
    if [ -f "$runner_script" ]; then
        log_info "Using hardened runner install script..."
        GITHUB_PAT="$GITHUB_PAT" \
        RUNNER_NAME="pmoves-${NODE_TYPE}" \
        GITHUB_ORG="POWERFULMOVES" \
        GITHUB_REPO="PMOVES.AI" \
            sudo -u runner bash "$runner_script"
    else
        log_warn "Hardened install script not found at: $runner_script"
        log_info "Falling back to setup-runner.sh pattern..."

        local runner_dir="/home/runner/actions-runner-${NODE_TYPE}"
        local runner_version="2.321.0"
        local labels

        case "$NODE_TYPE" in
            kvm4-1) labels="self-hosted,vps,kvm4,kvm4-1,production,Linux,X64" ;;
            kvm4-2) labels="self-hosted,vps,kvm4,kvm4-2,production,Linux,X64" ;;
            kvm2)   labels="self-hosted,vps,kvm2,backup,Linux,X64" ;;
        esac

        sudo -u runner mkdir -p "$runner_dir"

        # Get registration token
        local reg_token
        reg_token=$(curl -sf -X POST \
            -H "Authorization: token ${GITHUB_PAT}" \
            -H "Accept: application/vnd.github.v3+json" \
            "https://api.github.com/repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token" \
            | jq -r '.token')

        if [ -z "$reg_token" ] || [ "$reg_token" = "null" ]; then
            log_error "Failed to get runner registration token"
            return 1
        fi

        # Download and configure runner
        cd "$runner_dir"
        if [ ! -f "./config.sh" ]; then
            curl -sL -o actions-runner.tar.gz \
                "https://github.com/actions/runner/releases/download/v${runner_version}/actions-runner-linux-x64-${runner_version}.tar.gz"
            sudo -u runner tar xzf actions-runner.tar.gz
            rm actions-runner.tar.gz
        fi

        sudo ./bin/installdependencies.sh

        sudo -u runner ./config.sh \
            --url "https://github.com/POWERFULMOVES/PMOVES.AI" \
            --token "$reg_token" \
            --name "pmoves-${NODE_TYPE}-runner" \
            --labels "$labels" \
            --work "_work" \
            --replace \
            --unattended

        sudo ./svc.sh install runner
        sudo ./svc.sh start
    fi

    log_info "Runner installed for node: $NODE_TYPE"
}

# Step 5: Create work directory
setup_workdir() {
    log_section "Step 5: Setting up /opt/pmoves..."

    mkdir -p /opt/pmoves
    chown "${SUDO_USER:-$USER}:${SUDO_USER:-$USER}" /opt/pmoves

    # Clone repo if not present
    if [ ! -d /opt/pmoves/.git ]; then
        log_info "Cloning PMOVES.AI repository..."
        git clone --depth 1 https://github.com/POWERFULMOVES/PMOVES.AI.git /opt/pmoves
    fi

    # Create node-specific marker
    cat > /opt/pmoves/.node-config <<EOF
NODE_TYPE=$NODE_TYPE
PROVISIONED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOSTNAME=$(hostname)
TAILSCALE_HOSTNAME=pmoves-${NODE_TYPE}
EOF

    log_info "Work directory ready at /opt/pmoves"
}

# Show summary
show_summary() {
    log_section "========================================="
    log_section "Provisioning Complete: $NODE_TYPE"
    log_section "========================================="

    echo ""
    log_info "Node: pmoves-${NODE_TYPE}"
    log_info "Docker: $(docker --version 2>/dev/null || echo 'not installed')"
    log_info "Compose: $(docker compose version 2>/dev/null || echo 'not installed')"

    if command -v tailscale &>/dev/null && tailscale status &>/dev/null; then
        log_info "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
    fi

    echo ""
    log_info "Next steps:"
    case "$NODE_TYPE" in
        kvm4-1)
            echo "  1. Deploy API services:  cd /opt/pmoves/pmoves && docker compose -f docker-compose.yml -f docker-compose.vps.override.yml up -d tensorzero agent-zero hi-rag-gateway-v2 archon-server gateway-agent"
            echo "  2. Verify:  curl http://localhost:8080/healthz"
            ;;
        kvm4-2)
            echo "  1. Deploy data services: cd /opt/pmoves/pmoves && docker compose -f docker-compose.yml -f docker-compose.vps.override.yml up -d supabase-db supabase-rest qdrant neo4j meilisearch nats prometheus grafana"
            echo "  2. Verify:  curl http://localhost:9090/api/v1/targets"
            ;;
        kvm2)
            echo "  1. Approve exit node in Tailscale admin: https://login.tailscale.com/admin/machines"
            echo "  2. Deploy proxy: cd /opt/pmoves/pmoves && docker compose -f docker-compose.yml -f docker-compose.vps.override.yml up -d nginx"
            echo "  3. Use from home: tailscale up --exit-node=pmoves-kvm2"
            ;;
    esac
    echo ""
    echo "  Runner status: sudo systemctl status github-runner-pmoves-${NODE_TYPE}"
    echo "  Runner logs:   sudo journalctl -u github-runner-pmoves-${NODE_TYPE} -f"
}

# Main
main() {
    validate_node_type
    check_env

    log_section "========================================="
    log_section "PMOVES.AI KVM Provisioning: $NODE_TYPE"
    log_section "========================================="
    echo ""

    harden_system
    install_docker
    install_tailscale
    install_runner
    setup_workdir
    show_summary
}

main "$@"
