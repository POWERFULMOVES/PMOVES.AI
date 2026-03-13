#!/usr/bin/env bash
# GitHub App Integration Verification Script
#
# Verifies that GitHub App credentials are properly configured
# and that services can access them.
#
# Usage:
#   bash pmoves/scripts/verify_github_app.sh [--verbose]

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
# Script is in pmoves/scripts/, so we need to go up two levels to reach repo root
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

VERBOSE="${VERBOSE:-0}"

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE=1 ;;
  esac
done

log() { echo "[$(date +'%H:%M:%S')] $*"; }
log_verbose() { [ "$VERBOSE" = "1" ] && log "$*"; }

log "🔍 PMOVES GitHub App Integration Verification"
log ""

# Track results
declare -a CHECKS=()
declare -a FAILURES=()

# Helper functions
check_pass() {
  log "   ✓ $1"
  CHECKS+=("✓ $1")
}

check_fail() {
  log "   ✗ $1"
  CHECKS+=("✗ $1")
  FAILURES+=("$1")
}

check_warn() {
  log "   ○ $1"
  CHECKS+=("○ $1")
}

# =============================================================================
# 1. Check env.shared Configuration
# =============================================================================
log "📋 Checking env.shared configuration..."

if [ -f "$ROOT_DIR/pmoves/env.shared" ]; then
  check_pass "env.shared exists"

  # Check for GitHub App credentials
  if grep -q "^GH_APP_ID=" "$ROOT_DIR/pmoves/env.shared"; then
    GH_APP_ID=$(grep "^GH_APP_ID=" "$ROOT_DIR/pmoves/env.shared" | cut -d'=' -f2)
    if [ -n "$GH_APP_ID" ]; then
      check_pass "GH_APP_ID is set (value: ${GH_APP_ID})"
    else
      check_fail "GH_APP_ID is empty"
    fi
  else
    check_fail "GH_APP_ID not found in env.shared"
  fi

  if grep -q "^GH_APP_SEC=" "$ROOT_DIR/pmoves/env.shared"; then
    GH_APP_SEC=$(grep "^GH_APP_SEC=" "$ROOT_DIR/pmoves/env.shared" | cut -d'=' -f2)
    if [ -n "$GH_APP_SEC" ]; then
      # Check if it looks like a PEM key
      if echo "$GH_APP_SEC" | grep -q "BEGIN.*PRIVATE KEY"; then
        check_pass "GH_APP_SEC is set (PEM key detected)"
      else
        check_warn "GH_APP_SEC is set but may not be a valid PEM key"
      fi
    else
      check_fail "GH_APP_SEC is empty"
    fi
  else
    check_fail "GH_APP_SEC not found in env.shared"
  fi

  if grep -q "^GH_APP_INSTALLATION_ID=" "$ROOT_DIR/pmoves/env.shared"; then
    GH_APP_INSTALLATION_ID=$(grep "^GH_APP_INSTALLATION_ID=" "$ROOT_DIR/pmoves/env.shared" | cut -d'=' -f2)
    if [ -n "$GH_APP_INSTALLATION_ID" ]; then
      check_pass "GH_APP_INSTALLATION_ID is set (value: ${GH_APP_INSTALLATION_ID})"
    else
      check_fail "GH_APP_INSTALLATION_ID is empty"
    fi
  else
    check_fail "GH_APP_INSTALLATION_ID not found in env.shared"
  fi
else
  check_fail "env.shared not found"
fi

log ""

# =============================================================================
# 2. Check Docker Compose Configuration
# =============================================================================
log "🐳 Checking Docker Compose configuration..."

if command -v docker >/dev/null 2>&1; then
  check_pass "Docker is installed"

  if docker compose version >/dev/null 2>&1; then
    check_pass "Docker Compose is available"

    # Check if docker-compose.yml exists
    if [ -f "$ROOT_DIR/pmoves/docker-compose.yml" ]; then
      check_pass "docker-compose.yml exists"

      # Verify botz-gateway has GitHub App env vars
      if grep -A10 "botz-gateway:" "$ROOT_DIR/pmoves/docker-compose.yml" | grep -q "GH_APP_ID"; then
        check_pass "botz-gateway has GH_APP_ID configured"
      else
        check_fail "botz-gateway missing GH_APP_ID configuration"
      fi

      if grep -A10 "botz-gateway:" "$ROOT_DIR/pmoves/docker-compose.yml" | grep -q "GH_APP_SEC"; then
        check_pass "botz-gateway has GH_APP_SEC configured"
      else
        check_fail "botz-gateway missing GH_APP_SEC configuration"
      fi

      if grep -A10 "botz-gateway:" "$ROOT_DIR/pmoves/docker-compose.yml" | grep -q "GH_APP_INSTALLATION_ID"; then
        check_pass "botz-gateway has GH_APP_INSTALLATION_ID configured"
      else
        check_fail "botz-gateway missing GH_APP_INSTALLATION_ID configuration"
      fi

      # Verify archon has GitHub App env vars
      if grep -A20 "^  archon:" "$ROOT_DIR/pmoves/docker-compose.yml" | grep -q "GH_APP_ID"; then
        check_pass "archon has GH_APP_ID configured"
      else
        check_fail "archon missing GH_APP_ID configuration"
      fi

      # Test docker compose config resolution
      log_verbose "   Testing docker compose config resolution..."
      if docker compose -f "$ROOT_DIR/pmoves/docker-compose.yml" config >/dev/null 2>&1; then
        check_pass "docker compose config resolves successfully"

        # Check if GH_APP variables are resolved
        CONFIG_OUTPUT=$(docker compose -f "$ROOT_DIR/pmoves/docker-compose.yml" config 2>/dev/null)
        if echo "$CONFIG_OUTPUT" | grep -q "GH_APP_ID:"; then
          check_pass "GH_APP_ID variable is available to services"
        else
          check_warn "GH_APP_ID variable may not be resolved (empty default)"
        fi
      else
        check_fail "docker compose config has errors"
      fi
    else
      check_fail "docker-compose.yml not found"
    fi
  else
    check_fail "Docker Compose not available"
  fi
