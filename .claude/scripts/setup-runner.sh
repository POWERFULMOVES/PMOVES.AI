#!/bin/bash
# PMOVES.AI Self-Hosted Runner Setup Script
# Generated: 2025-12-23
#
# Usage: ./setup-runner.sh <HOST_TYPE>
# Where HOST_TYPE is one of: ai-lab, vps, cloudstartup, kvm4

set -e

HOST_TYPE="${1:-}"
REPO_URL="https://github.com/POWERFULMOVES/PMOVES.AI"
RUNNER_VERSION="2.321.0"

# Registration token (valid for 1 hour from generation)
# Generate with: gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token -X POST --jq '.token'
REG_TOKEN="${RUNNER_TOKEN:?RUNNER_TOKEN environment variable is required}"

# Host-specific labels
declare -A HOST_LABELS
HOST_LABELS["ai-lab"]="self-hosted,ai-lab,gpu,Linux,X64"
HOST_LABELS["vps"]="self-hosted,vps,Linux,X64"
HOST_LABELS["cloudstartup"]="self-hosted,cloudstartup,staging,Linux,X64"
HOST_LABELS["kvm4"]="self-hosted,kvm4,production,Linux,X64"

if [[ -z "$HOST_TYPE" ]] || [[ ! ${HOST_LABELS[$HOST_TYPE]+_} ]]; then
    echo "Usage: $0 <HOST_TYPE>"
    echo "HOST_TYPE must be one of: ai-lab, vps, cloudstartup, kvm4"
    exit 1
fi

LABELS="${HOST_LABELS[$HOST_TYPE]}"
RUNNER_NAME="pmoves-${HOST_TYPE}-runner"

echo "=== PMOVES.AI Self-Hosted Runner Setup ==="
echo "Host Type: $HOST_TYPE"
echo "Runner Name: $RUNNER_NAME"
echo "Labels: $LABELS"
echo ""

# Create runner directory
RUNNER_DIR="$HOME/actions-runner-${HOST_TYPE}"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download runner if not present
if [[ ! -f "./config.sh" ]]; then
    echo "Downloading GitHub Actions Runner v${RUNNER_VERSION}..."
    curl -sL -o actions-runner.tar.gz \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
    tar xzf actions-runner.tar.gz
    rm actions-runner.tar.gz
fi

# Configure runner
echo "Configuring runner..."
./config.sh --url "$REPO_URL" \
    --token "$REG_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$LABELS" \
    --work "_work" \
    --replace

# Install as service
echo "Installing runner as system service..."
sudo ./svc.sh install
sudo ./svc.sh start

echo ""
echo "=== Runner Setup Complete ==="
echo "Runner Name: $RUNNER_NAME"
echo "Status: $(sudo ./svc.sh status)"
echo ""
echo "To check status: sudo ./svc.sh status"
echo "To stop: sudo ./svc.sh stop"
echo "To uninstall: sudo ./svc.sh uninstall"
