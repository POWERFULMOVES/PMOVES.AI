#!/usr/bin/env python3
"""Sanitize env.shared using allowlist from env.shared.example + registry.json.

Only keeps variables whose keys appear in the canonical template or registry.
Everything else (leaked Windows env, stale vars) gets dropped.

Usage:
    python3 pmoves/tools/sanitize_env_shared.py [--dry-run]
"""
import json
import sys
from pathlib import Path

PMOVES_ROOT = Path(__file__).resolve().parents[1]


def build_allowlist() -> set:
    """Build canonical variable allowlist from template + registry."""
    allowed = set()

    # 1. Keys from env.shared.example (the committed template)
    template = PMOVES_ROOT / "env.shared.example"
    if template.exists():
        for line in template.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key:
                    allowed.add(key)

    # 2. Keys from bootstrap/registry.json (all service variables)
    registry = PMOVES_ROOT / "bootstrap" / "registry.json"
    if registry.exists():
        data = json.loads(registry.read_text(encoding="utf-8"))
        for service in data.get("services", []):
            for var in service.get("variables", []):
                key = var.get("key", "")
                if key:
                    allowed.add(key)

    # 3. Keys from all env.tier-* files (tier-specific vars)
    for tier_file in PMOVES_ROOT.glob("env.tier-*"):
        if tier_file.name.endswith(".example"):
            continue
        for line in tier_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key:
                    allowed.add(key)

    # 4. Always allow these infrastructure vars
    allowed.update({
        "SSL_CERT_FILE", "SSL_CERT_DIR",
        "DOCKED_MODE", "TOPOLOGY_MODE", "PARENT_SYSTEM", "PARENT_VERSION",
    })

    return allowed


def sanitize(env_path: Path, dry_run: bool = False) -> dict:
    """Keep only allowlisted keys, comments, and blank lines."""
    if not env_path.exists():
        print(f"env.shared not found at {env_path}")
        return {"error": "not found"}

    allowed = build_allowlist()
    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()

    kept = []
    removed = []

    for line in lines:
        stripped = line.strip()
        # Keep blank lines, comments, and managed-by headers
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        # Check key against allowlist
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in allowed:
                kept.append(line)
                continue
        # Not in allowlist — remove
        removed.append(stripped)

    if dry_run:
        print(f"Allowlist: {len(allowed)} canonical keys")
        print(f"Would keep {len(kept)} lines, remove {len(removed)} lines")
        for r in removed[:15]:
            print(f"  - {r[:80]}")
        if len(removed) > 15:
            print(f"  ... and {len(removed) - 15} more")
        return {"removed": len(removed), "kept": len(kept)}

    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"Sanitized: kept {len(kept)} lines, removed {len(removed)} non-allowlisted vars")
    if removed:
        print(f"Removed (first 10):")
        for r in removed[:10]:
            print(f"  - {r[:80]}")
        if len(removed) > 10:
            print(f"  ... and {len(removed) - 10} more")

    return {"removed": len(removed), "kept": len(kept)}


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    env_path = PMOVES_ROOT / "env.shared"
    sanitize(env_path, dry_run=dry_run)
