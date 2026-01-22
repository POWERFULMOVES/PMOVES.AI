#!/usr/bin/env python3
"""Worktree Tracker - Categorize and track PMOVES git worktrees.

Analyzes all worktrees for:
- Active PR branches
- Tier branches (pr-tiers/*)
- TAC review branches (tac-*)
- Feature branches (pr12-*, pr13-*, etc.)
- Cleanup candidates

Usage:
    python3 tools/worktree_tracker.py              # All worktrees
    python3 tools/worktree_tracker.py --category pr  # PR branches only
    python3 tools/worktree_tracker.py --cleanup    # Show cleanup candidates
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class WorktreeCategory(Enum):
    """Worktree category types."""
    ACTIVE_PR = "active_pr"
    TIER_BRANCH = "tier_branch"
    TAC_REVIEW = "tac_review"
    FEATURE_BRANCH = "feature_branch"
    RESTORE = "restore"
    CLEANUP_CANDIDATE = "cleanup_candidate"
    MAIN = "main"
    OTHER = "other"


@dataclass
class WorktreeInfo:
    """Information about a worktree."""

    path: str
    commit: str
    branch: str
    category: WorktreeCategory = WorktreeCategory.OTHER
    is_detached: bool = False
    is_bare: bool = False
    has_uncommitted: bool = False
    pr_number: int | None = None
    pr_url: str = ""

    @classmethod
    def from_git_line(cls, line: str) -> "WorktreeInfo":
        """Parse worktree list output line.

        Format: <path> <commit> [<branch>]
        """
        parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"Invalid worktree line: {line}")

        path = parts[0]
        commit = parts[1]
        branch = parts[2].strip("[]") if len(parts) > 2 else "HEAD"

        # Detect detached HEAD
        is_detached = branch == "HEAD" or "(detached" in branch
        if is_detached:
            branch = "HEAD"

        # Determine category
        category = categorize_worktree(path, branch)

        # Extract PR number if available
        pr_number = extract_pr_number(path, branch)

        worktree = cls(
            path=path,
            commit=commit,
            branch=branch,
            category=category,
            is_detached=is_detached,
            pr_number=pr_number,
        )

        if pr_number:
            worktree.pr_url = f"https://github.com/POWERFULMOVES/PMOVES.AI/pull/{pr_number}"

        return worktree


def extract_pr_number(path: str, branch: str) -> int | None:
    """Extract PR number from path or branch name."""
    # Check for PR number in common patterns
    patterns = [
        r"pr[-_]?(\d+)",  # pr-123, pr_123, pr123
        r"#(\d+)",         # #123
        r"fix[-_]pr(\d+)", # fix-pr123, fix_pr123
    ]

    for pattern in patterns:
        # Check path
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Check branch
        match = re.search(pattern, branch, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def categorize_worktree(path: str, branch: str) -> WorktreeCategory:
    """Categorize a worktree based on path and branch."""
    path_lower = path.lower()
    branch_lower = branch.lower()

    # Main repo
    if path == "/home/pmoves/PMOVES.AI" and branch in ("main", "master"):
        return WorktreeCategory.MAIN

    # Cleanup candidates (/tmp, stale)
    if path.startswith("/tmp/") or "prunable" in path_lower:
        return WorktreeCategory.CLEANUP_CANDIDATE

    # Restore branches
    if "restore" in path_lower or "restore" in branch_lower:
        return WorktreeCategory.RESTORE

    # TAC review branches
    if path_lower.startswith("/home/pmoves/tac-") or "tac-" in path_lower:
        return WorktreeCategory.TAC_REVIEW

    # Tier branches
    if "pr-tiers" in path_lower or "tier-" in branch_lower:
        return WorktreeCategory.TIER_BRANCH

    # Feature branches (pr12-*, pr13-*, etc.)
    if re.search(r"pr\d+-", path_lower):
        return WorktreeCategory.FEATURE_BRANCH

    # Active PR branches
    if extract_pr_number(path, branch):
        return WorktreeCategory.ACTIVE_PR

    # GPU-related
    if "gpu" in path_lower:
        return WorktreeCategory.FEATURE_BRANCH

    return WorktreeCategory.OTHER


def get_worktrees(repo_root: str = "/home/pmoves/PMOVES.AI") -> list[WorktreeInfo]:
    """Get all worktrees for the repository."""
    result = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        print(f"Failed to get worktrees: {result.stderr}", file=sys.stderr)
        return []

    worktrees = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            worktrees.append(WorktreeInfo.from_git_line(line))
        except ValueError:
            continue

    return worktrees


def check_uncommitted_changes(worktree: WorktreeInfo) -> bool:
    """Check if worktree has uncommitted changes."""
    if worktree.is_detached or worktree.branch == "HEAD":
        return False

    # Check if path exists
    if not Path(worktree.path).exists():
        return False

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree.path,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )

    return bool(result.stdout.strip())


def format_markdown(worktrees: list[WorktreeInfo]) -> str:
    """Format worktree report as Markdown."""
    # Group by category
    categorized: dict[WorktreeCategory, list[WorktreeInfo]] = {c: [] for c in WorktreeCategory}
    for wt in worktrees:
        categorized[wt.category].append(wt)

    lines = [
        "# Worktree Status Report",
        "",
        "## Summary",
        "",
        f"| Category | Count |",
        f"|----------|-------|",
    ]

    for category in [
        WorktreeCategory.ACTIVE_PR,
        WorktreeCategory.TIER_BRANCH,
        WorktreeCategory.TAC_REVIEW,
        WorktreeCategory.FEATURE_BRANCH,
        WorktreeCategory.RESTORE,
        WorktreeCategory.CLEANUP_CANDIDATE,
        WorktreeCategory.OTHER,
    ]:
        count = len(categorized[category])
        if count > 0:
            lines.append(f"| {category.value} | {count} |")

    lines.extend(["", "## Details", ""])

    # Active PRs
    if categorized[WorktreeCategory.ACTIVE_PR]:
        lines.extend([
            "### Active PR Worktrees",
            "",
            "| Path | Branch | PR |",
            "|------|--------|----|",
        ])
        for wt in categorized[WorktreeCategory.ACTIVE_PR]:
            pr_link = f"[#{wt.pr_number}]({wt.pr_url})" if wt.pr_url else "-"
            lines.append(f"| `{wt.path}` | `{wt.branch}` | {pr_link} |")
        lines.append("")

    # Tier branches
    if categorized[WorktreeCategory.TIER_BRANCH]:
        lines.extend([
            "### Tier Branches",
            "",
            "These are tier-specific refactoring branches ready for PR creation:",
            "",
        ])
        for wt in categorized[WorktreeCategory.TIER_BRANCH]:
            lines.append(f"- `{wt.path}` → `{wt.branch}`")
        lines.append("")

    # TAC reviews
    if categorized[WorktreeCategory.TAC_REVIEW]:
        lines.extend([
            "### TAC Review Branches",
            "",
            "Technical Review Committee review worktrees:",
            "",
        ])
        for wt in categorized[WorktreeCategory.TAC_REVIEW]:
            status = " [detached]" if wt.is_detached else ""
            lines.append(f"- `{wt.path}` → `{wt.branch}`{status}")
        lines.append("")

    # Feature branches
    if categorized[WorktreeCategory.FEATURE_BRANCH]:
        lines.extend([
            "### Feature Branches",
            "",
        ])
        for wt in categorized[WorktreeCategory.FEATURE_BRANCH]:
            status = " [detached]" if wt.is_detached else ""
            lines.append(f"- `{wt.path}` → `{wt.branch}`{status}")
        lines.append("")

    # Cleanup candidates
    if categorized[WorktreeCategory.CLEANUP_CANDIDATE]:
        lines.extend([
            "### 🔴 Cleanup Candidates",
            "",
            "These worktrees can be safely removed:",
            "",
        ])
        for wt in categorized[WorktreeCategory.CLEANUP_CANDIDATE]:
            lines.append(f"- `{wt.path}` → `{wt.branch}`")
        lines.extend([
            "",
            "**Remove command:**",
            "```bash",
        ])
        for wt in categorized[WorktreeCategory.CLEANUP_CANDIDATE]:
            lines.append(f"git worktree remove {wt.path}")
        lines.extend(["```", ""])

    return "\n".join(lines)


def format_table(worktrees: list[WorktreeInfo]) -> str:
    """Format worktree report as table."""
    lines = ["Worktree Status", "=" * 80]

    # Group by category
    categorized: dict[WorktreeCategory, list[WorktreeInfo]] = {c: [] for c in WorktreeCategory}
    for wt in worktrees:
        categorized[wt.category].append(wt)

    # Summary
    lines.append("\nSummary:")
    for category in [WorktreeCategory.ACTIVE_PR, WorktreeCategory.TIER_BRANCH, WorktreeCategory.TAC_REVIEW]:
        count = len(categorized[category])
        if count > 0:
            lines.append(f"  {category.value}: {count}")

    # Active PRs
    if categorized[WorktreeCategory.ACTIVE_PR]:
        lines.extend([
            "\nActive PR Worktrees:",
        ])
        for wt in categorized[WorktreeCategory.ACTIVE_PR]:
            pr_info = f" (PR #{wt.pr_number})" if wt.pr_number else ""
            lines.append(f"  {wt.path} → {wt.branch}{pr_info}")

    # Tier branches
    if categorized[WorktreeCategory.TIER_BRANCH]:
        lines.extend([
            "\nTier Branches (ready for PR):",
        ])
        for wt in categorized[WorktreeCategory.TIER_BRANCH]:
            lines.append(f"  {wt.path} → {wt.branch}")

    # TAC reviews
    if categorized[WorktreeCategory.TAC_REVIEW]:
        lines.extend([
            "\nTAC Review Worktrees:",
        ])
        for wt in categorized[WorktreeCategory.TAC_REVIEW]:
            detached = " [detached]" if wt.is_detached else ""
            lines.append(f"  {wt.path} → {wt.branch}{detached}")

    # Cleanup candidates
    if categorized[WorktreeCategory.CLEANUP_CANDIDATE]:
        lines.extend([
            "\nCleanup Candidates (safe to remove):",
        ])
        for wt in categorized[WorktreeCategory.CLEANUP_CANDIDATE]:
            lines.append(f"  {wt.path} → {wt.branch}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Track and categorize PMOVES worktrees"
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in WorktreeCategory],
        help="Filter by category"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Show cleanup candidates only"
    )
    parser.add_argument(
        "--format", choices=["table", "markdown", "json"], default="table"
    )
    parser.add_argument(
        "--repo-root", default="/home/pmoves/PMOVES.AI", help="Path to repo root"
    )

    args = parser.parse_args()

    # Get all worktrees
    worktrees = get_worktrees(args.repo_root)

    # Check for uncommitted changes
    for wt in worktrees:
        wt.has_uncommitted = check_uncommitted_changes(wt)

    # Filter by category if requested
    if args.category:
        filter_cat = WorktreeCategory(args.category)
        worktrees = [wt for wt in worktrees if wt.category == filter_cat]

    # Cleanup mode
    if args.cleanup:
        worktrees = [wt for wt in worktrees if wt.category == WorktreeCategory.CLEANUP_CANDIDATE]

    # Output
    if args.format == "table":
        print(format_table(worktrees))
    elif args.format == "markdown":
        print(format_markdown(worktrees))
    else:
        import json
        data = [
            {
                "path": wt.path,
                "branch": wt.branch,
                "category": wt.category.value,
                "is_detached": wt.is_detached,
                "pr_number": wt.pr_number,
                "pr_url": wt.pr_url,
                "has_uncommitted": wt.has_uncommitted,
            }
            for wt in worktrees
        ]
        print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
