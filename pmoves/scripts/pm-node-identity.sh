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

# ---------------------------------------------------------------------------
# PROMPT ACCUMULATION — pm_ident_append / pm_ident_prompt_args
#
# WHY A STRING AND NOT AN ARRAY OF FLAGS
# --------------------------------------
# `claude --append-system-prompt` does NOT accumulate. The LAST occurrence wins
# and every earlier one is discarded — no warning, no log line, no non-zero
# exit. Measured on B850 2026-09-17:
#
#   $ claude --print \
#       --append-system-prompt "MARKER_ALPHA is ZEBRA." \
#       --append-system-prompt "MARKER_BETA is WALRUS." \
#       "Output ALPHA=<value or UNKNOWN> and BETA=<value or UNKNOWN>."
#   ALPHA=UNKNOWN     <- first flag, dropped
#   BETA=WALRUS       <- last flag, survived
#
# and the same two facts in ONE flag, separated by a blank line:
#
#   ALPHA=ZEBRA
#   BETA=WALRUS
#
# claude-pmoves.sh had THREE contributors — node identity, cipher status, the
# identity-carry verdict — across six call sites, each adding its own flag. Only
# the last one ever reached the model. The node identity this whole fragment
# exists to resolve was the FIRST contributor, so it was the one that never
# arrived: the launcher
# printed `node=knuckles identity=claude_b850` to stderr, exported it, appended
# it — and the session still began by rediscovering both. Resolution was never
# at fault; the flag layer silently ate it.
#
# The cancellation is invisible from any test that inspects the array: the
# string IS in IDENTITY_ARGS on every path. It is lost one layer further out, in
# the argv the harness parses. So the invariant is enforced where it breaks —
# ONE flag, built by concatenation — and the test asserts on the composed argv.
# See pmoves/tests/test_launcher_prompt_accumulation.py.
#
# CONTRIBUTORS MUST NOT KNOW ABOUT EACH OTHER. That is the point: `+=` on a flag
# array reads as accumulation and is not, so every future contributor inherits
# the bug by writing the obvious thing. pm_ident_append can only ever add.
#
# NOT EXPORTED. This is argv material for one exec, not environment; the
# resolver's own note applies — exported variables do not reach the model.
PM_IDENT_PROMPT="${PM_IDENT_PROMPT:-}"

# pm_ident_append <text> — add one block to the single accumulated prompt.
# Empty text is a no-op, so a contributor with nothing to say cannot inject a
# stray separator. Blocks are joined by a blank line: the harness receives one
# system prompt, and the model reads it as distinct paragraphs.
pm_ident_append() {
  local text="${1:-}"
  [ -n "$text" ] || return 0
  if [ -n "${PM_IDENT_PROMPT:-}" ]; then
    PM_IDENT_PROMPT="${PM_IDENT_PROMPT}"$'\n\n'"${text}"
  else
    PM_IDENT_PROMPT="$text"
  fi
}

# pm_ident_prompt_args — compose the ONE flag, once, at the exec site.
# Sets PM_IDENT_PROMPT_ARGS[@]: either empty (nothing to say — do not pass a
# flag with an empty value) or exactly the two elements
# `--append-system-prompt` and the accumulated text.
pm_ident_prompt_args() {
  PM_IDENT_PROMPT_ARGS=()
  [ -n "${PM_IDENT_PROMPT:-}" ] || return 0
  PM_IDENT_PROMPT_ARGS=(--append-system-prompt "$PM_IDENT_PROMPT")
}
