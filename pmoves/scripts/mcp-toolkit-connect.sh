#!/usr/bin/env bash
# mcp-toolkit-connect.sh
#
# Connects the local Claude Code client to the canonical PMOVES Docker MCP
# Toolkit profile (default: pmoves_5090_web). Idempotent — safe to re-run.
#
# Per `pmoves/docs/operations/MCP_TOOLKIT.md` § 4. Run AFTER
# `make mcp-toolkit-bootstrap` confirms the profile is imported on this node.
#
# Produces .mcp.json at repo root with the MCP_DOCKER stdio entry pointing at
# `docker mcp gateway run --profile <profile>`. The file is ignored by git
# (per-node, host-specific env paths) — operator runs this script once per
# fresh-clone or once per node.
#
# Pre-flight check: profile must exist (`docker mcp profile ls | grep <profile>`).
# If absent, bootstrap first.
#
# Usage:
#   make -C pmoves mcp-toolkit-connect                 # default profile
#   make -C pmoves mcp-toolkit-connect PROFILE=other   # override
#   ./pmoves/scripts/mcp-toolkit-connect.sh            # direct invocation
#
# Exit codes:
#   0 — connected (or already connected)
#   1 — docker mcp CLI missing
#   2 — profile not imported (run mcp-toolkit-bootstrap first)
#   3 — connect command itself failed

set -euo pipefail

PROFILE="${PROFILE:-pmoves_5090_web}"

# 1. CLI present?
if ! command -v docker >/dev/null 2>&1 || ! docker mcp version >/dev/null 2>&1; then
  echo "[mcp-toolkit-connect] docker mcp CLI not available."
  echo "   Install Docker Desktop with MCP Toolkit enabled."
  exit 1
fi

# 2. Profile imported?
if ! docker mcp profile ls 2>/dev/null | awk 'NR>2 {print $1}' | grep -Fxq "$PROFILE"; then
  echo "[mcp-toolkit-connect] Profile '$PROFILE' not imported on this node."
  echo "   Run: make -C pmoves mcp-toolkit-bootstrap"
  exit 2
fi

# 3. Pre-connect backup (per § 4 of MCP_TOOLKIT.md)
if [ -f .claude/mcp.json ] && [ ! -f .claude/mcp.json.pre-toolkit-connect.bak ]; then
  cp .claude/mcp.json .claude/mcp.json.pre-toolkit-connect.bak
  echo "[mcp-toolkit-connect] Backed up .claude/mcp.json → .claude/mcp.json.pre-toolkit-connect.bak"
fi
if [ -f .mcp.json ] && [ ! -f .mcp.json.pre-toolkit-connect.bak ]; then
  cp .mcp.json .mcp.json.pre-toolkit-connect.bak
  echo "[mcp-toolkit-connect] Backed up .mcp.json → .mcp.json.pre-toolkit-connect.bak"
fi

# 4. Connect
echo "[mcp-toolkit-connect] Connecting claude-code to profile '$PROFILE'..."
if ! docker mcp client connect claude-code --profile "$PROFILE"; then
  echo "[mcp-toolkit-connect] connect command failed"
  exit 3
fi

# 5. Verify
if docker mcp client ls 2>/dev/null | grep -q "claude-code: connected"; then
  echo "[mcp-toolkit-connect] OK — claude-code now connected to '$PROFILE'."
  echo "   Restart Claude Code session to consume the new MCP_DOCKER gateway."
  echo "   Verify tool surface with: docker mcp tools ls"
else
  echo "[mcp-toolkit-connect] Connect reported success but ls shows not connected."
  echo "   Inspect: docker mcp client ls"
  exit 3
fi
