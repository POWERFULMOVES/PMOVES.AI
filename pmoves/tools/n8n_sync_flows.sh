#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLOWS_DIR="$ROOT_DIR/n8n/flows"

copy_match() { # pattern dest_dir
  local pattern="$1"
  local dest="$2"
  mkdir -p "$dest"
  local copied=0
  shopt -s nullglob
  for f in "$FLOWS_DIR"/$pattern; do
    base="$(basename "$f")"
    cp -f "$f" "$dest/$base"
    copied=$((copied+1))
  done
  shopt -u nullglob
  echo "  - $dest: $copied file(s)"
}

echo "→ Syncing n8n flow exports into integration folders"
echo "Source: $FLOWS_DIR"

# Optional: keep the PMOVES-n8n submodule's /workflows folder in sync when present.
SUBMODULE_DIR="$ROOT_DIR/../PMOVES-n8n/workflows"
if [ -d "$SUBMODULE_DIR" ]; then
  mkdir -p "$SUBMODULE_DIR"
  cp -f "$FLOWS_DIR"/*.json "$SUBMODULE_DIR/" 2>/dev/null || true
  echo "  - $SUBMODULE_DIR: synced (best-effort)"
fi

# Health/Wger integration
copy_match "*wger*json" "$ROOT_DIR/integrations/health-wger/n8n/flows"
copy_match "health_*json" "$ROOT_DIR/integrations/health-wger/n8n/flows"

# Finance/Firefly integration
copy_match "*firefly*json" "$ROOT_DIR/integrations/firefly-iii/n8n/flows"
copy_match "finance_*json" "$ROOT_DIR/integrations/firefly-iii/n8n/flows"

echo "✔ n8n flow sync complete"
