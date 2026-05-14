#!/bin/bash
# =============================================================================
# PMOVES.AI Remote Desktop & VPN Setup Script
# =============================================================================
# Initializes Headscale + RustDesk services for PMOVES.AI
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "🔧 PMOVES.AI Remote Desktop & VPN Setup"
echo "========================================"
echo ""

# Check if env.tier-vpn exists
if [ ! -f "$PROJECT_ROOT/env.tier-vpn" ]; then
    echo "❌ env.tier-vpn not found. Please create it from env.shared.example"
    echo "   Example: cp env.shared env.tier-vpn && edit env.tier-vpn"
    exit 1
fi

# Generate Headscale API key if not set
# Handles three cases: (1) sentinel from old example → replace,
# (2) real key already set → skip, (3) key absent → append
if grep -q '^HEADSCALE_API_KEY=change-me-generated-secret' "$PROJECT_ROOT/env.tier-vpn" 2>/dev/null; then
    echo "🔑 Replacing placeholder Headscale API key..."
    API_KEY=$(openssl rand -hex 32)
    sed -i "s/^HEADSCALE_API_KEY=change-me-generated-secret/HEADSCALE_API_KEY=$API_KEY/" "$PROJECT_ROOT/env.tier-vpn"
    echo "✅ API key generated and saved."
elif grep -q '^HEADSCALE_API_KEY=' "$PROJECT_ROOT/env.tier-vpn" 2>/dev/null; then
    echo "🔑 HEADSCALE_API_KEY already set in env.tier-vpn."
else
    echo "🔑 Generating new Headscale API key..."
    API_KEY=$(openssl rand -hex 32)
    echo "HEADSCALE_API_KEY=$API_KEY" >> "$PROJECT_ROOT/env.tier-vpn"
    echo "✅ API key generated and saved."
fi

# Create config directory
mkdir -p "$PROJECT_ROOT/config/headscale"

# Check if config exists
if [ ! -f "$PROJECT_ROOT/config/headscale/config.yaml" ]; then
    echo "❌ Headscale config not found at config/headscale/config.yaml"
    echo "   Please create the configuration file first."
    exit 1
fi

# Check if ACL exists
if [ ! -f "$PROJECT_ROOT/config/headscale/acl.yaml" ]; then
    echo "❌ Headscale ACL not found at config/headscale/acl.yaml"
    echo "   Please create the ACL file first."
    exit 1
fi

echo "✅ Remote Desktop & VPN setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start services:"
echo "     docker compose --profile remote up -d"
echo ""
echo "  2. Create first Headscale user:"
echo "     docker exec pmoves-headscale headscale users create admin@pmoves.local"
echo ""
echo "  3. Generate auth key for a device:"
echo "     docker exec pmoves-headscale headscale apikeys create --reusable admin@pmoves.local"
echo ""
echo "  4. Install Headscale on a client device:"
echo "     # On Linux/Mac:"
echo "     # 1. Install Tailscale"
echo "     # 2. Run: sudo headscale register --server https://headscale.pmoves.local --auth-key <your-key>"
echo ""
echo "  5. Install RustDesk client:"
echo "     # Download from https://rustdesk.com/"
echo "     # Set ID server to: headscale.pmoves.local:21118"
echo "     # Set relay server to: headscale.pmoves.local:21117"
echo ""
