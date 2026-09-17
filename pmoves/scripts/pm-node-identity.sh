#!/usr/bin/env bash
# pm-node-identity.sh — the ONE node-identity resolution, sourced by every
# PMOVES launcher that tells an agent who it is.
#
# WHY A SHARED FRAGMENT AND NOT A COPIED BLOCK
# --------------------------------------------
# This is the third fragment in the same family and it exists for the reason the
# other two record. pm-python.sh was extracted because "find python" had THREE
# conventions, two of them in one file (#2769). pm-cipher-identity.sh was
# extracted because the carry verdict shipped as 36 inline lines and the other
# launchers got none of it. The resolution block was the last duplicated piece:
# ~30 lines living in claude-pmoves.sh and again in crush-pmoves, and nowhere
# else — so six of the fleet's nine launchers told their agent nothing.
#
# Measured 2026-09-16 across the nine launchers (identity / carry / TS_ / env /
# roster): only the two CLAUDE launchers carried all five. codex-pmoves.sh was
# eleven lines — `cd "$PROJECT_ROOT"; exec codex "$@"` — while CODEX-GPT5 holds
# thirty register entries that identity_vocabulary.yaml calls "the cleanest lane
# in the register". The best-disciplined agent had the least-wired launcher and
# had been typing its identity by hand.
#
# THE CONTRACT
# ------------
# pm_node_identity <repo_root> <harness> <label>
#
#   returns 0  an identity resolved; PMOVES_NODE_IDENTITY is set
#   returns 1  it did not; PM_IDENT_LINE says WHY, and the caller must print it
#
# On return, ALWAYS set:
#   PM_IDENT_PY[@]   the python argv the resolver ran under ('' if none found)
#   PM_IDENT_LINE    one line for stderr, already prefixed with <label>
#   PM_IDENT_OK      1 when an identity resolved, 0 otherwise
# and on success also PMOVES_NODE / PMOVES_NODE_IDENTITY (exported).
#
# <harness> is passed through to node_identity.py --harness. It is NOT cosmetic:
# node-vocabulary.yaml keys the default identity per harness, so claude-code and
# crush can resolve to different agents on the same node.
#
# ALWAYS LOUD. Every path out sets PM_IDENT_LINE. An unbound session is a
# degraded session, not a broken one -- but it must never be a SILENT one, which
# is the defect claude-pmoves.sh's own header says this family keeps re-fixing.
#
# FAIL-OPEN. Losing an identity must never cost the launch.

pm_node_identity() {
  local root="${1:-}" harness="${2:-}" label="${3:-launcher}"

  PM_IDENT_PY=()
  PM_IDENT_LINE=""
  PM_IDENT_OK=0

  local tool="$root/pmoves/tools/node_identity.py"
  if [ ! -f "$tool" ]; then
    PM_IDENT_LINE="[$label] node identity: resolver missing ($tool); launching without it."
    return 1
  fi

  # Shared discovery, not a scalar `python`: on hosts where only python3 exists,
  # or where python lacks PyYAML while .venv-pmoves has it, the scalar form
  # silently never ran the resolver. `yaml` probe -- the resolver imports it.
  if [ -z "${PM_PICK_PYTHON_LOADED:-}" ] && [ -f "$root/pmoves/scripts/pm-python.sh" ]; then
    # shellcheck source=./pm-python.sh
    . "$root/pmoves/scripts/pm-python.sh"
  fi
  if command -v pm_pick_python >/dev/null 2>&1 && pm_pick_python yaml; then
    PM_IDENT_PY=("${PM_PY[@]}")
  fi
  if [ ${#PM_IDENT_PY[@]} -eq 0 ]; then
    PM_IDENT_LINE="[$label] node identity: no usable python (tried .venv-pmoves, python3, py -3, python — yaml required); launching without it."
    return 1
  fi

  # The resolver reads the process env, but a launcher runs BEFORE the harness
  # loads .claude/settings.local.json. A node whose HOSTNAME collides -- the
  # 5090, whose POWERFULMOVES casefolds onto the `powerfulmoves` org vocabulary
  # entry (kind=unresolved) -- resolves to nothing and fail-opens to an unbound
  # session even though its identity is declared in that file. Read
  # PMOVES_NODE_ID from the SAME block so declaring it once binds both. A shell
  # value still wins if already set.
  if [ -z "${PMOVES_NODE_ID:-}" ] && [ -f "$root/.claude/settings.local.json" ]; then
    local _sid
    _sid="$("${PM_IDENT_PY[@]}" -c 'import json,sys;print((json.load(open(sys.argv[1])).get("env") or {}).get("PMOVES_NODE_ID","") or "")' "$root/.claude/settings.local.json" 2>/dev/null || true)"
    [ -n "$_sid" ] && export PMOVES_NODE_ID="$_sid"
  fi

  local out
  if ! out="$("${PM_IDENT_PY[@]}" "$tool" --harness "$harness" --shell 2>/dev/null)"; then
    PM_IDENT_LINE="[$label] node identity: $tool failed; launching without it."
    return 1
  fi

  # The tool emits PMOVES_RESOLVED_IDENTITY, not PMOVES_NODE_IDENTITY: the
  # latter is the operator's INPUT override, and a resolver that answers under
  # the same name it reads cannot be called twice safely.
  eval "$out"
  PMOVES_NODE_IDENTITY="${PMOVES_RESOLVED_IDENTITY:-}"
  export PMOVES_NODE PMOVES_NODE_IDENTITY

  if [ -z "${PMOVES_NODE_IDENTITY:-}" ]; then
    PM_IDENT_LINE="[$label] node=${PMOVES_NODE:-unknown} identity=unresolved: ${PMOVES_IDENTITY_WHY:-no reason given}"
    return 1
  fi

  PM_IDENT_OK=1
  PM_IDENT_LINE="[$label] node=${PMOVES_NODE} identity=${PMOVES_NODE_IDENTITY}"
  return 0
}
