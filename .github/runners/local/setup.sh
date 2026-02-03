#!/bin/bash
# PMOVES.AI Local Self-Hosted GitHub Actions Runner Setup
#
# This script sets up a local GitHub Actions runner for PMOVES.AI development.
# Local runners enable faster iteration and testing without consuming cloud minutes.
#
# Usage:
#   ./setup.sh
#
# Prerequisites:
#   - Docker installed and running
#   - GitHub PAT with repo:admin scope
#   - RUNNER_TOKEN generated from GitHub Settings > Actions > Runners

set -euo pipefail

# Configuration
REPO_OWNER="${REPO_OWNER:-POWERFULMOVES}"
REPO_NAME="${REPO_NAME:-PMOVES.AI}"
RUNNER_NAME="${RUNNER_NAME:-local-dev}"
RUNNER_WORKDIR="${RUNNER_WORKDIR:-/tmp/runner-work}"
RUNNER_VERSION="${RUNNER_VERSION:-2.319.1}"
RUNNER_ARCH="${RUNNER_ARCH:-x64}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker."
        exit 1
    fi

    log_info "✓ Docker is installed and running"

    # Check for required tools
    for tool in curl jq tar; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is not installed. Please install $tool first."
            exit 1
        fi
    done

    log_info "✓ Required tools are available"
}

# Get runner token
get_runner_token() {
    log_info "To configure the runner, we need a runner token."
    log_info ""
    log_info "1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/actions/runners"
    log_info "2. Click 'New self-hosted runner'"
    log_info "3. Select 'Linux' and 'x64'"
    log_info "4. Copy the token below"
    log_info ""

    read -p "Enter runner token: " RUNNER_TOKEN

    if [[ -z "$RUNNER_TOKEN" ]]; then
        log_error "Runner token is required."
        exit 1
    fi

    export RUNNER_TOKEN
}

# Download and configure runner
setup_runner() {
    log_info "Setting up GitHub Actions runner..."

    # Create work directory
    mkdir -p "$RUNNER_WORKDIR"

    # Create runner directory
    RUNNER_DIR="/tmp/actions-runner"
    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"

    # Download runner
    log_info "Downloading Actions Runner v${RUNNER_VERSION}..."
    RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    if [[ ! -f "actions-runner.tar.gz" ]]; then
        curl -o actions-runner.tar.gz -L "$RUNNER_URL"
    fi

    # Extract runner
    log_info "Extracting runner..."
    tar xzf ./actions-runner.tar.gz

    # Configure runner
    log_info "Configuring runner: ${RUNNER_NAME}"
    ./config.sh \
        --url "https://github.com/${REPO_OWNER}/${REPO_NAME}" \
        --token "$RUNNER_TOKEN" \
        --name "$RUNNER_NAME" \
        --labels "self-hosted,local,linux,x64" \
        --work "$RUNNER_WORKDIR" \
        --replace

    log_info "✓ Runner configured successfully"
}

# Install as service (optional)
install_service() {
    log_info "Do you want to install the runner as a system service?"
    log_info "This will start the runner automatically on boot."

    read -p "Install as service? (y/N): " INSTALL_SERVICE

    if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
        log_info "Installing runner service..."
        ./svc.sh install
        ./svc.sh start
        log_info "✓ Runner service installed and started"
    else
        log_info "You can start the runner manually with:"
        log_info "  cd $RUNNER_DIR && ./run.sh"
    fi
}

# Display runner info
show_info() {
    log_info ""
    log_info "==================================="
    log_info "Runner Setup Complete!"
    log_info "==================================="
    log_info ""
    log_info "Runner Name: ${RUNNER_NAME}"
    log_info "Runner Labels: self-hosted, local, linux, x64"
    log_info "Work Directory: ${RUNNER_WORKDIR}"
    log_info ""
    log_info "Runner URL: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/actions/runners"
    log_info ""
    log_info "To remove the runner later:"
    log_info "  cd ${RUNNER_DIR} && ./config.sh remove --token ${RUNNER_TOKEN}"
    log_info ""
}

# Main execution
main() {
    log_info "PMOVES.AI Local GitHub Actions Runner Setup"
    log_info "=========================================="
    log_info ""

    check_prerequisites
    get_runner_token
    setup_runner
    install_service
    show_info
}

main "$@"
