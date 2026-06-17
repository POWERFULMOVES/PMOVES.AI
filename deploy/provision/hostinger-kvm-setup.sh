#!/bin/bash
# Hostinger KVM Provisioning Script
#
# Single script to provision a fresh Hostinger KVM as a PMOVES.AI node:
#   1. System update + hardening (ufw, fail2ban, sshd)
#   2. Docker + Docker Compose v2
#   3. Tailscale mesh join
#   4. GitHub Actions runner (via install-hardened.sh)
#   5. /opt/pmoves work directory
#   6. PMOVES.Flare model namespace configuration
#   7. vLLM remote GPU endpoint wiring
#
# Usage:
#   GITHUB_PAT=ghp_xxx TAILSCALE_AUTHKEY=tskey-xxx ./hostinger-kvm-setup.sh <kvm4-1|kvm4-2|kvm2|gpu-5090>
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

# Autodetect output captured for show_summary (populated only when autodetect ran)
AUTODETECT_RAN=0
AUTODETECT_SUGGESTION=""

# Resolve $NODE_TYPE via glances-autodetect when operator passes "auto"
# or when PMOVES_AUTODETECT=1 is set in the environment. Safe to call multiple
# times; behaves as a no-op if $NODE_TYPE is already a valid explicit value.
autodetect_node_type() {
    local autodetect_script="${SCRIPT_DIR}/glances-autodetect.sh"

    # Only run if explicitly requested
    if [ "$NODE_TYPE" != "auto" ] && [ "${PMOVES_AUTODETECT:-0}" != "1" ]; then
        return 0
    fi

    log_section "Autodetect: resolving node-type via glances-autodetect.sh..."

    if [ ! -x "$autodetect_script" ] && [ ! -f "$autodetect_script" ]; then
        log_error "Autodetect requested but script not found at: $autodetect_script"
        log_error "Pass an explicit node-type instead: $0 <kvm4-1|kvm4-2|kvm2|gpu-5090>"
        exit 1
    fi

    local suggested
    suggested="$(bash "$autodetect_script" --suggest 2>/dev/null || echo unknown)"
    AUTODETECT_RAN=1
    AUTODETECT_SUGGESTION="$suggested"

    if [ -z "$suggested" ] || [ "$suggested" = "unknown" ]; then
        log_error "Autodetect could not confidently determine a node-type."
        log_error "Run 'sudo bash ${autodetect_script}' for the full spec report, then"
        log_error "pass the node-type explicitly:  $0 <kvm4-1|kvm4-2|kvm2|gpu-5090>"
        exit 1
    fi

    log_info "Autodetect suggested node-type: $suggested"
    NODE_TYPE="$suggested"
}

# Validate node type
validate_node_type() {
    case "$NODE_TYPE" in
        kvm4-1|kvm4-2|kvm2|gpu-5090|rdna4-workstation|dgx-spark|pve-member|pve-member-fresh) ;;
        *)
            log_error "Invalid node type: '$NODE_TYPE'"
            echo "Usage: $0 <node-type>"
            echo ""
            echo "VPS node types (Hostinger KVM):"
            echo "  kvm4-1            API Gateway (TensorZero, Agent Zero, Hi-RAG CPU)"
            echo "  kvm4-2            Data/Storage (Supabase, Qdrant, Neo4j, Meilisearch)"
            echo "  kvm2              Exit Node (Tailscale exit, Nginx, SSL, RustDesk relay)"
            echo "  gpu-5090          GPU Node (vLLM, Ollama, GPU Orchestrator) — NVIDIA"
            echo ""
            echo "Workstation node types (bare-metal AI lab):"
            echo "  rdna4-workstation AMD Ryzen 9850X3D + dual R9700 (ROCm 7.1 + llama.cpp HIP)"
            echo "  dgx-spark         NVIDIA DGX Spark ARM64 overlay (Ollama + fleet agent)"
            echo "  pve-member        Proxmox VE 9 cluster member (no Docker-on-host; VMs only)"
            echo "  pve-member-fresh  Bare Debian box — install PVE then join as cluster member"
            echo ""
            echo "  auto              Detect via deploy/provision/glances-autodetect.sh"
            echo ""
            echo "Or set PMOVES_AUTODETECT=1 to force detection regardless of argument."
            exit 1
            ;;
    esac
}

