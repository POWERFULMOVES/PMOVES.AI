#!/usr/bin/env bash
# a0-node-verify.sh — fleet-standard node verification gate (runbook step 7)
# Usage: bash scripts/a0-node-verify.sh <host> <port> [name]
# Gates: HTTP probe, then manual CLI/browser rounds per docs/runbooks.
# Exit codes: 0=online, 1=http dead, 2=arg error
set -euo pipefail

HOST="${1:-}"
PORT="${2:-}"
NAME="${3:-${HOST}}"

if [[ -z "$HOST" || -z "$PORT" ]]; then
  echo "usage: $0 <host> <port> [name]" >&2
  exit 2
fi

code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "http://${HOST}:${PORT}/" 2>/dev/null || true)
echo "${NAME} http://${HOST}:${PORT}/ -> ${code}"

if [[ "$code" == "000" ]]; then
  echo "${NAME}: OFFLINE (http dead)" >&2
  exit 1
fi

echo "${NAME}: HTTP ALIVE (${code}) — proceed to CLI round-trip + browser tabs gate"
echo "  1) code_execution_remote: hostname  2) browser: list (host mode)"
exit 0
