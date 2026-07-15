#!/usr/bin/env bash
# Crush Fleet Bootstrap — configures Crush CLI for any PMOVES node.
#
# Performs:
#   1. CHIT passphrase resolution (from secrets funnel, env, or tier files)
#   2. Crush config generation (providers, models, MCP servers)
#   3. Context path injection (CRUSH.md, AGENT_TRAIL, BOOTSTRAP)
#   4. CHIT signing verification (test sign to confirm passphrase works)
#   5. Status report
#
# Usage:
#   make -C pmoves crush-bootstrap
#   bash pmoves/scripts/crush-fleet-bootstrap.sh
#
# Environment overrides:
#   CHIT_PASSPHRASE        If set, used directly (skips funnel scan)
#   CHIT_PASSPHRASE_FILE   If set, reads passphrase from this file
#   CRUSH_CONFIG           Override crush.json path (default: ~/.config/crush/crush.json)
#   CRUSH_NODE             Node identifier for trail signing (default: hostname)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PMOVES_DIR="${REPO_ROOT}/pmoves"
CRUSH_CONFIG="${CRUSH_CONFIG:-${HOME}/.config/crush/crush.json}"
CRUSH_NODE="${CRUSH_NODE:-$(hostname -s)}"

info()  { printf '\033[1;34m[crush-bootstrap]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[crush-bootstrap] WARN:\033[0m %s\n' "$*" >&2; }
fail()  { printf '\033[1;31m[crush-bootstrap] FAIL:\033[0m %s\n' "$*" >&2; exit 1; }

info "Starting Crush fleet bootstrap on node: ${CRUSH_NODE}"

# ── 1. CHIT Passphrase Resolution ────────────────────────────────────────────

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
  if [ -z "$CHIT_PASS" ]; then
    LOCAL_ENV="${XDG_CONFIG_HOME:-${HOME}/.config}/pmoves/secrets/local.env"
    if [ -f "$LOCAL_ENV" ]; then
      val=$(grep '^CHIT_PASSPHRASE=' "$LOCAL_ENV" 2>/dev/null | head -1 | cut -d= -f2- || true)
      if [ -n "$val" ]; then
        CHIT_PASS="$val"
        CHIT_SOURCE="local.env"
      fi
    fi
  fi
fi

if [ -n "$CHIT_PASS" ]; then
  info "CHIT passphrase resolved (source: ${CHIT_SOURCE}, len=${#CHIT_PASS})"
  export CHIT_PASSPHRASE="$CHIT_PASS"
else
  warn "CHIT_PASSPHRASE not found — trail signing will emit unsigned payloads"
  warn "To fix: run 'make secrets-funnel' or set CHIT_PASSPHRASE env var"
fi

# ── 2. Python Environment ────────────────────────────────────────────────────

export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 not found on PATH"
fi
PYTHON=python3

if ! ${PYTHON} -c "import yaml" 2>/dev/null; then
  warn "PyYAML not available in system python — Hermes YAML merge may fail"
fi

# ── 3. Crush Config Generation ───────────────────────────────────────────────

info "Generating Crush config: ${CRUSH_CONFIG}"
${PYTHON} -m pmoves.tools.mcp_config_generator --client crush --output "${CRUSH_CONFIG}" \
  || fail "Crush config generation failed"

info "Running crush_configurator for provider/model setup..."
CRUSH_CONFIG_DIR=$(dirname "${CRUSH_CONFIG}")
mkdir -p "${CRUSH_CONFIG_DIR}"
${PYTHON} -m pmoves.tools.mini_cli crush setup 2>/dev/null \
  || warn "mini_cli crush setup not available (non-fatal)"

# ── 4. CHIT Signing Test ─────────────────────────────────────────────────────

if [ -n "$CHIT_PASS" ]; then
  info "Testing CHIT trail signing..."
  if CHIT_PASSPHRASE="$CHIT_PASS" ${PYTHON} "${PMOVES_DIR}/tools/sign_trail.py" \
      --agent-id "crush-${CRUSH_NODE}" \
      --summary "Fleet bootstrap signing test" \
      --phase "fleet-bootstrap" \
      --no-log 2>/dev/null; then
    info "CHIT signing: OK (signed payload emitted)"
  else
    warn "CHIT signing test failed (non-fatal — unsigned mode is acceptable in dev)"
  fi
else
  info "Skipping CHIT signing test (no passphrase)"
fi

# ── 5. Status Report ─────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Crush Fleet Bootstrap Complete — Node: ${CRUSH_NODE}"
echo "═══════════════════════════════════════════════════════════════"
echo "  Config:        ${CRUSH_CONFIG}"
echo "  CHIT source:   ${CHIT_SOURCE:-none (unsigned mode)}"
echo "  Python:        $(${PYTHON} --version)"
echo ""
if [ -n "$CHIT_PASS" ]; then
  echo "  ✓ Trail signing enabled (make sign-trail will produce signed payloads)"
else
  echo "  ⚠ Trail signing disabled (unsigned mode — run 'make secrets-funnel' to enable)"
fi
echo ""
echo "  Next steps:"
echo "    1. Run 'crush' to launch the CLI"
echo "    2. Write a trail entry in docs/AGENT_TRAIL.md"
echo "    3. Sign with: make sign-trail AGENT=crush-${CRUSH_NODE} SUMMARY='...'"
echo "═══════════════════════════════════════════════════════════════"