# Check required environment variables
check_env() {
    log_section "Checking environment..."

    # GITHUB_PAT required for any node that will run a GitHub Actions runner.
    # pve-member runs NO runner on the hypervisor (VMs do), so skip the check.
    if [ "$NODE_TYPE" != "pve-member" ] && [ "$NODE_TYPE" != "pve-member-fresh" ]; then
        if [ -z "${GITHUB_PAT:-}" ]; then
            log_error "GITHUB_PAT not set. Generate at: https://github.com/settings/tokens/new"
            exit 1
        fi
    fi

    if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
        log_warn "TAILSCALE_AUTHKEY not set. Tailscale setup will be skipped."
        log_info "Generate at: https://login.tailscale.com/admin/settings/keys"
    fi

    if [ -z "${CHIT_PASSPHRASE:-}" ]; then
        log_warn "CHIT_PASSPHRASE not set. Provisioning beacon will be emitted unsigned."
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
        curl wget git jq unzip htop make \
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
        gpu-5090)
            # GPU inference node
            ufw allow 8200/tcp comment "GPU Orchestrator"
            ufw allow 11434/tcp comment "Ollama"
            ufw allow 8100:8160/tcp comment "vLLM model ports"
            ;;
        rdna4-workstation)
            # AMD R9700 inference node — llama.cpp HIP server + metrics
            ufw allow 8080/tcp comment "llama-server (OpenAI-compatible)"
            ufw allow 9835/tcp comment "rocm-smi Prometheus exporter"
            ufw allow 8200/tcp comment "GPU Orchestrator"
            ;;
        dgx-spark)
            # NVIDIA DGX Spark ARM64 — Ollama + fleet agent
            ufw allow 11434/tcp comment "Ollama"
            ufw allow 8200/tcp comment "GPU Orchestrator"
            ;;
        pve-member|pve-member-fresh)
            # Proxmox cluster member — PVE web UI + corosync cluster ports
            ufw allow 8006/tcp comment "PVE Web UI"
            ufw allow 5404:5412/udp comment "Corosync cluster membership"
            ufw allow 22/tcp comment "SSH"
            # Deliberately NO Docker ports — containers run in VMs, not host
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

    if [ "$NODE_TYPE" = "pve-member" ] || [ "$NODE_TYPE" = "pve-member-fresh" ]; then
        log_info "Skipping Docker — PVE cluster members run containers inside VMs/LXCs, not on the host."
        log_info "See pmoves/docs/infrastructure/docker_proxmox_integration.md"
        return 0
    fi

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
    case "$NODE_TYPE" in
        kvm2)
            log_info "Configuring as Tailscale exit node..."
            # Enable IP forwarding for exit node
            sysctl -w net.ipv4.ip_forward=1
            sysctl -w net.ipv6.conf.all.forwarding=1
            cat >> /etc/sysctl.d/99-tailscale.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
            ts_args+=(--advertise-exit-node)
            ts_args+=(--tag=tag:pmoves --tag=tag:kvm --tag=tag:exit)
            ;;
        gpu-5090)
            ts_args+=(--tag=tag:pmoves --tag=tag:gpu --tag=tag:gpu-5090 --tag=tag:production)
            ;;
        rdna4-workstation)
            ts_args+=(--tag=tag:pmoves --tag=tag:gpu --tag=tag:rdna4 --tag=tag:production)
            ;;
        dgx-spark)
            ts_args+=(--tag=tag:pmoves --tag=tag:gpu --tag=tag:spark --tag=tag:arm64 --tag=tag:production)
            ;;
        pve-member|pve-member-fresh)
            ts_args+=(--tag=tag:pmoves --tag=tag:pve --tag=tag:cluster --tag=tag:production)
            ;;
        *)
            ts_args+=(--tag=tag:pmoves --tag=tag:kvm --tag=tag:production)
            ;;
    esac

    tailscale up "${ts_args[@]}"

    # Key expiry: tagged auth keys (--auth-key with tag:server) auto-disable expiry.
    # For untagged keys, disable manually via Admin Console or Tailscale API:
    #   POST /api/v2/device/{deviceID}/key  {"keyExpiryDisabled": true}
    log_info "Key expiry is auto-disabled for tagged auth keys"

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

    if [ "$NODE_TYPE" = "pve-member" ] || [ "$NODE_TYPE" = "pve-member-fresh" ]; then
        log_info "Skipping runner install — GitHub Actions runners live inside PVE VMs, not on the hypervisor."
        return 0
    fi

    # Create runner user if not exists
    if ! id -u runner &>/dev/null; then
        useradd -m -s /bin/bash runner
        if command -v docker &>/dev/null; then
            usermod -aG docker runner
        fi
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
        local runner_version="2.332.0"
        local labels

        case "$NODE_TYPE" in
            kvm4-1) labels="self-hosted,vps,kvm4,kvm4-1,production,Linux,X64" ;;
            kvm4-2) labels="self-hosted,vps,kvm4,kvm4-2,production,Linux,X64" ;;
            kvm2)   labels="self-hosted,vps,kvm2,backup,Linux,X64" ;;
            gpu-5090) labels="self-hosted,vps,gpu,gpu-5090,production,Linux,X64" ;;
            rdna4-workstation) labels="self-hosted,ai-lab,gpu,rdna4,rocm,production,Linux,X64" ;;
            dgx-spark) labels="self-hosted,ai-lab,gpu,spark,arm64,production,Linux,ARM64" ;;
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
            local runner_arch="x64"
            [ "$NODE_TYPE" = "dgx-spark" ] && runner_arch="arm64"
            curl -sL -o actions-runner.tar.gz \
                "https://github.com/actions/runner/releases/download/v${runner_version}/actions-runner-linux-${runner_arch}-${runner_version}.tar.gz"
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
MODEL_NAMESPACE=pmoves
EOF

    log_info "Work directory ready at /opt/pmoves"
}

