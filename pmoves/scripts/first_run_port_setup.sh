#!/usr/bin/env bash
# first_run_port_setup.sh - First-run port allocation setup
#
# This script detects port conflicts and assigns ports dynamically
# on first run, persisting the assignments to data/ports.json
#
# Usage:
#   make ports-auto-detect    # Detect and assign ports
#   make ports-validate       # Check for conflicts
#   make ports-reset          # Reset port assignments

set -euo pipefail

# Configuration
PORTS_JSON="${PMOVES_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/data/ports.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT_ALLOCATOR="$SCRIPT_DIR/port_allocator.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if ports.json exists (first run check)
is_first_run() {
    [[ ! -f "$PORTS_JSON" ]]
}

# Auto-detect and assign ports
auto_detect_ports() {
    log_info "Detecting port conflicts and assigning ports..."

    if ! python3 "$PORT_ALLOCATOR" --detect; then
        log_error "Port detection failed"
        return 1
    fi

    log_success "Port allocation complete"
}

# Validate current port assignments
validate_ports() {
    log_info "Validating port assignments..."

    if ! python3 "$PORT_ALLOCATOR" --validate; then
        log_warning "Port conflicts detected. Run 'make ports-auto-detect' to fix."
        return 1
    fi

    log_success "No port conflicts detected"
}

# Reset port assignments
reset_ports() {
    log_warning "Resetting all port assignments..."

    if [[ -f "$PORTS_JSON" ]]; then
        rm -f "$PORTS_JSON"
        log_success "Port assignments reset. Run 'make ports-auto-detect' to reassign."
    else
        log_info "No port assignments to reset."
    fi
}

# Show current port assignments
show_ports() {
    log_info "Current port assignments:"

    if [[ ! -f "$PORTS_JSON" ]]; then
        log_warning "No port assignments found. Run 'make ports-auto-detect' first."
        return 1
    fi

    python3 "$PORT_ALLOCATOR"
}

# Generate environment overrides for docker-compose
generate_env_overrides() {
    if [[ ! -f "$PORTS_JSON" ]]; then
        return 1
    fi

    python3 "$PORT_ALLOCATOR" --env-overrides
}

# Main function
main() {
    cd "$(dirname "$0")/.." || exit 1

    local action="${1:-detect}"

    case "$action" in
        detect)
            if is_first_run; then
                log_info "First run detected - initializing port assignments..."
            fi
            auto_detect_ports
            ;;
        validate)
            validate_ports
            ;;
        reset)
            reset_ports
            ;;
        show)
            show_ports
            ;;
        env)
            generate_env_overrides
            ;;
        *)
            echo "Usage: $0 {detect|validate|reset|show|env}"
            echo ""
            echo "Commands:"
            echo "  detect   - Auto-detect conflicts and assign ports (default)"
            echo "  validate - Check for port conflicts"
            echo "  reset    - Reset all port assignments"
            echo "  show     - Show current port assignments"
            echo "  env      - Generate environment variable overrides"
            exit 1
            ;;
    esac
}

main "$@"
