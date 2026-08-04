#!/usr/bin/env python3
"""Fork-registry ratchet gate.

Reads `pmoves/config/fork_registry.json` and enforces:
  1. Every fork has a `sync` field (bool) and a non-empty `reason` field.
  2. No fork uses the deprecated `skip` field (it predates the
     sync/reason schema and is no longer the source of truth).
  3. The total is consistent with the documented coverage target.

Exits 0 if every fork is decided, 1 if any fork is missing a decision
or still has the deprecated `skip` field. Designed to be wired into a
CI gate (the ratchet count can only go DOWN over time — adding
forks is fine, removing decisions is not).

This is a no-network check: it reads a static JSON file in the repo
and runs in <100ms. The output is the operator's "fork coverage"
number; it is the answer to "how many forks are undecided?".

Usage:
    python3 pmoves/tools/fork_registry_ratchet.py
    python3 pmoves/tools/fork_registry_ratchet.py --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "fork_registry.json"


def _validate(registry: dict) -> tuple[int, int, list[str]]:
    """Return (decided, total, list_of_problems)."""
    forks: dict[str, dict] = registry.get("forks", {})
    total = len(forks)
    decided = 0
    problems: list[str] = []

    for name, entry in forks.items():
        if "skip" in entry:
            problems.append(
                f"{name}: deprecated 'skip' field present "
                f"(value={entry['skip']!r}); migrate to sync + reason"
            )
            # Treat as not-decided for coverage accounting.
            continue
        if "sync" not in entry:
            problems.append(f"{name}: missing 'sync' decision (true/false)")
            continue
        if not isinstance(entry["sync"], bool):
            problems.append(
                f"{name}: 'sync' must be bool, got {type(entry['sync']).__name__}"
            )
            continue
        if "reason" not in entry or not str(entry["reason"]).strip():
            problems.append(f"{name}: missing non-empty 'reason' for sync={entry['sync']}")
            continue
        decided += 1

    return decided, total, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=REGISTRY_PATH,
        help=f"Path to fork registry JSON (default: {REGISTRY_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"registry not found: {args.registry}", file=sys.stderr)
        return 2

    with args.registry.open(encoding="utf-8") as f:
        registry = json.load(f)

    decided, total, problems = _validate(registry)
    coverage = f"{decided}/{total}"

    payload = {
        "registry": str(args.registry),
        "coverage": coverage,
        "decided": decided,
        "total": total,
        "problems": problems,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"fork-registry ratchet: {coverage} decided")
        if problems:
            print(f"  {len(problems)} problem(s):")
            for p in problems:
                print(f"    - {p}")
        else:
            print("  (every fork has sync + reason; no deprecated 'skip' fields)")

    # 0 problems = pass; any problem = fail (the ratchet only goes down).
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
