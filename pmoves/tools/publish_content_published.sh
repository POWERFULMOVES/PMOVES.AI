#!/usr/bin/env bash
set -euo pipefail

# Post a sample content.published.v1 envelope to Agent Zero.
# Usage:
#   ./pmoves/tools/publish_content_published.sh [FILE] [BASE_URL]
# Defaults:
#   FILE=pmoves/contracts/samples/content.published.v1.sample.json
#   BASE_URL=${AGENT_ZERO_BASE_URL:-http://localhost:8080}

FILE=${1:-pmoves/contracts/samples/content.published.v1.sample.json}
BASE_URL=${2:-${AGENT_ZERO_BASE_URL:-http://localhost:8080}}

if [[ ! -f "$FILE" ]]; then
  echo "Sample file not found: $FILE" >&2
  exit 1
fi

which jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

jq -c '{topic:"content.published.v1", payload:.}' "$FILE" | \
curl -s -X POST "$BASE_URL/events/publish" -H 'content-type: application/json' --data-binary @- | jq .

