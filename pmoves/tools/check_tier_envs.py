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
    # Drift ON by default. It shipped opt-in, the Makefile target passed no
    # flags, and so the check that catches "declared in .example, absent from the
    # runtime tier" never ran in the pipeline. That is how Z_AI_API_KEY reached
    # env.tier-llm.example, two hardcoded TIER_MAPPINGs, and the funnel -- while
    # being absent from the runtime tier on every node that reads it. SPARK hit
    # the same shape with Hermes.
    parser.add_argument(
        "--drift",
        action="store_true",
        default=True,
        help="Check key drift between .example and runtime files (default: on)",
    )
    parser.add_argument(
        "--no-drift",
        dest="drift",
        action="store_false",
        help="Skip the drift check (existence only).",
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
    drift_found = False

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
            drift_found = True
            if args.strict:
                rc = 1

    if rc == 0:
        if args.drift and drift_found:
            # Previously this branch printed "no drift detected" unconditionally,
            # immediately after listing the drift. A summary that contradicts the
            # output above it is worse than no summary: the reader believes the
            # last line.
            print(
                "DRIFT PRESENT (not failing: pass --strict to make this an error). "
                "Keys above are declared in .example but absent from the runtime "
                "tier, so every consumer reading that tier gets nothing."
            )
        elif args.drift:
            print("OK: All tier env files exist, no drift detected.")
        else:
            print("OK: All tier env files exist.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
