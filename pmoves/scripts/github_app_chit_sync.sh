#!/usr/bin/env bash
# GitHub App CHIT Sync Helper
#
# This script automates the CHIT credentials workflow for GitHub App integration.
# Run this AFTER populating GitHub App credentials in env.shared.
#
# Usage: bash pmoves/scripts/github_app_chit_sync.sh

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

PMOVES_DIR="$ROOT_DIR/pmoves"
ENV_SHARED="$PMOVES_DIR/env.shared"
CHIT_BUNDLE="$PMOVES_DIR/data/chit/env.cgp.json"

log() { echo "[$(date +'%H:%M:%S')] $*"; }
log_error() { echo "❌ $*" >&2; }
log_success() { echo "✅ $*"; }
log_step() { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

log "🔐 PMOVES GitHub App CHIT Sync"
log ""

# Check if we're in the right directory
if [ ! -f "$ENV_SHARED" ]; then
  log_error "env.shared not found at: $ENV_SHARED"
  exit 1
fi

# Function to check if GitHub App credentials are populated
check_credentials() {
  log "📋 Checking GitHub App credentials in env.shared..."

  local missing=0

  # Check GH_APP_ID
  if grep -q "^#GH_APP_ID=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_ID is commented out"
    missing=1
  elif grep -q "^GH_APP_ID=$" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_ID is empty"
    missing=1
  elif ! grep -q "^GH_APP_ID=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_ID not found"
    missing=1
  else
    log_success "  ✓ GH_APP_ID is populated"
  fi

  # Check GH_APP_INSTALLATION_ID
  if grep -q "^#GH_APP_INSTALLATION_ID=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_INSTALLATION_ID is commented out"
    missing=1
  elif grep -q "^GH_APP_INSTALLATION_ID=$" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_INSTALLATION_ID is empty"
    missing=1
  elif ! grep -q "^GH_APP_INSTALLATION_ID=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_INSTALLATION_ID not found"
    missing=1
  else
    log_success "  ✓ GH_APP_INSTALLATION_ID is populated"
  fi

  # Check GH_APP_SEC
  if grep -q "^#GH_APP_SEC=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_SEC is commented out"
    missing=1
  elif grep -q "^GH_APP_SEC=$" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_SEC is empty"
    missing=1
  elif ! grep -q "^GH_APP_SEC=" "$ENV_SHARED"; then
    log_error "  ❌ GH_APP_SEC not found"
    missing=1
  else
    log_success "  ✓ GH_APP_SEC is populated"
  fi

  log ""
  if [ $missing -eq 1 ]; then
    log_error "GitHub App credentials are not fully populated in env.shared"
    log ""
    log "Please populate credentials first:"
    log "  1. Edit pmoves/env.shared"
    log "  2. Uncomment GH_APP_ID, GH_APP_SEC, GH_APP_INSTALLATION_ID"
    log "  3. Add actual credential values"
    log "  4. Run this script again"
    log ""
    log "Or use: bash pmoves/scripts/populate_github_app_secrets.sh"
    exit 1
  fi

  log_success "All required GitHub App credentials are populated"
  log ""
}

# Function to encode to CHIT bundle
encode_chit_bundle() {
  log_step
  log "🔢 Encoding credentials to CHIT bundle..."
  log ""

  cd "$PMOVES_DIR"

  # Run chit_encode_secrets.py
  if python tools/chit_encode_secrets.py; then
    log_success "CHIT bundle created: $CHIT_BUNDLE"
  else
    log_error "Failed to encode CHIT bundle"
    exit 1
  fi

  log ""
}

# Function to sync to tier files
sync_to_tier_files() {
  log_step
  log "🔄 Syncing credentials to tier files..."
  log ""

  cd "$PMOVES_DIR"

  # Run secrets_sync.py
  if python tools/secrets_sync.py generate --manifest chit/secrets_manifest_v2.yaml; then
    log_success "Credentials synced to tier files"
  else
    log_error "Failed to sync credentials"
    exit 1
  fi

  log ""
}

# Function to verify output
verify_output() {
  log_step
  log "✅ Verifying output..."
  log ""

  # Check if CHIT bundle contains GitHub App credentials
  log "Checking CHIT bundle..."
  if command -v jq &> /dev/null; then
    if jq -e '.env.GH_APP_ID' "$CHIT_BUNDLE" &> /dev/null; then
      log_success "  ✓ CHIT bundle contains GH_APP_ID"
    else
      log_error "  ❌ CHIT bundle missing GH_APP_ID"
    fi

    if jq -e '.env.GH_APP_INSTALLATION_ID' "$CHIT_BUNDLE" &> /dev/null; then
      log_success "  ✓ CHIT bundle contains GH_APP_INSTALLATION_ID"
    else
      log_error "  ❌ CHIT bundle missing GH_APP_INSTALLATION_ID"
    fi
  else
    log "  ⚠️  jq not installed, skipping JSON verification"
  fi

  log ""

  # Check if env.tier-agent contains GitHub App credentials
  log "Checking env.tier-agent..."
  if [ -f "$PMOVES_DIR/env.tier-agent" ]; then
    if grep -q "^GH_APP_ID=" "$PMOVES_DIR/env.tier-agent"; then
      log_success "  ✓ env.tier-agent contains GH_APP_ID"
    else
      log_error "  ❌ env.tier-agent missing GH_APP_ID"
    fi

    if grep -q "^GH_APP_INSTALLATION_ID=" "$PMOVES_DIR/env.tier-agent"; then
      log_success "  ✓ env.tier-agent contains GH_APP_INSTALLATION_ID"
    else
      log_error "  ❌ env.tier-agent missing GH_APP_INSTALLATION_ID"
    fi
  else
    log_error "  ❌ env.tier-agent not found"
  fi

  log ""
}

# Function to show next steps
show_next_steps() {
  log_step
  log "🚀 Next Steps"
  log ""
  log "1. Test token minting:"
  log "   cd PMOVES-BoTZ"
  log "   export GH_APP_ID=\$(grep \"^GH_APP_ID=\" ../pmoves/env.shared | cut -d'=' -f2)"
  log "   export GH_APP_SEC=\$(grep \"^GH_APP_SEC=\" ../pmoves/env.shared | cut -d'=' -f2-)"
  log "   export GH_APP_INSTALLATION_ID=\$(grep \"^GH_APP_INSTALLATION_ID=\" ../pmoves/env.shared | cut -d'=' -f2)"
  log "   python features/github/mint_and_exec.py"
  log ""
  log "2. Start services:"
  log "   cd pmoves"
  log "   docker compose up -d archon botz-gateway"
  log "   docker compose logs -f archon botz-gateway"
  log ""
  log "3. Verify service health:"
  log "   curl http://localhost:8054/healthz  # BoTZ gateway"
  log "   curl http://localhost:8091/healthz  # Archon"
  log ""
  log "4. Run comprehensive verification:"
  log "   bash pmoves/scripts/verify_github_app.sh"
  log ""
}

# Main workflow
main() {
  check_credentials
  encode_chit_bundle
  sync_to_tier_files
  verify_output
  show_next_steps

  log_step
  log_success "GitHub App CHIT sync complete!"
  log ""
}

main "$@"
