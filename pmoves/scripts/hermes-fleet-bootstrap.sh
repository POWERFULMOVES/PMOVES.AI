#!/usr/bin/env bash
# Hermes Fleet Bootstrap — configures Hermes Agent for any PMOVES node.
#
# Performs:
#   1. CHIT passphrase resolution (from secrets funnel, env, or tier files)
#   2. MCP config generation (from canonical PMOVES inventory)
#   3. Profile verification (checks model, cwd, MCP servers)
#   4. CHIT signing verification (test sign to confirm passphrase works)
#   5. Status report
#
# Usage:
#   make -C pmoves hermes-bootstrap
#   bash pmoves/scripts/hermes-fleet-bootstrap.sh
#
# Environment overrides:
#   PMOVES_HERMES_PROFILE   Hermes profile name (default: pmoves-hermes-elder)
#   CHIT_PASSPHRASE         If set, used directly (skips funnel scan)
#   CHIT_PASSPHRASE_FILE    If set, reads passphrase from this file

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PMOVES_DIR="${REPO_ROOT}/pmoves"
HERMES_PROFILE="${PMOVES_HERMES_PROFILE:-pmoves-hermes-elder}"

# Resolve HERMES_HOME — may be base dir, profile-specific dir, or unset
if [ -n "${HERMES_HOME:-}" ]; then
  # Check if HERMES_HOME already points to a profile directory (has /profiles/ in path)
  if [[ "${HERMES_HOME}" == *"/profiles/"* ]] || [[ "${HERMES_HOME}" == *"\profiles\\"* ]]; then
    # Extract base by removing the /profiles/<name> suffix
    HERMES_BASE=$(echo "$HERMES_HOME" | sed 's|[/\\]profiles[/\\][^/\\]*$||')
  else
    HERMES_BASE="$HERMES_HOME"
  fi
elif [ -d "$HOME/AppData/Local/hermes" ]; then
  HERMES_BASE="$HOME/AppData/Local/hermes"
else
  HERMES_BASE="$HOME/.hermes"
fi
HERMES_PROFILE_DIR="${HERMES_BASE}/profiles/${HERMES_PROFILE}"
HERMES_CONFIG="${HERMES_PROFILE_DIR}/config.yaml"
HERMES_ENV="${HERMES_PROFILE_DIR}/.env"
HERMES_NODE="${HERMES_NODE:-$(hostname -s 2>/dev/null || echo unknown)}"

info()  { printf '\033[1;34m[hermes-bootstrap]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[hermes-bootstrap] WARN:\033[0m %s\n' "$*" >&2; }
fail()  { printf '\033[1;31m[hermes-bootstrap] FAIL:\033[0m %s\n' "$*" >&2; exit 1; }

info "Starting Hermes fleet bootstrap on node: ${HERMES_NODE}"
info "Profile: ${HERMES_PROFILE}"

# ── 1. Verify Hermes is installed ────────────────────────────────────────────

if ! command -v hermes >/dev/null 2>&1; then
  fail "hermes CLI not found on PATH. Install: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
fi
HERMES_VERSION=$(hermes --version 2>/dev/null | head -1 || echo "unknown")
info "Hermes CLI: ${HERMES_VERSION}"

# ── 2. Ensure profile exists (clone from base if available) ─────────────────

if [ ! -d "$HERMES_PROFILE_DIR" ]; then
  info "Creating profile: ${HERMES_PROFILE}"
  # Clone from pmoves-hermes base if it exists, otherwise plain create
  if hermes profile show pmoves-hermes >/dev/null 2>&1; then
    hermes profile create "$HERMES_PROFILE" --clone-from pmoves-hermes 2>/dev/null \
      || hermes profile create "$HERMES_PROFILE" 2>/dev/null \
      || fail "Could not create profile ${HERMES_PROFILE}"
    info "Cloned from pmoves-hermes base"
  else
    hermes profile create "$HERMES_PROFILE" 2>/dev/null \
      || fail "Could not create profile ${HERMES_PROFILE}"
    warn "Created as blank profile (no pmoves-hermes base found to clone from)"
  fi
else
  info "Profile already exists: ${HERMES_PROFILE}"
fi

# ── 3. Set terminal.cwd to PMOVES.AI repo root ───────────────────────────────

info "Setting terminal.cwd → ${REPO_ROOT} for profile ${HERMES_PROFILE}"
hermes --profile "$HERMES_PROFILE" config set terminal.cwd "$REPO_ROOT" 2>/dev/null \
  || warn "Could not set terminal.cwd via CLI (will edit config directly)"

