#!/usr/bin/env bash
# Bootstrap Hermes Agent and Crush CLI MCP configurations from the canonical
# PMOVES inventory. Idempotent — safe to re-run.
#
# Usage:
#   bash pmoves/scripts/bootstrap-hermes-crush.sh
#   make -C pmoves hermes-crush-bootstrap
#
# Environment:
#   PMOVES_HERMES_PROFILE   Hermes profile name (default: pmoves-hermes)
#   PMOVES_CRUSH_CONFIG     Crush config path (default: ~/.config/crush/crush.json)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HERMES_PROFILE="${PMOVES_HERMES_PROFILE:-pmoves-hermes}"
CRUSH_CONFIG="${PMOVES_CRUSH_CONFIG:-${HOME}/.config/crush/crush.json}"
HERMES_CONFIG="${HOME}/.hermes/profiles/${HERMES_PROFILE}/config.yaml"

info() { printf '\033[1;34m[hermes-crush-bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hermes-crush-bootstrap] WARN:\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[hermes-crush-bootstrap] FAIL:\033[0m %s\n' "$*" >&2; exit 1; }

info "Bootstrapping Hermes (${HERMES_PROFILE}) and Crush MCP configs"

# Ensure Python tooling is available.
if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 not found on PATH"
fi

# Set PYTHONPATH so 'python3 -m pmoves.tools.*' resolves from the repo root
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

# ── Crush ────────────────────────────────────────────────────────────────────

info "Updating Crush config: ${CRUSH_CONFIG}"
python3 -m pmoves.tools.mcp_config_generator --client crush --output "${CRUSH_CONFIG}" || fail "Crush config update failed"

# ── Hermes ───────────────────────────────────────────────────────────────────

info "Updating Hermes config: ${HERMES_CONFIG}"

python3 - <<PY
import json
import os
import shutil
import sys
from pathlib import Path

hermes_path = Path(os.path.expanduser("${HERMES_CONFIG}"))
inventory_path = Path("${REPO_ROOT}") / "pmoves" / "config" / "mcp_inventory.json"

try:
    import yaml
except Exception as exc:
    print(f"FAIL PyYAML not available; cannot merge Hermes YAML: {exc}", file=sys.stderr)
    sys.exit(1)

# Import generator to reuse rendering logic.
sys.path.insert(0, str(Path("${REPO_ROOT}") / "pmoves" / "tools"))
from mcp_config_generator import generate_for_client, load_inventory

inventory = load_inventory(inventory_path)
rendered = generate_for_client("hermes", inventory=inventory, context={})
mcp_servers = rendered.get("mcp_servers", {})

hermes_path.parent.mkdir(parents=True, exist_ok=True)
backup = Path(str(hermes_path) + ".pre-mcp-bootstrap.bak")
if hermes_path.exists() and not backup.exists():
    shutil.copy2(hermes_path, backup)

if hermes_path.exists():
    with hermes_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
else:
    config = {}

config["mcp_servers"] = {**(config.get("mcp_servers") or {}), **mcp_servers}

with hermes_path.open("w", encoding="utf-8") as fh:
    yaml.safe_dump(config, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

print(f"OK Updated Hermes config: {hermes_path}")
PY

info "Hermes + Crush MCP bootstrap complete"
