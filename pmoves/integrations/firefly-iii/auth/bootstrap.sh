#!/usr/bin/env bash
set -euo pipefail

# Firefly III auth bootstrap: validates APP_KEY format, service health,
# and access token validity.

FIREFLY_BASE="${FIREFLY_BASE_URL:-http://localhost:8075}"
FIREFLY_KEY="${FIREFLY_APP_KEY:-}"
FIREFLY_TOKEN="${FIREFLY_ACCESS_TOKEN:-}"

echo "[firefly-iii] auth bootstrap: starting validation..."

# 1. Validate FIREFLY_APP_KEY format (must be base64: + 44 chars)
if [ -n "$FIREFLY_KEY" ]; then
  if echo "$FIREFLY_KEY" | grep -qE '^base64:[A-Za-z0-9+/=]{43,44}$'; then
    echo "[firefly-iii] OK: FIREFLY_APP_KEY has valid Laravel format"
  elif [ "$FIREFLY_KEY" = "base64:CHANGE_ME" ]; then
    echo "[firefly-iii] FAIL: FIREFLY_APP_KEY is still the placeholder — run: make env-setup"
    exit 1
  else
    echo "[firefly-iii] WARN: FIREFLY_APP_KEY format may be invalid (expected base64: prefix + 32 bytes)"
  fi
else
  echo "[firefly-iii] FAIL: FIREFLY_APP_KEY not set — Firefly III cannot encrypt data"
  echo "[firefly-iii] Run: make env-setup  (brand_defaults.py will auto-generate)"
  exit 1
fi

# 2. Check Firefly III is reachable
if curl -sf "${FIREFLY_BASE}/api/v1/about" >/dev/null 2>&1; then
  echo "[firefly-iii] OK: Firefly III API reachable at ${FIREFLY_BASE}"
else
  echo "[firefly-iii] WARN: Firefly III API not reachable at ${FIREFLY_BASE} — is the service running?"
  exit 0  # Non-fatal: service may not be started yet
fi

# 3. Validate access token if set
if [ -n "$FIREFLY_TOKEN" ]; then
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${FIREFLY_TOKEN}" \
    "${FIREFLY_BASE}/api/v1/about" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[firefly-iii] OK: FIREFLY_ACCESS_TOKEN is valid"
  elif [ "$STATUS" = "401" ]; then
    echo "[firefly-iii] FAIL: FIREFLY_ACCESS_TOKEN is invalid"
    echo "[firefly-iii] Generate a new token from Firefly III: Profile -> OAuth -> Personal Access Tokens"
    exit 1
  else
    echo "[firefly-iii] WARN: Could not validate token (HTTP $STATUS)"
  fi
else
  echo "[firefly-iii] WARN: FIREFLY_ACCESS_TOKEN not set — API integrations will not work"
  echo "[firefly-iii] Create one from Firefly III UI: Profile -> OAuth -> Personal Access Tokens"
fi

echo "[firefly-iii] auth bootstrap: complete"
