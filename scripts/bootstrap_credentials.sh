#!/usr/bin/env bash
# =============================================================================
# PMOVES.AI Universal Credential Bootstrap (v5)
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials.
#
# Full Documentation: pmoves/docs/SECRETS_MANAGEMENT.md
#
# MODES:
#   DOCKED MODE:   ONLY loads from parent PMOVES.AI (detected via env vars)
#   STANDALONE:    Loads from Active Fetcher -> GitHub Secrets -> CHIT -> git-crypt -> Docker Secrets -> Parent
#
# Usage: source scripts/bootstrap_credentials.sh
#        OR ./scripts/bootstrap_credentials.sh && source .env.bootstrap
#        OR GITHUB_OWNER=owner GITHUB_REPO=repo ./scripts/bootstrap_credentials.sh --active
#
# Platforms: Linux, macOS, WSL2, Git Bash (Windows), GitHub Actions, Codespaces
#
# Credential Sources (tried in order):
#   1. Active Fetcher - Python module that calls GitHub/Docker APIs (new in v5)
#   2. GitHub Secrets - Environment variables in GitHub Actions/Codespaces
#   3. CHIT Geometry Packet (env.cgp.json) - Encoded secrets in git
#   4. git-crypt (.env.enc) - GPG-encrypted files in git
#   5. Docker Secrets (/run/secrets/) - Container-standard secrets
#   6. Parent PMOVES.AI - Fallback to parent env.shared
#
# Active Fetcher Configuration:
#   GITHUB_OWNER - GitHub repository owner for API calls
#   GITHUB_REPO  - GitHub repository name for API calls
#   GITHUB_PAT   - GitHub Personal Access Token (or ~/.github-pat file)
#
# Empty Value Filtering:
#   - Keys ending in _KEY, _TOKEN, _SECRET, _PASSWORD must have values
#   - Exception: OPENAI_API_BASE= is valid (means use default endpoint)
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

    # Check if parent looks like PMOVES.AI (multiple patterns)
    # Pattern 1: Has tier files (env.tier-llm, env.tier-data, etc.) - ROOT PMOVES.AI
    local has_tier_files=0
    for tier_file in "$parent_dir"/env.tier-*; do
        if [ -f "$tier_file" ]; then
            has_tier_files=1
            break
        fi
    done

    if [ $has_tier_files -eq 1 ]; then
        echo "$parent_dir"
        return 0
    fi

    # Pattern 2: Has pmoves/env.shared (submodule structure)
    if [ -f "$parent_dir/pmoves/env.shared" ]; then
        echo "$parent_dir"
        return 0
    fi

    # Pattern 3: Has .env file
    if [ -f "$parent_dir/pmoves/.env" ]; then
        echo "$parent_dir"
        return 0
    fi

    # Try going up another level (for nested structures)
    local grandparent="$(dirname "$parent_dir")"
    for tier_file in "$grandparent"/env.tier-*; do
        if [ -f "$tier_file" ]; then
            echo "$grandparent"
            return 0
        fi
    done
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

    # NEW: Check for tier-based env files first (PMOVES.AI root structure)
    # Root PMOVES.AI uses env.tier-llm, env.tier-data, env.tier-api, etc.
    local tier_files=()
    local requested_tier="${TIER:-}"

    # Find all available tier files
    for tier_file in "$parent_dir"/env.tier-*; do
        if [ -f "$tier_file" ]; then
            tier_files+=("$tier_file")
        fi
    done

    # Load from tier files if they exist
    if [ ${#tier_files[@]} -gt 0 ]; then
        log_info "Found ${#tier_files[@]} tier file(s) at parent root"

        # If TIER is specified, ONLY load that tier (security: fail explicitly if not found)
        if [ -n "$requested_tier" ]; then
            local tier_file="$parent_dir/env.tier-$requested_tier"
            if [ -f "$tier_file" ]; then
                log_info "Loading from TIER=$requested_tier ($tier_file)..."
                grep -E '^[A-Z_]+=' "$tier_file" 2>/dev/null >> "$output_file" || true
                log_success "Loaded tier-specific credentials from env.tier-$requested_tier"
            else
                # Security: Fail explicitly when requested tier is missing
                log_error "Tier file env.tier-$requested_tier not found"
                log_error "Available tier files:"
                for tf in "${tier_files[@]}"; do
                    log_error "  - $(basename "$tf")"
                done
                log_error "Set TIER to one of the available tiers, or unset TIER to load all tiers"
                return 1
            fi
        else
            # No tier specified, load all available tier files
            for tf in "${tier_files[@]}"; do
                grep -E '^[A-Z_]+=' "$tf" 2>/dev/null >> "$output_file" || true
                log_info "  Loaded from $(basename "$tf")"
            done
            log_success "Loaded credentials from all tier files"
        fi
    else
        log_info "No tier files found at parent root"
    fi

    # FALLBACK: Source env.shared (for submodules with pmoves/env.shared structure)
    if [ -f "$env_shared" ]; then
        log_info "Loading env.shared structure..."
        # Copy env.shared to output, filtering out:
        # - comments and empty lines
        # - placeholder values (any line ending with -here, -if-needed, descriptive placeholders)
        grep -E '^[A-Z_]+=|^export ' "$env_shared" 2>/dev/null | \
            sed 's/^export //' | \
            grep -vE '-here$|-if-needed$|-when-needed$|-optional$' | \
            grep -vE '@your-' | \
            grep -vE '=TEMPLATE_' | \
            grep -vE '^TEMPLATE_' | \
            grep -vE '=super-secret-jwt-token-with-at-least' | \
            grep -vE '=Replace this with actual' \
            >> "$output_file" || true
        log_success "Loaded $(grep -c '^' "$output_file") variables from env.shared (placeholders filtered)"
    else
        log_info "env.shared not found at $env_shared (using tier files only)"
    fi

    # FALLBACK: Source .env if it exists (has actual credential values)
    if [ -f "$parent_env" ]; then
        log_info "Loading credential values from parent .env..."
        # Append actual values from parent .env
        grep -E '^[A-Z_]+=' "$parent_env" 2>/dev/null >> "$output_file" || true
        log_success "Merged parent .env credentials"
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
        # Parent data directory (if in submodule)
        "../pmoves/data/chit/env.cgp.json"
        "../../pmoves/data/chit/env.cgp.json"
        "../../../pmoves/data/chit/env.cgp.json"
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
        log_info "  No CGP file found (checked: data/chit/env.cgp.json, pmoves/data/chit/, etc.)"
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
            # Filter out placeholders before writing
            local filtered
            filtered=$(echo "$decoded" | \
                grep -vE '-here$|-if-needed$|-when-needed$|-optional$' | \
                grep -vE '@your-' | \
                grep -vE '=TEMPLATE_' | \
                grep -vE '^TEMPLATE_' | \
                grep -vE '\*\*\*CHIT_HEX_ENCODED\*\*\*' | \
                grep -vE '=Replace this with actual' || true)
            echo "$filtered" >> "$output_file" || true
            local count=$(echo "$filtered" | wc -l)
            log_success "  Decoded $count secrets from CHIT Geometry Packet (placeholders filtered)"
            return 0
        fi
    fi

    log_warning "  CHIT decode failed (Python CHIT module not available)"
    return 1
}

# =============================================================================
# Load Credentials from git-crypt Encrypted File
# =============================================================================

load_from_git_crypt() {
    local output_file="${1:-.env.bootstrap}"
    local enc_paths=(
        # Current repository
        "$(pwd)/pmoves/.env.enc"
        "$(pwd)/.env.enc"
        # Parent directories
        "$(pwd)/../pmoves/.env.enc"
        "$(pwd)/../../pmoves/.env.enc"
        "$(pwd)/../../../pmoves/.env.enc"
    )

    log_info "Attempting to load from git-crypt..."

    # Find encrypted file
    local enc_file=""
    for path in "${enc_paths[@]}"; do
        if [ -f "$path" ]; then
            enc_file="$path"
            break
        fi
    done

    if [ -z "$enc_file" ]; then
        log_info "  No git-crypt file found (checked: pmoves/.env.enc, .env.enc, etc.)"
        return 1
    fi

    log_info "  Found git-crypt file at: $enc_file"

    # Check if file is decrypted (content is readable)
    local first_line=$(head -1 "$enc_file" 2>/dev/null || echo "")

    # git-crypt encrypted files start with specific bytes
    # If we can read a normal-looking line, it's decrypted
    # Use proper glob patterns to detect environment variable declarations (e.g., VAR_NAME=)
    if [[ "$first_line" == *"#"* ]] || [[ "$first_line" =~ ^[A-Z_]+[[:space:]]*= ]] || [[ "$first_line" == *"PMOVES"* ]]; then
        # File is decrypted, load it (filtering placeholders)
        grep -E '^[A-Z_]+=' "$enc_file" 2>/dev/null | \
            grep -vE '-here$|-if-needed$|-when-needed$|-optional$' | \
            grep -vE '@your-' | \
            grep -vE '=TEMPLATE_' | \
            grep -vE '^TEMPLATE_' | \
            grep -vE '=Replace this with actual' \
            >> "$output_file" || true
        local count=$(grep -c '^' "$output_file" 2>/dev/null || echo "0")
        log_success "  Loaded $count credentials from git-crypt (decrypted, placeholders filtered)"
        return 0
    else
        log_warning "  git-crypt file is encrypted. Run: git-crypt unlock"
        log_info "  Then re-run bootstrap to load credentials."
        return 1
    fi
}

# =============================================================================
# Load Credentials from GitHub Secrets (GitHub Actions/Codespaces)
# =============================================================================

load_from_github_secrets() {
    local output_file="${1:-.env.bootstrap}"

    # Check if running in GitHub Actions or Codespaces
    if [ -z "${GITHUB_ACTIONS:-}" ] && [ -z "${CODESPACES:-}" ]; then
        return 1
    fi

    log_info "Attempting to load from GitHub Secrets..."

    # List of GitHub Secrets to try loading
    # These match common GitHub Secret names for PMOVES.AI
    local secret_vars=(
        "OPENAI_API_KEY"
        "ANTHROPIC_API_KEY"
        "GOOGLE_API_KEY"
        "GEMINI_API_KEY"
        "OPENROUTER_API_KEY"
        "VENICE_API_KEY"
        "HUGGINGFACE_HUB_TOKEN"
        "VOYAGE_API_KEY"
        "COHERE_API_KEY"
        "TELEGRAM_BOT_TOKEN"
        "TELEGRAM_BOT_NAME"
        "DISCORD_BOT_TOKEN"
        "SUPABASE_URL"
        "SUPABASE_SERVICE_KEY"
        "SUPABASE_ANON_KEY"
        "RESEND_API_KEY"
        "TENSORZERO_API_KEY"
        "OPEN_NOTEBOOK_API_KEY"
        "E2B_API_KEY"
        "JINA_API_KEY"
        "FIREWORKS_API_KEY"
        "REPLICATE_API_TOKEN"
        "LANGCHAIN_API_KEY"
        "TAVILY_API_KEY"
        "SERPER_API_KEY"
        "BRIGHTDATA_API_KEY"
    )

    local found=0
    for var in "${secret_vars[@]}"; do
        # Use indirect expansion to get the variable's value
        local value="${!var:-}"
        if [ -n "$value" ]; then
            echo "${var}=${value}" >> "$output_file"
            log_info "  Loaded $var from GitHub Secret"
            ((found++))
        fi
    done

    if [ $found -gt 0 ]; then
        log_success "  Loaded $found credentials from GitHub Secrets"
        return 0
    else
        log_info "  No GitHub Secrets found"
        return 1
    fi
}

# =============================================================================
# Load Credentials from Active GitHub/Docker API Fetcher
# =============================================================================

load_from_active_fetcher() {
    local output_file="${1:-.env.bootstrap}"

    log_info "Attempting active credential fetching..."

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log_info "  Python 3 not available for active fetching"
        return 1
    fi

    # Check if credential_fetcher module exists
    local fetcher_module="$(dirname "${BASH_SOURCE[0]}")/../pmoves/tools/credential_fetcher.py"
    if [ ! -f "$fetcher_module" ]; then
        # Try relative to repo root
        fetcher_module="pmoves/tools/credential_fetcher.py"
    fi

    if [ ! -f "$fetcher_module" ]; then
        log_info "  Credential fetcher module not found"
        return 1
    fi

    # Run the active fetcher
    local temp_output="${output_file}.active"

    # Check for GitHub credentials
    local github_owner="${GITHUB_OWNER:-}"
    local github_repo="${GITHUB_REPO:-}"
    if [ -n "$github_owner" ] && [ -n "$github_repo" ]; then
        log_info "  Fetching from GitHub: ${github_owner}/${github_repo}"
    fi

    # Execute the Python fetcher
    local err_file="${output_file}.fetch.err"
    if python3 "$fetcher_module" fetch \
        --output "$temp_output" \
        ${github_owner:+--github-owner "$github_owner"} \
        ${github_repo:+--github-repo "$github_repo"} \
        2> "$err_file"; then

        # Merge with existing output
        if [ -f "$temp_output" ]; then
            # Get count BEFORE deleting file (fixes race condition)
            local var_count=$(grep -E '^[A-Z0-9_]+=' "$temp_output" 2>/dev/null | wc -l)
            cat "$temp_output" >> "$output_file"
            rm -f "$temp_output"
            rm -f "$err_file"
            log_success "  Fetched $var_count credentials via active fetcher"
            return 0
        fi
    else
        # Fetcher failed - show error if available
        local exit_code=$?
        if [ -f "$err_file" ] && [ -s "$err_file" ]; then
            log_error "  Active fetcher failed:"
            while IFS= read -r line; do
                log_error "    $line"
            done < "$err_file"
        else
            log_info "  Active fetcher failed with exit code $exit_code"
        fi
        rm -f "$err_file"
    fi

    log_info "  Active fetcher completed but no credentials found"
    rm -f "$temp_output"
    return 1
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
# Filter out truly empty values that should have content
# =============================================================================

filter_empty_values() {
    local output_file="${1:-.env.bootstrap}"

    if [ ! -f "$output_file" ]; then
        return 0
    fi

    # Filter out empty values for keys that SHOULD have content
    # Keys ending in _KEY, _TOKEN, _SECRET, _PASSWORD must have values
    # Exception: _API_BASE= is valid (means use default)
    local temp_file="${output_file}.tmp"
    grep -E '^[A-Z_]+=' "$output_file" 2>/dev/null | \
        grep -vE '^(OPENAI_API_BASE|OPENAI_COMPATIBLE_BASE|CUSTOM_.*|ALTERNATIVE_.*|FALLBACK_.*)=$' | \
        grep -vE '(_KEY|_TOKEN|_SECRET|_PASSWORD|_API_KEY)=$' \
        > "$temp_file" || true

    # Check if any entries were removed
    local original_count=$(grep -c '^[A-Z_]+=' "$output_file" 2>/dev/null || echo "0")
    local filtered_count=$(grep -c '^[A-Z_]+=' "$temp_file" 2>/dev/null || echo "0")

    if [ "$original_count" -gt "$filtered_count" ]; then
        local removed=$((original_count - filtered_count))
        log_info "  Filtered $removed empty credential values (keys without values)"
        mv "$temp_file" "$output_file"
    else
        rm -f "$temp_file"
    fi
}

# =============================================================================
# Main Bootstrap Flow
# =============================================================================

main() {
    local output_file=".env.bootstrap"
    local parent_dir=""
    local source_used=""

    log_info "PMOVES.AI Credential Bootstrap v5"
    log_info "====================================="

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
        log_mode "STANDALONE MODE detected - trying Active Fetcher, GitHub Secrets, CHIT, git-crypt, Docker secrets"
        echo ""

        # STANDALONE MODE: Try multiple sources
        local sources_tried=()

        # 1. Try Active Fetcher FIRST (new in v5 - calls GitHub/Docker APIs)
        if [ "${USE_ACTIVE_FETCHER:-true}" = "true" ]; then
            if load_from_active_fetcher "$output_file"; then
                source_used="Active Fetcher"
                sources_tried+=("Active Fetcher: success")
            else
                sources_tried+=("Active Fetcher: failed (not configured or no credentials found)")
            fi
        fi

        # 2. Try GitHub Secrets (highest priority in GitHub Actions/Codespaces)
        if load_from_github_secrets "$output_file"; then
            source_used="GitHub Secrets"
            sources_tried+=("GitHub Secrets: success")
        else
            sources_tried+=("GitHub Secrets: skipped (not in GitHub environment)")
        fi

        # 2. Try CHIT decode
        if load_from_chit "$output_file"; then
            source_used="${source_used:+$source_used + }CHIT Geometry Packet"
            sources_tried+=("CHIT: success")
        else
            sources_tried+=("CHIT: failed")
        fi

        # 3. Try git-crypt
        if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 3 ]; then
            if load_from_git_crypt "$output_file"; then
                source_used="${source_used:+$source_used + }git-crypt"
                sources_tried+=("git-crypt: success")
            else
                sources_tried+=("git-crypt: failed")
            fi
        fi

        # 4. Try Docker Secrets
        if [ ! -s "$output_file" ] || [ $(grep -c '^' "$output_file" 2>/dev/null || echo "0") -lt 3 ]; then
            if load_from_docker_secrets "$output_file"; then
                source_used="${source_used:+$source_used + }Docker Secrets"
                sources_tried+=("Docker: success")
            else
                sources_tried+=("Docker: failed")
            fi
        fi

        # 5. Fallback: Try parent (last resort in standalone)
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

    # Filter out empty credential values
    filter_empty_values "$output_file"

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
        log_info "  1. Set GitHub Secrets in repository settings"
        log_info "  2. Create CHIT Geometry Packet: python3 -m pmoves.tools.chit_encode_secrets"
        log_info "  3. OR setup git-crypt: git-crypt init && git-crypt add-gpg-user you@email.com"
        log_info "  4. OR create Docker secrets for your stack"
        log_info "  5. OR create .env file manually with required credentials"
        echo ""
        log_info "Full documentation: pmoves/docs/SECRETS.md"
        return 1
    fi
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
