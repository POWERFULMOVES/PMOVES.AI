#!/usr/bin/env bash
# kilo-pmoves — Bootstrap KiloCode/OpenCode with PMOVES per-node config
# Usage: kilo-pmoves [node-name] [opencode-args...]
# Default node: 5090 (GPU inference workhorse)
# Other nodes: 4090, kvm4-1, kvm4-2, nemotron-claw, nemoclaw
#
# Examples:
#   kilo-pmoves                    # 5090 node (default)
#   kilo-pmoves 4090               # 4090 laptop node
#   kilo-pmoves kvm4-1             # KVM4-1 VPS gateway node

NODE="${1:-5090}"
shift 2>/dev/null || true

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
  pm_node_identity "$PROJECT_ROOT" kilo kilo-pmoves || true
  echo "${PM_IDENT_LINE}" >&2
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh" ]; then
    # shellcheck source=./pm-cipher-identity.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh"
    pm_cipher_identity "$PROJECT_ROOT" "${PMOVES_NODE_IDENTITY:-}" ${PM_IDENT_PY[@]+"${PM_IDENT_PY[@]}"} || true
    echo "[kilo-pmoves] ${PM_CARRY_LINE}" >&2
  fi
fi

CONFIG="$PROJECT_ROOT/pmoves/configs/claws/opencode-${NODE}.json"

if [ ! -f "$CONFIG" ]; then
  echo "[!] Config not found: $CONFIG"
  echo "    Available nodes:"
  ls "$PROJECT_ROOT/pmoves/configs/claws/opencode-"*.json 2>/dev/null | \
    xargs -n1 basename | sed 's/opencode-//; s/.json//' | \
    awk '{print "      - "$0}'
  exit 1
fi

exec opencode --config "$CONFIG" "$@"