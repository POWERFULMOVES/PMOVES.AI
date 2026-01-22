#!/usr/bin/env bash
# tailscale_setup.sh - Automated Tailscale mesh network setup for PMOVES.AI
#
# This script sets up Tailscale for secure multi-host service discovery.
# Services running on different hosts (e.g., PMOVES-DoX on Jetson, PMOVES.AI on PC)
# can discover each other via the Tailscale mesh network.
#
# Usage:
#   make mesh-setup                    # Interactive setup
#   make mesh-setup AUTHKEY=...        # Non-interactive with auth key
#   make mesh-status                   # Show mesh status
#
# Environment Variables:
#   TAILSCALE_AUTHKEY    - Your Tailscale auth key (get from https://login.tailscale.com/admin/settings/keys)
#   MESH_NETWORK_MODE    - "tailscale", "nats", "both" (default: "both")
#   MESH_HOSTNAME        - Hostname for this machine (default: system hostname)
#   PMOVES_MESH_NAME     - Name of the PMOVES mesh network (default: "pmoves-mesh")

set -euo pipefail

# Configuration from env or defaults
TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"
MESH_NETWORK_MODE="${MESH_NETWORK_MODE:-both}"
MESH_HOSTNAME="${MESH_HOSTNAME:-$(hostname -s | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')}"
PMOVES_MESH_NAME="${PMOVES_MESH_NAME:-pmoves-mesh}"
TAILSCALE_TIMEOUT="${TAILSCALE_TIMEOUT:-300}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if Tailscale is installed
check_tailscale() {
    if ! command -v tailscale &> /dev/null; then
        log_info "Tailscale not found. Installing..."

        # Detect OS and install
        if [[ -f /etc/debian_version ]]; then
            # Debian/Ubuntu
            curl -fsSL https://tailscale.com/install.sh | sh
        elif [[ -f /etc/redhat-release ]]; then
            # RHEL/CentOS/Fedora
            curl -fsSL https://tailscale.com/install.sh | sh
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if ! command -v brew &> /dev/null; then
                log_error "Homebrew not found. Please install from https://brew.sh"
                exit 1
            fi
            brew install tailscale
        else
            log_error "Unsupported OS. Please install Tailscale manually from https://tailscale.com/download"
            exit 1
        fi

        # Verify installation
        if command -v tailscale &> /dev/null; then
            log_success "Tailscale installed successfully"
        else
            log_error "Tailscale installation failed"
            exit 1
        fi
    else
        log_success "Tailscale is already installed"
    fi
}

# Get Tailscale auth key
get_auth_key() {
    if [[ -n "$TAILSCALE_AUTHKEY" ]]; then
        return 0
    fi

    echo ""
    log_info "Tailscale requires an auth key for setup."
    echo "  1. Go to: https://login.tailscale.com/admin/settings/keys"
    echo "  2. Generate a new reusable key"
    echo "  3. Paste it below (or press Enter to skip Tailscale setup)"
    echo ""
    read -rp "Tailscale Auth Key (tskey-...): " TAILSCALE_AUTHKEY

    if [[ -z "$TAILSCALE_AUTHKEY" ]]; then
        log_warning "No auth key provided. Skipping Tailscale setup."
        return 1
    fi

    # Save to env.shared
    if [[ -f "pmoves/env.shared" ]]; then
        if ! grep -q "TAILSCALE_AUTHKEY" pmoves/env.shared; then
            echo "" >> pmoves/env.shared
            echo "# Tailscale mesh network for multi-host service discovery" >> pmoves/env.shared
            echo "TAILSCALE_AUTHKEY=$TAILSCALE_AUTHKEY" >> pmoves/env.shared
            log_success "Auth key saved to pmoves/env.shared"
        fi
    fi

    return 0
}

# Connect to Tailscale
connect_tailscale() {
    log_info "Connecting to Tailscale mesh network: $PMOVES_MESH_NAME"
    log_info "This machine will be known as: $MESH_HOSTNAME"

    # Run tailscale up with auth key
    if tailscale up \
        --authkey "$TAILSCALE_AUTHKEY" \
        --hostname "$MESH_HOSTNAME" \
        --accept-routes \
        --accept-dns \
        --operator="$PMOVES_MESH_NAME"; then
        log_success "Connected to Tailscale mesh network"
    else
        log_error "Failed to connect to Tailscale"
        return 1
    fi

    # Wait for connection to be ready
    log_info "Waiting for connection to be ready..."
    local count=0
    while [[ $count -lt $TAILSCALE_TIMEOUT ]]; do
        if tailscale status --json 2>/dev/null | grep -q '"BackendState":"Running"'; then
            log_success "Tailscale connection is ready"
            break
        fi
        sleep 2
        count=$((count + 2))
        echo -n "."
    done
    echo ""

    if [[ $count -ge $TAILSCALE_TIMEOUT ]]; then
        log_error "Timeout waiting for Tailscale connection"
        return 1
    fi
}

