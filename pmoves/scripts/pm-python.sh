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
# THE CONTRACT: a 0 return means PM_PY holds something the caller can RUN.
# Not "PMOVES_PYTHON was non-empty", not "a candidate existed" — runnable. The
# point of a shared discovery is that every caller relies on one sentence, and
# callers pass no probe far more often than they pass one (the MCP roster
# normalizer needs only the stdlib), so the no-probe path has to carry the same
# guarantee as the probe path. It did not, and the caller that trusted it
# launched sessions with unauthenticated MCP servers.
#
# Usage:
#   source pmoves/scripts/pm-python.sh
#   if pm_pick_python; then ...          # any python (json/os/re tools)
#   if pm_pick_python yaml; then ...     # candidate must also `import yaml`
#
# PMOVES_PYTHON (space-separated override) always wins, for operator pinning.
#
# Tests: pmoves/tests/test_pm_python_discovery.py (hermetic; no real CPython).

_pm_py_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # pmoves/
_pm_py_root="$(cd "$_pm_py_dir/.." && pwd)"                    # repo root

# The public entry point is a WRAPPER and the search is separate, so the
# contract above is enforced in ONE place rather than re-promised at every
# `return 0`. That distinction is the fix, not a style choice:
# `PMOVES_PYTHON=" "` passed `[ -n ]`, word-split to ZERO elements, and the
# no-probe short-circuit returned 0 with an empty PM_PY. The caller —
# deploy/provision/claude-pmoves.sh — then ran `"${PM_PY[@]}" "$NORMALIZER" …`,
# i.e. the non-executable .py file as the command, and fell back to the RAW MCP
# roster whose bearer tokens are still literal ${VAR} text. Repairing only that
# branch would leave the next branch free to repeat it; the wrapper cannot be
# bypassed by a branch that has not been written yet.
pm_pick_python() {
  PM_PY=()
  if ! _pm_pick_python_search "$@"; then
    # Also the reset: PM_PY is a global no caller declares, so without this a
    # failed pick leaves the PREVIOUS call's interpreter in place for anyone
    # who checks ${#PM_PY[@]} instead of the return code.
    PM_PY=()
    return 1
  fi
  if [ "${#PM_PY[@]}" -eq 0 ]; then
    # A search that says "found it" and leaves nothing behind is a bug in the
    # search, not an interpreter. Never hand a caller an empty argv vector.
    return 1
  fi
  return 0
}

_pm_pick_python_search() {
  local probe="${1:-}"
  local p

  if [ -n "${PMOVES_PYTHON:-}" ]; then
    # `read -ra` splits on IFS and does NOT glob. The old `PM_PY=(${...})` did
    # both, because `set -f` is not in effect: `PMOVES_PYTHON='*'` became the
    # caller's directory listing, and from a directory that happens to contain
    # a file named `python3` the pin was silently satisfied by that filename —
    # which then resolved through PATH to a real interpreter, so it looked like
    # it worked. `read` is preferred over a scoped `set -f` because toggling a
    # shell option inside a sourced function means saving and restoring the
    # CALLER's own -f state, and this function is sourced into launchers whose
    # shell settings are not ours to disturb.
    #
    # Newlines fold to spaces first: `read` stops at the first line, so without
    # this a multi-line pin would silently lose its tail — the same class of
    # quiet truncation being fixed here. A pin is one argv vector.
    read -ra PM_PY <<<"${PMOVES_PYTHON//$'\n'/ }"
    # Whitespace-only pins arrive here with zero elements. What the wrapper
    # cannot see is a pin that names something which does not exist, so probe
    # the pin for liveness even when the caller asked for no module: `-c ''` is
    # a no-op for any interpreter and non-zero for anything that is not one.
    # The other branches already gate on `-x` / `command -v`; this branch had
    # no gate at all.
    if [ "${#PM_PY[@]}" -eq 0 ]; then
      return 1
    fi
    if [ -n "$probe" ]; then
      "${PM_PY[@]}" -c "import $probe" >/dev/null 2>&1 || return 1
    else
      "${PM_PY[@]}" -c "" >/dev/null 2>&1 || return 1
    fi
    return 0
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
