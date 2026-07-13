#!/usr/bin/env bash
# kilo-pmoves — Bootstrap KiloCode/OpenCode with PMOVES config
# Usage: kilo-pmoves [node-name] [opencode-args...]
# Default: uses node-specific config from pmoves/configs/claws/

NODE="${1:-5090}"
shift 2>/dev/null || true

CONFIG="pmoves/configs/claws/opencode-${NODE}.json"
if [ ! -f "$CONFIG" ]; then
    echo "[!] Config not found: $CONFIG"
    echo "    Available: $(ls pmoves/configs/claws/opencode-*.json 2>/dev/null | xargs -n1 basename)"
    exit 1
fi

exec opencode --config "$CONFIG" "$@"
