#!/usr/bin/env sh
set -e

BASE="${N8N_BASE_URL:-http://n8n:5678}"
AUTH_USER="${N8N_USER:-admin}"
AUTH_PASS="${N8N_PASS:-adminpass}"

import_dir () {
  DIR="$1"
  if [ -d "$DIR" ]; then
    for f in "$DIR"/*.json; do
      [ -e "$f" ] || continue
      echo "Importing: $f"
      NAME=$(jq -r '.name // .meta.name // "Unnamed Flow"' < "$f")
      EXISTING=$(curl -sS -u "$AUTH_USER:$AUTH_PASS" "$BASE/rest/workflows")
      ID=$(echo "$EXISTING" | jq -r --arg n "$NAME" '.data[] | select(.name==$n) | .id' | head -n1)

      if [ -n "$ID" ]; then
        curl -sS -u "$AUTH_USER:$AUTH_PASS" -X PATCH "$BASE/rest/workflows/$ID" -H 'Content-Type: application/json' --data-binary "@$f" >/dev/null
        echo "Updated: $NAME ($ID)"
      else
        curl -sS -u "$AUTH_USER:$AUTH_PASS" -X POST "$BASE/rest/workflows" -H 'Content-Type: application/json' --data-binary "@$f" >/dev/null
        echo "Created: $NAME"
      fi
    done
  fi
}

import_dir "/opt/flows/health-wger"
import_dir "/opt/flows/firefly-iii"

echo "n8n flow import complete."
