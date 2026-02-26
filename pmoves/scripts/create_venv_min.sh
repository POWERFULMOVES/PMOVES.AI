#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pmoves_root="$(cd -- "${script_dir}/.." && pwd)"
venv_dir="${pmoves_root}/.venv-pmoves"
req_file="${pmoves_root}/tools/requirements-lite.txt"
uv_cmd=""
if command -v uv >/dev/null 2>&1; then
  uv_cmd="uv"
elif command -v uv.exe >/dev/null 2>&1; then
  uv_cmd="uv.exe"
fi
py_cmd="python3"
if ! command -v "${py_cmd}" >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
  py_cmd="python"
fi

to_native_path() {
  local p="$1"
  if [[ "${uv_cmd}" == "uv.exe" ]] && command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
    return
  fi
  printf '%s\n' "$p"
}

if ! command -v "${py_cmd}" >/dev/null 2>&1; then
  echo "python/python3 not found. Please install Python 3.11+ and retry." >&2
  exit 1
fi

if [[ ! -d "${venv_dir}" ]]; then
  echo "Creating ${venv_dir} (Python virtual environment)..."
  if [[ -n "${uv_cmd}" ]]; then
    "${uv_cmd}" venv "$(to_native_path "${venv_dir}")"
  else
    "${py_cmd}" -m venv "${venv_dir}"
  fi
else
  echo "${venv_dir} already exists; reusing."
fi

venv_python="${venv_dir}/bin/python"
if [[ ! -x "${venv_python}" ]]; then
  venv_python="${venv_dir}/Scripts/python.exe"
fi
if [[ ! -x "${venv_python}" ]]; then
  echo "Unable to resolve venv python under ${venv_dir}" >&2
  exit 1
fi

if [[ "${venv_python}" == *.exe ]] && [[ "${uv_cmd}" == "uv" ]]; then
  uv_cmd=""
fi

if [[ -n "${uv_cmd}" ]]; then
  "${uv_cmd}" pip install --python "$(to_native_path "${venv_python}")" -r "$(to_native_path "${req_file}")"
else
  "${venv_python}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  req_for_pip="${req_file}"
  if [[ "${venv_python}" == *.exe ]] && command -v cygpath >/dev/null 2>&1; then
    req_for_pip="$(cygpath -w "${req_file}")"
  fi
  "${venv_python}" -m pip install -r "${req_for_pip}"
fi
activate_hint="${venv_dir}/bin/activate"
if [[ ! -f "${activate_hint}" ]]; then
  activate_hint="${venv_dir}/Scripts/activate"
fi
echo "Done. Activate with: source ${activate_hint}"