else
  check_warn "Docker not installed (skip container checks)"
fi

log ""

# =============================================================================
# 3. Check BoTZ MCP Catalog
# =============================================================================
log "🔧 Checking BoTZ MCP catalog configuration..."

if [ -f "$ROOT_DIR/PMOVES-BoTZ/core/mcp/catalog.yml" ]; then
  check_pass "BoTZ MCP catalog exists"

  # Check if github server is configured
  if grep -q "^  github:" "$ROOT_DIR/PMOVES-BoTZ/core/mcp/catalog.yml"; then
    check_pass "GitHub MCP server is configured in catalog"

    # Check if it uses mint_and_exec.py
    if grep -A10 "^  github:" "$ROOT_DIR/PMOVES-BoTZ/core/mcp/catalog.yml" | grep -q "mint_and_exec.py"; then
      check_pass "GitHub server uses token minting wrapper"
    else
      check_warn "GitHub server may not use token minting"
    fi

    # Check if env vars are configured
    if grep -A10 "^  github:" "$ROOT_DIR/PMOVES-BoTZ/core/mcp/catalog.yml" | grep -q "GH_APP_ID"; then
      check_pass "GitHub server has GH_APP_ID configured"
    else
      check_fail "GitHub server missing GH_APP_ID configuration"
    fi
  else
    check_fail "GitHub MCP server not found in catalog"
  fi
else
  check_warn "PMOVES-BoTZ submodule not found"
fi

log ""

# =============================================================================
# 4. Check Token Minting Script
# =============================================================================
log "🔑 Checking token minting script..."

if [ -f "$ROOT_DIR/PMOVES-BoTZ/features/github/mint_and_exec.py" ]; then
  check_pass "Token minting script exists"

  # Check if it has required dependencies
  if grep -q "import jwt" "$ROOT_DIR/PMOVES-BoTZ/features/github/mint_and_exec.py"; then
    check_pass "Script has JWT dependency"
  else
    check_fail "Script missing JWT dependency"
  fi

  if grep -q "import requests" "$ROOT_DIR/PMOVES-BoTZ/features/github/mint_and_exec.py"; then
    check_pass "Script has requests dependency"
  else
    check_fail "Script missing requests dependency"
  fi
else
  check_warn "Token minting script not found"
fi

log ""

# =============================================================================
# 5. Summary
# =============================================================================
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "Verification Summary:"
log ""

# Count results
PASS_COUNT=$(printf '%s\n' "${CHECKS[@]}" | grep -c "^✓" || true)
FAIL_COUNT=$(printf '%s\n' "${CHECKS[@]}" | grep -c "^✗" || true)
WARN_COUNT=$(printf '%s\n' "${CHECKS[@]}" | grep -c "^○" || true)
TOTAL_COUNT=${#CHECKS[@]}

# Print all checks
for check in "${CHECKS[@]}"; do
  log "  $check"
done

log ""
log "Results: $PASS_COUNT/$TOTAL_COUNT passed, $FAIL_COUNT failed, $WARN_COUNT warnings"
log ""

if [ $FAIL_COUNT -eq 0 ]; then
  log "✅ All critical checks passed!"
  log ""
  log "Next steps:"
  log "  1. Populate GitHub App credentials in pmoves/env.shared"
  log "  2. Test token minting: cd PMOVES-BoTZ && python features/github/mint_and_exec.py"
  log "  3. Start services: cd pmoves && docker compose up -d archon botz-gateway"
  log "  4. Verify MCP catalog: curl http://localhost:8054/mcp/catalog"
  log ""
  exit 0
else
  log "❌ Some checks failed. Please address the following issues:"
  log ""
  for failure in "${FAILURES[@]}"; do
    log "  - $failure"
  done
  log ""
  log "Setup guide: pmoves/docs/GITHUB_APP_LOCAL_SETUP.md"
  log "Strategy doc: pmoves/docs/infrastructure/github-app-strategy.md"
  log ""
  exit 1
fi
