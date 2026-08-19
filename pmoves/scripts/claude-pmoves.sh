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
# Default agent: delivery-agent
# Other agents: control-agent, memory-agent, researcher, test-runner, pr-trimmer, verifier, code-review
#
# Examples:
#   claude-pmoves                          # delivery-agent (default)
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
# WHY `CDPATH= cd -P --`: dirname yields a bare relative path when the script is
# invoked relatively; `cd` consults CDPATH for such arguments, which both jumps
# elsewhere AND echoes the destination, embedding a newline in the captured path.
# ---------------------------------------------------------------------------
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH= cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "$SELF")" && pwd)"

# PMOVES_LAUNCHER_ROOT, not PMOVES_REPO_ROOT: the latter is already consumed by
# pmoves/services/creator-operator/config.py.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH= cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
fi

LAUNCHER="$ROOT/deploy/provision/claude-pmoves.sh"

AGENT="${1:-delivery-agent}"
shift 2>/dev/null || true

if [ ! -f "$LAUNCHER" ]; then
  # Degrade to the pre-delegation behavior rather than failing: the agent still
  # loads, MCP creds do not. Warn so the missing half is visible, not silent.
  echo "[claude-pmoves] WARN: $LAUNCHER not found — launching without env.shared or the MCP roster." >&2
  exec claude --agent "$AGENT" "$@"
fi

# The launcher forwards "$@" straight to claude after --mcp-config=, so --agent
# rides through unchanged.
exec bash "$LAUNCHER" --agent "$AGENT" "$@"
