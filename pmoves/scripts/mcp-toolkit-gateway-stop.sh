#!/usr/bin/env bash
# Stop the host-side MCP gateway listener started by mcp-toolkit-gateway-listen.sh.
#
# Reads the PID from /tmp/pmoves-mcp-gateway.pid (override via
# PMOVES_MCP_GATEWAY_PID), sends SIGTERM, waits up to 10s for graceful exit,
# then SIGKILL if still alive.
#
# Make target: make -C pmoves mcp-toolkit-gateway-stop

set -euo pipefail

PID_FILE="${PMOVES_MCP_GATEWAY_PID:-/tmp/pmoves-mcp-gateway.pid}"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info() { color "1;34" "[mcp-gateway-stop] $*"; }
warn() { color "1;33" "[mcp-gateway-stop] WARN: $*" >&2; }

if [ ! -f "${PID_FILE}" ]; then
  info "no PID file at ${PID_FILE} — gateway not running (or started outside this script)"
  exit 0
fi

PID="$(cat "${PID_FILE}")"

if ! kill -0 "${PID}" 2>/dev/null; then
  warn "PID ${PID} not alive — cleaning up stale PID file"
  rm -f "${PID_FILE}"
  exit 0
fi

# Verify the PID still belongs to our gateway process before signaling. PIDs
# get recycled, and a stale .pid file pointing at a reused PID would otherwise
# send SIGTERM/SIGKILL to an unrelated host process. Match against `docker mcp`
# in the command line; bail out if it doesn't look right.
PID_CMDLINE="$(ps -p "${PID}" -o command= 2>/dev/null || true)"
if [ -z "${PID_CMDLINE}" ] || ! printf '%s' "${PID_CMDLINE}" | grep -qE 'docker.*mcp.*gateway|mcp[-_]toolkit[-_]gateway'; then
  warn "PID ${PID} does not look like the MCP gateway (cmdline: ${PID_CMDLINE:-<none>})"
  warn "refusing to signal — cleaning up stale PID file instead"
  rm -f "${PID_FILE}"
  exit 0
fi

info "sending SIGTERM to pid ${PID} (verified: ${PID_CMDLINE})"
kill -TERM "${PID}" || true

for _ in $(seq 1 10); do
  if ! kill -0 "${PID}" 2>/dev/null; then
    info "gateway stopped cleanly"
    rm -f "${PID_FILE}"
    exit 0
  fi
  sleep 1
done

warn "gateway did not exit on SIGTERM within 10s — sending SIGKILL"
kill -KILL "${PID}" || true
rm -f "${PID_FILE}"
info "gateway killed"
