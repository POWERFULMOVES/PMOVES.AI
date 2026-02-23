#!/usr/bin/env bash
# Compatibility wrapper for unified env setup.
# Prefer: make -C pmoves env-setup

set -euo pipefail
cd "$(dirname "$0")/.."

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "python is required to run env setup" >&2
  exit 1
fi

exec "$PYTHON_BIN" tools/env_setup_unified.py "$@"
