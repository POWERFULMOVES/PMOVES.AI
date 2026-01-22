#!/usr/bin/env bash
set -euo pipefail

# UI Videos Realtime Smoke
# - Loads pmoves/env.shared
# - Inserts a dummy row into public.videos via Supabase REST
# - Prints links to the UI page and the REST row

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# Load unified env if available (env.shared.generated → env.shared → .env.generated → .env.local)
if [[ -f "$ROOT_DIR/pmoves/scripts/with-env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/pmoves/scripts/with-env.sh"
else
  ENV_FILE="$ROOT_DIR/pmoves/env.shared"
  if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
  fi
fi

: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY required}"
SUPABASE_REST_URL="${SUPABASE_REST_URL:-${SUPA_REST_URL:-http://localhost:65421/rest/v1}}"

NAMESPACE="${1:-pmoves}"
VID="ui-smoke-$(date +%Y%m%d_%H%M%S)-$RANDOM"
TITLE="UI Realtime Smoke: ${VID}"
SRC_URL="https://youtu.be/${VID}"

BODY=$(jq -c -n --arg vid "$VID" --arg ns "$NAMESPACE" --arg t "$TITLE" --arg url "$SRC_URL" '{
  video_id: $vid,
  namespace: $ns,
  title: $t,
  source_url: $url,
  meta: { approval_status: "pending", inserted_by: "ui-videos-realtime-smoke" }
}')

echo "→ Inserting dummy row into public.videos (video_id=$VID, namespace=$NAMESPACE)"
HTTP_CODE=$(curl -s -o /tmp/ui_videos_smoke_resp.json -w "%{http_code}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'content-type: application/json' \
  -X POST "${SUPABASE_REST_URL%/}/videos" \
  -d "$BODY")

if [[ "$HTTP_CODE" != "201" && "$HTTP_CODE" != "200" ]]; then
  echo "✖ Insert failed (HTTP $HTTP_CODE):" >&2
  cat /tmp/ui_videos_smoke_resp.json >&2
  exit 1
fi

echo "✔ Inserted. REST verification:"
curl -s "${SUPABASE_REST_URL%/}/videos?video_id=eq.${VID}&select=id,video_id,namespace,title,created_at" -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" | jq .

UI_BASE="${NEXT_PUBLIC_BASE_URL:-http://localhost:3001}"
echo
echo "Open the Videos dashboard and you should see the new row appear (Realtime):"
echo "  ${UI_BASE}/dashboard/videos"
echo "Direct REST link to the row:"
echo "  ${SUPABASE_REST_URL%/}/videos?video_id=eq.${VID}"
