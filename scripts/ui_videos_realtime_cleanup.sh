#!/usr/bin/env bash
set -euo pipefail

# Cleanup UI Realtime Smoke rows from public.videos
# Deletes rows where video_id starts with 'ui-smoke-' OR meta.inserted_by == 'ui-videos-realtime-smoke'

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/pmoves/scripts/with-env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/pmoves/scripts/with-env.sh"
else
  ENV_FILE="$ROOT_DIR/pmoves/env.shared"; set -a; [[ -f "$ENV_FILE" ]] && source "$ENV_FILE"; set +a
fi

: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY required}"
SUPABASE_REST_URL="${SUPABASE_REST_URL:-${SUPA_REST_URL:-http://localhost:65421/rest/v1}}"

REST="${SUPABASE_REST_URL%/}/videos"

echo "→ Deleting videos with meta.inserted_by='ui-videos-realtime-smoke'"
curl -fsS -X DELETE "$REST?meta->>inserted_by=eq.ui-videos-realtime-smoke" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'prefer: tx=commit' -o /dev/null || true

echo "→ Deleting videos with video_id like 'ui-smoke-%'"
curl -fsS -X DELETE "$REST?video_id=like.ui-smoke-%25" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'prefer: tx=commit' -o /dev/null || true

echo "✔ Cleanup complete"
