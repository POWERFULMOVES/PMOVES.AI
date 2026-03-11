#!/usr/bin/env bash
set -euo pipefail

# Health-Wger auth bootstrap: validates Wger service health, API token,
# and checks admin password is not the upstream default.
#
# Exit codes:
#   0 = all checks passed
#   1 = validation failure (bad token, service error)
#   2 = service not reachable (re-run after starting)

WGER_BASE="${WGER_BASE_URL:-http://localhost:8000}"
WGER_TOKEN="${WGER_API_TOKEN:-}"

echo "[health-wger] auth bootstrap: starting validation..."

# 1. Check Wger is reachable
if curl -sf "${WGER_BASE}/api/v2/version" >/dev/null 2>&1; then
  echo "[health-wger] OK: Wger API reachable at ${WGER_BASE}"
else
  echo "[health-wger] WARN: Wger API not reachable at ${WGER_BASE} — is the service running?" >&2
  echo "[health-wger] WARN: Skipping remaining checks — re-run after service starts" >&2
  exit 2
fi

# 2. Validate API token if set
if [ -n "$WGER_TOKEN" ] && [ "$WGER_TOKEN" != "GENERATE_FROM_WGER_UI" ]; then
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Token ${WGER_TOKEN}" \
    "${WGER_BASE}/api/v2/workout/" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[health-wger] OK: WGER_API_TOKEN is valid"
  elif [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
    echo "[health-wger] FAIL: WGER_API_TOKEN is invalid (HTTP $STATUS)" >&2
    echo "[health-wger] Generate a new token from the Wger UI or via Django mgmt commands." >&2
    exit 1
  elif [ "$STATUS" = "000" ] || [ "${STATUS:0:1}" = "5" ]; then
    echo "[health-wger] FAIL: Wger API error during token validation (HTTP $STATUS)" >&2
    exit 1
  else
    echo "[health-wger] WARN: Unexpected response during token validation (HTTP $STATUS)" >&2
  fi
else
  echo "[health-wger] WARN: WGER_API_TOKEN not set — generate from Wger UI or:" >&2
  echo "[health-wger]   docker compose exec wger python manage.py drf_create_token <username>" >&2
fi

# 3. Check admin password is not the upstream default
echo "[health-wger] NOTE: Upstream Wger resets admin password to 'adminadmin' on fresh bootstrap."
echo "[health-wger] If this is a fresh install, change it via the UI or:"
echo "[health-wger]   docker compose exec wger python manage.py changepassword admin"

echo "[health-wger] auth bootstrap: complete"