# Step 5b: RDNA4 GPU stack (only for rdna4-workstation)
install_rdna4_stack() {
    if [ "$NODE_TYPE" != "rdna4-workstation" ]; then
        return 0
    fi

    log_section "Step 5b: Installing RDNA4 (ROCm 7.1 + llama.cpp HIP)..."

    local installer="${SCRIPT_DIR}/rdna4-gpu-install.sh"
    if [ ! -f "$installer" ]; then
        log_error "rdna4-gpu-install.sh not found at: $installer"
        return 1
    fi

    local extra_flags=()
    local gpu_count
    gpu_count="$(lspci -nn 2>/dev/null | grep -iE 'amd.*radeon.*(navi 48|9070|9700)' | wc -l || echo 0)"
    if [ "${gpu_count:-0}" -ge 2 ]; then
        log_info "Detected ${gpu_count} R9700-class GPUs — enabling --dual-gpu"
        extra_flags+=("--dual-gpu")
    fi

    bash "$installer" "${extra_flags[@]}"
    log_info "RDNA4 stack provisioning dispatched (reboot may be required for amdgpu-dkms)."
}

# Step 5c: DGX Spark ARM64 overlay (Ollama + fleet agent only; stock OS retained)
install_dgx_spark_overlay() {
    if [ "$NODE_TYPE" != "dgx-spark" ]; then
        return 0
    fi

    log_section "Step 5c: Installing DGX Spark ARM64 overlay..."

    # Ollama ARM64 install (NVIDIA DGX OS already ships CUDA-on-ARM drivers)
    if ! command -v ollama &>/dev/null; then
        log_info "Installing Ollama (ARM64)..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        log_info "Ollama already installed: $(ollama --version 2>/dev/null || true)"
    fi

    # Expose Ollama on all interfaces (Tailscale ACL gates access)
    mkdir -p /etc/systemd/system/ollama.service.d
    cat >/etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=http://100.64.0.0/10,http://127.0.0.1:*"
EOF
    systemctl daemon-reload
    systemctl enable --now ollama || true

    log_info "DGX Spark overlay ready. Stock NVIDIA DGX OS retained."
}