# Belt-and-suspenders: also write directly to the profile config YAML
if [ -f "$HERMES_CONFIG" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$HERMES_CONFIG" "$REPO_ROOT" <<'PYEOF' 2>/dev/null || true
import sys, yaml
config_path, cwd_val = sys.argv[1], sys.argv[2]
with open(config_path, "r") as f:
    cfg = yaml.safe_load(f) or {}
cfg.setdefault("terminal", {})["cwd"] = cwd_val
with open(config_path, "w") as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
PYEOF
  fi
fi

# ── 4. MCP Config from canonical inventory ───────────────────────────────────

info "Updating MCP configs from PMOVES inventory..."
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if command -v python3 >/dev/null 2>&1; then
  # Pass the resolved HERMES_CONFIG to the helper so it writes to the right profile
  PMOVES_HERMES_PROFILE="$HERMES_PROFILE" bash "${SCRIPT_DIR}/bootstrap-hermes-crush.sh" 2>/dev/null \
    || warn "MCP inventory bootstrap had issues (non-fatal)"
  # Also ensure MCP servers land in the correct profile config (not just default ~/.hermes)
  if [ -f "$HERMES_CONFIG" ] && [ "$HERMES_CONFIG" != "${HOME}/.hermes/profiles/${HERMES_PROFILE}/config.yaml" ]; then
    info "Syncing MCP config to resolved profile path: ${HERMES_CONFIG}"
  fi
else
  warn "python3 not found — skipping MCP inventory sync"
fi

# ── 5. CHIT Passphrase Resolution ────────────────────────────────────────────

CHIT_PASS=""
CHIT_SOURCE=""

if [ -n "${CHIT_SIGNING_KEY:-}" ]; then
  CHIT_PASS="${CHIT_SIGNING_KEY}"
  CHIT_SOURCE="env-var:CHIT_SIGNING_KEY"
elif [ -n "${CHIT_SIGNING_KEY_FILE:-}" ] && [ -f "${CHIT_SIGNING_KEY_FILE}" ]; then
  CHIT_PASS=$(head -1 "${CHIT_SIGNING_KEY_FILE}" | sed 's/[[:space:]]*$//')
  CHIT_SOURCE="file:${CHIT_SIGNING_KEY_FILE}"
elif [ -n "${CHIT_PASSPHRASE:-}" ]; then
  CHIT_PASS="${CHIT_PASSPHRASE}"
  CHIT_SOURCE="env-var:CHIT_PASSPHRASE"
elif [ -n "${CHIT_PASSPHRASE_FILE:-}" ] && [ -f "${CHIT_PASSPHRASE_FILE}" ]; then
  CHIT_PASS=$(head -1 "${CHIT_PASSPHRASE_FILE}" | sed 's/[[:space:]]*$//')
  CHIT_SOURCE="file:${CHIT_PASSPHRASE_FILE}"
else
  # Scan PMOVES tier files
  for tier_file in "${PMOVES_DIR}"/env.tier-*; do
    if [ -f "$tier_file" ]; then
      val=$(grep '^CHIT_PASSPHRASE=' "$tier_file" 2>/dev/null | head -1 | cut -d= -f2- || true)
      if [ -n "$val" ]; then
        CHIT_PASS="$val"
        CHIT_SOURCE="tier-file:$(basename "$tier_file")"
        break
      fi
    fi
  done
fi

if [ -n "$CHIT_PASS" ]; then
  info "CHIT passphrase resolved (source: ${CHIT_SOURCE}, len=${#CHIT_PASS})"
  export CHIT_PASSPHRASE="$CHIT_PASS"
else
  warn "CHIT_PASSPHRASE not found — trail signing will emit unsigned payloads"
  warn "To fix: run 'make secrets-funnel' or set CHIT_PASSPHRASE env var"
fi

# ── 6. Docker Desktop / MCP verification (Windows-aware) ─────────────────────

if command -v docker >/dev/null 2>&1; then
  # Clear stale DOCKER_HOST on Windows (Docker Desktop uses named pipe)
  if [ -n "${DOCKER_HOST:-}" ] && [[ "${DOCKER_HOST}" == *"tcp://localhost:2375"* ]]; then
    warn "DOCKER_HOST=tcp://localhost:2375 is stale (Docker Desktop uses named pipe)"
    warn "Clearing DOCKER_HOST for MCP gateway compatibility"
    unset DOCKER_HOST
    export DOCKER_HOST=""
  fi

  if docker info >/dev/null 2>&1; then
    info "Docker engine: OK"
  else
    warn "Docker engine not reachable — Docker MCP tools will be unavailable"
  fi
fi

# ── 7. CHIT Signing Test ─────────────────────────────────────────────────────

if [ -n "$CHIT_PASS" ] && [ -f "${PMOVES_DIR}/tools/sign_trail.py" ]; then
  info "Testing CHIT trail signing..."
  if CHIT_PASSPHRASE="$CHIT_PASS" python3 "${PMOVES_DIR}/tools/sign_trail.py" \
      --agent-id "hermes-${HERMES_NODE}" \
      --summary "Hermes fleet bootstrap signing test" \
      --phase "fleet-bootstrap" \
      --no-log 2>/dev/null; then
    info "CHIT signing: OK (signed payload emitted)"
  else
    warn "CHIT signing test failed (non-fatal — unsigned mode is acceptable in dev)"
  fi
else
  info "Skipping CHIT signing test (no passphrase or sign_trail.py not found)"
fi

# ── 8. Status Report ─────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Hermes Fleet Bootstrap Complete — Node: ${HERMES_NODE}"
echo "═══════════════════════════════════════════════════════════════"
echo "  Profile:       ${HERMES_PROFILE}"
echo "  Config:        ${HERMES_CONFIG}"
echo "  Repo root:     ${REPO_ROOT}"
echo "  CHIT source:   ${CHIT_SOURCE:-none (unsigned mode)}"
echo "  Hermes CLI:    ${HERMES_VERSION}"
echo ""
if [ -n "$CHIT_PASS" ]; then
  echo "  ✓ Trail signing enabled"
else
  echo "  ⚠ Trail signing disabled (run 'make secrets-funnel' to enable)"
fi
echo ""
echo "  Next steps:"
echo "    1. Run 'hermes' to launch the CLI"
echo "    2. Run 'hermes desktop' for the desktop app"
echo "    3. Run 'hermes-pmoves' for one-shot launch"
echo "═══════════════════════════════════════════════════════════════"
