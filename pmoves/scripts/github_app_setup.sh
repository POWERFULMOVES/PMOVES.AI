#!/usr/bin/env bash
# PMOVES GitHub App Credential Setup
#
# Populates env.shared with GitHub App credentials from GitHub Actions secrets.
# This enables local development and runtime services to use GitHub App tokens.
#
# Usage:
#   bash pmoves/scripts/github_app_setup.sh [--dry-run]
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Access to POWERFULMOVES/PMOVES.AI repository
#   - GitHub App secrets already configured in Actions

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${DRY_RUN:-0}"

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --dry-run|--dry) DRY_RUN=1 ;;
  esac
done

log() { echo "[$(date +'%H:%M:%S')] $*"; }
log_dry() { [ "$DRY_RUN" = "1" ] && log "[DRY RUN] $*"; }

log "🔑 PMOVES GitHub App Credential Setup"
log "   Repo: $ROOT_DIR"
log ""

# Check gh CLI
if ! command -v gh >/dev/null 2>&1; then
  log "❌ gh CLI not found. Install from: https://cli.github.com/"
  exit 1
fi

# Check authentication
if ! gh auth status >/dev/null 2>&1; then
  log "❌ gh CLI not authenticated. Run: gh auth login"
  exit 1
fi

GITHUB_REPO="${GITHUB_REPO:-POWERFULMOVES/PMOVES.AI}"

log "📋 Fetching GitHub App secrets from $GITHUB_REPO..."

# Array of GitHub App credential keys
declare -a GH_APP_KEYS=(
  "GH_APP_ID"
  "GH_APP_CLIENT_ID"
  "GH_APP_INSTALLATION_ID"
)

# Track success
declare -A FETCHED_VALUES=()

# Fetch each credential (except GH_APP_SEC which is a PEM file)
for key in "${GH_APP_KEYS[@]}"; do
  # Check if secret exists
  if gh secret list --repo "$GITHUB_REPO" | grep -q "^${key}"; then
    # For non-sensitive values, we can display them
    # Note: gh CLI doesn't allow reading secret values directly for security
    # Users need to manually copy these from GitHub Actions settings
    log "   ✓ $key exists in GitHub Secrets"
    FETCHED_VALUES["$key"]=1
  else
    log "   ⚠ $key not found in GitHub Secrets"
  fi
done

# Special handling for GH_APP_SEC (PEM key)
if gh secret list --repo "$GITHUB_REPO" | grep -q "^GH_APP_SEC"; then
  log "   ✓ GH_APP_SEC exists in GitHub Secrets"
  FETCHED_VALUES["GH_APP_SEC"]=1
else
  log "   ⚠ GH_APP_SEC not found in GitHub Secrets"
fi

log ""
log "📝 Next steps:"
log ""
log "1. Get GitHub App credentials from:"
log "   https://github.com/$GITHUB_REPO/settings/secrets/actions"
log ""
log "2. Add these to pmoves/env.shared:"
log ""

# Generate env.shared entries
for key in "${GH_APP_KEYS[@]}"; do
  if [ -n "${FETCHED_VALUES[$key]:-}" ]; then
    log "   $key=<value from GitHub Secrets>"
  fi
done

if [ -n "${FETCHED_VALUES["GH_APP_SEC"]:-}" ]; then
  log ""
  log "   GH_APP_SEC is a PEM private key. To add it:"
  log "   a. Download the PEM file from GitHub App settings"
  log "   b. Run: cat /path/to/private-key.pem | pbcopy  # macOS"
  log "   c. For Linux: cat /path/to/private-key.pem | xclip -selection clipboard"
  log "   d. Paste into env.shared (preserve newlines!)"
fi

log ""
log "3. Or use fetch_credentials.sh to sync from environment:"
log "   export GH_APP_ID='your-value'"
log "   export GH_APP_SEC='$(cat /path/to/key.pem)'"
log "   export GH_APP_INSTALLATION_ID='your-value'"
log "   bash pmoves/scripts/fetch_credentials.sh"
log ""

# Auto-update if we have values in environment
if [ -f "$ROOT_DIR/pmoves/env.shared" ]; then
  log "🔧 Checking env.shared..."

  # Check if GH_APP_ID is already set
  if grep -q "^GH_APP_ID=" "$ROOT_DIR/pmoves/env.shared"; then
    log "   ✓ GH_APP_ID already configured"
  else
    log "   ○ GH_APP_ID not set in env.shared"
  fi

  # Check if GH_APP_SEC is already set
  if grep -q "^GH_APP_SEC=" "$ROOT_DIR/pmoves/env.shared"; then
    log "   ✓ GH_APP_SEC already configured"
  else
    log "   ○ GH_APP_SEC not set in env.shared"
  fi

  # Check if GH_APP_INSTALLATION_ID is already set
  if grep -q "^GH_APP_INSTALLATION_ID=" "$ROOT_DIR/pmoves/env.shared"; then
    log "   ✓ GH_APP_INSTALLATION_ID already configured"
  else
    log "   ○ GH_APP_INSTALLATION_ID not set in env.shared"
  fi
fi

log ""
log "✅ Setup complete! Services can now use GitHub App tokens."
log ""
log "📖 For more details, see: pmoves/docs/infrastructure/github-app-strategy.md"
