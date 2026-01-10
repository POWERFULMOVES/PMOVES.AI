#!/usr/bin/env bash
#
# PMOVES Integration Authentication Setup Script
#
# This script helps set up authentication for Health/Wealth integrations:
# - Firefly III (Personal Finance)
# - wger (Health/Fitness)
# - Jellyfin (Media Server)
# - Open Notebook (Knowledge Base)
#
# Usage: ./integration-auth-setup.sh [integration] [action]
#
# Examples:
#   ./integration-auth-setup.sh status          # Check all integration status
#   ./integration-auth-setup.sh wger token      # Generate new wger API token
#   ./integration-auth-setup.sh firefly status  # Check Firefly status
#   ./integration-auth-setup.sh jellyfin setup  # Start Jellyfin setup wizard
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_SHARED="${SCRIPT_DIR}/../env.shared"

if [[ -f "$ENV_SHARED" ]]; then
    set -a
    source "$ENV_SHARED"
    set +a
fi

# Default URLs
FIREFLY_URL="${FIREFLY_URL:-http://localhost:8082}"
WGER_URL="${WGER_URL:-http://localhost:8002}"
JELLYFIN_URL="${JELLYFIN_URL:-http://localhost:8096}"
OPEN_NOTEBOOK_URL="${OPEN_NOTEBOOK_URL:-http://localhost:5055}"

# Container names
FIREFLY_CONTAINER="${FIREFLY_CONTAINER:-firefly}"
WGER_CONTAINER="${WGER_CONTAINER:-pmoves-wger}"
JELLYFIN_CONTAINER="${JELLYFIN_CONTAINER:-jellyfin}"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

#######################################
# Check if a service is healthy
#######################################
check_service_health() {
    local name="$1"
    local url="$2"
    local endpoint="${3:-/health}"

    if curl -sf "${url}${endpoint}" > /dev/null 2>&1; then
        log_success "$name is healthy at $url"
        return 0
    else
        log_error "$name is NOT responding at $url"
        return 1
    fi
}

