#!/usr/bin/env bash
# GitHub App Credential Population Helper
#
# This script helps populate GitHub App credentials in env.shared
# by guiding you through the process of retrieving and formatting them.

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

ENV_SHARED="$ROOT_DIR/pmoves/env.shared"

log() { echo "[$(date +'%H:%M:%S')] $*"; }
log_error() { echo "❌ $*" >&2; }
log_success() { echo "✅ $*"; }

log "🔑 PMOVES GitHub App Credential Population"
log ""

# Check if env.shared exists
if [ ! -f "$ENV_SHARED" ]; then
  log_error "env.shared not found at: $ENV_SHARED"
  exit 1
fi

log "This script will help you populate GitHub App credentials."
log "You'll need the following values from GitHub:"
log ""
log "1. GH_APP_ID - Numeric App ID"
log "2. GH_APP_CLIENT_ID - OAuth Client ID (optional)"
log "3. GH_APP_INSTALLATION_ID - Installation ID for POWERFULMOVES org"
log "4. GH_APP_SEC - PEM private key contents"
log ""

# Function to uncomment and set value
set_credential() {
  local key="$1"
  local prompt="$2"
  local default="${3:-}"

  log "📝 $prompt"
  if [ -n "$default" ]; then
    log "   Default: $default"
  fi
  log "   Current in env.shared:"
  grep "^#${key}=" "$ENV_SHARED" || grep "^${key}=" "$ENV_SHARED" || true
  echo ""

  # Check if already uncommented
  if grep -q "^${key}=" "$ENV_SHARED"; then
    log "   ✓ $key is already uncommented"
    # Check if it has a value
    current_value=$(grep "^${key}=" "$ENV_SHARED" | cut -d'=' -f2)
    if [ -n "$current_value" ]; then
      log "   ✓ $key has a value set"
      echo ""
      return 0
    fi
  fi

  # For GH_APP_SEC, we need special handling (multiline)
  if [ "$key" = "GH_APP_SEC" ]; then
    log ""
    log "   GH_APP_SEC requires your PEM private key."
    log "   Please provide the path to your PEM file:"
    read -p "   Path to PEM file: " pem_path

    if [ -z "$pem_path" ]; then
      log "   ⚠ Skipping GH_APP_SEC (you can add it manually)"
      echo ""
      return 0
    fi

    if [ ! -f "$pem_path" ]; then
      log_error "PEM file not found: $pem_path"
      return 1
    fi

    # Read PEM content
    pem_content=$(cat "$pem_path")

    # Uncomment and set value
    sed -i "s|^#${key}=.*|${key}=${pem_content}|" "$ENV_SHARED"
    log_success "GH_APP_SEC populated from $pem_path"
    echo ""
    return 0
  fi

  # For regular values, prompt for input
  read -p "   Value (or press Enter to skip): " value

  if [ -z "$value" ] && [ -n "$default" ]; then
    value="$default"
  fi

  if [ -z "$value" ]; then
    log "   ⚠ Skipping $key (you can add it manually)"
    echo ""
    return 0
  fi

  # Uncomment and set value
  sed -i "s|^#${key}=.*|${key}=${value}|" "$ENV_SHARED"
  log_success "$key populated"
  echo ""
}

# Interactive population
set_credential "GH_APP_ID" "GitHub App ID (numeric)"
set_credential "GH_APP_CLIENT_ID" "GitHub App Client ID (optional)"
set_credential "GH_APP_INSTALLATION_ID" "Installation ID (numeric)"

# Special prompt for PEM key
log "📝 GH_APP_SEC - PEM Private Key"
log "   This is the full contents of your private key file."
log "   Current in env.shared:"
grep "^#GH_APP_SEC=" "$ENV_SHARED" || grep "^GH_APP_SEC=" "$ENV_SHARED" || true
log ""
log "   To populate GH_APP_SEC, you have two options:"
log ""
log "   Option 1: Provide PEM file path"
log "   Option 2: Skip and add manually (recommended for security)"
log ""
read -p "   Provide PEM file path now? (y/N): " provide_now

if [ "$provide_now" = "y" ] || [ "$provide_now" = "Y" ]; then
  set_credential "GH_APP_SEC" "GitHub App PEM Private Key"
else
  log "   ⚠ Skipping GH_APP_SEC (add manually with proper PEM formatting)"
  log ""
  log "   To add manually:"
  log "   1. Uncomment the GH_APP_SEC line in pmoves/env.shared"
  log "   2. Paste your PEM key contents after the equals sign"
  log "   3. Preserve newlines! The key should span multiple lines."
fi

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "✅ Credential population complete!"
log ""
log "Next steps:"
log "  1. Verify credentials: bash pmoves/scripts/verify_github_app.sh"
log "  2. Test token minting: cd PMOVES-BoTZ && python features/github/mint_and_exec.py"
log "  3. Start services: cd pmoves && docker compose up -d archon botz-gateway"
log ""
