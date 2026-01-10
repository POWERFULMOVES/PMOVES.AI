#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-PMOVES.AI}"
include_docs="${INCLUDE_DOCS:-0}"

script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
env_file="${repo_root}/environment.yml"
install_script="${repo_root}/scripts/install_all_requirements.sh"

echo "== PMOVES Codex Bootstrap =="
echo "CWD: $(pwd)"
echo "Repo root: ${repo_root}"
echo "Environment file: ${env_file}"
echo "Install script: ${install_script}"

have(){ command -v "$1" >/dev/null 2>&1; }

# 1) make (Linux/macOS assumed to have package manager)
if ! have make; then
  echo "GNU make not found. Please install via your package manager (apt/brew/etc.)." >&2
fi

# 2) Ensure conda env exists
if have conda; then
  if ! conda env list | grep -qE "\b${env_name}\b"; then
    if [[ -f "${env_file}" ]]; then
      echo "Creating conda env '${env_name}' from ${env_file}..."
      conda env create -f "${env_file}" -n "${env_name}" || true
    else
      echo "environment.yml not found at ${env_file}; skipping conda env creation" >&2
    fi
  else
    echo "Conda env '${env_name}' exists."
  fi
else
  echo "Conda not detected; using system Python for deps." >&2
fi

# 3) Install Python deps
if [[ ! -f "${install_script}" ]]; then
  echo "Install script not found: ${install_script}" >&2
  exit 1
fi

if [[ "$include_docs" == "1" ]]; then
  (cd "${repo_root}" && INCLUDE_DOCS=1 bash "${install_script}" "${env_name}")
else
  (cd "${repo_root}" && INCLUDE_DOCS=0 bash "${install_script}" "${env_name}")
fi

echo "Bootstrap complete."

