#!/usr/bin/env python3
"""
PMOVES.AI Branch Cleanup Tool

Lists merged and stale remote branches, suggests cleanup actions.
Dry-run by default; pass --execute to actually delete/archive.

Usage:
    python branch_cleanup.py                # Dry-run audit
    python branch_cleanup.py --execute      # Actually clean up
    python branch_cleanup.py --ttl 30       # Override TTL (days)
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List


# Protected branches that are never deleted
PROTECTED = frozenset({
    "main",
    "PMOVES.AI-Edition-Hardened",
    "PMOVES.AI-Edition-Hardened-Integrations",
    "PMOVES.AI-Edition-Hardened-v3-clean",
})

# Default TTL for branch types (days)
TTL_MAP = {
    "feature": 14,
    "fix": 7,
    "codex": 14,
    "chore": 7,
    "docs": 7,
}
DEFAULT_TTL = 30  # branches not matching any prefix


@dataclass
class BranchInfo:
    name: str
    last_commit_date: datetime
    is_merged: bool
    age_days: int
    ttl_days: int
    action: str  # "delete", "archive", "keep", "protected"


def run(cmd: List[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return result.stdout.strip()


def get_remote_branches() -> List[str]:
    """Get all remote branches (excluding HEAD)."""
    raw = run(["git", "branch", "-r", "--format=%(refname:short)"])
    branches = []
    for line in raw.splitlines():
        name = line.strip()
        if not name or name.endswith("/HEAD"):
            continue
        # Strip origin/ prefix
        if name.startswith("origin/"):
            name = name[len("origin/"):]
        branches.append(name)
    return branches


def get_merged_branches(base: str = "main") -> set:
    """Get branches already merged into base."""
    raw = run(
        ["git", "branch", "-r", "--merged", f"origin/{base}", "--format=%(refname:short)"],
        check=False,
    )
    merged = set()
    for line in raw.splitlines():
        name = line.strip()
        if name.startswith("origin/"):
            name = name[len("origin/"):]
        if name:
            merged.add(name)
    return merged


def get_last_commit_date(branch: str) -> datetime:
    """Get the date of the last commit on a remote branch."""
    raw = run(
        ["git", "log", "-1", "--format=%aI", f"origin/{branch}"],
        check=False,
    )
    if raw:
        return datetime.fromisoformat(raw)
    return datetime.now(timezone.utc)


def get_ttl(branch_name: str) -> int:
    """Determine TTL for a branch based on its prefix."""
    for prefix, ttl in TTL_MAP.items():
        if branch_name.startswith(f"{prefix}/"):
            return ttl
    return DEFAULT_TTL


def audit_branches(ttl_override: int | None = None) -> List[BranchInfo]:
    """Audit all remote branches and determine actions."""
    now = datetime.now(timezone.utc)
    branches = get_remote_branches()
    merged = get_merged_branches("main")

    results = []
    for name in sorted(branches):
        if name in PROTECTED:
            results.append(BranchInfo(
                name=name,
                last_commit_date=now,
                is_merged=name in merged,
                age_days=0,
                ttl_days=0,
                action="protected",
            ))
            continue

        last_date = get_last_commit_date(name)
        age_days = (now - last_date).days
        ttl = ttl_override if ttl_override is not None else get_ttl(name)

        if name in merged:
            action = "delete"
        elif age_days > ttl:
            action = "archive"
        else:
            action = "keep"

        results.append(BranchInfo(
            name=name,
            last_commit_date=last_date,
            is_merged=name in merged,
            age_days=age_days,
            ttl_days=ttl,
            action=action,
        ))

    return results


def print_summary(results: List[BranchInfo]) -> None:
    """Print a summary table of branch audit results."""
    # Header
    print(f"\n{'Branch':<55} {'Age':>5} {'TTL':>5} {'Merged':>7} {'Action':>10}")
    print("-" * 90)

    counts = {"delete": 0, "archive": 0, "keep": 0, "protected": 0}

    for b in results:
        merged_str = "yes" if b.is_merged else "no"
        action_str = b.action.upper()
        if b.action == "protected":
            print(f"  {b.name:<53} {'':>5} {'':>5} {merged_str:>7} {action_str:>10}")
        else:
            print(f"  {b.name:<53} {b.age_days:>4}d {b.ttl_days:>4}d {merged_str:>7} {action_str:>10}")
        counts[b.action] += 1

    print("-" * 90)
    print(f"  Total: {len(results)} branches")
    print(f"  Protected: {counts['protected']} | Keep: {counts['keep']} | "
          f"Delete (merged): {counts['delete']} | Archive (stale): {counts['archive']}")


def execute_cleanup(results: List[BranchInfo]) -> None:
    """Execute branch cleanup actions."""
    for b in results:
        if b.action == "delete":
            print(f"  Deleting merged branch: {b.name}")
            run(["git", "push", "origin", "--delete", b.name], check=False)

        elif b.action == "archive":
            tag_name = f"archive/{b.name}"
            print(f"  Archiving stale branch: {b.name} -> tag {tag_name}")
            run(["git", "tag", tag_name, f"origin/{b.name}"], check=False)
            run(["git", "push", "origin", tag_name], check=False)
            run(["git", "push", "origin", "--delete", b.name], check=False)


def main():
    parser = argparse.ArgumentParser(description="PMOVES.AI Branch Cleanup Tool")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform cleanup (default: dry-run)",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=None,
        help="Override TTL in days for all branches",
    )
    args = parser.parse_args()

    # Fetch latest remote state
    print("Fetching remote branches...")
    run(["git", "fetch", "--prune", "origin"], check=False)

    results = audit_branches(ttl_override=args.ttl)
    print_summary(results)

    actionable = [b for b in results if b.action in ("delete", "archive")]

    if not actionable:
        print("\nNo branches need cleanup.")
        return

    if args.execute:
        print(f"\nExecuting cleanup on {len(actionable)} branches...")
        execute_cleanup(results)
        print("Cleanup complete.")
    else:
        print(f"\nDry-run: {len(actionable)} branches would be cleaned up.")
        print("Run with --execute to perform cleanup.")


if __name__ == "__main__":
    main()
