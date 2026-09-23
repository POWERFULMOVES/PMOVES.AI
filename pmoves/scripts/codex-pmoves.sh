#!/usr/bin/env bash
# codex-pmoves — Bootstrap Codex CLI with PMOVES context
# Usage: codex-pmoves [codex-args...]
#
# Launches OpenAI Codex CLI with PMOVES project context.
# Codex is restricted to OpenAI models (GPT-5.4 / codex).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# ---------------------------------------------------------------------------
# NODE IDENTITY + CIPHER CARRY -- added 2026-09-16.
#
# This launcher previously told its agent NOTHING: not which node it was on, not
# which registered identity it wears, and not whether cipher would record its
# memories as itself. Measured across the nine launchers that day, only the two
# CLAUDE ones carried the full set. Cipher is shared by every agent on a node --
# auth.ts files an uncarried write under `bootstrap`, "shared with every other
# agent on the node, attributed to none" (crush-pmoves) -- so an unwired harness
# does not merely lose its own attribution, it pollutes everyone's.
#
# Both measurements are SHARED FRAGMENTS, never copied blocks: that is the rule
# pm-python.sh and pm-cipher-identity.sh were extracted under, and copying into
# eight files is named there as the cause of this family's last three defects.
#
# FAIL-OPEN, ALWAYS LOUD. Neither call can cost the launch, and every path prints
# its reason -- an unbound session is degraded, not broken, but never silent.
# ---------------------------------------------------------------------------
if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-node-identity.sh" ]; then
  # shellcheck source=./pm-node-identity.sh
  . "$PROJECT_ROOT/pmoves/scripts/pm-node-identity.sh"
  pm_node_identity "$PROJECT_ROOT" codex codex-pmoves || true
  echo "${PM_IDENT_LINE}" >&2
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh" ]; then
    # shellcheck source=./pm-cipher-token-bind.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh"
    pm_cipher_token_bind "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-}" || true
    echo "[codex-pmoves] ${PM_CARRY_BIND_LINE}" >&2
  fi
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh" ]; then
    # shellcheck source=./pm-cipher-identity.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh"
    pm_cipher_identity "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-${PMOVES_NODE_IDENTITY:-}}" ${PM_IDENT_PY[@]+"${PM_IDENT_PY[@]}"} || true
    echo "[codex-pmoves] ${PM_CARRY_LINE}" >&2
  fi
fi

cd "$PROJECT_ROOT"
exec codex "$@"