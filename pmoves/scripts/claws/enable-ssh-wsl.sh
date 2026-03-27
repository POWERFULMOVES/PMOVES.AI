#!/usr/bin/env bash
# enable-ssh-wsl.sh — Enable SSH server + inject authorized key in WSL
# Usage: ./enable-ssh-wsl.sh [pubkey]
#
# Run inside WSL on the target machine.
# This script:
#   1. Installs openssh-server if not present
#   2. Starts sshd
#   3. Injects the provided public key
#   4. Sets correct permissions

set -euo pipefail

PUBKEY="${1:-ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILwNwCmQKDS3c6LuRRLKf60yQHfLyUINnU1Z1eTytcrf pmoves-claw@pmoves.ai}"

echo "=== PMOVES SSH Setup for WSL ==="

# 1. Install openssh-server
echo "[1/4] Checking openssh-server..."
if ! which sshd > /dev/null 2>&1; then
    echo "  Installing openssh-server..."
    sudo apt-get update -qq && sudo apt-get install -y -qq openssh-server
else
    echo "  openssh-server already installed"
fi

# 2. Start sshd
echo "[2/4] Starting sshd..."
sudo service ssh start 2>/dev/null || sudo systemctl start ssh 2>/dev/null || echo "  WARNING: Could not start sshd"

# Verify it's running
if pgrep -x sshd > /dev/null; then
    echo "  sshd: Running (PID $(pgrep -x sshd | head -1))"
else
    echo "  ERROR: sshd not running"
    exit 1
fi

# 3. Inject authorized key
echo "[3/4] Injecting authorized key..."
SSH_DIR="$HOME/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
printf '%s\n' "$PUBKEY" > "$SSH_DIR/authorized_keys"
chmod 600 "$SSH_DIR/authorized_keys"
echo "  Key written to: $SSH_DIR/authorized_keys"

# 4. Verify
echo "[4/4] Verifying..."
echo "  User: $(whoami)"
echo "  Home: $HOME"
echo "  Key lines: $(wc -l < "$SSH_DIR/authorized_keys")"
echo "  sshd port: $(grep -E '^Port ' /etc/ssh/sshd_config 2>/dev/null || echo '22 (default)')"

# Check GPU
if which nvidia-smi > /dev/null 2>&1; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "not visible")
    echo "  GPU: $GPU"
else
    echo "  GPU: nvidia-smi not found"
fi

echo ""
echo "=== SSH Setup Complete ==="
TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
echo "Test from Z890: ssh -i /tmp/hostinger_vps $(whoami)@$TS_IP"
echo ""