#######################################
# FIREFLY III Functions
#######################################
firefly_status() {
    echo ""
    echo "=== Firefly III Status ==="

    # Check health
    if curl -sf "${FIREFLY_URL}/health" > /dev/null 2>&1; then
        log_success "Firefly III is healthy"
    else
        log_error "Firefly III is NOT responding"
        return 1
    fi

    # Check API with token
    if [[ -n "${FIREFLY_ACCESS_TOKEN:-}" ]]; then
        local api_response
        api_response=$(curl -sf -H "Authorization: Bearer ${FIREFLY_ACCESS_TOKEN}" \
            "${FIREFLY_URL}/api/v1/about" 2>&1) || true

        if echo "$api_response" | grep -q '"version"'; then
            local version
            version=$(echo "$api_response" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
            log_success "Firefly API accessible (version: $version)"
        else
            log_warn "Firefly API token may be expired or invalid"
            log_info "Generate new token: Dashboard -> Profile -> API Access"
        fi
    else
        log_warn "FIREFLY_ACCESS_TOKEN not set in env.shared"
    fi

    # Check container
    if docker ps --format '{{.Names}}' | grep -q "$FIREFLY_CONTAINER"; then
        log_success "Container $FIREFLY_CONTAINER is running"
    else
        log_error "Container $FIREFLY_CONTAINER is NOT running"
    fi
}

firefly_generate_token() {
    echo ""
    echo "=== Firefly III Token Generation ==="
    log_warn "Firefly III requires manual token generation via web UI"
    echo ""
    echo "Steps to generate a new API token:"
    echo "1. Open: ${FIREFLY_URL}"
    echo "2. Log in with your admin account"
    echo "3. Go to: Options (gear icon) -> Profile"
    echo "4. Scroll to 'Personal Access Tokens'"
    echo "5. Click 'Create New Token'"
    echo "6. Copy the token and update env.shared:"
    echo "   FIREFLY_ACCESS_TOKEN=<your-new-token>"
    echo ""
}

#######################################
# WGER Functions
#######################################
wger_status() {
    echo ""
    echo "=== wger Status ==="

    # Check if accessible (may redirect)
    if curl -sf -L "${WGER_URL}/" > /dev/null 2>&1; then
        log_success "wger is accessible"
    else
        log_error "wger is NOT responding"
        return 1
    fi

    # Check API with token
    if [[ -n "${WGER_API_TOKEN:-}" ]]; then
        local api_response
        api_response=$(curl -sf -H "Authorization: Token ${WGER_API_TOKEN}" \
            "${WGER_URL}/api/v2/userprofile/" 2>&1) || true

        if echo "$api_response" | grep -q '"username"'; then
            local username
            username=$(echo "$api_response" | grep -o '"username":"[^"]*"' | head -1 | cut -d'"' -f4)
            log_success "wger API accessible (user: $username)"
        else
            log_warn "wger API token may be invalid"
        fi
    else
        log_warn "WGER_API_TOKEN not set in env.shared"
    fi

    # Check container
    if docker ps --format '{{.Names}}' | grep -q "$WGER_CONTAINER"; then
        log_success "Container $WGER_CONTAINER is running"
    else
        log_error "Container $WGER_CONTAINER is NOT running"
    fi
}

wger_generate_token() {
    echo ""
    echo "=== wger Token Generation ==="

    if ! docker ps --format '{{.Names}}' | grep -q "$WGER_CONTAINER"; then
        log_error "Container $WGER_CONTAINER is not running"
        return 1
    fi

    local username="${1:-admin}"
    log_info "Generating API token for user: $username"

    local token
    token=$(docker exec "$WGER_CONTAINER" python3 manage.py drf_create_token "$username" 2>&1 | \
        grep -oE '[a-f0-9]{40}' | tail -1) || true

    if [[ -n "$token" ]]; then
        log_success "Generated token: $token"
        echo ""
        echo "Update env.shared with:"
        echo "WGER_API_TOKEN=$token"
    else
        log_error "Failed to generate token"
        log_info "Trying to retrieve existing token..."

        token=$(docker exec "$WGER_CONTAINER" python3 -c "
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
try:
    user = User.objects.get(username='$username')
    token, created = Token.objects.get_or_create(user=user)
    print(token.key)
except Exception as e:
    print('')
" 2>/dev/null) || true

        if [[ -n "$token" ]]; then
            log_success "Existing token: $token"
            echo ""
            echo "Update env.shared with:"
            echo "WGER_API_TOKEN=$token"
        else
            log_error "Could not retrieve token"
        fi
    fi
}

wger_reset_admin() {
    echo ""
    echo "=== wger Admin Reset ==="

    if ! docker ps --format '{{.Names}}' | grep -q "$WGER_CONTAINER"; then
        log_error "Container $WGER_CONTAINER is not running"
        return 1
    fi

    log_info "Resetting admin user to default credentials..."
    docker exec "$WGER_CONTAINER" python3 manage.py wger create-or-reset-admin

    log_success "Admin credentials reset to:"
    echo "  Username: admin"
    echo "  Password: adminadmin"
    log_warn "Change the password after logging in!"
}

#######################################
# JELLYFIN Functions
#######################################
jellyfin_status() {
    echo ""
    echo "=== Jellyfin Status ==="

    # Check health
    if curl -sf "${JELLYFIN_URL}/health" > /dev/null 2>&1; then
        log_success "Jellyfin is healthy"
    else
        log_error "Jellyfin is NOT responding"
        return 1
    fi

    # Check API with token
    if [[ -n "${JELLYFIN_API_KEY:-}" ]]; then
        local api_response
        api_response=$(curl -sf -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
            "${JELLYFIN_URL}/System/Info" 2>&1) || true

        if echo "$api_response" | grep -q '"ServerName"'; then
            local server_name
            server_name=$(echo "$api_response" | grep -o '"ServerName":"[^"]*"' | cut -d'"' -f4)
            log_success "Jellyfin API accessible (server: $server_name)"
        else
            log_warn "Jellyfin API key may be invalid"
        fi
    else
        log_warn "JELLYFIN_API_KEY not set in env.shared"
    fi

    # Check user ID
    if [[ -n "${JELLYFIN_USER_ID:-}" ]]; then
        log_info "Configured User ID: ${JELLYFIN_USER_ID}"
    else
        log_warn "JELLYFIN_USER_ID not set in env.shared"
    fi

    # Check container
    if docker ps --format '{{.Names}}' | grep -q "$JELLYFIN_CONTAINER"; then
        log_success "Container $JELLYFIN_CONTAINER is running"
    else
        log_error "Container $JELLYFIN_CONTAINER is NOT running"
    fi
}

jellyfin_generate_key() {
    echo ""
    echo "=== Jellyfin API Key Generation ==="
    log_warn "Jellyfin requires manual API key generation via web UI"
    echo ""
    echo "Steps to generate a new API key:"
    echo "1. Open: ${JELLYFIN_URL}"
    echo "2. Log in with your admin account"
    echo "3. Go to: Dashboard (hamburger menu) -> Settings -> API Keys"
    echo "4. Click '+' to create a new key"
    echo "5. Give it a name (e.g., 'PMOVES')"
    echo "6. Copy the key and update env.shared:"
    echo "   JELLYFIN_API_KEY=<your-new-key>"
    echo ""
    echo "To get your User ID:"
    echo "1. Go to: Dashboard -> Users"
    echo "2. Click on your user"
    echo "3. The URL will contain the User ID"
    echo "   Example: .../users/4979C6E8-8F62-4E0A-84CB-8592E334566D/..."
    echo ""
}

jellyfin_list_users() {
    echo ""
    echo "=== Jellyfin Users ==="

    if [[ -z "${JELLYFIN_API_KEY:-}" ]]; then
        log_error "JELLYFIN_API_KEY not set"
        return 1
    fi

    local users
    users=$(curl -sf -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
        "${JELLYFIN_URL}/Users" 2>&1) || true

    if [[ -n "$users" ]]; then
        echo "$users" | python3 -c "
import json, sys
users = json.load(sys.stdin)
for u in users:
    admin = '(Admin)' if u.get('Policy', {}).get('IsAdministrator') else ''
    print(f\"  {u['Name']:20} {u['Id']} {admin}\")
" 2>/dev/null || echo "$users"
    else
        log_error "Could not retrieve users"
    fi
}

#######################################
# OPEN NOTEBOOK Functions
#######################################
open_notebook_status() {
    echo ""
    echo "=== Open Notebook Status ==="

    # Check health
    local response
    response=$(curl -sf "${OPEN_NOTEBOOK_URL}/" 2>&1) || true

    if echo "$response" | grep -qi "running"; then
        log_success "Open Notebook is healthy"
    else
        log_error "Open Notebook is NOT responding"
        return 1
    fi

    # Check token
    if [[ -n "${OPEN_NOTEBOOK_API_TOKEN:-}" ]]; then
        log_success "API token configured"
    else
        log_warn "OPEN_NOTEBOOK_API_TOKEN not set"
    fi

    # Check password
    if [[ -n "${OPEN_NOTEBOOK_PASSWORD:-}" ]]; then
        log_success "Password configured"
    else
        log_warn "OPEN_NOTEBOOK_PASSWORD not set"
    fi
}

#######################################
# Overall Status
#######################################
status_all() {
    echo ""
    echo "========================================"
    echo "  PMOVES Integration Status Report"
    echo "========================================"

    firefly_status || true
    wger_status || true
    jellyfin_status || true
    open_notebook_status || true

    echo ""
    echo "========================================"
    echo "  Summary"
    echo "========================================"
    echo ""
    echo "For detailed setup instructions, run:"
    echo "  $0 <integration> help"
    echo ""
}

#######################################
# Help
#######################################
show_help() {
    cat << EOF
PMOVES Integration Authentication Setup

Usage: $0 [integration] [action]

Integrations:
  firefly     Firefly III (Personal Finance)
  wger        wger (Health/Fitness)
  jellyfin    Jellyfin (Media Server)
  notebook    Open Notebook (Knowledge Base)

Actions:
  status      Check integration status (default)
  token       Generate/retrieve API token
  help        Show help for integration

Examples:
  $0 status              # Check all integrations
  $0 wger token          # Generate wger API token
  $0 wger reset          # Reset wger admin password
  $0 firefly status      # Check Firefly status
  $0 jellyfin users      # List Jellyfin users

EOF
}

#######################################
# Main
#######################################
main() {
    local integration="${1:-status}"
    local action="${2:-status}"

    case "$integration" in
        status)
            status_all
            ;;
        firefly)
            case "$action" in
                status) firefly_status ;;
                token) firefly_generate_token ;;
                help|*)
                    echo "Firefly III actions: status, token"
                    firefly_generate_token
                    ;;
            esac
            ;;
        wger)
            case "$action" in
                status) wger_status ;;
                token) wger_generate_token "${3:-admin}" ;;
                reset) wger_reset_admin ;;
                help|*)
                    echo "wger actions: status, token [username], reset"
                    ;;
            esac
            ;;
        jellyfin)
            case "$action" in
                status) jellyfin_status ;;
                token|key) jellyfin_generate_key ;;
                users) jellyfin_list_users ;;
                help|*)
                    echo "Jellyfin actions: status, token/key, users"
                    jellyfin_generate_key
                    ;;
            esac
            ;;
        notebook|open-notebook)
            case "$action" in
                status) open_notebook_status ;;
                help|*)
                    echo "Open Notebook actions: status"
                    open_notebook_status
                    ;;
            esac
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown integration: $integration"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
