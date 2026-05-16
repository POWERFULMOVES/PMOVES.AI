#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-PMOVES.AI}"
python_target="${2:-${PMOVES_PYTHON:-}}"
include_docs="${INCLUDE_DOCS:-0}"
include_bringup="${INCLUDE_BRINGUP:-0}"

have(){ command -v "$1" >/dev/null 2>&1; }
py_cmd="python"
if ! have "${py_cmd}" && have python3; then py_cmd="python3"; fi
if ! have "${py_cmd}"; then
  echo "python or python3 required" >&2
  exit 1
fi

echo "Scanning for requirements.txt files..."
roots=(services tools)
if [[ "$include_docs" == "1" ]]; then roots+=(docs); fi
mapfile -t reqs < <(find "${roots[@]}" -type f -name requirements.txt \
  -not -path "*/bringup/*" 2>/dev/null || true)
# INCLUDE_BRINGUP=1 → also install pmoves/tools/bringup/requirements.txt
# (operator-facing CLI tooling: glances, etc.). Kept separate so the default
# venv stays focused on service runtime deps.
if [[ "$include_bringup" == "1" ]] && [[ -f "tools/bringup/requirements.txt" ]]; then
  reqs+=("tools/bringup/requirements.txt")
fi
if [[ ${#reqs[@]} -eq 0 ]]; then echo "No requirements.txt under: ${roots[*]}"; exit 0; fi

have_uv=0
uv_cmd=""
if have uv; then uv_cmd="uv"; have_uv=1
elif have uv.exe; then uv_cmd="uv.exe"; have_uv=1
fi

if [[ -n "${python_target}" ]] && [[ "${python_target}" == *.exe ]] && [[ "${uv_cmd}" == "uv" ]]; then
  # WSL/Git-Bash mixed mode: linux uv cannot target Windows interpreters reliably.
  uv_cmd=""
  have_uv=0
fi

to_native_path() {
  local p="$1"
  if [[ "${uv_cmd}" == "uv.exe" ]] && command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
    return
  fi
  if [[ -n "${python_target}" ]] && [[ "${python_target}" == *.exe ]] && command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
    return
  fi
  printf '%s\n' "$p"
}

if [[ -z "${uv_cmd}" ]]; then
  if [[ -n "${python_target}" ]]; then
    "${python_target}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  else
    "${py_cmd}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi
fi

use_conda=0
if [[ -z "${python_target}" ]] && have conda; then
  if conda env list | grep -qE "\b${env_name}\b"; then use_conda=1; fi
fi

for req in "${reqs[@]}"; do
  echo "Installing deps from: $req"
  if [[ -n "${python_target}" ]]; then
    if [[ $have_uv -eq 1 ]]; then
      "${uv_cmd}" pip install --python "$(to_native_path "${python_target}")" -r "$(to_native_path "$req")"
    else
      "${python_target}" -m pip install -r "$(to_native_path "$req")"
    fi
  elif [[ $use_conda -eq 1 ]]; then
    if [[ $have_uv -eq 1 ]]; then conda run -n "$env_name" "${uv_cmd}" pip install -r "$req"; else conda run -n "$env_name" python -m pip install -r "$req"; fi
  else
    if [[ $have_uv -eq 1 ]]; then "${uv_cmd}" pip install -r "$req"; else "${py_cmd}" -m pip install -r "$req"; fi
  fi
done

echo "All requirements installed."
