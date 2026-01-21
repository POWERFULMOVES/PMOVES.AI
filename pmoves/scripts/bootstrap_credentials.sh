#!/usr/bin/env bash
# =============================================================================
# PMOVES.AI Universal Credential Bootstrap (v2)
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials.
#
# MODES:
#   DOCKED MODE:   ONLY loads from parent PMOVES.AI (detected via env vars)
#   STANDALONE:    Loads from CHIT -> GitHub Secrets -> Docker Secrets
#
# Usage: source scripts/bootstrap_credentials.sh
#        OR ./scripts/bootstrap_credentials.sh && source .env.bootstrap
#
# Platforms: Linux, macOS, WSL2, Git Bash (Windows)
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_mode() { echo -e "${CYAN}▶${NC} $1"; }

# =============================================================================
# Detect Mode: Docked vs Standalone
# =============================================================================

is_docked_mode() {
    # Check explicit environment variable
    if [ "${DOCKED_MODE:-false}" = "true" ]; then
        return 0
    fi

    # Check if running in Docker container
    if [ -f /.dockerenv ] 2>/dev/null; then
        # Only consider docked if we can reach parent services
        if [ -n "${NATS_URL:-}" ] || [ -n "${TENSORZERO_URL:-}" ]; then
            return 0
        fi
    fi

    # Check cgroup for container indicators
    if [ -f /proc/1/cgroup ] 2>/dev/null; then
        if grep -qE '(docker|kubepods|containerd)' /proc/1/cgroup 2>/dev/null; then
            # Only consider docked if we can reach parent services
            if [ -n "${NATS_URL:-}" ] || [ -n "${TENSORZERO_URL:-}" ]; then
                return 0
            fi
        fi
    fi

    return 1
}

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
# Load Credentials from Parent PMOVES.AI (DOCKED MODE ONLY)
# =============================================================================

load_from_parent() {
    local parent_dir="$1"
    local output_file="${2:-.env.bootstrap}"
    local env_shared="$parent_dir/pmoves/env.shared"
    local parent_env="$parent_dir/pmoves/.env"

    log_info "Loading from parent PMOVES.AI at: $parent_dir"

    # Source env.shared first (has structure)
    if [ -f "$env_shared" ]; then
        log_info "Loading env.shared structure..."
        # Copy env.shared to output, filtering out comments and empty lines
        grep -E '^[A-Z_]+=|^export ' "$env_shared" 2>/dev/null | sed 's/^export //' > "$output_file"
        log_success "Loaded $(grep -c '^' "$output_file") variables from env.shared"
    else
        log_warning "env.shared not found at $env_shared"
    fi

    # Then source .env (has actual credential values)
    if [ -f "$parent_env" ]; then
        log_info "Loading credential values from parent .env..."
        # Append actual values from parent .env
        grep -E '^[A-Z_]+=' "$parent_env" 2>/dev/null >> "$output_file" || true
        log_success "Merged parent .env credentials"
    else
        log_warning "Parent .env not found at $parent_env"
    fi

    return 0
}

# =============================================================================
# Load Credentials from CHIT Geometry Packet
# =============================================================================

