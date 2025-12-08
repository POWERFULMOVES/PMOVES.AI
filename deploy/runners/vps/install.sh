#!/bin/bash
# GitHub Actions Self-Hosted Runner Installation for VPS (CPU-only)
#
# This script installs a GitHub Actions runner on Hostinger VPS servers.
# Supports: cloudstartup, kvm4, kvm2
#
# Prerequisites:
#   - Docker installed
#   - GitHub PAT with admin:org or repo scope
#
# Usage:
#   GITHUB_PAT=ghp_xxx RUNNER_NAME=cloudstartup ./install.sh
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

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_warn "Docker not found. Installing..."
        curl -fsSL https://get.docker.com | sudo sh
        sudo usermod -aG docker "$USER"
        log_info "Docker installed. You may need to log out and back in."
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

    # Configure runner
    log_info "Configuring runner..."
    ./config.sh \
        --url "https://github.com/${GITHUB_ORG}/${GITHUB_REPO}" \
        --token "$RUNNER_TOKEN" \
        --name "$RUNNER_NAME" \
        --labels "$LABELS" \
        --work "_work" \
        --replace \
        --unattended

    log_info "Runner configured successfully"
}

install_systemd_service() {
    log_section "Installing systemd service..."

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

# Resource limits
LimitNOFILE=65536
LimitNPROC=65536

# Memory limit for VPS (adjust as needed)
MemoryMax=2G

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

setup_docker_cleanup() {
    log_section "Setting up Docker cleanup cron..."

    # Add weekly Docker cleanup to prevent disk space issues
    local cron_file="/etc/cron.weekly/docker-cleanup"

    sudo tee "$cron_file" > /dev/null <<'EOF'
#!/bin/bash
# Clean up Docker resources weekly
docker system prune -af --volumes --filter "until=168h"
docker builder prune -af --filter "until=168h"
EOF

    sudo chmod +x "$cron_file"
    log_info "Docker cleanup cron installed"
}

show_verification() {
    log_section "Verification"

    echo ""
    log_info "Runner installation complete!"
    echo ""
    log_info "Verify at: https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/settings/actions/runners"
    echo ""
    log_info "Runner details:"
    echo "  Name:   $RUNNER_NAME"
    echo "  Labels: $LABELS"
    echo "  Dir:    $RUNNER_DIR"
    echo ""
    log_info "Service management:"
    echo "  Status:  sudo systemctl status github-runner-${RUNNER_NAME}"
    echo "  Logs:    sudo journalctl -u github-runner-${RUNNER_NAME} -f"
    echo "  Restart: sudo systemctl restart github-runner-${RUNNER_NAME}"
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
}

# Main
main() {
    log_section "========================================="
    log_section "VPS Runner Installation: $RUNNER_NAME"
    log_section "========================================="

    check_prerequisites
    get_runner_token
    install_runner
    install_systemd_service
    setup_docker_cleanup
    show_verification
}

main "$@"
