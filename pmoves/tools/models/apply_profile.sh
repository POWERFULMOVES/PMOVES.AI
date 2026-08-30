#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PROFILE="${PROFILE:-}"
HOST="${HOST:-desktop-9950xd}"
TENSORZERO_BASE="${TENSORZERO_BASE_URL:-http://tensorzero-gateway:3000}"

if [ -z "$PROFILE" ]; then
  echo "Usage: PROFILE=<agent-zero|archon|media|vlm-and-creator> [HOST=<host>] make -C pmoves model-apply"
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
elif command -v py >/dev/null 2>&1; then
  PYTHON_CMD="py -3"
else
  echo "Python is required for model-apply"
  exit 1
fi

set -x
eval "$PYTHON_CMD \"$ROOT_DIR/tools/models/models_sync.py\" sync --profile \"$PROFILE\" --host \"$HOST\" --tensorzero-base \"$TENSORZERO_BASE\""
