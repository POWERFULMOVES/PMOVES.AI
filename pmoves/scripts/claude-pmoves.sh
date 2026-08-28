#!/usr/bin/env bash
# claude-pmoves — Bootstrap Claude Code with a PMOVES agent AND its MCP creds.
# ===========================================================================
# THIN DELEGATE. The real launcher is deploy/provision/claude-pmoves.sh, which
# loads pmoves/env.shared and passes the normalized MCP roster via
# --mcp-config=. This script only adds the positional-agent shorthand on top.
#
# WHY THE SPLIT EXISTED: these two files share a name but were never duplicates.
# This one selected an agent (`claude --agent`) and loaded nothing; the
# provisioning one loaded env.shared + the MCP roster and selected no agent.
# Each ended in its own `exec claude`, so they were mutually exclusive — you
# could have a PMOVES agent OR working MCP creds, never both. `make -C pmoves
# claude-pmoves` took this path, so the documented way to launch the delivery
# agent came up with every cred-dependent MCP empty.
#
# Delegating fixes that without changing either UI: the shorthand still works,
# and it now inherits env.shared + the roster.
#
# Usage: claude-pmoves [agent-name] [claude-args...]
# Default agent: node-steward (claims work, then spawns delivery agents)
# Other agents: control-agent, memory-agent, researcher, test-runner, pr-trimmer, verifier, code-review
#
# Examples:
#   claude-pmoves                          # node-steward (default)
#   claude-pmoves delivery-agent           # straight to execution
#   claude-pmoves control-agent            # review/gate agent
#   claude-pmoves memory-agent             # cipher memory agent
#   claude-pmoves test-runner --worktree   # test runner in worktree
#
# To launch with NO agent (plain Claude + PMOVES MCP), call the provisioning
# script directly: deploy/provision/claude-pmoves.sh
set -u

# ---------------------------------------------------------------------------
# REPO-ROOT RESOLUTION — keep byte-identical across the three launchers that
# carry it (deploy/provision/claude-pmoves.sh, deploy/provision/crush-pmoves.sh,
# this file). Enforced by deploy/provision/tests/test-launcher-root-resolution.sh,
# which fails if one is fixed and the others are not.
#
# WHY THE WALK: taking dirname of a PATH symlink instead of the real file makes
# ROOT=$HOME, so the delegate cannot find the real launcher and degrades to
# `claude --agent` with no creds — the silent-credless class this file exists to
# close.
#
# WHY `CDPATH='' cd -P --`: dirname yields a bare relative path when the script is
# invoked relatively; `cd` consults CDPATH for such arguments, which both jumps
# elsewhere AND echoes the destination, embedding a newline in the captured path.
# ---------------------------------------------------------------------------
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"

# PMOVES_LAUNCHER_ROOT, not PMOVES_REPO_ROOT: the latter is already consumed by
# pmoves/services/creator-operator/config.py.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH='' cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
fi

LAUNCHER="$ROOT/deploy/provision/claude-pmoves.sh"

# DEFAULT AGENT: node-steward, not delivery-agent.
#
# The old default made every node session an execution body with no node context
# and no claim discipline. A B850 session on 2026-08-23 ran that way to
# completion -- eight PRs and three live DB mutations on the data-tier host, all
# unclaimed -- and the register recorded nobody as having been there. An agent
# that starts holding Edit will edit; the steward is denied Write/Edit and spawns
# delivery agents instead. See .claude/agents/node-steward.md.
#
# Overridable: `claude-pmoves delivery-agent` still gets the old behaviour, and
# PMOVES_DEFAULT_AGENT sets it per node without editing this file.
#
# Falls back to delivery-agent if the steward definition is absent, so a node on
# an older checkout keeps working rather than launching with --agent pointed at
# nothing.
DEFAULT_AGENT="${PMOVES_DEFAULT_AGENT:-node-steward}"
if [ ! -f "$ROOT/.claude/agents/$DEFAULT_AGENT.md" ]; then
  DEFAULT_AGENT="delivery-agent"
fi
# Only treat $1 as an agent NAME if it is not a flag. The previous form,
# AGENT="${1:-delivery-agent}", consumed anything: `claude-pmoves --print ping`
# silently launched with `--agent --print`, which claude rejects or misreads.
# A leading `-` now means "no agent named, these are claude's args".
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  AGENT="$1"
  shift
else
  AGENT="$DEFAULT_AGENT"
fi

