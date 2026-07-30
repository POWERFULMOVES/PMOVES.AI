#!/usr/bin/env python3
"""Cross-platform validation for tiered env files.

Checks:
1. All expected tier files exist (or have .example counterparts).
2. DRIFT detection: keys in .example but missing from runtime tier files.
   This catches the exact class of bug where secrets_sync.py generates a tier
   file but omits keys that the .example says should be present.
"""

from __future__ import annotations

import argparse
from pathlib import Path


TIERS = ("data", "supabase", "api", "llm", "worker", "media", "agent", "ui")


def parse_env_keys(path: Path) -> set[str]:
    """Extract variable names from a dotenv-style file."""
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def check_existence() -> list[str]:
    """Check that all tier env files exist. Return list of hard-missing tiers."""
    missing_hard: list[str] = []
    for tier in TIERS:
        env_file = Path(f"env.tier-{tier}")
        example = Path(f"env.tier-{tier}.example")
        if env_file.exists():
            continue
        if example.exists():
            print(f"WARN: {env_file} missing (example exists)")
            print("   Fix: run 'make bootstrap-tier-envs' or 'make secrets-funnel'")
        else:
            print(f"ERROR: {env_file} missing (no example found)")
            missing_hard.append(str(env_file))
    return missing_hard


def check_drift() -> list[str]:
    """Compare .example keys against runtime tier files. Return drift warnings."""
    drift: list[str] = []
    for tier in TIERS:
        env_file = Path(f"env.tier-{tier}")
        example = Path(f"env.tier-{tier}.example")
        if not example.exists() or not env_file.exists():
            continue

        example_keys = parse_env_keys(example)
        runtime_keys = parse_env_keys(env_file)
        missing = sorted(example_keys - runtime_keys)
        if missing:
            drift.append(f"DRIFT env.tier-{tier}: {len(missing)} keys in .example but not in runtime")
            for key in missing:
                drift.append(f"  - {key}")
            drift.append("  Fix: run 'make secrets-funnel' to regenerate from CHIT source,")
            drift.append("       or add missing keys to secrets_manifest_v2.yaml")
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate tiered env files.")
    parser.add_argument(
        "--drift",
        action="store_true",
        default=False,
        help="Also check for key drift between .example and runtime files",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat drift warnings as errors (non-zero exit)",
    )
    args = parser.parse_args(argv)

    print("Checking tier environment files...")
    rc = 0

    # 1. Existence check
    missing_hard = check_existence()
    if missing_hard:
        print("")
        print("Missing tier files will cause services to fail or use defaults.")
        print("Fix: run 'make bootstrap-tier-envs' then 'make secrets-funnel'")
        rc = 1

    # 2. Drift check (always run if --drift or --strict)
    if args.drift or args.strict:
        drift = check_drift()
        if drift:
            print("")
            for line in drift:
                print(line)
            if args.strict:
                rc = 1

    if rc == 0:
        if args.drift:
            print("OK: All tier env files exist, no drift detected.")
        else:
            print("OK: All tier env files exist.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
