#!/usr/bin/env bash
# kimi-pmoves — Bootstrap Kimi Code CLI with PMOVES project config and MCP
# Usage: kimi-pmoves [kimi-args...]
#
# Launches Kimi with PMOVES context files, MCP config (Cipher + Agent Zero),
# and skill merging from .kimi/, .claude/, .codex/ skill trees.
#
# Prerequisites:
#   - kimi CLI installed
#   - .kimi/config.toml exists (created by make -C pmoves env-setup)
#   - .kimi/mcp.json exists (created by PR #2112)

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
  pm_node_identity "$PROJECT_ROOT" kimi kimi-pmoves || true
  echo "${PM_IDENT_LINE}" >&2
  # CIPHER TOKEN BIND + TS_ RESOLUTION. .kimi/mcp.json addresses cipher as
  # ${TS_Z890} and authenticates with ${CIPHER_API_TOKEN}; this launcher loads
  # neither, so every reference went out literal and cipher never connected.
  # Bind the minted per-agent token for the declared agentId BEFORE the carry
  # measurement so the verdict reports the post-bind reality.
  TS_HELPER="$PROJECT_ROOT/pmoves/scripts/tailscale-node-ips.sh"
  if [ -f "$TS_HELPER" ]; then
    # shellcheck source=./tailscale-node-ips.sh
    . "$TS_HELPER"
  fi
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh" ]; then
    # shellcheck source=./pm-cipher-token-bind.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh"
    pm_cipher_token_bind "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-}" || true
    echo "[kimi-pmoves] ${PM_CARRY_BIND_LINE}" >&2
  fi
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh" ]; then
    # shellcheck source=./pm-cipher-identity.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh"
    pm_cipher_identity "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-${PMOVES_NODE_IDENTITY:-}}" ${PM_IDENT_PY[@]+"${PM_IDENT_PY[@]}"} || true
    echo "[kimi-pmoves] ${PM_CARRY_LINE}" >&2
  fi
fi

CONFIG="$PROJECT_ROOT/.kimi/config.toml"
MCP_CONFIG="$PROJECT_ROOT/.kimi/mcp.json"

if [ ! -f "$CONFIG" ]; then
  echo "[!] Kimi config not found: $CONFIG"
  echo "    Run 'make -C pmoves env-setup' to generate it."
  exit 1
fi

if [ -f "$MCP_CONFIG" ]; then
  exec kimi --config-file "$CONFIG" --mcp-config-file "$MCP_CONFIG" "$@"
else
  echo "[!] Warning: $MCP_CONFIG not found; launching Kimi without MCP config."
  echo "    Cipher and Agent Zero MCP servers will not be available."
  exec kimi --config-file "$CONFIG" "$@"
fi