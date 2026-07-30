#!/usr/bin/env bash
# Sync website/hyperdim/ from the Pmoves-hyperdimensions fork.
# Run before CF Pages deploy to ensure the vendored copy matches canonical.
set -euo pipefail

FORK_DIR="${1:-Pmoves-hyperdimensions/website/hyperdim}"
DEST="website/hyperdim"

if [ ! -d "$FORK_DIR" ]; then
  echo "❌ Fork website dir not found at $FORK_DIR"
  echo "   Ensure Pmoves-hyperdimensions submodule is initialized."
  exit 1
fi

echo "🔄 Syncing $FORK_DIR → $DEST"
rsync -av --delete "$FORK_DIR/" "$DEST/"
echo "✅ Synced. Commit the changes or deploy to CF Pages."
