\
#!/usr/bin/env bash
set -euo pipefail

SUPA_REST_URL="${SUPA_REST_URL:-http://localhost:3000}"
TITLE="${JELLYFIN_TEST_TITLE:-DARKXSIDE – Test Release (Smoke)}"
NAMESPACE="${NAMESPACE:-pmoves}"
CONTENT_URL="${CONTENT_URL:-https://raw.githubusercontent.com/sindresorhus/awesome/main/readme.md}"
POLL_SEC="${POLL_SEC:-45}"

echo "== PMOVES Publisher Enrichments Smoke Test =="
echo "SUPA_REST_URL=$SUPA_REST_URL"
echo "TITLE=$TITLE"
echo "NAMESPACE=$NAMESPACE"
echo "CONTENT_URL=$CONTENT_URL"
echo "POLL_SEC=$POLL_SEC"

# 1) Insert a studio_board row with status=published
echo "Inserting test row into studio_board ..."
RESP=$(curl -s -S -X POST "$SUPA_REST_URL/studio_board" \
  -H "content-type: application/json" \
  -H "Prefer: return=representation" \
  -d "{\"title\":\"$TITLE\",\"namespace\":\"$NAMESPACE\",\"content_url\":\"$CONTENT_URL\",\"status\":\"published\",\"meta\":{\"smoketest\":true}}")

if command -v jq >/dev/null 2>&1; then
  echo "$RESP" | jq .
fi

STUDIO_ID=$(echo "$RESP" | sed -n 's/.*"id":[ ]*\([0-9][0-9]*\).*/\1/p' | head -n1)
if [ -z "${STUDIO_ID:-}" ]; then
  echo "Failed to parse studio_id from response:"
  echo "$RESP"
  exit 1
fi
echo "Created studio_id=$STUDIO_ID"

# 2) Poll for published_events and publisher_audit entries
echo "Polling for publisher activity (up to $POLL_SEC seconds) ..."
DEADLINE=$(( $(date +%s) + POLL_SEC ))
EVENT_FOUND=0
AUDIT_FOUND=0

while [ $(date +%s) -lt $DEADLINE ]; do
  EV=$(curl -s -S "$SUPA_REST_URL/published_events?studio_id=eq.$STUDIO_ID&order=created_at.desc&limit=1")
  AUD=$(curl -s -S "$SUPA_REST_URL/publisher_audit?studio_id=eq.$STUDIO_ID&order=created_at.asc")

  if echo "$EV" | grep -q "\"event\""; then EVENT_FOUND=1; fi
  if echo "$AUD" | grep -q "\"action\""; then AUDIT_FOUND=1; fi

  if [ $EVENT_FOUND -eq 1 ] && [ $AUDIT_FOUND -eq 1 ]; then
    break
  fi
  sleep 2
done

echo
echo "=== published_events ==="
if command -v jq >/dev/null 2>&1; then
  echo "$EV" | jq .
else
  echo "$EV"
fi

echo
echo "=== publisher_audit ==="
if command -v jq >/dev/null 2>&1; then
  echo "$AUD" | jq .
else
  echo "$AUD"
fi

if [ $EVENT_FOUND -eq 1 ] && [ $AUDIT_FOUND -eq 1 ]; then
  echo
  echo "✅ PASS: event + audit rows detected for studio_id=$STUDIO_ID"
  exit 0
else
  echo
  echo "⚠️  WARN: missing event or audit rows (EVENT_FOUND=$EVENT_FOUND, AUDIT_FOUND=$AUDIT_FOUND)"
  echo "Check that the publisher container is running and env vars are set."
  exit 2
fi
