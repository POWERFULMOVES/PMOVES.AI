#!/usr/bin/env python3
"""Submodule Reviewer - Scan and categorize all PMOVES submodules.

Analyzes the 39 PMOVES submodules for:
- Branch status vs PMOVES.AI-Edition-Hardened
- Unpushed commits
- Diverged branches
- Open PRs in submodule repos
- Tier categorization

Usage:
    python3 tools/submodule_reviewer.py              # All submodules
    python3 tools/submodule_reviewer.py --tier agent # Agent tier only
    python3 tools/submodule_reviewer.py --check-prs  # Check submodule PRs
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Tier(Enum):
    """PMOVES 6-tier architecture."""
    AGENT = "agent"
    API = "api"
    DATA = "data"
    LLM = "llm"
    MEDIA = "media"
    WORKER = "worker"
    UI = "ui"
    INFRA = "infra"
    INTEGRATION = "integration"
    E2B = "e2b"
    UNKNOWN = "unknown"


@dataclass
class SubmoduleInfo:
    """Information about a submodule."""

    name: str
    path: str
    commit: str
    branch: str | None = None
    tier: Tier = Tier.UNKNOWN
    has_unpushed: bool = False
    is_diverged: bool = False
    open_prs: list[dict[str, Any]] = field(default_factory=list)
    status: str = "synced"  # synced, diverged, unpushed, unknown

    @property
    def repo_owner(self) -> str:
        """Get repository owner (default: POWERFULMOVES)."""
        return "POWERFULMOVES"

    @property
    def repo_name(self) -> str:
        """Get repository name."""
        return self.name


# Tier categorization for all known submodules
SUBMODULE_TIERS: dict[str, Tier] = {
    # Agent Tier
    "PMOVES-Agent-Zero": Tier.AGENT,
    "PMOVES-Archon": Tier.AGENT,
    "PMOVES-BoTZ": Tier.AGENT,
    "PMOVES-BoTZ-gateway": Tier.AGENT,
    "pmoves/integrations/archon": Tier.AGENT,
    # API Tier
    "PMOVES-n8n": Tier.API,
    # Data Tier
    "pmoves/vendor/agentgym-rl": Tier.DATA,
    # LLM Tier
    "PMOVES-tensorzero": Tier.LLM,
    # Media Tier
    "PMOVES.YT": Tier.MEDIA,
    "PMOVES-Jellyfin": Tier.MEDIA,
    "PMOVES-Pinokio-Ultimate-TTS-Studio": Tier.MEDIA,
    "PMOVES-transcribe-and-fetch": Tier.MEDIA,
    "PMOVES-Pipecat": Tier.MEDIA,
    "PMOVES-Ultimate-TTS-Studio": Tier.MEDIA,
    # RAG (Worker/Data)
    "PMOVES-HiRAG": Tier.WORKER,
    "PMOVES-Deep-Serch": Tier.WORKER,
    "PMOVES-Open-Notebook": Tier.WORKER,
    # UI Tier
    "PMOVES-A2UI": Tier.UI,
    "PMOVES-MAI-UI": Tier.UI,
    "PMOVES-ToKenism-Multi": Tier.UI,
    # Infra Tier
    "PMOVES-Danger-infra": Tier.INFRA,
    "PMOVES-crush": Tier.INFRA,
    # Integration Tier
    "PMOVES-Wealth": Tier.INTEGRATION,
    "PMOVES-Health-wger": Tier.INTEGRATION,
    "PMOVES-Jellyfin-AI-Media-Stack": Tier.INTEGRATION,
    # E2B Tier
    "e2b": Tier.E2B,
    "PMOVES-E2B-Danger-Room-Deskdesktop": Tier.E2B,
    "PMOVES-E2b-Spells": Tier.E2B,
    "pmoves/vendor/e2b": Tier.E2B,
    "pmoves/vendor/e2b-desktop": Tier.E2B,
    "pmoves/vendor/e2b-infra": Tier.E2B,
    "pmoves/vendor/e2b-mcp-server": Tier.E2B,
    "pmoves/vendor/e2b-spells": Tier.E2B,
    "pmoves/vendor/e2b-surf": Tier.E2B,
    "pmoves-surf": Tier.E2B,
    "pmoves-e2b-mcp-server": Tier.E2B,
    # Other
    "PMOVES-Creator": Tier.UNKNOWN,
    "PMOVES-Remote-View": Tier.UNKNOWN,
    "PMOVES-Tailscale": Tier.UNKNOWN,
    "PMOVES-hyperdimensions": Tier.UNKNOWN,
    "research/A2UI": Tier.UNKNOWN,
}


def get_tier_for_submodule(name: str) -> Tier:
    """Get tier for a submodule by name."""
    return SUBMODULE_TIERS.get(name, Tier.UNKNOWN)


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run git command."""
    cmd = ["git"] + args
    env = os.environ.copy()
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, env=env
    )


