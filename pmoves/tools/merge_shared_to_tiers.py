#!/usr/bin/env python3
"""Merge env.shared values into tier env files.

Default mode rewrites each tier file (sorted, comments dropped) with every key it
already carries refreshed from env.shared when env.shared has a non-empty value.

--only mode is SURGICAL. Only the named keys change, only in tiers that already
carry them, in place (other lines, comments and order preserved). The env.shared
value is copied even when it is EMPTY, because naming the key is the request.
This is how `supabase-key-reconcile` repairs tier-only drift, such as
env.tier-supabase holding a JWT family the running stack does not use, or
env.tier-ui blanking SUPABASE_SERVICE_ROLE_KEY, which is last in the --env-file
chain and so wins interpolation.
Values are never printed; changes are reported as sha256[:4] classes.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_TIERS = [
    "env.tier-data",
    "env.tier-supabase",
    "env.tier-api",
    "env.tier-llm",
    "env.tier-worker",
    "env.tier-media",
    "env.tier-agent",
    "env.tier-ui",
]


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _mask(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:4] if value else "EMPTY"


def sync_keys(path: Path, wanted: dict[str, str]) -> list[tuple[str, str, str]]:
    """Set each wanted key that the file already carries. The first occurrence is
    replaced and later duplicates are dropped (last-wins parsers would otherwise
    read them). Returns (name, old, new) for every key whose effective value changed."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    effective: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            name, value = s.split("=", 1)
            effective[name.strip()] = value.strip()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        s = line.strip()
        name = s.split("=", 1)[0].strip() if s and not s.startswith("#") and "=" in s else None
        if name in wanted:
            if name in seen:
                continue
            seen.add(name)
            out.append(f"{name}={wanted[name]}")
            continue
        out.append(line)
    changes = [(n, effective[n], wanted[n]) for n in wanted if n in effective and effective[n] != wanted[n]]
    if changes or len(out) != len(lines):
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to pmoves/ directory",
    )
    parser.add_argument(
        "--tier",
        action="append",
        default=[],
        help="Tier env filename (repeatable). Defaults to all env.tier-* files.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Surgical mode: sync ONLY this key (repeatable); see module docstring.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    env_shared = root / "env.shared"
    if not env_shared.exists():
        raise FileNotFoundError(f"env.shared not found: {env_shared}")

    shared_values = parse_env(env_shared)
    print(f"Read {len(shared_values)} values from {env_shared}")

    tier_files = args.tier if args.tier else DEFAULT_TIERS
    if args.only:
        missing = [n for n in args.only if n not in shared_values]
        if missing:
            print(f"refusing: not in env.shared: {missing}")
            return 1
        for tier_file in tier_files:
            tier_path = root / tier_file
            if tier_path.exists():
                wanted = {n: shared_values[n] for n in args.only}
                for name, old, new in sync_keys(tier_path, wanted):
                    print(f"{tier_file}: {name} {_mask(old)} -> {_mask(new)}")
        return 0
    for tier_file in tier_files:
        tier_path = root / tier_file
        if not tier_path.exists():
            print(f"Skipping {tier_file} (not found)")
            continue

        lines = tier_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        updated: dict[str, str] = {}
        for line in lines:
            if line.startswith("#") or not line.strip() or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in shared_values and shared_values[key]:
                updated[key] = shared_values[key]
            else:
                updated[key] = value.strip()

        output = ["# Auto-generated by pmoves.tools.merge_shared_to_tiers. Do not edit."]
        for key in sorted(updated.keys()):
            output.append(f"{key}={updated[key]}")
        tier_path.write_text("\n".join(output) + "\n", encoding="utf-8")
        print(f"{tier_file}: {len(updated)} entries")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
