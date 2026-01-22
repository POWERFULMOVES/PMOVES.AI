#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLOWS_DIR="$ROOT_DIR/n8n/flows"
N8N_CONTAINER="${N8N_CONTAINER:-pmoves-n8n}"

mkdir -p "$FLOWS_DIR"

name_to_file() {
  case "$1" in
    "PMOVES • Supabase Approval Poller v1") echo "approval_poller.json" ;;
    "Voice Platform Router - PMOVES") echo "voice_platform_router.json" ;;
    "Discord Voice Agent - PMOVES") echo "discord_voice_agent.json" ;;
    "Telegram Voice Agent - PMOVES") echo "telegram_voice_agent.json" ;;
    "Voice Shared Functions - PMOVES") echo "voice_shared_functions.json" ;;
    *) echo "" ;;
  esac
}

echo "→ Exporting workflows from n8n container: $N8N_CONTAINER"
rows="$(docker exec "$N8N_CONTAINER" /usr/bin/sqlite3 /home/node/.n8n/database.sqlite 'select id,name from workflow_entity;')"
if [ -z "$rows" ]; then
  echo "✗ No workflows found in n8n DB; is n8n initialized?" >&2
  exit 1
fi

exported=0
while IFS='|' read -r wf_id wf_name; do
  out_file="$(name_to_file "$wf_name")"
  if [ -z "$out_file" ]; then
    continue
  fi
  tmp="/tmp/pmoves_n8n_export_${wf_id}.json"
  docker exec "$N8N_CONTAINER" n8n export:workflow --id="$wf_id" --output="$tmp" >/dev/null
  docker exec "$N8N_CONTAINER" cat "$tmp" > "$FLOWS_DIR/$out_file"
  python3 "$ROOT_DIR/tools/n8n_flow_normalize.py" --file "$FLOWS_DIR/$out_file"
  exported=$((exported+1))
  echo "  - $out_file (from $wf_name)"
done <<< "$rows"

if [ "$exported" -eq 0 ]; then
  echo "✗ No matching workflows exported (expected voice + approval flows)" >&2
  exit 1
fi

echo "✔ Exported $exported workflow(s) into $FLOWS_DIR"
