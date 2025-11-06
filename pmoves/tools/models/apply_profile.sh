#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${PROFILE:-${1:-archon}}"
HOST="${HOST:-workstation_5090}"
TZ_BASE="${TENSORZERO_BASE_URL:-}"

if [[ -z "$TZ_BASE" ]]; then
  # fall back to default compose service
  TZ_BASE="http://tensorzero-gateway:3000"
fi

echo "→ Applying model profile: $PROFILE (host=$HOST, tz_base=$TZ_BASE)"
python3 "$SCRIPT_DIR/models_sync.py" sync --profile "$PROFILE" --host "$HOST" --tensorzero-base "$TZ_BASE"

echo "✔ Updated pmoves/.env.local. Restart services as needed (e.g. make -C pmoves recreate-v2)."
