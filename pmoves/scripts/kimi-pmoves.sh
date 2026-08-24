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