# Get Tailscale IP
get_tailscale_ip() {
    tailscale status --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'Self' in data and 'TailscaleIPs' in data['Self'] and data['Self']['TailscaleIPs']:
    print(data['Self']['TailscaleIPs'][0])
else:
    print('', end='')
" 2>/dev/null
}

# Configure Tailscale for PMOVES mesh
configure_tailscale() {
    log_info "Configuring Tailscale for PMOVES mesh..."

    # Enable subnet router if in NATS mode
    if [[ "$MESH_NETWORK_MODE" == "both" || "$MESH_NETWORK_MODE" == "nats" ]]; then
        log_info "Enabling NATS subnet routing..."
        # This allows other mesh nodes to reach our NATS server
        tailscale up --advertise-exit-node --reset 2>/dev/null || true
    fi

    log_success "Tailscale configured for PMOVES mesh"
}

# Get list of all mesh nodes
get_mesh_nodes() {
    tailscale status --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    peers = data.get('Peer', {})
    nodes = []

    # Add self
    if 'Self' in data:
        self_data = data['Self']
        nodes.append({
            'name': self_data.get('HostName', 'unknown'),
            'ip': self_data.get('TailscaleIPs', ['N/A'])[0] if self_data.get('TailscaleIPs') else 'N/A',
            'online': self_data.get('BackendState') == 'Running',
            'is_self': True
        })

    # Add peers
    for key, peer in peers.items():
        nodes.append({
            'name': peer.get('HostName', 'unknown'),
            'ip': peer.get('TailscaleIPs', ['N/A'])[0] if peer.get('TailscaleIPs') else 'N/A',
            'online': peer.get('Online', False),
            'is_self': False
        })

    for node in nodes:
        status = 'ONLINE' if node['online'] else 'OFFLINE'
        marker = '*' if node['is_self'] else ' '
        print(f\"{marker} {node['name']:<20} {node['ip']:<18} {status}\")
except Exception as e:
    print(f\"Error: {e}\", file=sys.stderr)
" 2>/dev/null || echo "No mesh nodes found"
}

# Show mesh status
show_status() {
    echo ""
    echo "=== PMOVES Mesh Network Status ==="
    echo ""

    if ! command -v tailscale &> /dev/null; then
        log_warning "Tailscale is not installed"
        return 1
    fi

    if ! tailscale status &> /dev/null; then
        log_warning "Tailscale is not connected"
        echo "Run 'make mesh-setup' to connect"
        return 1
    fi

    log_info "Mesh: $PMOVES_MESH_NAME"
    log_info "This host: $MESH_HOSTNAME"

    local ts_ip
    ts_ip=$(get_tailscale_ip)
    if [[ -n "$ts_ip" ]]; then
        log_info "Tailscale IP: $ts_ip"
    fi

    echo ""
    echo "Mesh Nodes:"
    echo "  * = this machine"
    echo ""
    get_mesh_nodes

    echo ""
    echo "NATS URL for mesh nodes:"
    if [[ -n "$ts_ip" ]]; then
        echo "  nats://$ts_ip:4222"
    fi

    return 0
}

# Generate PMOVES mesh configuration
generate_config() {
    local ts_ip
    ts_ip=$(get_tailscale_ip)

    if [[ -z "$ts_ip" ]]; then
        log_error "Could not get Tailscale IP"
        return 1
    fi

    cat > "pmoves/data/mesh_config.json" <<EOF
{
  "mesh_name": "$PMOVES_MESH_NAME",
  "hostname": "$MESH_HOSTNAME",
  "tailscale_ip": "$ts_ip",
  "nats_url": "nats://$ts_ip:4222",
  "nats_external_url": "nats://$ts_ip:4222",
  "mesh_mode": "$MESH_NETWORK_MODE",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

    log_success "Mesh configuration written to pmoves/data/mesh_config.json"
}

# Main setup function
main() {
    cd "$(dirname "$0")/.." || exit 1

    echo ""
    echo "🔗 PMOVES.AI Mesh Network Setup"
    echo "================================"
    echo ""

    # Check what to do based on arguments
    if [[ "${1:-}" == "status" ]]; then
        show_status
        exit $?
    fi

    # Check if already connected
    if tailscale status &> /dev/null; then
        log_info "Already connected to Tailscale"
        show_status

        # Still generate config in case IP changed
        generate_config
        exit 0
    fi

    # Run setup steps
    check_tailscale

    if ! get_auth_key; then
        log_warning "Skipping Tailscale setup (no auth key)"
        log_info "You can still use NATS for local discovery"
        exit 0
    fi

    connect_tailscale || exit 1
    configure_tailscale || exit 1
    generate_config || exit 1

    echo ""
    log_success "PMOVES mesh network setup complete!"
    echo ""
    show_status
    echo ""
    log_info "Next steps:"
    echo "  1. Start services: docker compose up -d"
    echo "  2. Check mesh status: make mesh-status"
    echo "  3. View discovered services: make registry-status"
}

# Run main
main "$@"
