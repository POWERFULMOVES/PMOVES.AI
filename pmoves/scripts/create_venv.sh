#!/usr/bin/env bash
set -euo pipefail

# Create a local Python venv at .venv and install all service requirements.
# Usage:
#   bash pmoves/scripts/create_venv.sh            # basic
#   INCLUDE_DOCS=1 bash pmoves/scripts/create_venv.sh  # include docs/** requirements

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3.11+ and retry." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv (Python virtual environment)..."
  python3 -m venv .venv
else
  echo ".venv already exists; reusing."
fi

echo "Activating venv and upgrading pip..."
source .venv/bin/activate
python -m pip install -U pip

echo "Installing requirements across services/tools..."
INCLUDE_DOCS=${INCLUDE_DOCS:-0} bash pmoves/scripts/install_all_requirements.sh || bash pmoves/scripts/install_all_requirements.sh

echo "Done. Activate with: source .venv/bin/activate"

