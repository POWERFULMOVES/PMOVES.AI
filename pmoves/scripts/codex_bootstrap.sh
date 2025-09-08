#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-PMOVES.AI}"
include_docs="${INCLUDE_DOCS:-0}"

echo "== PMOVES Codex Bootstrap =="
echo "CWD: $(pwd)"

have(){ command -v "$1" >/dev/null 2>&1; }

# 1) make (Linux/macOS assumed to have package manager)
if ! have make; then
  echo "GNU make not found. Please install via your package manager (apt/brew/etc.)." >&2
fi

# 2) Ensure conda env exists
if have conda; then
  if ! conda env list | grep -qE "\b${env_name}\b"; then
    if [[ -f environment.yml ]]; then
      echo "Creating conda env '${env_name}' from environment.yml..."
      conda env create -f environment.yml -n "${env_name}" || true
    else
      echo "environment.yml not found; skipping conda env creation" >&2
    fi
  else
    echo "Conda env '${env_name}' exists."
  fi
else
  echo "Conda not detected; using system Python for deps." >&2
fi

# 3) Install Python deps
if [[ "$include_docs" == "1" ]]; then
  ./scripts/install_all_requirements.sh "${env_name}"
else
  INCLUDE_DOCS=0 ./scripts/install_all_requirements.sh "${env_name}"
fi

echo "Bootstrap complete."