def get_submodule_status(repo_root: Path) -> list[SubmoduleInfo]:
    """Get status of all submodules."""
    result = run_git(["submodule", "status"], cwd=repo_root)

    submodules = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        # Parse: [+-]?<commit sha> <path> (<branch>)?
        parts = line.split()
        if len(parts) < 2:
            continue

        commit = parts[0][1:] if parts[0][0] in "+-" else parts[0]
        path = parts[1]
        name = path.replace("/", "-")

        # Detect unpushed changes (+ prefix)
        has_unpushed = parts[0].startswith("+")

        # Detect branch if specified
        branch = None
        if len(parts) > 2 and parts[2].startswith("("):
            branch = parts[2][1:-1]

        # Determine tier
        tier = get_tier_for_submodule(name)

        submodules.append(SubmoduleInfo(
            name=name,
            path=path,
            commit=commit,
            branch=branch,
            tier=tier,
            has_unpushed=has_unpushed,
        ))

    return submodules


def check_divergence(submodule: SubmoduleInfo, repo_root: Path) -> bool:
    """Check if submodule branch is diverged from remote."""
    submodule_path = repo_root / submodule.path

    if not submodule_path.exists():
        return False

    # Check if there's a branch
    result = run_git(["branch", "--show-current"], cwd=submodule_path)
    if not result.stdout.strip():
        return False

    branch = result.stdout.strip()
    submodule.branch = branch

    # Check for divergence
    result = run_git(
        ["rev-list", "--count", "--left-right", f"origin/{branch}...{branch}"],
        cwd=submodule_path
    )

    if result.returncode != 0:
        return False

    parts = result.stdout.strip().split("\t")
    if len(parts) == 2:
        behind, ahead = parts
        return int(ahead) > 0 or int(behind) > 0

    return False


def get_submodule_prs(submodule: SubmoduleInfo) -> list[dict[str, Any]]:
    """Get open PRs for a submodule repo."""
    # Only check submodules that are external repos (not vendor paths)
    if submodule.path.startswith("pmoves/vendor/"):
        return []

    # Try to get PRs using gh CLI
    try:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", f"{submodule.repo_owner}/{submodule.repo_name}",
                "--state", "open",
                "--json", "number,title,state,author,createdAt",
                "--limit", "10"
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except Exception:
        pass

    return []


def check_submodule_branch_status(submodule: SubmoduleInfo, repo_root: Path) -> str:
    """Check submodule branch status."""
    submodule_path = repo_root / submodule.path

    if not submodule_path.exists():
        return "not-found"

    # Check current branch
    result = run_git(["branch", "--show-current"], cwd=submodule_path)
    if result.returncode != 0:
        return "no-branch"

    current_branch = result.stdout.strip() or "HEAD"
    submodule.branch = current_branch

    # Check if on expected branch
    if current_branch == "PMOVES.AI-Edition-Hardened":
        if submodule.has_unpushed:
            return "unpushed"
        return "synced"

    # Check if diverged
    if check_divergence(submodule, repo_root):
        return "diverged"

    return "branch-mismatch"


def categorize_submodules(submodules: list[SubmoduleInfo]) -> dict[Tier, list[SubmoduleInfo]]:
    """Categorize submodules by tier."""
    categorized: dict[Tier, list[SubmoduleInfo]] = {t: [] for t in Tier}
    categorized[Tier.UNKNOWN] = []

    for sm in submodules:
        categorized[sm.tier].append(sm)

    # Remove empty categories
    return {k: v for k, v in categorized.items() if v}


