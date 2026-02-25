#!/usr/bin/env bash
set -euo pipefail

include_docs="${INCLUDE_DOCS:-0}"

script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
bootstrap_tool="${repo_root}/tools/bootstrap_light_env.py"
install_script="${repo_root}/scripts/install_all_requirements.sh"
venv_python="${repo_root}/.venv-pmoves/bin/python"

echo "== PMOVES Codex Bootstrap =="
echo "CWD: $(pwd)"
echo "Repo root: ${repo_root}"
echo "Bootstrap tool: ${bootstrap_tool}"
echo "Install script: ${install_script}"

have(){ command -v "$1" >/dev/null 2>&1; }
py_bin="python"
if have python3; then py_bin="python3"; fi

# 1) Create/check pmoves/.venv-pmoves and install lite prerequisites (uv-first)
if [[ ! -f "${bootstrap_tool}" ]]; then
  echo "Bootstrap tool not found: ${bootstrap_tool}" >&2
  exit 1
fi
(cd "${repo_root}" && "${py_bin}" tools/bootstrap_light_env.py --strict-tools)
if [[ ! -x "${venv_python}" ]]; then
  venv_python="${repo_root}/.venv-pmoves/Scripts/python.exe"
fi
if [[ ! -x "${venv_python}" ]]; then
  echo "Unable to resolve venv python under ${repo_root}/.venv-pmoves" >&2
  exit 1
fi

# 2) Install Python deps into the venv interpreter
if [[ ! -f "${install_script}" ]]; then
  echo "Install script not found: ${install_script}" >&2
  exit 1
fi

if [[ "$include_docs" == "1" ]]; then
  (cd "${repo_root}" && INCLUDE_DOCS=1 bash "${install_script}" "PMOVES.AI" "${venv_python}")
else
  (cd "${repo_root}" && INCLUDE_DOCS=0 bash "${install_script}" "PMOVES.AI" "${venv_python}")
fi

echo "Bootstrap complete."
