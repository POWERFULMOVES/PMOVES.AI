#!/usr/bin/env bash
# Host-side MCP gateway listener for the canonical PMOVES profile.
#
# Runs `docker mcp gateway run --profile pmoves_5090_web --transport sse` and
# exposes the 25-server tool surface on a TCP port so remote clients (E2B
# sandboxes, Danger Room Desktop sessions, BoTZ Gateway proxy) can connect
# without needing the Toolkit installed locally.
#
# Security model:
#   - SSE transport uses MCP_GATEWAY_AUTH_TOKEN to prevent DNS rebinding.
#   - --block-secrets is on by default — secrets cannot exfil through tool
#     args/responses.
#   - --block-network can be enabled per-deployment to lock tool containers
#     from arbitrary outbound (set PMOVES_MCP_BLOCK_NETWORK=1).
#   - Bind address should be a Tailscale interface, NOT 0.0.0.0, when run
#     on a node whose host firewall is not configured. Default below.
#
# Usage:
#   bash pmoves/scripts/mcp-toolkit-gateway-listen.sh             # foreground
#   bash pmoves/scripts/mcp-toolkit-gateway-listen.sh --background # nohup-style
#
# Make target: make -C pmoves mcp-toolkit-gateway-start

set -euo pipefail

# Short-circuit --help BEFORE any side-effecting setup (token generation,
# env.shared writes, etc.). Operators inspecting usage shouldn't trigger
# a token generation as a side effect.
case "${1:-}" in
  --help|-h)
    cat <<'USAGE'
mcp-toolkit-gateway-listen.sh — host-side Docker MCP gateway listener

Usage:
  bash pmoves/scripts/mcp-toolkit-gateway-listen.sh             # foreground
  bash pmoves/scripts/mcp-toolkit-gateway-listen.sh --background # nohup + PID file
  bash pmoves/scripts/mcp-toolkit-gateway-listen.sh --help       # this message

Environment overrides:
  PMOVES_MCP_PROFILE_ID         (default: pmoves_5090_web)
  PMOVES_MCP_GATEWAY_PORT       (default: 8090)
  PMOVES_MCP_GATEWAY_TRANSPORT  (default: sse — also stdio/streaming)
  PMOVES_MCP_GATEWAY_PID        (default: /tmp/pmoves-mcp-gateway.pid)
  PMOVES_MCP_GATEWAY_LOG        (default: /tmp/pmoves-mcp-gateway.log)
  PMOVES_MCP_BLOCK_NETWORK      (default: 0 — set 1 to add --block-network)
  MCP_GATEWAY_AUTH_TOKEN        (auto-generated and persisted to env.shared
                                 on first run; reused thereafter)

Make targets:
  make -C pmoves mcp-toolkit-gateway-start
  make -C pmoves mcp-toolkit-gateway-stop
  make -C pmoves mcp-toolkit-gateway-tail
USAGE
    exit 0
    ;;
esac

PROFILE_ID="${PMOVES_MCP_PROFILE_ID:-pmoves_5090_web}"
PORT="${PMOVES_MCP_GATEWAY_PORT:-8090}"
TRANSPORT="${PMOVES_MCP_GATEWAY_TRANSPORT:-sse}"
PID_FILE="${PMOVES_MCP_GATEWAY_PID:-/tmp/pmoves-mcp-gateway.pid}"
LOG_FILE="${PMOVES_MCP_GATEWAY_LOG:-/tmp/pmoves-mcp-gateway.log}"
BLOCK_NETWORK="${PMOVES_MCP_BLOCK_NETWORK:-0}"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info() { color "1;34" "[mcp-gateway] $*"; }
warn() { color "1;33" "[mcp-gateway] WARN: $*" >&2; }
fail() { color "1;31" "[mcp-gateway] FAIL: $*" >&2; exit 1; }

if ! command -v docker >/dev/null 2>&1 || ! docker mcp version >/dev/null 2>&1; then
  fail "Docker MCP Toolkit not available. Run: make mcp-toolkit-bootstrap"
fi

if ! docker mcp profile ls 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "${PROFILE_ID}"; then
  fail "Profile '${PROFILE_ID}' not imported. Run: make mcp-toolkit-bootstrap"
fi