def format_markdown(submodules: list[SubmoduleInfo], categorized: dict[Tier, list[SubmoduleInfo]]) -> str:
    """Format submodule report as Markdown."""
    lines = [
        "# Submodule Review Status",
        "",
        "## Summary",
        "",
        f"| Tier | Count | Synced | Diverged | Unpushed |",
        f"|------|-------|--------|----------|----------|",
    ]

    for tier in [Tier.AGENT, Tier.MEDIA, Tier.RAG, Tier.LLM, Tier.INFRA, Tier.E2B, Tier.UI, Tier.API]:
        if tier not in categorized:
            continue
        sms = categorized[tier]
        synced = sum(1 for s in sms if s.status == "synced")
        diverged = sum(1 for s in sms if s.status == "diverged")
        unpushed = sum(1 for s in sms if s.status == "unpushed")
        lines.append(f"| {tier.value.upper()} | {len(sms)} | {synced} | {diverged} | {unpushed} |")

    lines.extend(["", "## Issues Requiring Attention", ""])

    # List diverged/unpushed submodules
    for sm in submodules:
        if sm.status in ("diverged", "unpushed", "branch-mismatch"):
            status_emoji = {
                "diverged": "🔴",
                "unpushed": "🟡",
                "branch-mismatch": "🟠",
            }.get(sm.status, "⚪")
            lines.extend([
                f"{status_emoji} **{sm.name}**",
                f"  - Path: `{sm.path}`",
                f"  - Branch: `{sm.branch or 'unknown'}`",
                f"  - Status: {sm.status}",
                "",
            ])

    # Submodule PRs
    lines.extend(["## Open Submodule PRs", ""])

    for sm in submodules:
        if sm.open_prs:
            lines.append(f"### {sm.name}")
            for pr in sm.open_prs:
                lines.append(f"- #{pr['number']}: {pr['title']}")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review PMOVES submodules for branch status and PRs"
    )
    parser.add_argument(
        "--tier", choices=[t.value for t in Tier], help="Filter by tier"
    )
    parser.add_argument(
        "--check-prs", action="store_true", help="Check for open PRs in submodules"
    )
    parser.add_argument(
        "--format", choices=["markdown", "json", "table"], default="table"
    )
    parser.add_argument(
        "--repo-root", default="/home/pmoves/PMOVES.AI", help="Path to repo root"
    )

    args = parser.parse_args()

    repo_root = Path(args.repo_root)

    # Get submodule status
    submodules = get_submodule_status(repo_root)

    # Check branch status
    for sm in submodules:
        sm.status = check_submodule_branch_status(sm, repo_root)

    # Check for PRs if requested
    if args.check_prs:
        for sm in submodules:
            sm.open_prs = get_submodule_prs(sm)

    # Filter by tier if requested
    if args.tier:
        filter_tier = Tier(args.tier)
        submodules = [sm for sm in submodules if sm.tier == filter_tier]

    # Categorize
    categorized = categorize_submodules(submodules)

    # Output
    if args.format == "table":
        print("Submodule Review Status")
        print("=" * 80)

        for tier in [Tier.AGENT, Tier.MEDIA, Tier.WORKER, Tier.LLM, Tier.INFRA, Tier.E2B]:
            if tier not in categorized:
                continue
            print(f"\n## {tier.value.upper()} Tier")
            for sm in categorized[tier]:
                status_emoji = {
                    "synced": "✅",
                    "diverged": "🔴",
                    "unpushed": "🟡",
                    "branch-mismatch": "🟠",
                }.get(sm.status, "⚪")
                print(f"{status_emoji} {sm.name}")
                print(f"   Path: {sm.path}")
                print(f"   Branch: {sm.branch or 'unknown'}")
                if sm.open_prs:
                    print(f"   Open PRs: {len(sm.open_prs)}")
                    for pr in sm.open_prs[:3]:
                        print(f"     - #{pr['number']}: {pr['title'][:50]}")

    elif args.format == "markdown":
        print(format_markdown(submodules, categorized))

    else:
        data = [
            {
                "name": sm.name,
                "path": sm.path,
                "tier": sm.tier.value,
                "branch": sm.branch,
                "status": sm.status,
                "has_unpushed": sm.has_unpushed,
                "open_prs": sm.open_prs,
            }
            for sm in submodules
        ]
        print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
