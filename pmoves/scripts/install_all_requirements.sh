#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-PMOVES.AI}"
include_docs="${INCLUDE_DOCS:-0}"

have(){ command -v "$1" >/dev/null 2>&1; }

echo "Scanning for requirements.txt files..."
roots=(services tools)
if [[ "$include_docs" == "1" ]]; then roots+=(docs); fi
mapfile -t reqs < <(find "${roots[@]}" -type f -name requirements.txt 2>/dev/null || true)
if [[ ${#reqs[@]} -eq 0 ]]; then echo "No requirements.txt under: ${roots[*]}"; exit 0; fi

pip_cmd=""
if have uv; then pip_cmd=(uv pip install -r)
elif have pip; then pip_cmd=(python -m pip install -r)
else echo "pip or uv required" && exit 1; fi

use_conda=0
if have conda; then
  if conda env list | grep -qE "\b${env_name}\b"; then use_conda=1; fi
fi

for req in "${reqs[@]}"; do
  echo "Installing deps from: $req"
  if [[ $use_conda -eq 1 ]]; then
    if have uv; then conda run -n "$env_name" uv pip install -r "$req"; else conda run -n "$env_name" python -m pip install -r "$req"; fi
  else
    "${pip_cmd[@]}" "$req"
  fi
done

echo "All requirements installed."

