#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3.10+ and retry." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv (Python virtual environment)..."
  python3 -m venv .venv
else
  echo ".venv already exists; reusing."
fi

source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r pmoves/tools/requirements-minimal.txt
echo "Done. Activate with: source .venv/bin/activate"

