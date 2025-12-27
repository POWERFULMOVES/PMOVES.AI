#!/bin/bash
# GitHub Actions Self-Hosted Runner Installation for VPS (Hardened)
#
# This script installs a hardened GitHub Actions runner on Hostinger VPS servers.
# Supports: cloudstartup, kvm4, kvm2
#
# Hardening Features:
#   - Rootless Docker (daemon runs as non-root)
#   - cgroupsV2 resource isolation
#   - Optional JIT ephemeral runner mode
#
# Prerequisites:
#   - GitHub PAT with admin:org or repo scope
#
# Usage:
#   GITHUB_PAT=ghp_xxx RUNNER_NAME=cloudstartup ./install-hardened.sh [--jit]
#
# Labels applied based on RUNNER_NAME:
#   cloudstartup: self-hosted, vps, cloudstartup, staging, linux, x64
#   kvm4:         self-hosted, vps, kvm4, production, linux, x64
#   kvm2:         self-hosted, vps, kvm2, backup, linux, x64

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
RUNNER_VERSION="${RUNNER_VERSION:-2.311.0}"
RUNNER_ARCH="linux-x64"
GITHUB_ORG="${GITHUB_ORG:-frostbytten}"
GITHUB_REPO="${GITHUB_REPO:-PMOVES.AI}"
RUNNER_NAME="${RUNNER_NAME:-vps-$(hostname)}"
JIT_MODE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "${BLUE}[====]${NC} $1"; }

# Determine labels based on runner name
get_labels() {
    local base_labels="self-hosted,vps,linux,x64"

    case "$RUNNER_NAME" in
        *cloudstartup*)
            echo "${base_labels},cloudstartup,staging"
            ;;
        *kvm4*)
            echo "${base_labels},kvm4,production"
            ;;
        *kvm2*)
            echo "${base_labels},kvm2,backup"
            ;;
        *)
            echo "${base_labels}"
            ;;
    esac
}

LABELS=$(get_labels)

check_prerequisites() {
    log_section "Checking prerequisites..."

    # Check for root or sudo
    if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
        log_error "This script requires root or sudo access"
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_info "Installing jq..."
        sudo apt-get update && sudo apt-get install -y jq
    fi

    # Check GitHub PAT
    if [ -z "$GITHUB_PAT" ]; then
        log_error "GITHUB_PAT environment variable not set"
        log_info "Create a PAT at: https://github.com/settings/tokens/new"
        log_info "Required scopes: repo (for repo runner) or admin:org (for org runner)"
        exit 1
    fi

    # Show system info
    log_info "System info:"
    echo "  Hostname: $(hostname)"
    echo "  CPU:      $(nproc) cores"
    echo "  Memory:   $(free -h | awk '/^Mem:/{print $2}')"
    echo "  Disk:     $(df -h / | awk 'NR==2{print $4}') available"

    log_info "Prerequisites check passed"
}

check_cgroups_v2() {
    log_section "Checking cgroupsV2 configuration..."

    # Check if cgroupsV2 is already enabled
    if mount | grep -q "cgroup2 on /sys/fs/cgroup type cgroup2"; then
        log_info "cgroupsV2 already enabled"
        return 0
    fi

    log_warn "cgroupsV2 not enabled. This provides resource isolation for containers."
    log_info "cgroupsV2 benefits:"
    echo "  - CPU/memory limits enforcement"
    echo "  - Prevention of resource exhaustion attacks"
    echo "  - Better container performance monitoring"
    echo ""

    read -p "Enable cgroupsV2? (requires reboot) [y/N]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Configuring cgroupsV2..."

        # Backup GRUB config
        sudo cp /etc/default/grub /etc/default/grub.backup.$(date +%Y%m%d-%H%M%S)

        # Update GRUB configuration
        sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"/' /etc/default/grub
        sudo update-grub

        log_warn "System configuration updated. Reboot required."
        log_info "After reboot, re-run this script to complete installation:"
        echo "  GITHUB_PAT=\$GITHUB_PAT RUNNER_NAME=$RUNNER_NAME ./install-hardened.sh"
        echo ""

        read -p "Reboot now? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Rebooting..."
            sudo reboot
        else
            log_warn "Please reboot manually and re-run the script."
            exit 0
        fi
    else
        log_warn "Skipping cgroupsV2 configuration. Proceeding without resource isolation."
    fi
}

