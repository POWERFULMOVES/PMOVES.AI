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