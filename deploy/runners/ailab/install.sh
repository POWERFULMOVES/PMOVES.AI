#!/bin/bash
# GitHub Actions Self-Hosted Runner Installation for AI Lab (GPU-enabled)
#
# This script installs a GitHub Actions runner with GPU support on the AI Lab machine.
# Supports: RTX 5090, 4090, 3090 Ti
#
# Prerequisites:
#   - NVIDIA drivers installed
#   - Docker with NVIDIA Container Toolkit
#   - GitHub PAT with admin:org or repo scope
#
# Usage:
#   GITHUB_PAT=ghp_xxx ./install.sh [--containerized]
#
# Labels applied:
#   self-hosted, ai-lab, gpu, cuda, linux, x64

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
RUNNER_VERSION="${RUNNER_VERSION:-2.311.0}"
RUNNER_ARCH="linux-x64"
GITHUB_ORG="${GITHUB_ORG:-frostbytten}"
GITHUB_REPO="${GITHUB_REPO:-PMOVES.AI}"
RUNNER_NAME="${RUNNER_NAME:-ailab-gpu}"
LABELS="self-hosted,ai-lab,gpu,cuda,linux,x64"

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

check_prerequisites() {
    log_section "Checking prerequisites..."

    # Check for root or sudo
    if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
        log_error "This script requires root or sudo access"
        exit 1
    fi

    # Check NVIDIA drivers
    if ! command -v nvidia-smi &> /dev/null; then
        log_error "nvidia-smi not found. Please install NVIDIA drivers first."
        exit 1
    fi

    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
    log_info "GPU detected: $GPU_INFO"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi

    # Check NVIDIA Container Toolkit
    if ! docker info 2>/dev/null | grep -q "nvidia"; then
        log_warn "NVIDIA Container Toolkit may not be configured"
        log_info "Install with: distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)"
        log_info "             curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -"
        log_info "             curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
        log_info "             sudo apt-get update && sudo apt-get install -y nvidia-docker2"
    fi

    # Check GitHub PAT
    if [ -z "$GITHUB_PAT" ]; then
        log_error "GITHUB_PAT environment variable not set"
        log_info "Create a PAT at: https://github.com/settings/tokens/new"
        log_info "Required scopes: repo (for repo runner) or admin:org (for org runner)"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

get_runner_token() {
    log_section "Obtaining runner registration token..."

    # Try repo-level first, fall back to org-level
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

install_runner_native() {
    log_section "Installing GitHub Actions runner (native)..."

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

    local service_file="/etc/systemd/system/github-runner-ailab.service"

    sudo tee "$service_file" > /dev/null <<EOF
[Unit]
Description=GitHub Actions Runner (AI Lab GPU)
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

# GPU support
Environment=NVIDIA_VISIBLE_DEVICES=all
Environment=NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Resource limits
LimitNOFILE=65536
LimitNPROC=65536

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable github-runner-ailab
    sudo systemctl start github-runner-ailab

    log_info "Systemd service installed and started"

    # Show status
    sudo systemctl status github-runner-ailab --no-pager || true
}

install_runner_containerized() {
    log_section "Installing GitHub Actions runner (containerized)..."

    local compose_dir="${SCRIPT_DIR}"

    # Create docker-compose.yml for containerized runner
    cat > "${compose_dir}/docker-compose.yml" <<EOF
version: '3.8'

services:
  github-runner:
    image: myoung34/github-runner:latest
    container_name: github-runner-ailab
    restart: unless-stopped
    environment:
      - RUNNER_NAME=${RUNNER_NAME}
      - RUNNER_TOKEN=${RUNNER_TOKEN}
      - RUNNER_REPOSITORY_URL=https://github.com/${GITHUB_ORG}/${GITHUB_REPO}
      - RUNNER_LABELS=${LABELS}
      - RUNNER_WORKDIR=/work
      - DISABLE_AUTO_UPDATE=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - runner-work:/work
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  runner-work:
EOF

    log_info "Starting containerized runner..."
    docker compose -f "${compose_dir}/docker-compose.yml" up -d

    log_info "Containerized runner started"
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
    log_info "Test GPU in workflow:"
    echo "  jobs:"
    echo "    gpu-test:"
    echo "      runs-on: [self-hosted, ai-lab, gpu]"
    echo "      steps:"
    echo "        - run: nvidia-smi"
}

# Main
main() {
    log_section "========================================="
    log_section "AI Lab GPU Runner Installation"
    log_section "========================================="

    local containerized=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --containerized)
                containerized=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    check_prerequisites
    get_runner_token

    if [ "$containerized" = true ]; then
        install_runner_containerized
    else
        install_runner_native
        install_systemd_service
    fi

    show_verification
}

main "$@"