install_rootless_docker() {
    log_section "Installing rootless Docker..."

    # Check if Docker is already installed
    if command -v docker &> /dev/null; then
        # Check if it's rootless
        if [ -S "/run/user/$(id -u)/docker.sock" ]; then
            log_info "Rootless Docker already installed"
            return 0
        else
            log_warn "Standard Docker detected. Rootless Docker is recommended for security."
            log_info "Rootless Docker benefits:"
            echo "  - Prevents privilege escalation attacks"
            echo "  - Daemon runs as non-root user"
            echo "  - Reduces container breakout risks"
            echo ""

            read -p "Install rootless Docker (will not remove existing Docker)? [y/N]: " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_warn "Keeping standard Docker. Security posture reduced."
                return 0
            fi
        fi
    fi

    log_info "Installing rootless Docker..."

    # Install prerequisites
    sudo apt-get update
    sudo apt-get install -y \
        uidmap \
        dbus-user-session \
        fuse-overlayfs \
        slirp4netns

    # Install rootless Docker
    curl -fsSL https://get.docker.com/rootless | sh

    # Configure environment
    export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
    export PATH=/home/$USER/bin:$PATH
    export DOCKER_BUILDKIT=1

    # Make environment persistent
    cat >> ~/.bashrc <<EOF

# Rootless Docker configuration
export DOCKER_HOST=unix:///run/user/\$(id -u)/docker.sock
export PATH=/home/$USER/bin:\$PATH
export DOCKER_BUILDKIT=1
EOF

    # Enable and start Docker service
    systemctl --user enable docker
    systemctl --user start docker
    sudo loginctl enable-linger "$USER"

    log_info "Rootless Docker installed successfully"
    log_info "Docker socket: /run/user/$(id -u)/docker.sock"

    # Verify installation
    if docker version &> /dev/null; then
        log_info "Docker verification: ✓"
    else
        log_warn "Docker verification failed. You may need to log out and back in."
    fi
}

get_runner_token() {
    log_section "Obtaining runner registration token..."

    local token_url="https://api.github.com/repos/${GITHUB_ORG}/${GITHUB_REPO}/actions/runners/registration-token"

    RUNNER_TOKEN=$(curl -sf -X POST \
        -H "Authorization: token ${GITHUB_PAT}" \
        -H "Accept: application/vnd.github.v3+json" \
        "$token_url" | jq -r '.token')

    if [ -z "$RUNNER_TOKEN" ] || [ "$RUNNER_TOKEN" = "null" ]; then
        log_error "Failed to obtain runner token. Check your GITHUB_PAT permissions."
        exit 1
    fi

    log_info "Runner token obtained successfully"
}

install_runner() {
    log_section "Installing GitHub Actions runner..."

    # Create runner directory
    sudo mkdir -p "$RUNNER_DIR"
    sudo chown "$USER:$USER" "$RUNNER_DIR"
    cd "$RUNNER_DIR"

    # Download runner
    local runner_url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    if [ ! -f "run.sh" ]; then
        log_info "Downloading runner v${RUNNER_VERSION}..."
        curl -sL "$runner_url" -o runner.tar.gz
        tar xzf runner.tar.gz
        rm runner.tar.gz
    else
        log_info "Runner already downloaded, skipping..."
    fi

    # Install dependencies
    log_info "Installing dependencies..."
    sudo ./bin/installdependencies.sh || true

    if [ "$JIT_MODE" = true ]; then
        log_info "JIT mode selected. Runner will be configured via systemd service."
    else
        # Configure persistent runner
        log_info "Configuring persistent runner..."
        ./config.sh \
            --url "https://github.com/${GITHUB_ORG}/${GITHUB_REPO}" \
            --token "$RUNNER_TOKEN" \
            --name "$RUNNER_NAME" \
            --labels "$LABELS" \
            --work "_work" \
            --replace \
            --unattended

        log_info "Runner configured successfully"
    fi
}

install_systemd_service_persistent() {
    log_section "Installing systemd service (persistent mode)..."

    local service_name="github-runner-${RUNNER_NAME}"
    local service_file="/etc/systemd/system/${service_name}.service"

    sudo tee "$service_file" > /dev/null <<EOF
[Unit]
Description=GitHub Actions Runner (${RUNNER_NAME})
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${RUNNER_DIR}
ExecStart=${RUNNER_DIR}/run.sh
Restart=always
RestartSec=10
Environment=RUNNER_ALLOW_RUNASROOT=0
Environment=DOCKER_HOST=unix:///run/user/%U/docker.sock
Environment=PATH=/home/${USER}/bin:/usr/local/bin:/usr/bin:/bin
Environment=DOCKER_BUILDKIT=1

# Resource limits (prevent runaway jobs)
LimitNOFILE=65536
LimitNPROC=65536
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$service_name"
    sudo systemctl start "$service_name"

    log_info "Systemd service installed and started"

    # Show status
    sudo systemctl status "$service_name" --no-pager || true
}

