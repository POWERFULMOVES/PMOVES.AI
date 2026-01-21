#!/usr/bin/env bash
# =============================================================================
# PMOVES.AI Universal Credential Bootstrap
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials from:
# 1. Parent PMOVES.AI environment (preferred)
# 2. GitHub Secrets (fallback)
# 3. Local .env file (last resort)
#
# Usage: source scripts/bootstrap_credentials.sh
#        OR ./scripts/bootstrap_credentials.sh && export $(grep -v '^#' .env.bootstrap)
#
# Platforms: Linux, macOS, WSL2, Git Bash (Windows)
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# =============================================================================
# Find Parent PMOVES.AI Repository
# =============================================================================

find_parent_pmoves() {
    local current_dir="$(pwd)"
    local parent_dir=""

    # Check if we're in a submodule
    if [ -f "$current_dir/.git" ] && grep -q "gitdir:.*modules" "$current_dir/.git" 2>/dev/null; then
        # We're in a submodule - find the parent
        local git_root="$(cd "$current_dir" && git rev-parse --show-toplevel 2>/dev/null || echo "$current_dir")"
        parent_dir="$(dirname "$git_root")"
    else
        # Not in a submodule, try going up
        parent_dir="$(cd "$current_dir/.." && pwd)"
    fi

    # Check if parent looks like PMOVES.AI
    if [ -f "$parent_dir/pmoves/env.shared" ] || [ -f "$parent_dir/pmoves/.env" ]; then
        echo "$parent_dir"
        return 0
    fi

    # Try going up another level (for nested structures)
    local grandparent="$(dirname "$parent_dir")"
    if [ -f "$grandparent/pmoves/env.shared" ] || [ -f "$grandparent/pmoves/.env" ]; then
        echo "$grandparent"
        return 0
    fi

    return 1
}

# =============================================================================
# Load Credentials from Parent PMOVES.AI
# =============================================================================

load_from_parent() {
    local parent_dir="$1"
    local output_file="${2:-.env.bootstrap}"
    local env_shared="$parent_dir/pmoves/env.shared"
    local parent_env="$parent_dir/pmoves/.env"

    log_info "Found parent PMOVES.AI at: $parent_dir"

    # Source env.shared first (has structure)
    if [ -f "$env_shared" ]; then
        log_info "Loading from env.shared..."
        # Copy env.shared to output, filtering out comments and empty lines
        grep -E '^[A-Z_]+=|^export ' "$env_shared" 2>/dev/null | sed 's/^export //' > "$output_file"
        log_success "Loaded $(grep -c '^' "$output_file") variables from env.shared"
    else
        log_warning "env.shared not found at $env_shared"
    fi

    # Then source .env (has actual credential values)
    if [ -f "$parent_env" ]; then
        log_info "Loading from parent .env..."
        # Append actual values from parent .env
        grep -E '^[A-Z_]+=' "$parent_env" 2>/dev/null >> "$output_file" || true
        log_success "Merged parent .env credentials"
    else
        log_warning "Parent .env not found at $parent_env"
    fi

    return 0
}

# =============================================================================
# Load Credentials from GitHub Secrets
# =============================================================================

load_from_github_secrets() {
    local output_file="${1:-.env.bootstrap}"
    local repo_name="${2:-POWERFULMOVES/PMOVES.AI}"

    log_info "Attempting to load from GitHub Secrets..."

    # Check if gh CLI is available and authenticated
    if ! command -v gh &>/dev/null; then
        log_warning "GitHub CLI (gh) not installed. Install from: https://cli.github.com/"
        return 1
    fi

    if ! gh auth status &>/dev/null; then
        log_warning "Not logged into GitHub. Run: gh auth login"
        return 1
    fi

    # Get all secrets that match credential patterns
    log_info "Fetching secrets from $repo_name..."

    # List secrets and filter for credential keys
    local secrets
    secrets=$(gh secret list --repo "$repo_name" 2>/dev/null | grep -E "(API_KEY|APIKEY|TOKEN|PASSWORD|SECRET)" | awk '{print $1}' || true)

    if [ -z "$secrets" ]; then
        log_warning "No credential secrets found in repo"
        return 1
    fi

    # Export each secret (this will prompt for values if not set)
    for secret in $secrets; do
        # Convert secret name to env var format (e.g., MY_SECRET -> MY_SECRET)
        local env_name="$secret"
        echo "${env_name}=\${GH_SECRET_${env_name}}" >> "$output_file"
        log_info "  - Added placeholder for $env_name (use gh secret to populate)"
    done

    log_warning "GitHub Secrets fetched - placeholders created. Use 'gh secret set' to populate values."
    return 0
}

# =============================================================================
# Main Bootstrap Flow
# =============================================================================

main() {
    local output_file=".env.bootstrap"
    local parent_dir=""
    local source_used=""

    log_info "PMOVES.AI Credential Bootstrap"
    log_info "================================"

    # 1. Try to find and load from parent PMOVES.AI
    parent_dir="$(find_parent_pmoves)" || true
    if [ -n "$parent_dir" ]; then
        load_from_parent "$parent_dir" "$output_file"
        source_used="parent PMOVES.AI"
    fi

    # 2. If parent failed, try GitHub Secrets
    if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 5 ]; then
        if load_from_github_secrets "$output_file"; then
            source_used="GitHub Secrets"
        fi
    fi

    # 3. Final check
    if [ -f "$output_file" ] && [ -s "$output_file" ]; then
        local var_count=$(grep -c '^' "$output_file" 2>/dev/null || echo "0")
        log_success "Bootstrapped $var_count variables from $source_used"
        log_info ""
        log_info "To use these credentials:"
        log_info "  source $output_file                    # Bash/Zsh"
        log_info "  OR"
        log_info "  cat $output_file >> .env               # Append to .env"
        log_info "  OR"
        log_info "  export \$(cat $output_file | xargs)    # Export to current shell"
        echo ""
        log_info "Preview of loaded credentials:"
        grep -E '^(OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER|SUPABASE)_' "$output_file" 2>/dev/null | sed 's/=.*/=***masked***/' || echo "  (No LLM provider keys found)"
        return 0
    else
        log_error "Failed to bootstrap credentials from any source"
        log_info ""
        log_info "Manual setup required:"
        log_info "  1. Ensure parent PMOVES.AI repo exists with pmoves/.env populated"
        log_info "  2. OR authenticate with GitHub: gh auth login"
        log_info "  3. OR create .env file manually with required credentials"
        return 1
    fi
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
else
    # If sourced, export the function for use
    export -f find_parent_pmoves
    export -f load_from_parent
    export -f load_from_github_secrets
    export -f main
    log_info "PMOVES.AI Bootstrap functions loaded. Run 'bootstrap_credentials' to load credentials."
fi
