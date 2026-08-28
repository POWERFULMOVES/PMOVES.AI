"""Update OpenCode node configs with canonical PMOVES MCP servers.

Preserves non-PMOVES MCP servers (e.g., zai-vision, docker) and replaces or adds
the canonical PMOVES entries from pmoves/config/mcp_inventory.json.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAWS_DIR = REPO_ROOT / "pmoves" / "configs" / "claws"
INVENTORY_PATH = REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json"

# Keys that the PMOVES inventory owns. These are replaced; others are preserved.
PMOVES_MCP_KEYS = {
    "pmoves-cipher",
    "pmoves-cipher-local",
    "agent-zero",
    "pmoves-nats-fleet",
    "pmoves-supabase",
    "supabase-db",
    "huggingface",
    "tailscale",
    "pmoves-docker-gateway",
    "pmoves-docker-gateway-sse",
}


def load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def canonical_opencode_mcp_servers() -> dict:
    """Return the canonical PMOVES mcpServers block for OpenCode/scope format."""
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
    from mcp_config_generator import generate_for_client

    rendered = generate_for_client("opencode", inventory=load_inventory(), context={})
    return rendered["mcpServers"]


def update_config(path: Path, canonical: dict) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = data.get("mcpServers", {})

    # Preserve non-PMOVES servers, replace/add PMOVES ones.
    preserved = {k: v for k, v in existing.items() if k not in PMOVES_MCP_KEYS}
    merged = {**preserved, **canonical}

    if existing == merged:
        return False

    backup = Path(str(path) + ".pre-mcp-bootstrap.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    data["mcpServers"] = merged
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    canonical = canonical_opencode_mcp_servers()
    updated = 0
    skipped = 0

    for path in sorted(CLAWS_DIR.glob("opencode-*.json")):
        changed = update_config(path, canonical)
        if changed:
            print(f"UPDATED {path.relative_to(REPO_ROOT)}")
            updated += 1
        else:
            print(f"SKIPPED {path.relative_to(REPO_ROOT)} (already canonical)")
            skipped += 1
    print(f"Done: {updated} updated, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