# Step 5d: PVE cluster-member helper (Tailscale join + cluster prep notes)
install_pve_member_prep() {
    if [ "$NODE_TYPE" != "pve-member" ] && [ "$NODE_TYPE" != "pve-member-fresh" ]; then
        return 0
    fi

    log_section "Step 5d: PVE cluster-member preparation..."

    # Ensure corosync IP forwarding + multicast hints (PVE cluster requirement)
    if ! grep -q 'pve.cluster' /etc/sysctl.d/99-pmoves-pve.conf 2>/dev/null; then
        cat >/etc/sysctl.d/99-pmoves-pve.conf <<'EOF'
# PMOVES PVE cluster member sysctls
net.ipv4.conf.all.rp_filter = 2
EOF
        sysctl --system >/dev/null 2>&1 || true
    fi

    log_info "PVE prep complete. Join cluster with:"
    log_info "  pvecm add <controller-host-or-tailscale-name>"
    log_info "See deploy/proxmox/cluster/join-cluster.sh (created in Phase G)"
}

# Step 6: PMOVES.Flare model namespace & vLLM endpoint
setup_flare_config() {
    log_section "Step 6: Configuring PMOVES.Flare model namespace..."

    local env_file="/opt/pmoves/.env.local"
    touch "$env_file"

    if ! grep -q '^MODEL_NAMESPACE=' "$env_file" 2>/dev/null; then
        cat >> "$env_file" <<'EOF'

# PMOVES.Flare model namespace
MODEL_NAMESPACE=pmoves
EOF
    fi

    case "$NODE_TYPE" in
        gpu-5090)
            if ! grep -q '^VLLM_ENDPOINT=' "$env_file" 2>/dev/null; then
                cat >> "$env_file" <<'EOF'

# vLLM remote GPU endpoint
VLLM_ENDPOINT=http://localhost:8100
VLLM_ENDPOINT_LARGE=http://localhost:8130

# Coding plan lane
GLM_CODING_PLAN_ENABLED=true
EOF
            fi
            ;;
        rdna4-workstation)
            if ! grep -q '^LLAMA_SERVER_ENDPOINT=' "$env_file" 2>/dev/null; then
                cat >> "$env_file" <<'EOF'

# Local llama.cpp HIP server (R9700 / RDNA4 gfx1201)
LLAMA_SERVER_ENDPOINT=http://localhost:8080
INFERENCE_BACKEND=llamacpp-rocm
EOF
            fi
            ;;
        dgx-spark)
            if ! grep -q '^OLLAMA_ENDPOINT=' "$env_file" 2>/dev/null; then
                cat >> "$env_file" <<'EOF'

# Local Ollama on DGX Spark ARM64
OLLAMA_ENDPOINT=http://localhost:11434
INFERENCE_BACKEND=ollama-arm64
EOF
            fi
            ;;
        pve-member|pve-member-fresh)
            # PVE host keeps env minimal — services live in VMs
            :
            ;;
        *)
            if ! grep -q '^VLLM_ENDPOINT=' "$env_file" 2>/dev/null; then
                cat >> "$env_file" <<'EOF'

# vLLM remote GPU endpoint (routed via Tailscale)
VLLM_ENDPOINT=http://pmoves-gpu-5090:8100
VLLM_ENDPOINT_LARGE=http://pmoves-gpu-5090:8130

# Coding plan lane
GLM_CODING_PLAN_ENABLED=true
EOF
            fi
            ;;
    esac

    log_info "PMOVES.Flare model namespace configured (MODEL_NAMESPACE=pmoves)"
}

