#!/usr/bin/env bash
# mcp-toolkit-connect.sh
#
# Connects the local Claude Code client to THIS NODE's Docker MCP Toolkit
# profile, resolved by pmoves/tools/node_gateway_profile.py. Idempotent — safe
# to re-run.
#
# The default used to be the literal `pmoves_5090_web`. That is one node's
# profile serving as every node's default, and it failed silently: measured on
# the 4090 on 2026-09-13, `docker mcp profile ls` lists BOTH pmoves_4090_web and
# pmoves_5090_web, so the pre-flight below passed and the node connected
# claude-code to the other node's server set. There is no fallback default now —
# an unresolvable node is an error the operator can fix (declare
# `docker_mcp.gateway_profile` in its pmoves/config/profiles/<id>.yaml, pin a
# profile, or pass PROFILE=), not a guess this script makes on their behalf.
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
#   make -C pmoves mcp-toolkit-connect                 # this node's profile
#   make -C pmoves mcp-toolkit-connect PROFILE=other   # override
#   ./pmoves/scripts/mcp-toolkit-connect.sh            # direct invocation
#
# Exit codes:
#   0 — connected (or already connected)
#   1 — docker mcp CLI missing
#   2 — profile not imported (run mcp-toolkit-bootstrap first)
#   3 — connect command itself failed
#   4 — this node's gateway profile could not be resolved

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 0. Which profile is THIS node's?
#
# Shared python discovery, not a bare `python3` — pm-python.sh is the repo's one
# convention for this and already handles the venv/py-launcher/Windows spread.
# The `yaml` probe is load-bearing, not decoration: the resolver reads node
# profile YAMLs through profile_loader, so an interpreter without PyYAML would
# be selected and then ImportError at the point of use. A per-user
# site-packages is on every interpreter on some of these nodes, which is exactly
# how a missing dep hides until the one machine that lacks it runs this.
if [ -z "${PROFILE:-}" ]; then
  # shellcheck source=pm-python.sh
  . "$REPO_ROOT/pmoves/scripts/pm-python.sh"
  if ! pm_pick_python yaml; then
    echo "[mcp-toolkit-connect] no python with PyYAML to resolve this node's profile." >&2
    echo "   Pass it explicitly: make -C pmoves mcp-toolkit-connect PROFILE=<name>" >&2
    exit 4
  fi
  if ! PROFILE="$("${PM_PY[@]}" "$REPO_ROOT/pmoves/tools/node_gateway_profile.py")"; then
    # The resolver already printed WHY on stderr. Do not restate it as a guess.
    echo "[mcp-toolkit-connect] cannot determine this node's gateway profile." >&2
    echo "   Fix one of: declare docker_mcp.gateway_profile in this node's" >&2
    echo "   pmoves/config/profiles/<id>.yaml, run \`pmoves mini profile use <id>\`," >&2
    echo "   or pass PROFILE=<name>." >&2
    exit 4
  fi
  echo "[mcp-toolkit-connect] Resolved this node's profile: $PROFILE"
fi

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