# Preflight. ADVISORY on purpose -- see tools/mcp_toolkit_preflight.py for why a
# wedged resolver should not refuse to start 25 servers because 4 cannot
# authenticate. It exists because this script used to start a gateway whose
# credentialed servers were guaranteed to 401, and said nothing.
#   exit 0  ready
#   exit 1  measured a problem (resolver down) -- reported, not blocked here
#   exit 3  could not measure -- NOT a pass; surfaced so it is not mistaken for one
# Set PMOVES_MCP_STRICT=1 to refuse to start on anything but 0, which is what
# CI and unattended bring-up should do.
PREFLIGHT_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/tools/mcp_toolkit_preflight.py"
if [ -f "${PREFLIGHT_PY}" ]; then
  set +e
  python3 "${PREFLIGHT_PY}" --profile "${PROFILE_ID}"
  preflight_rc=$?
  set -e
  if [ "${preflight_rc}" -ne 0 ]; then
    if [ "${PMOVES_MCP_STRICT:-0}" = "1" ]; then
      fail "preflight exit ${preflight_rc} and PMOVES_MCP_STRICT=1 -- refusing to start."
    fi
    warn "preflight exit ${preflight_rc}; starting anyway (set PMOVES_MCP_STRICT=1 to gate)."
  fi
else
  warn "preflight tool missing at ${PREFLIGHT_PY} -- starting unchecked."
fi

# Generate MCP_GATEWAY_AUTH_TOKEN if not already set. Persist to env.shared so
# clients (E2B sandboxes, BoTZ Gateway, this host's secrets-funnel consumers)
# can read the same value. The Toolkit gateway reads the env var directly.
PMOVES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_SHARED="${PMOVES_DIR}/env.shared"

if [ -z "${MCP_GATEWAY_AUTH_TOKEN:-}" ]; then
  if [ -f "${ENV_SHARED}" ] && grep -q '^MCP_GATEWAY_AUTH_TOKEN=' "${ENV_SHARED}"; then
    # shellcheck disable=SC2046
    export $(grep '^MCP_GATEWAY_AUTH_TOKEN=' "${ENV_SHARED}" | head -1)
    info "loaded MCP_GATEWAY_AUTH_TOKEN from ${ENV_SHARED}"
  else
    NEW_TOKEN="$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '/+=' | head -c 64)"
    export MCP_GATEWAY_AUTH_TOKEN="${NEW_TOKEN}"
    # Writability check must target the file we're appending to, not the parent
    # directory. Two cases work: (a) file exists and is writable, or (b) file
    # doesn't exist yet but the directory is writable so we can create it.
    if { [ -e "${ENV_SHARED}" ] && [ -w "${ENV_SHARED}" ]; } \
       || { [ ! -e "${ENV_SHARED}" ] && [ -w "${PMOVES_DIR}" ]; }; then
      info "generated new MCP_GATEWAY_AUTH_TOKEN and appending to ${ENV_SHARED}"
      printf '\n# Docker MCP Toolkit SSE gateway auth (host: pmoves_5090_web profile)\n' >> "${ENV_SHARED}"
      printf 'MCP_GATEWAY_AUTH_TOKEN=%s\n' "${MCP_GATEWAY_AUTH_TOKEN}" >> "${ENV_SHARED}"
    else
      warn "cannot persist MCP_GATEWAY_AUTH_TOKEN to ${ENV_SHARED} (not writable). Export it manually in your secrets-funnel and re-run."
    fi
  fi
fi

GATEWAY_ARGS=(
  gateway run
  --profile "${PROFILE_ID}"
  --transport "${TRANSPORT}"
  --port "${PORT}"
  --verbose
)

if [ "${BLOCK_NETWORK}" = "1" ]; then
  GATEWAY_ARGS+=(--block-network)
  info "block-network ENABLED (PMOVES_MCP_BLOCK_NETWORK=1)"
fi

run_foreground() {
  info "starting gateway: profile=${PROFILE_ID} transport=${TRANSPORT} port=${PORT}"
  info "auth token persisted to ${ENV_SHARED} (clients read MCP_GATEWAY_AUTH_TOKEN there)"
  exec docker mcp "${GATEWAY_ARGS[@]}"
}

run_background() {
  if [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    warn "gateway already running (pid $(cat "${PID_FILE}")). Stop with: make mcp-toolkit-gateway-stop"
    return 0
  fi
  info "starting gateway in background: profile=${PROFILE_ID} port=${PORT} log=${LOG_FILE}"
  nohup docker mcp "${GATEWAY_ARGS[@]}" >"${LOG_FILE}" 2>&1 &
  echo $! > "${PID_FILE}"
  sleep 2
  if ! kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    fail "gateway exited within 2s. Check ${LOG_FILE}"
  fi
  info "gateway pid $(cat "${PID_FILE}"). Tail logs: tail -f ${LOG_FILE}"
}

case "${1:-}" in
  --background|-d) run_background ;;
  --foreground|"") run_foreground ;;
  *) fail "unknown flag: $1 (try --foreground / --background / --help)" ;;
esac
