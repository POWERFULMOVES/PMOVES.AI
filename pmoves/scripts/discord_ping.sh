#!/usr/bin/env bash
set -euo pipefail

# Simple Discord webhook ping using env vars.
# Usage:
#   export DISCORD_WEBHOOK_URL=...
#   export DISCORD_WEBHOOK_USERNAME="PMOVES Publisher"  # optional
#   ./pmoves/scripts/discord_ping.sh "Hello from PMOVES"

MSG=${1:-"PMOVES Discord wiring check"}

if [[ -z "${DISCORD_WEBHOOK_URL:-}" ]]; then
  echo "ERROR: DISCORD_WEBHOOK_URL is not set" >&2
  exit 1
fi

USERNAME=${DISCORD_WEBHOOK_USERNAME:-"PMOVES Publisher"}

payload=$(jq -n --arg content "$MSG" --arg username "$USERNAME" '{content:$content, username:$username}')

curl -sS -H "Content-Type: application/json" -d "$payload" "$DISCORD_WEBHOOK_URL" -o /dev/null -w "%{http_code}\n"
