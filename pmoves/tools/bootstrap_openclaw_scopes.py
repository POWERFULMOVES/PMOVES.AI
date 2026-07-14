"""Update OpenClaw scope configs with canonical PMOVES MCP servers.

Scope configs live in pmoves/configs/claws/scopes/*.json. Each scope is assigned a
tier (full or edge) and an endpoint mode (fleet or local). The script generates a
canonical PMOVES mcp_servers block from pmoves/config/mcp_inventory.json, filters
it by tier, and merges it non-destructively with the existing scope file so that
scope-specific non-PMOVES MCPs (e.g., gpu-mesh, docker, zai-*) are preserved.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPES_DIR = REPO_ROOT / "pmoves" / "configs" / "claws" / "scopes"
INVENTORY_PATH = REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json"

# Canonical PMOVES MCP keys. These are replaced/added; everything else is preserved.
PMOVES_MCP_KEYS: Set[str] = {
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

# Per-scope policy: (tier, endpoint_mode)
SCOPE_CONFIG: Dict[str, Tuple[str, str]] = {
    "4090": ("full", "fleet"),
    "5090": ("full", "fleet"),
    "z890": ("full", "local"),
    "kvm4-1": ("full", "fleet"),
    "kvm4-2": ("full", "fleet"),
    "nemotron-claw": ("full", "fleet"),
    "nemoclaw": ("edge", "fleet"),
    "kvm2": ("full", "fleet"),
}

# MCP keys included per tier.
TIER_KEYS: Dict[str, Set[str]] = {
    "full": {
        "pmoves-cipher",
        "agent-zero",
        "pmoves-nats-fleet",
        "pmoves-supabase",
        "supabase-db",
        "huggingface",
        "tailscale",
        "pmoves-docker-gateway",
    },
    "edge": {
        "pmoves-cipher",
        "agent-zero",
        "tailscale",
    },
}


def load_inventory() -> Dict[str, Any]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def canonical_scope_mcp_servers(tier: str, endpoint: str) -> Dict[str, Any]:
    """Return the canonical PMOVES mcp_servers block for an OpenClaw scope."""
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
    from mcp_config_generator import generate_for_client

    rendered = generate_for_client(
        "opencode",
        inventory=load_inventory(),
        endpoint=endpoint,
        context={},
    )
    allowed = TIER_KEYS.get(tier, TIER_KEYS["edge"])
    return {k: v for k, v in rendered["mcpServers"].items() if k in allowed}


def update_scope(path: Path, dry_run: bool = False) -> Tuple[bool, list[str]]:
    """Update a single scope file. Returns (changed, list of messages)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    node = data.get("identity", {}).get("node")
    if node is None:
        return False, [f"SKIP {path.name}: missing identity.node"]

    tier, endpoint = SCOPE_CONFIG.get(node, ("edge", "fleet"))
    canonical = canonical_scope_mcp_servers(tier, endpoint)

    existing = data.get("mcp_servers", {})

    # Preserve non-PMOVES servers, replace/add PMOVES ones.
    preserved = {k: v for k, v in existing.items() if k not in PMOVES_MCP_KEYS}
    merged = {**preserved, **canonical}

    missing = sorted(set(canonical.keys()) - set(merged.keys()))
    if missing:
        # Should not happen because canonical keys are disjoint from preserved keys,
        # but guard against scope-specific keys accidentally shadowing PMOVES keys.
        return False, [f"SKIP {path.name}: key collision for {missing}"]

    if existing == merged:
        return False, [f"SKIP {path.name} (already canonical)"]

    if dry_run:
        return True, [f"DRY-RUN {path.name}: would update ({len(merged)} servers)"]

    backup = Path(str(path) + ".pre-mcp-bootstrap.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    data["mcp_servers"] = merged
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True, [f"UPDATED {path.name} (tier={tier}, endpoint={endpoint})"]


def check_scopes() -> int:
    """Validate that every scope matches its tier/endpoint expectation."""
    errors: list[str] = []
    ok = 0

    for path in sorted(SCOPES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        node = data.get("identity", {}).get("node")
        if node is None:
            errors.append(f"{path.name}: missing identity.node")
            continue

        tier, endpoint = SCOPE_CONFIG.get(node, ("edge", "fleet"))
        expected_keys = set(TIER_KEYS.get(tier, TIER_KEYS["edge"]))
        actual_keys = set(data.get("mcp_servers", {}).keys())

        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(
            k for k in (actual_keys - expected_keys) if k in PMOVES_MCP_KEYS
        )

        if missing or unexpected:
            errors.append(
                f"{path.name} (tier={tier}): missing={missing}, unexpected_pmoves={unexpected}"
            )
        else:
            ok += 1

    if errors:
        print("OpenClaw scope MCP check FAILED", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        print(f"  {ok} scopes OK", file=sys.stderr)
        return 1

    print(f"OpenClaw scope MCP check OK: {ok} scopes canonical")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update OpenClaw scope configs with canonical PMOVES MCP servers."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate scopes without modifying files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing files.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_scopes()

    updated = 0
    skipped = 0
    for path in sorted(SCOPES_DIR.glob("*.json")):
        changed, messages = update_scope(path, dry_run=args.dry_run)
        for msg in messages:
            print(msg)
        if changed:
            updated += 1
        else:
            skipped += 1
    print(f"Done: {updated} updated, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