install_systemd_service_jit() {
    log_section "Installing systemd service (JIT ephemeral mode)..."

    local service_name="github-runner-${RUNNER_NAME}"
    local service_file="/etc/systemd/system/${service_name}.service"

    log_warn "JIT mode: Runner will self-destruct after each job and restart automatically."
    log_info "This provides maximum security by eliminating cross-job contamination."

    sudo tee "$service_file" > /dev/null <<EOF
[Unit]
Description=GitHub Actions JIT Runner (${RUNNER_NAME})
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${RUNNER_DIR}
Environment=GITHUB_PAT=${GITHUB_PAT}
Environment=GITHUB_ORG=${GITHUB_ORG}
Environment=GITHUB_REPO=${GITHUB_REPO}
Environment=RUNNER_LABELS=${LABELS}
Environment=DOCKER_HOST=unix:///run/user/%U/docker.sock
Environment=PATH=/home/${USER}/bin:/usr/local/bin:/usr/bin:/bin
Environment=DOCKER_BUILDKIT=1

# Generate JIT config and run (ephemeral runner)
ExecStart=/bin/bash -c '\
    RUNNER_ID="${RUNNER_NAME}-\$(date +%%s)"; \
    echo "Requesting JIT runner: \$RUNNER_ID"; \
    JIT_CONFIG=\$(curl -sf -X POST \
        -H "Authorization: token \$GITHUB_PAT" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/\$GITHUB_ORG/\$GITHUB_REPO/actions/runners/generate-jitconfig" \
        -d "{\"name\": \"\$RUNNER_ID\", \"runner_group_id\": 1, \"labels\": [\$(echo "\$RUNNER_LABELS" | sed "s/,/\",\"/g" | sed "s/^/\"/;s/\$/\"/")], \"work_folder\": \"_work\"}" \
        | jq -r ".encoded_jit_config"); \
    if [ -z "\$JIT_CONFIG" ] || [ "\$JIT_CONFIG" = "null" ]; then \
        echo "Failed to obtain JIT config"; \
        exit 1; \
    fi; \
    echo "Starting JIT runner..."; \
    ${RUNNER_DIR}/run.sh --jitconfig "\$JIT_CONFIG"'

Restart=always
RestartSec=30

# Resource limits
LimitNOFILE=65536
LimitNPROC=65536
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$service_name"
    sudo systemctl start "$service_name"

    log_info "JIT runner service installed and started"
    log_info "Runner will request new JIT config for each job"

    # Show status
    sleep 2
    sudo systemctl status "$service_name" --no-pager || true
}

setup_docker_cleanup() {
    log_section "Setting up Docker cleanup cron..."

    # Add weekly Docker cleanup to prevent disk space issues
    local cron_file="/etc/cron.weekly/docker-cleanup"

    sudo tee "$cron_file" > /dev/null <<'EOF'
#!/bin/bash
# Clean up Docker resources weekly (rootless Docker compatible)
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
docker system prune -af --volumes --filter "until=168h"
docker builder prune -af --filter "until=168h"
EOF

    sudo chmod +x "$cron_file"
    log_info "Docker cleanup cron installed (runs weekly)"
}

show_verification() {
    log_section "Installation Complete!"

    echo ""
    log_info "Runner details:"
    echo "  Name:   $RUNNER_NAME"
    echo "  Labels: $LABELS"
    echo "  Dir:    $RUNNER_DIR"
    echo "  Mode:   $([ "$JIT_MODE" = true ] && echo "JIT Ephemeral" || echo "Persistent")"
    echo ""
    log_info "Verify at: https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/settings/actions/runners"
    echo ""
    log_info "Service management:"
    echo "  Status:  sudo systemctl status github-runner-${RUNNER_NAME}"
    echo "  Logs:    sudo journalctl -u github-runner-${RUNNER_NAME} -f"
    echo "  Restart: sudo systemctl restart github-runner-${RUNNER_NAME}"
    echo ""
    log_info "Docker configuration:"
    echo "  Socket:  /run/user/$(id -u)/docker.sock"
    echo "  Test:    docker run --rm hello-world"
    echo ""
    log_info "Use in workflow:"

    case "$RUNNER_NAME" in
        *cloudstartup*)
            echo "  runs-on: [self-hosted, cloudstartup, staging]"
            ;;
        *kvm4*)
            echo "  runs-on: [self-hosted, kvm4, production]"
            ;;
        *kvm2*)
            echo "  runs-on: [self-hosted, kvm2, backup]"
            ;;
        *)
            echo "  runs-on: [self-hosted, vps]"
            ;;
    esac
    echo ""

    if [ "$JIT_MODE" = true ]; then
        log_info "Security notes (JIT mode):"
        echo "  ✓ Ephemeral runners eliminate cross-job contamination"
        echo "  ✓ Each job runs on a fresh runner instance"
        echo "  ✓ Runner self-destructs after job completion"
    else
        log_warn "Security notes (Persistent mode):"
        echo "  ⚠ Runner persists between jobs"
        echo "  ⚠ Consider migrating to JIT mode for maximum security"
        echo "  → Re-run with --jit flag to enable ephemeral runners"
    fi
}

# Main
main() {
    log_section "========================================="
    log_section "Hardened VPS Runner Installation"
    log_section "Runner: $RUNNER_NAME"
    log_section "========================================="

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --jit)
                JIT_MODE=true
                log_info "JIT ephemeral mode enabled"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    check_prerequisites
    check_cgroups_v2
    install_rootless_docker
    get_runner_token
    install_runner

    if [ "$JIT_MODE" = true ]; then
        install_systemd_service_jit
    else
        install_systemd_service_persistent
    fi

    setup_docker_cleanup
    show_verification
}

main "$@"
