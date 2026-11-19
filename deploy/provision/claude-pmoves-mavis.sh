#!/usr/bin/env bash
# claude-pmoves-mavis.sh -- thin wrapper that pins --backend=minimax and execs
# the main claude-pmoves.sh. Sits alongside claude-pmoves.sh; not a duplicate
# of its env-strip / env.shared / blocklist logic.
#
# WHY a SEPARATE launcher (not a flag on claude-pmoves):
# Per operator directive on 2026-10-03: vanilla claude-pmoves stays clean
# Claude Code settings (Claude Max by default). The Mavis/MiniMax SDK overlay
# is opt-in by RUN NAME, not by flag. claude-pmoves-mavis is the explicit
# opt-in. The launcher's --backend=minimax underneath is the implementation
# detail; the run-name is the contract.
#
# Defaults to env-PMOVES_CLAUDE_BACKEND=minimax. Operator can override with
# PMOVES_CLAUDE_BACKEND=anthropic to temporarily route clean even when invoking
# the -mavis launcher name (handy for A/B testing).
#
# Usage:  claude-pmoves-mavis.sh [claude-args...]
#   All args pass through to the main claude-pmoves.sh after --backend=minimax
#   is prepended. No flag-parsing on this wrapper -- it's intentionally minimal.

set -u

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
MAIN="$SELF_DIR/claude-pmoves.sh"

if [ ! -x "$MAIN" ]; then
  echo "[claude-pmoves-mavis] ERROR: main launcher not found or not executable: $MAIN" >&2
  exit 1
fi

# Pin the backend unless the operator already set it explicitly.
# (PMOVES_CLAUDE_BACKEND inherited from process env wins over the default.)
: "${PMOVES_CLAUDE_BACKEND:=minimax}"
export PMOVES_CLAUDE_BACKEND

echo "[claude-pmoves-mavis] launching with --backend=$PMOVES_CLAUDE_BACKEND" >&2
exec "$MAIN" --backend="$PMOVES_CLAUDE_BACKEND" "$@"