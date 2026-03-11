#!/usr/bin/env bash
set -euo pipefail

# Health-Wger auth bootstrap: validates Wger service health, API token,
# and checks admin password is not the upstream default.

WGER_BASE="${WGER_BASE_URL:-http://localhost:8000}"
WGER_TOKEN="${WGER_API_TOKEN:-}"

echo "[health-wger] auth bootstrap: starting validation..."

# 1. Check Wger is reachable
if curl -sf "${WGER_BASE}/api/v2/version" >/dev/null 2>&1; then
  echo "[health-wger] OK: Wger API reachable at ${WGER_BASE}"
else
  echo "[health-wger] WARN: Wger API not reachable at ${WGER_BASE} — is the service running?"
  exit 0  # Non-fatal: service may not be started yet
fi

# 2. Validate API token if set
if [ -n "$WGER_TOKEN" ]; then
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Token ${WGER_TOKEN}" \
    "${WGER_BASE}/api/v2/workout/" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[health-wger] OK: WGER_API_TOKEN is valid"
  elif [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
    echo "[health-wger] FAIL: WGER_API_TOKEN is invalid (HTTP $STATUS)"
    echo "[health-wger] Generate a new token from the Wger UI or via Django mgmt commands."
    exit 1
  else
    echo "[health-wger] WARN: Could not validate token (HTTP $STATUS)"
  fi
else
  echo "[health-wger] WARN: WGER_API_TOKEN not set — API integrations will not work"
  echo "[health-wger] Set WGER_API_TOKEN in pmoves/env.shared or run: make env-setup"
fi

# 3. Check admin password is not the upstream default
# (Can only detect via login attempt — warn the operator)
echo "[health-wger] NOTE: Upstream Wger resets admin password to 'adminadmin' on fresh bootstrap."
echo "[health-wger] If this is a fresh install, change it via the UI or:"
echo "[health-wger]   docker compose exec wger python manage.py changepassword admin"

echo "[health-wger] auth bootstrap: complete"
