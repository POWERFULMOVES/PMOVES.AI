#!/usr/bin/env bash
set -euo pipefail

# Seed an approved studio_board row via Supabase PostgREST.
# Defaults target Supabase CLI on host (http://localhost:54321/rest/v1).
# Usage:
#   export SUPABASE_SERVICE_ROLE_KEY=...
#   ./pmoves/tools/seed_studio_board.sh "Demo" "s3://outputs/demo/example.png" pmoves
#   or with env: TITLE=Demo URL=s3://... NAMESPACE=pmoves ./pmoves/tools/seed_studio_board.sh

which jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

BASE=${SUPABASE_REST_URL:-${SUPA_REST_URL:-http://localhost:54321/rest/v1}}
KEY=${SUPABASE_SERVICE_ROLE_KEY:-}
if [[ -z "${KEY}" ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY is not set" >&2
  exit 1
fi

TITLE=${TITLE:-${1:-Demo}}
URL=${URL:-${2:-s3://outputs/demo/example.png}}
NAMESPACE=${NAMESPACE:-${3:-${INDEXER_NAMESPACE:-pmoves}}}

body=$(jq -n \
  --arg status "approved" \
  --arg url "$URL" \
  --arg title "$TITLE" \
  --arg ns "$NAMESPACE" \
  '{status:$status, content_url:$url, title:$title, namespace:$ns, meta:{}}')

curl -s -X POST "$BASE/studio_board" \
  -H "content-type: application/json" \
  -H "prefer: return=representation" \
  -H "apikey: $KEY" \
  -H "Authorization: Bearer $KEY" \
  -d "$body" | jq .

