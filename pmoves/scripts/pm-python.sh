#!/usr/bin/env bash
# pm-python.sh — the ONE python discovery, sourced by every PMOVES launcher
# that needs an interpreter.
#
# Before this file there were three conventions for the same question, two of
# them in ONE launcher (pair-review finding on PR #2769, 2026-08-26):
#   * claude-pmoves.sh hardcoded a scalar `python` — on hosts where only
#     python3 exists, or where python lacks PyYAML while .venv-pmoves has it,
#     the identity resolver silently never ran and every session launched
#     unbound.
#   * the normalizer block used bare `command -v python3`.
#   * crush-pmoves carried its own inline venv/python3/py -3 chain (from
#     #2763, mirroring crush-fleet-bootstrap.sh).
#
# Discovery order mirrors crush-fleet-bootstrap.sh: the canonical venv first
# (preflight installs PyYAML there), then platform launchers. Bare `python3`
# hard-fails on Windows nodes (Git Bash has no python3; the Windows Store stub
# is unusable), and bare `python` is the scalar trap above.
#
# PM_PY is an ARRAY, not a scalar. Two branches below cannot both survive a
# scalar: the venv branch holds a filesystem path that may contain spaces, while
# the launcher branch is genuinely two words (`py -3`). Use "${PM_PY[@]}".
#
# Usage:
#   source pmoves/scripts/pm-python.sh
#   if pm_pick_python; then ...          # any python (json/os/re tools)
#   if pm_pick_python yaml; then ...     # candidate must also `import yaml`
#
# PMOVES_PYTHON (space-separated override) always wins, for operator pinning.

_pm_py_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # pmoves/
_pm_py_root="$(cd "$_pm_py_dir/.." && pwd)"                    # repo root

pm_pick_python() {
  local probe="${1:-}"
  local p

  if [ -n "${PMOVES_PYTHON:-}" ]; then
    # shellcheck disable=SC2206
    PM_PY=(${PMOVES_PYTHON})
    if [ -z "$probe" ] || "${PM_PY[@]}" -c "import $probe" >/dev/null 2>&1; then
      return 0
    fi
    return 1
  fi

  # 1. canonical venv — has PyYAML when preflight has run; space-safe as one
  #    array element.
  for p in "$_pm_py_dir/.venv-pmoves/bin/python" \
           "$_pm_py_dir/.venv-pmoves/Scripts/python.exe"; do
    if [ -x "$p" ]; then
      if [ -z "$probe" ] || "$p" -c "import $probe" >/dev/null 2>&1; then
        PM_PY=("$p")
        return 0
      fi
      # venv exists but failed the probe: fall through to launchers.
      break
    fi
  done

  # 2. platform launchers. `py -3` is two words; each branch is explicit so no
  #    string re-splitting can corrupt a path or join a launcher.
  if command -v python3 >/dev/null 2>&1; then
    if [ -z "$probe" ] || python3 -c "import $probe" >/dev/null 2>&1; then
      PM_PY=(python3)
      return 0
    fi
  fi
  if command -v py >/dev/null 2>&1; then
    if [ -z "$probe" ] || py -3 -c "import $probe" >/dev/null 2>&1; then
      PM_PY=(py -3)
      return 0
    fi
  fi
  if command -v python >/dev/null 2>&1; then
    if [ -z "$probe" ] || python -c "import $probe" >/dev/null 2>&1; then
      PM_PY=(python)
      return 0
    fi
  fi
  return 1
}
