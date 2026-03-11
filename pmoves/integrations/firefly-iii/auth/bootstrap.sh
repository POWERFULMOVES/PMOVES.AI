#!/usr/bin/env bash
set -euo pipefail

# Firefly III auth bootstrap: validates APP_KEY format, service health,
# and access token validity.
#
# Exit codes:
#   0 = all checks passed
#   1 = validation failure (bad key/token, service error)
#   2 = service not reachable (re-run after starting)

FIREFLY_BASE="${FIREFLY_BASE_URL:-http://localhost:8075}"
FIREFLY_KEY="${FIREFLY_APP_KEY:-}"
FIREFLY_TOKEN="${FIREFLY_ACCESS_TOKEN:-}"

echo "[firefly-iii] auth bootstrap: starting validation..."

# 1. Validate FIREFLY_APP_KEY format (must be base64: + 44 chars from 32 bytes)
if [ -n "$FIREFLY_KEY" ]; then
  if echo "$FIREFLY_KEY" | grep -qE '^base64:[A-Za-z0-9+/=_-]{43,44}$'; then
    echo "[firefly-iii] OK: FIREFLY_APP_KEY has valid Laravel format"
  elif [ "$FIREFLY_KEY" = "base64:CHANGE_ME" ]; then
    echo "[firefly-iii] FAIL: FIREFLY_APP_KEY is still the placeholder — run: make env-setup" >&2
    exit 1
  else
    echo "[firefly-iii] FAIL: FIREFLY_APP_KEY format invalid (expected base64: prefix + 32 bytes)" >&2
    exit 1
  fi
else
  echo "[firefly-iii] FAIL: FIREFLY_APP_KEY not set — Firefly III cannot encrypt data" >&2
  echo "[firefly-iii] Run: make env-setup  (brand_defaults.py will auto-generate)" >&2
  exit 1
fi

# 2. Check Firefly III is reachable
if curl -sf "${FIREFLY_BASE}/api/v1/about" >/dev/null 2>&1; then
  echo "[firefly-iii] OK: Firefly III API reachable at ${FIREFLY_BASE}"
else
  echo "[firefly-iii] WARN: Firefly III API not reachable at ${FIREFLY_BASE} — is the service running?" >&2
  echo "[firefly-iii] WARN: Skipping remaining checks — re-run after service starts" >&2
  exit 2
fi

# 3. Validate access token if set
if [ -n "$FIREFLY_TOKEN" ]; then
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${FIREFLY_TOKEN}" \
    "${FIREFLY_BASE}/api/v1/about" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[firefly-iii] OK: FIREFLY_ACCESS_TOKEN is valid"
  elif [ "$STATUS" = "401" ]; then
    echo "[firefly-iii] FAIL: FIREFLY_ACCESS_TOKEN is invalid" >&2
    echo "[firefly-iii] Generate a new token from Firefly III: Profile -> OAuth -> Personal Access Tokens" >&2
    exit 1
  elif [ "$STATUS" = "403" ]; then
    echo "[firefly-iii] FAIL: FIREFLY_ACCESS_TOKEN has insufficient permissions (HTTP 403)" >&2
    exit 1
  elif [ "$STATUS" = "000" ] || [ "${STATUS:0:1}" = "5" ]; then
    echo "[firefly-iii] FAIL: Firefly III API error during token validation (HTTP $STATUS)" >&2
    exit 1
  else
    echo "[firefly-iii] WARN: Unexpected response during token validation (HTTP $STATUS)" >&2
  fi
else
  echo "[firefly-iii] WARN: FIREFLY_ACCESS_TOKEN not set — API integrations will not work" >&2
  echo "[firefly-iii] Create one from Firefly III UI: Profile -> OAuth -> Personal Access Tokens" >&2
fi

echo "[firefly-iii] auth bootstrap: complete"
