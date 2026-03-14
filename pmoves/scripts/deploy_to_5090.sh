#!/usr/bin/env bash
# Deploy PMOVES-Tailscale to 5090 PC (POWERFULMOVES)
# Usage: ./pmoves/scripts/deploy_to_5090.sh

set -euo pipefail

# 5090 PC Configuration
PC_IP="192.168.1.65"
PC_USER="Administrator"  # Change if needed
DEPLOY_DIR="C:\\PMOVES-Tailscale"

echo "=== PMOVES Tailscale Deployment for 5090 PC ==="
echo "Target: $PC_IP ($PC_USER)"
echo ""

# Check if we can reach the PC
echo "[1/5] Testing network connectivity..."
if ping -c 1 -W 2 "$PC_IP" &>/dev/null; then
    echo "✅ 5090 PC is reachable"
else
    echo "❌ Cannot reach 5090 PC at $PC_IP"
    echo "   Check if the PC is on and network is connected"
    exit 1
fi

# Create deployment directory on 5090
echo "[2/5] Creating deployment directory..."
# Using PowerShell for Windows directory creation
powershell.exe -Command "
    if (-not (Test-Path '$DEPLOY_DIR')) {
        New-Item -ItemType Directory -Path '$DEPLOY_DIR' -Force | Out-Null
        Write-Host '✅ Created deployment directory'
    } else {
        Write-Host '✅ Deployment directory exists'
    }
" || {
    echo "❌ Failed to create deployment directory"
    echo "   You may need to enable PowerShell remoting or create directory manually"
    exit 1
}

# Copy deployment files
echo "[3/5] Copying deployment files..."
TAILSCALE_DIR="../PMOVES-Tailscale"

if [[ ! -d "$TAILSCALE_DIR" ]]; then
    echo "❌ PMOVES-Tailscale submodule not found at $TAILSCALE_DIR"
    echo "   Run: git submodule update --init --recursive"
    exit 1
fi

# Files to copy
FILES=(
    "$TAILSCALE_DIR/deploy/deploy.ps1"
    "$TAILSCALE_DIR/deploy/profiles/workstation.env"
)

for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        filename=$(basename "$file")
        echo "   → $filename"
        # For Windows, we'd typically use SCP or SMB
        # This is a placeholder - user needs to copy manually or use SCP
        echo "   (Manual copy required: $file → $DEPLOY_DIR)"
    fi
done

echo ""
echo "⚠️  Automatic file copy not available in this environment"
echo ""
echo "=== MANUAL DEPLOYMENT INSTRUCTIONS ==="
echo ""
echo "1. Copy these files to $DEPLOY_DIR on 5090 PC:"
echo "   - $TAILSCALE_DIR/deploy/deploy.ps1"
echo "   - $TAILSCALE_DIR/deploy/profiles/"
echo ""
echo "2. On 5090 PC (PowerShell as Administrator):"
echo "   cd $DEPLOY_DIR"
echo "   .\\deploy.ps1 -Role workstation"
echo ""
echo "3. The script will use TAILSCALE_AUTHKEY from environment"
echo "   or prompt for authentication."
echo ""
echo "4. After deployment, verify from Z890:"
echo "   tailscale status | grep POWERFULMOVES"
echo "   tailscale ping POWERFULMOVES"
echo ""
echo "=== ALTERNATIVE: SCP Method ==="
echo ""
echo "If SCP is available on 5090 (e.g., via OpenSSH Server):"
echo "  scp $TAILSCALE_DIR/deploy/deploy.ps1 $PC_USER@$PC_IP:$DEPLOY_DIR/"
echo "  scp -r $TAILSCALE_DIR/deploy/profiles $PC_USER@$PC_IP:$DEPLOY_DIR/"
echo ""
echo "=== ALTERNATIVE: SMB Method ==="
echo ""
echo "If 5090 has enabled file sharing:"
echo "  1. Create share on 5090 pointing to $DEPLOY_DIR"
echo "  2. Mount share on Z890: net use Z: \\\\$PC_IP\\PMOVES-Tailscale"
echo "  3. Copy files to Z: drive"
echo ""