# ---------------------------------------------------------------------------
# NODE IDENTITY — the half the agent selection above does not answer.
#
# `--agent node-steward` says what this session DOES. It says nothing about
# which node it is on or which registered agent it IS, so every session began
# by rediscovering both. `topology.node_affinity` in agent_registry.yaml was
# written for exactly this and nothing read it.
#
# Resolution is declared, not inferred: eight registry agents claim the 4090
# under one spelling or another, so "the agent whose affinity matches" would be
# a guess wearing a resolver's clothes. See pmoves/tools/node_identity.py.
#
# FAIL-OPEN, LOUDLY. Every failure here -- no python, no config, unknown node,
# identity declared but not yet registered -- leaves the session launching
# exactly as it did before, and prints why. An identity is a convenience;
# losing it must never cost you the launch. Losing it SILENTLY is the defect
# this file keeps having to fix, so the reason is always printed.
# ---------------------------------------------------------------------------
IDENTITY_ARGS=()
IDENT_TOOL="$ROOT/pmoves/tools/node_identity.py"
# Shared discovery (pm-python.sh), not a scalar `python`: on hosts where only
# python3 exists, or where python lacks PyYAML while .venv-pmoves has it, the
# scalar form silently never ran the resolver and sessions launched unbound —
# the exact gap #2763 fixed for crush-pmoves, which this launcher then still
# carried (pair-review finding on #2769).
# shellcheck source=./pm-python.sh
. "$ROOT/pmoves/scripts/pm-python.sh"
IDENT_PY=()
if [ -f "$IDENT_TOOL" ] && pm_pick_python yaml; then
  IDENT_PY=("${PM_PY[@]}")
fi
# The resolver reads the process env, but this launcher runs BEFORE the harness
# loads .claude/settings.local.json. So a node whose HOSTNAME collides — the 5090,
# whose POWERFULMOVES casefolds onto the `powerfulmoves` org vocabulary entry
# (kind=unresolved) — resolves to nothing and fail-opens to an unbound session,
# even though its identity is declared in settings.local.json's env block. Read
# PMOVES_NODE_ID from that SAME block so declaring it once binds both the launcher
# and the session. A shell env value still wins if already set (kept parity with
# claude-pmoves.bat; node_identity.py invocation below is unchanged).
if [ -z "${PMOVES_NODE_ID:-}" ] && [ ${#IDENT_PY[@]} -gt 0 ] && [ -f "$ROOT/.claude/settings.local.json" ]; then
  _sid="$("${IDENT_PY[@]}" -c 'import json,sys;print((json.load(open(sys.argv[1])).get("env") or {}).get("PMOVES_NODE_ID","") or "")' "$ROOT/.claude/settings.local.json" 2>/dev/null || true)"
  [ -n "$_sid" ] && export PMOVES_NODE_ID="$_sid"
  unset _sid
fi
if [ -f "$IDENT_TOOL" ] && [ ${#IDENT_PY[@]} -gt 0 ]; then
  if IDENT_OUT="$("${IDENT_PY[@]}" "$IDENT_TOOL" --harness claude-code --shell 2>/dev/null)"; then
    # The tool emits PMOVES_RESOLVED_IDENTITY, not PMOVES_NODE_IDENTITY: the
    # latter is the operator's INPUT override, and a resolver that answers under
    # the same name it reads cannot be called twice safely.
    eval "$IDENT_OUT"
    PMOVES_NODE_IDENTITY="${PMOVES_RESOLVED_IDENTITY:-}"
    export PMOVES_NODE PMOVES_NODE_IDENTITY
    if [ -n "${PMOVES_NODE_IDENTITY:-}" ]; then
      echo "[claude-pmoves] node=${PMOVES_NODE} identity=${PMOVES_NODE_IDENTITY} agent=${AGENT}" >&2
      # Put it where the session can actually READ it. Exported variables do
      # not reach the model's context; an appended system prompt does. This is
      # the difference between the identity existing and the identity working.
      IDENTITY_ARGS=(--append-system-prompt "You are running on PMOVES node '${PMOVES_NODE}'. Your registered identity in pmoves/config/agent_registry.yaml is '${PMOVES_NODE_IDENTITY}'. Disclose it at session start rather than rediscovering it. Your selected role for this session is the '${AGENT}' agent.")
    else
      echo "[claude-pmoves] node=${PMOVES_NODE:-unknown} identity=unresolved: ${PMOVES_IDENTITY_WHY:-no reason given}" >&2
    fi
  else
    echo "[claude-pmoves] node identity: $IDENT_TOOL failed; launching without it." >&2
  fi
elif [ -f "$IDENT_TOOL" ]; then
  echo "[claude-pmoves] node identity: no usable python found (tried .venv-pmoves, python3, py -3, python — yaml required); launching without it." >&2
fi

if [ ! -f "$LAUNCHER" ]; then
  # Degrade to the pre-delegation behavior rather than failing: the agent still
  # loads, MCP creds do not. Warn so the missing half is visible, not silent.
  echo "[claude-pmoves] WARN: $LAUNCHER not found — launching without env.shared or the MCP roster." >&2
  exec claude --agent "$AGENT" ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"} "$@"
fi

# The launcher forwards "$@" straight to claude after --mcp-config=, so --agent
# rides through unchanged.
exec bash "$LAUNCHER" --agent "$AGENT" ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"} "$@"