# CHIT-signed completion beacon — best-effort, skipped if tooling/passphrase absent
emit_provision_beacon() {
    log_section "Emitting provisioning beacon..."

    local sign_trail="/opt/pmoves/pmoves/tools/sign_trail.py"
    if [ -x "$sign_trail" ] && [ -n "${CHIT_PASSPHRASE:-}" ]; then
        python3 "$sign_trail" \
            --agent-id "hostinger-kvm-setup" \
            --summary "Provisioned $NODE_TYPE on $(hostname)" \
            --phase "Phase A" 2>/dev/null \
            || log_warn "CHIT beacon emit failed (non-fatal)"
    else
        log_info "CHIT beacon skipped (sign_trail.py or CHIT_PASSPHRASE absent)"
    fi
}

# Show summary
show_summary() {
    log_section "========================================="
    log_section "Provisioning Complete: $NODE_TYPE"
    log_section "========================================="

    echo ""
    if [ "$AUTODETECT_RAN" -eq 1 ]; then
        log_info "Node-type resolved via autodetect: ${AUTODETECT_SUGGESTION}"
    fi
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
        gpu-5090)
            echo "  1. Install NVIDIA drivers: apt-get install -y nvidia-driver-550"
            echo "  2. Start GPU stack: cd /opt/pmoves/pmoves && make -C pmoves up-gpu"
            echo "  3. Verify orchestrator: curl http://localhost:8200/healthz"
            echo "  4. Pull a model:  curl http://localhost:11434/api/pull -d '{\"name\":\"qwen3-coder:32b\"}'"
            ;;
        rdna4-workstation)
            echo "  1. Reboot to activate amdgpu-dkms kernel module"
            echo "  2. Verify ROCm: rocminfo | head -40"
            echo "  3. Pull a model: make -C pmoves rdna4-model-pull  (or manual: huggingface-cli download)"
            echo "  4. Start llama-server: systemctl start llama-server"
            echo "  5. Smoke test: curl http://localhost:8080/v1/models"
            echo "  6. GPU metrics: curl http://localhost:9835/"
            ;;
        dgx-spark)
            echo "  1. Verify CUDA-on-ARM: nvidia-smi  (stock DGX OS ships drivers)"
            echo "  2. Pull a model: ollama pull gemma2:27b"
            echo "  3. Smoke test: curl http://localhost:11434/api/tags"
            echo "  4. Ensure Tailscale tag:spark is approved in ACL"
            ;;
        pve-member|pve-member-fresh)
            echo "  1. Join PVE cluster: pvecm add <controller-tailscale-hostname>"
            echo "  2. Verify membership: pvecm status"
            echo "  3. Configure storage (ZFS or Ceph): see deploy/proxmox/cluster/ (Phase G)"
            echo "  4. Enable HA for critical VMs: see PROXMOX_CLUSTER_RUNBOOK.md (Phase G)"
            ;;
    esac
    echo ""
    echo "  Runner status: sudo systemctl status github-runner-pmoves-${NODE_TYPE}"
    echo "  Runner logs:   sudo journalctl -u github-runner-pmoves-${NODE_TYPE} -f"
}

# Main
main() {
    autodetect_node_type
    validate_node_type
    check_env

    log_section "========================================="
    log_section "PMOVES.AI KVM Provisioning: $NODE_TYPE"
    log_section "========================================="

    # pve-member-fresh: bare Debian box needs PVE installed first
    if [ "$NODE_TYPE" = "pve-member-fresh" ]; then
        log_section "Installing Proxmox VE on bare Debian..."
        if [ -x "${SCRIPT_DIR:-.}/pve_on_debian13.sh" ]; then
            bash "${SCRIPT_DIR:-.}/pve_on_debian13.sh"
        else
            log_error "pve_on_debian13.sh not found in ${SCRIPT_DIR:-.} — cannot provision pve-member-fresh"
            exit 1
        fi
        log_info "PVE installed. Continuing as pve-member..."
    fi

    echo ""

    harden_system
    install_docker
    install_tailscale
    install_runner
    setup_workdir
    install_rdna4_stack
    install_dgx_spark_overlay
    install_pve_member_prep
    setup_flare_config
    emit_provision_beacon
    show_summary
}

main "$@"
