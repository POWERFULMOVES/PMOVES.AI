#!/usr/bin/env bash
# =============================================================================
# GitHub App First-Time Setup Script (Linux/macOS)
# =============================================================================
#
# This script automates the first-time setup of GitHub App credentials
# on Linux and macOS systems.
#
# PREREQUISITES:
#   - GitHub CLI installed (https://cli.github.com/)
#   - GitHub CLI authenticated (gh auth login)
#   - Python 3.8+ installed
#
# USAGE:
#   bash pmoves/scripts/github_app_first_time_setup.sh
#
# =============================================================================

set -euo pipefail

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BLUE='\033[0;34m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Helper functions
print_header() {
    local text="$1"
    echo ""
    echo -e "${BLUE}${BOLD}================================================================================${NC}"
    echo -e "${BLUE}${BOLD}$(printf "%70s" "$text")${NC}"
    echo -e "${BLUE}${BOLD}================================================================================${NC}"
    echo ""
}

print_step() {
    local step="$1"
    local text="$2"
    echo -e "${GREEN}${BOLD}[Step ${step}]${NC} ${text}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PMOVES_DIR="${REPO_ROOT}/pmoves"

# Check prerequisites
check_prerequisites() {
    print_step 1 "Checking prerequisites..."

    local all_good=true

    # Check Python
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python installed: ${python_version}"
    else
        print_error "Python 3 not found"
        echo "  Install Python 3.8+ from https://www.python.org/"
        all_good=false
    fi

    # Check GitHub CLI
    if command -v gh &> /dev/null; then
        local gh_version=$(gh --version 2>&1 | head -n1)
        print_success "GitHub CLI installed: ${gh_version}"
    else
        print_error "GitHub CLI not found"
        echo "  Install from https://cli.github.com/"
        all_good=false
    fi

    # Check GitHub CLI authentication
    if command -v gh &> /dev/null; then
        if gh auth status &> /dev/null; then
            print_success "GitHub CLI authenticated"
        else
            print_error "GitHub CLI not authenticated"
            echo "  Run: gh auth login"
            all_good=false
        fi
    fi

    if [ "$all_good" = false ]; then
        echo ""
        print_error "Prerequisites not met. Please install missing dependencies."
        exit 1
    fi

    echo ""
}

# Verify GitHub Secrets
verify_github_secrets() {
    print_step 2 "Verifying GitHub App credentials in GitHub Secrets..."

    local gh_app_keys=('GH_APP_ID' 'GH_APP_SEC' 'GH_APP_CLIENT_ID' 'GH_APP_INSTALLATION_ID')
    local found_count=0

    echo "  Checking GitHub Secrets for POWERFULMOVES/PMOVES.AI:"
    for key in "${gh_app_keys[@]}"; do
        if gh secret list --repo POWERFULMOVES/PMOVES.AI | grep -q "^${key}"; then
            print_success "  ${key}: Found"
            ((found_count++))
        else
            print_warning "  ${key}: Not found"
        fi
    done

    if [ $found_count -lt 4 ]; then
        echo ""
        print_error "Only ${found_count}/4 credentials found in GitHub Secrets"
        echo ""
        echo "  Missing credentials must be added to GitHub Secrets first:"
        echo "  https://github.com/organizations/POWERFULMOVES/PMOVES.AI/settings/secrets/actions"
        echo ""
        exit 1
    fi

    echo ""
}

# Run automated setup
run_automated_setup() {
    print_step 3 "Running automated GitHub App setup..."

    cd "${PMOVES_DIR}"

    if python3 tools/github_app_auto_setup.py; then
        print_success "Automated setup completed"
    else
        print_error "Automated setup failed"
        echo ""
        echo "  Try running manually:"
        echo "  1. Edit pmoves/env.shared and uncomment GH_APP_* lines"
        echo "  2. Run: cd pmoves && make secrets-funnel"
        echo ""
        exit 1
    fi

    echo ""
}

# Verify setup
verify_setup() {
    print_step 4 "Verifying GitHub App setup..."

    cd "${PMOVES_DIR}"

    if python3 tools/verify_github_app_setup.py; then
        print_success "Setup verification passed"
    else
        print_warning "Setup verification failed (this is OK on first run)"
        echo "  You may need to restart services to pick up new credentials"
    fi

    echo ""
}

# Show next steps
show_next_steps() {
    print_header "Setup Complete! 🎉"

    echo "GitHub App credentials are now configured."
    echo ""
    echo "Next steps:"
    echo "  1. Start services:"
    echo "     ${PMOVES_DIR}/docker compose up -d archon botz-gateway"
    echo ""
    echo "  2. Verify services are healthy:"
    echo "     curl http://localhost:8091/healthz  # Archon"
    echo "     curl http://localhost:8054/healthz  # BoTZ Gateway"
    echo ""
    echo "  3. Test token minting:"
    echo "     cd ${REPO_ROOT}/PMOVES-BoTZ"
    echo "     python features/github/mint_and_exec.py"
    echo ""
    echo "For troubleshooting, see:"
    echo "  • Quick Start: pmoves/docs/GITHUB_APP_QUICK_START.md"
    echo "  • Agent Docs: pmoves/docs/AGENTS/GITHUB_APP_CREDENTIALS.md"
    echo ""
}

# Main execution
main() {
    print_header "GitHub App First-Time Setup"

    check_prerequisites
    verify_github_secrets
    run_automated_setup
    verify_setup
    show_next_steps
}

# Run main function
main "$@"
