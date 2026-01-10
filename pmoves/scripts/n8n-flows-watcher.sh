#!/usr/bin/env sh
set -e

BASE="${N8N_BASE_URL:-http://n8n:5678}"
AUTH_USER="${N8N_USER:-admin}"
AUTH_PASS="${N8N_PASS:-adminpass}"

import_file () {
  FILE="$1"
  [ -f "$FILE" ] || return 0
  NAME=$(jq -r '.name // .meta.name // "Unnamed Flow"' < "$FILE")
  [ "$NAME" = "null" ] && NAME="Unnamed Flow"
  echo "Importing flow: $NAME from $FILE"

  EXISTING=$(curl -sS -u "$AUTH_USER:$AUTH_PASS" "$BASE/rest/workflows" || echo '{}')
  ID=$(echo "$EXISTING" | jq -r --arg n "$NAME" '.data[]? | select(.name==$n) | .id' | head -n1)

  if [ -n "$ID" ] && [ "$ID" != "null" ]; then
    curl -sS -u "$AUTH_USER:$AUTH_PASS" \
      -X PATCH "$BASE/rest/workflows/$ID" \
      -H 'Content-Type: application/json' --data-binary "@$FILE" >/dev/null && echo "Updated: $NAME ($ID)"
  else
    curl -sS -u "$AUTH_USER:$AUTH_PASS" \
      -X POST "$BASE/rest/workflows" \
      -H 'Content-Type: application/json' --data-binary "@$FILE" >/dev/null && echo "Created: $NAME"
  fi
}

initial_import_dir () {
  DIR="$1"
  [ -d "$DIR" ] || return 0
  for f in "$DIR"/*.json; do
    [ -e "$f" ] || continue
    import_file "$f"
  done
}

initial_import_dir "/opt/flows/health-wger"
initial_import_dir "/opt/flows/firefly-iii"

echo "Watching for flow changes..."
inotifywait -m -e close_write,create,delete,move \
  /opt/flows/health-wger /opt/flows/firefly-iii 2>/dev/null | while read -r DIR EVENT FILE; do
    case "$FILE" in
      *.json)
        if echo "$EVENT" | grep -qi "DELETE"; then
          echo "Detected deletion: $FILE (no DELETE API yet; will re-import on next change)"
        else
          import_file "$DIR/$FILE"
        fi
        ;;
      *)
        :
        ;;
    esac
  done
