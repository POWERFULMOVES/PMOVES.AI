#!/usr/bin/env python3
"""Cross-platform validation for tiered env files."""

from __future__ import annotations

from pathlib import Path


TIERS = ("data", "supabase", "api", "llm", "worker", "media", "agent", "ui")


def main() -> int:
    print("Checking tier environment files...")
    missing_hard: list[str] = []

    for tier in TIERS:
        env_file = Path(f"env.tier-{tier}")
        example = Path(f"env.tier-{tier}.example")
        if env_file.exists():
            continue
        if example.exists():
            print(f"WARN: {env_file} missing (example exists)")
            print(f"   Copy from example: cp {example} {env_file}")
        else:
            print(f"ERROR: {env_file} missing (no example found)")
            missing_hard.append(str(env_file))

    if missing_hard:
        print("")
        print("Missing tier files will cause services to fail or use defaults.")
        print("Create missing files from their .example counterparts.")
        return 1

    print("OK: All tier env files exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