load_from_chit() {
    local output_file="${1:-.env.bootstrap}"
    local cgp_paths=(
        # Current submodule data directory
        "$(pwd)/data/chit/env.cgp.json"
        "$(pwd)/pmoves/data/chit/env.cgp.json"
        # User home config
        "$HOME/.config/pmoves/chit/env.cgp.json"
        "$HOME/.pmoves/chit/env.cgp.json"
        # Parent data directory (if in submodule)
        "../data/chit/env.cgp.json"
        "../../data/chit/env.cgp.json"
    )

    log_info "Attempting to load from CHIT Geometry Packet..."

    # Find CGP file
    local cgp_file=""
    for path in "${cgp_paths[@]}"; do
        if [ -f "$path" ]; then
            cgp_file="$path"
            break
        fi
    done

    if [ -z "$cgp_file" ]; then
        log_info "  No CGP file found (checked: data/chit/env.cgp.json, ~/.config/pmoves/chit/, etc.)"
        return 1
    fi

    log_info "  Found CGP at: $cgp_file"

    # Try to decode using Python CHIT module
    if command -v python3 &>/dev/null; then
        local decoded
        decoded=$(python3 -c "
import sys
import json
from pathlib import Path

# Try to import CHIT module from parent PMOVES.AI
repo_root = Path('$output_file').resolve().parent
for parent in [repo_root] + list(repo_root.parents):
    chit_path = parent / 'pmoves' / 'chit'
    if chit_path.exists():
        sys.path.insert(0, str(parent))
        break

try:
    from pmoves.chit import load_cgp, decode_secret_map
    cgp = load_cgp('$cgp_file')
    secrets = decode_secret_map(cgp)
    for k, v in sorted(secrets.items()):
        print(f'{k}={v}')
except ImportError:
    # Fallback: simple JSON parsing for cleartext values
    with open('$cgp_file') as f:
        cgp = json.load(f)
    for point in cgp.get('points', []):
        label = point['label']
        value = point.get('value', '')
        encoding = point.get('encoding', 'cleartext')
        if encoding == 'cleartext':
            print(f'{label}={value}')
        else:
            # For hex-encoded, just show placeholder
            print(f'{label}=***CHIT_HEX_ENCODED***')
" 2>/dev/null || true)

        if [ -n "$decoded" ]; then
            echo "$decoded" >> "$output_file"
            local count=$(echo "$decoded" | wc -l)
            log_success "  Decoded $count secrets from CHIT Geometry Packet"
            return 0
        fi
    fi

    log_warning "  CHIT decode failed (Python CHIT module not available)"
    return 1
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
        log_info "  GitHub CLI (gh) not installed."
        return 1
    fi

    if ! gh auth status &>/dev/null; then
        log_info "  Not logged into GitHub (run: gh auth login)"
        return 1
    fi

    # Get all secrets that match credential patterns
    log_info "  Fetching secret names from $repo_name..."

    # List secrets and filter for credential keys
    local secrets
    secrets=$(gh secret list --repo "$repo_name" 2>/dev/null | grep -E "(API_KEY|APIKEY|TOKEN|PASSWORD|SECRET|OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER)" | awk '{print $1}' || true)

    if [ -z "$secrets" ]; then
        log_info "  No credential secrets found in repo"
        return 1
    fi

    # NOTE: GitHub CLI cannot read secret values (security restriction)
    # We create reference placeholders that the user must populate
    log_warning "  GitHub Secrets found but values cannot be fetched via CLI"
    log_info "  Creating reference placeholders..."

    for secret in $secrets; do
        local env_name="$secret"
        echo "# GitHub Secret: $secret" >> "$output_file"
        echo "${env_name}=\"\${GH_SECRET_${env_name}}\"" >> "$output_file"
    done

    log_warning "  GitHub Secrets placeholders created. Populate via: gh secret set"
    return 0
}

# =============================================================================
# Load Credentials from Docker Secrets
# =============================================================================

load_from_docker_secrets() {
    local output_file="${1:-.env.bootstrap}"
    local secrets_dir="/run/secrets"

    log_info "Attempting to load from Docker Secrets..."

    if [ ! -d "$secrets_dir" ]; then
        log_info "  Docker secrets directory not found: $secrets_dir"
        return 1
    fi

    # Find PMOVES-related secrets
    local found=0
    for secret_file in "$secrets_dir"/pmoves_* "$secrets_dir"/*_api_key "$secrets_dir"/*_token; do
        if [ -f "$secret_file" ]; then
            local basename=$(basename "$secret_file")
            # Convert docker secret name to env var format
            # pmoves_openai_api_key -> OPENAI_API_KEY
            local env_name=$(echo "$basename" | sed 's/^pmoves_//' | tr '[:lower:]' '[:upper:]' | sed 's/_API_KEY/_API_KEY/' | sed 's/_TOKEN/_TOKEN/')

            local value=$(cat "$secret_file" 2>/dev/null || echo "")
            if [ -n "$value" ]; then
                echo "${env_name}=${value}" >> "$output_file"
                log_info "  Loaded $env_name from Docker secret"
                ((found++))
            fi
        fi
    done

    if [ $found -gt 0 ]; then
        log_success "  Loaded $found credentials from Docker secrets"
        return 0
    else
        log_info "  No PMOVES Docker secrets found"
        return 1
    fi
}

# =============================================================================
# Main Bootstrap Flow
# =============================================================================

main() {
    local output_file=".env.bootstrap"
    local parent_dir=""
    local source_used=""

    log_info "PMOVES.AI Credential Bootstrap v2"
    log_info "===================================="

    # Detect mode
    if is_docked_mode; then
        log_mode "DOCKED MODE detected - loading from parent only"
        echo ""

        # DOCKED MODE: Only load from parent
        parent_dir="$(find_parent_pmoves)" || true
        if [ -n "$parent_dir" ]; then
            load_from_parent "$parent_dir" "$output_file"
            source_used="parent PMOVES.AI (docked)"
        else
            log_error "DOCKED MODE: Parent PMOVES.AI not found!"
            log_info "In docked mode, credentials MUST come from parent repo."
            return 1
        fi
    else
        log_mode "STANDALONE MODE detected - trying CHIT, GitHub, Docker secrets"
        echo ""

        # STANDALONE MODE: Try multiple sources
        local sources_tried=()

        # 1. Try CHIT decode first
        if load_from_chit "$output_file"; then
            source_used="CHIT Geometry Packet"
            sources_tried+=("CHIT: success")
        else
            sources_tried+=("CHIT: failed")
        fi

        # 2. Try GitHub Secrets
        if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 3 ]; then
            if load_from_github_secrets "$output_file"; then
                source_used="${source_used:+$source_used + }GitHub Secrets"
                sources_tried+=("GitHub: success (placeholders)")
            else
                sources_tried+=("GitHub: failed")
            fi
        fi

        # 3. Try Docker Secrets
        if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 3 ]; then
            if load_from_docker_secrets "$output_file"; then
                source_used="${source_used:+$source_used + }Docker Secrets"
                sources_tried+=("Docker: success")
            else
                sources_tried+=("Docker: failed")
            fi
        fi

        # 4. Fallback: Try parent (last resort in standalone)
        if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 3 ]; then
            parent_dir="$(find_parent_pmoves)" || true
            if [ -n "$parent_dir" ]; then
                log_info "Fallback: loading from parent PMOVES.AI..."
                load_from_parent "$parent_dir" "$output_file"
                source_used="${source_used:+$source_used + }parent PMOVES.AI"
                sources_tried+=("Parent: success")
            else
                sources_tried+=("Parent: not found")
            fi
        fi

        echo ""
        log_info "Sources tried: ${sources_tried[*]}"
    fi

    # Final check and output
    if [ -f "$output_file" ] && [ -s "$output_file" ]; then
        local var_count=$(grep -c '^[A-Z_]=' "$output_file" 2>/dev/null || echo "0")
        log_success "Bootstrapped $var_count variables from: $source_used"
        echo ""
        log_info "To use these credentials:"
        log_info "  source $output_file                    # Bash/Zsh"
        log_info "  OR"
        log_info "  cat $output_file >> .env               # Append to .env"
        echo ""
        log_info "Preview of loaded credentials:"
        grep -E '^(OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER|SUPABASE)_' "$output_file" 2>/dev/null | sed 's/=.*/=***masked***/' || echo "  (No LLM provider keys found)"
        return 0
    else
        log_error "Failed to bootstrap credentials from any source"
        echo ""
        log_info "Manual setup required:"
        log_info "  1. Create CHIT Geometry Packet: pmoves/tools/chit_encode_secrets.py"
        log_info "  2. OR set keys in GitHub Secrets: gh secret set"
        log_info "  3. OR create Docker secrets for your stack"
        log_info "  4. OR create .env file manually with required credentials"
        return 1
    fi
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
else
    # If sourced, export the function for use
    export -f is_docked_mode
    export -f find_parent_pmoves
    export -f load_from_parent
    export -f load_from_chit
    export -f load_from_github_secrets
    export -f load_from_docker_secrets
    export -f main
    log_info "PMOVES.AI Bootstrap functions loaded. Run 'bootstrap_credentials' to load credentials."
fi
