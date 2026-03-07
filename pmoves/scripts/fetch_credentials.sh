#!/usr/bin/env bash
# PMOVES Credential Fetcher for Production Bring-Up
#
# Fetches available credentials from:
# - GitHub Secrets (via gh CLI - checks existence, reads from env)
# - Docker config (registry auth from ~/.docker/config.json)
# - Current environment (any *_KEY, *_TOKEN, *_SECRET vars)
#
# Writes to: env.shared, env.tier-llm, .env.generated
#
# Usage:
#   bash scripts/fetch_credentials.sh [--verbose|--dry-run]

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

VERBOSE="${VERBOSE:-0}"
DRY_RUN="${DRY_RUN:-0}"

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE=1 ;;
    --dry-run|--dry) DRY_RUN=1 ;;
  esac
done

log() { echo "[$(date +'%H:%M:%S')] $*"; }
log_verbose() { [ "$VERBOSE" = "1" ] && log "$*"; }
log_dry() { [ "$DRY_RUN" = "1" ] && log "[DRY RUN] $*"; }

# Track what we found/fetched
# Note: Using empty associative arrays - must check with ${!array[@]:+"isset"} pattern
declare -A GITHUB_SECRETS=()
declare -A DOCKER_CREDS=()
declare -A ENV_CREDS=()

log "🔍 PMOVES Credential Fetcher"
log "   Root: $ROOT_DIR"

# =============================================================================
# 1. Check GitHub Secrets (via gh CLI)
# =============================================================================
log "   Checking GitHub Secrets availability..."

if command -v gh >/dev/null 2>&1; then
  # Check if authenticated
  if gh auth status >/dev/null 2>&1; then
    GITHUB_REPO="${GITHUB_REPO:-POWERFULMOVES/PMOVES.AI}"
    log "   ✓ gh CLI authenticated"

    # List secrets (names only - values are security-restricted)
    if gh secret list --repo "$GITHUB_REPO" >/dev/null 2>&1; then
      SECRET_NAMES=$(gh secret list --repo "$GITHUB_REPO" 2>/dev/null | awk '{print $1}' || true)
      COUNT=$(echo "$SECRET_NAMES" | wc -w)
      log "   Found $COUNT GitHub secrets in $GITHUB_REPO"

      # For each secret, check if value exists in environment
      for secret in $SECRET_NAMES; do
        env_name="${secret}"  # Try exact name
        if [ -z "${!env_name:-}" ]; then
          # Try with PMOVES_ prefix
          env_name="PMOVES_${secret}"
        fi
        value="${!env_name:-}"

        if [ -n "$value" ]; then
          GITHUB_SECRETS["$secret"]="$value"
          log_verbose "   ✓ $secret from environment"
        else
          log_verbose "   ○ $secret exists in GitHub but not in environment"
        fi
      done
    else
      log "   ⚠ Could not list secrets from $GITHUB_REPO"
    fi
  else
    log "   ⚠ gh CLI not authenticated"
  fi
else
  log "   ⚠ gh CLI not found"
fi

# =============================================================================
# 2. Check Docker Config
# =============================================================================
log "   Checking Docker registry credentials..."

DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker/config.json}"
if [ -f "$DOCKER_CONFIG" ]; then
  # Extract auths using basic parsing (no jq for portability)
  log "   ✓ Docker config found"

  # Read auths - simple grep/parse approach
  while IFS= read -r line; do
    # Look for registry auth in format: "https://index.docker.io/v1/": { "auth": "..." }
    if [[ "$line" =~ \"https://[^\"]+\":[[:space:]]*\{[[:space:]]*\"auth\":[[:space:]]*\"([^\"]+)\" ]]; then
      AUTH="${BASH_REMATCH[1]}"
      if [ -n "$AUTH" ]; then
        # Decode base64 auth (username:password)
        if command -v base64 >/dev/null 2>&1; then
          DECODED=$(echo "$AUTH" | base64 -d 2>/dev/null || echo "")
          if [ -n "$DECODED" ]; then
            USERNAME="${DECODED%%:*}"
            PASSWORD="${DECODED#*:}"
            # Check for GHCR, Docker Hub, etc.
            if [[ "$line" =~ "index.docker.io" ]] || [[ "$line" =~ "ghcr.io" ]]; then
              if [[ "$line" =~ "ghcr.io" ]]; then
                DOCKER_CREDS["GHCR_USERNAME"]="$USERNAME"
                DOCKER_CREDS["GHCR_PASSWORD"]="$PASSWORD"
                log_verbose "   ✓ GHCR credentials found"
              else
                DOCKER_CREDS["DOCKER_HUB_USERNAME"]="$USERNAME"
                DOCKER_CREDS["DOCKER_HUB_PASSWORD"]="$PASSWORD"
                log_verbose "   ✓ Docker Hub credentials found"
              fi
            fi
          fi
        fi
      fi
    fi
  done < "$DOCKER_CONFIG"
else
  log "   ⚠ Docker config not found at $DOCKER_CONFIG"
fi

# =============================================================================
# 3. Scan Current Environment for Credential-like Variables
# =============================================================================
log "   Scanning environment for credential variables..."

# Scan environment for credential-like variables
# Use temp file to avoid subshell issue with associative arrays
TEMP_ENV_CREDS=$(mktemp)

# Collect credential variables with simple pattern matching
printenv | while IFS='=' read -r var value; do
  # Check if it looks like a credential
  case "$var" in
    *_API_KEY|*_TOKEN|*_SECRET|*_PASSWORD|*_PRIVATE_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|GROQ_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|MISTRAL_API_KEY|DEEPSEEK_API_KEY|OPENROUTER_API_KEY|XAI_API_KEY|ELEVENLABS_API_KEY|VOYAGE_API_KEY|COHERE_API_KEY|FIREWORKS_AI_API_KEY|PERPLEXITYAI_API_KEY|TOGETHER_AI_API_KEY|Z_AI_API_KEY|ALIBABA_PRO_CODING_PLAN|VENICE_API_KEY|CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID|OLLAMA_BASE_URL)
      if [ -n "$value" ]; then
        echo "$var=$value" >> "$TEMP_ENV_CREDS"
      fi
      ;;
  esac
done

# Load collected credentials
while IFS='=' read -r var value; do
  ENV_CREDS["$var"]="$value"
  log_verbose "   ✓ $var (set)"
done < "$TEMP_ENV_CREDS"

rm -f "$TEMP_ENV_CREDS"
log "   Found ${#ENV_CREDS[@]} credential variables in environment"

# =============================================================================
# 4. Merge and Write to Files
# =============================================================================
log ""
log "📝 Writing credentials to env files..."

# Track written files
declare -a WRITTEN_FILES=()

# Function to write key=value to a file (with backup)
write_to_env() {
  local file="$1"
  local key="$2"
  local value="$3"
  local temp_file="${file}.tmp"

  # Create directory if needed
  mkdir -p "$(dirname "$file")"

  # Check if file exists
  if [ -f "$file" ]; then
    # Check if key already exists
    if grep -q "^${key}=" "$file" 2>/dev/null; then
      # Update existing value
      if [ "$DRY_RUN" = "1" ]; then
        log_dry "   Would update $key in $file"
      else
        # Use sed for in-place update
        sed -i "s/^${key}=.*/${key}=${value}/" "$file"
        log_verbose "   ✓ Updated $key in $file"
      fi
    else
      # Append new key
      if [ "$DRY_RUN" = "1" ]; then
        log_dry "   Would add $key to $file"
      else
        echo "${key}=${value}" >> "$file"
        log_verbose "   ✓ Added $key to $file"
      fi
    fi
  else
    # Create new file
    if [ "$DRY_RUN" = "1" ]; then
      log_dry "   Would create $file with $key"
    else
      echo "# Auto-generated by fetch_credentials.sh" > "$file"
      echo "${key}=${value}" >> "$file"
      log_verbose "   ✓ Created $file with $key"
    fi
  fi

  # Track this file as written
  if [[ ! " ${WRITTEN_FILES[@]} " =~ " ${file} " ]]; then
    WRITTEN_FILES+=("$file")
  fi
}

# Write GitHub-sourced credentials to .env.generated
for secret in "${!GITHUB_SECRETS[@]}"; do
  write_to_env "$ROOT_DIR/.env.generated" "$secret" "${GITHUB_SECRETS[$secret]}"
done

# Write Docker-sourced credentials to env.shared
for cred in "${!DOCKER_CREDS[@]}"; do
  write_to_env "$ROOT_DIR/env.shared" "$cred" "${DOCKER_CREDS[$cred]}"
done

# Write environment-sourced credentials to env.shared
# These are the main API keys for LLM providers
TARGET_KEYS=("OPENAI_API_KEY" "ANTHROPIC_API_KEY" "GROQ_API_KEY" "GEMINI_API_KEY" "GOOGLE_API_KEY" "MISTRAL_API_KEY" "DEEPSEEK_API_KEY" "OPENROUTER_API_KEY" "XAI_API_KEY" "ELEVENLABS_API_KEY" "VOYAGE_API_KEY" "COHERE_API_KEY" "FIREWORKS_AI_API_KEY" "PERPLEXITYAI_API_KEY" "TOGETHER_AI_API_KEY" "Z_AI_API_KEY" "ALIBABA_PRO_CODING_PLAN" "VENICE_API_KEY" "CLOUDFLARE_API_TOKEN" "CLOUDFLARE_ACCOUNT_ID" "OLLAMA_CLOUD_API_KEY")

# Check env.tier-llm for LLM provider keys
for key in "${TARGET_KEYS[@]}"; do
  if [ -n "${ENV_CREDS[$key]:-}" ]; then
    # Write to both env.shared and env.tier-llm
    write_to_env "$ROOT_DIR/env.shared" "$key" "${ENV_CREDS[$key]}"
    write_to_env "$ROOT_DIR/env.tier-llm" "$key" "${ENV_CREDS[$key]}"
  fi
done

# =============================================================================
# 5. Summary Report
# =============================================================================
log ""
log "═══════════════════════════════════════════════════════════"
log "  CREDENTIAL FETCH SUMMARY"
log "═══════════════════════════════════════════════════════════"

# Safe check: if array has any keys, iterate
if [[ "${!GITHUB_SECRETS[*]}" ]]; then
  log ""
  log "GitHub Secrets (from environment):"
  for secret in "${!GITHUB_SECRETS[@]}"; do
    log "   ✓ $secret"
  done
fi

# Safe check: if array has any keys, iterate
if [[ "${!DOCKER_CREDS[*]}" ]]; then
  log ""
  log "Docker Registry Credentials:"
  for cred in "${!DOCKER_CREDS[@]}"; do
    log "   ✓ $cred"
  done
fi

# Safe check: if array has any keys
if [[ "${!ENV_CREDS[*]}" ]]; then
  log ""
  log "Environment Credential Variables: ${#ENV_CREDS[@]}"
fi

log ""
log "Files Updated:"
if [ ${#WRITTEN_FILES[@]} -eq 0 ]; then
  log "   (none - no credentials to write)"
else
  for file in "${WRITTEN_FILES[@]}"; do
    # Show relative path from root
    rel_path="${file#$ROOT_DIR/}"
    log "   ✓ $rel_path"
  done
fi

log ""
log "═══════════════════════════════════════════════════════════"

# Exit with appropriate code - safely count array elements
written_ct=${#WRITTEN_FILES[@]}
# Use pattern expansion to safely get array lengths (defaults to 0 if empty)
github_keys=("${!GITHUB_SECRETS[@]}")
github_ct=${#github_keys[@]}
docker_keys=("${!DOCKER_CREDS[@]}")
docker_ct=${#docker_keys[@]}
if [ "$written_ct" -eq 0 ] && [ "$github_ct" -eq 0 ] && [ "$docker_ct" -eq 0 ]; then
  log "⚠ No credentials found - services will use local-only mode"
  log "   To add API keys, set them in your shell before running bring-up:"
  log "   export OPENAI_API_KEY=sk-..."
  log "   export ANTHROPIC_API_KEY=sk-ant-..."
fi

exit 0
