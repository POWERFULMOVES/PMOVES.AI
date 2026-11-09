"""Verify kilo.json MCP keys match the canonical PMOVES inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    inventory_path = repo_root / "pmoves" / "config" / "mcp_inventory.json"
    kilo_path = repo_root / "kilo.json"

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    kilo = json.loads(kilo_path.read_text(encoding="utf-8"))
    kilo_keys = set(kilo.get("mcp", {}).keys())

    expected: set[str] = set()
    for group in inventory.get("groups", {}).values():
        for srv in group.get("servers", []):
            clients = srv.get("clients")
            if clients is None or "kilocode" in clients:
                expected.add(srv["key"])

    missing = sorted(expected - kilo_keys)
    for key in missing:
        print(f"  ❌ kilo.json missing MCP: {key}", file=sys.stderr)
    if not missing:
        print("  ✅ kilo.json contains all canonical MCP servers", file=sys.stderr)
    return len(missing)


if __name__ == "__main__":
    sys.exit(main())
