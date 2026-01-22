#!/usr/bin/env python3
"""PR Monitor - Track all PR comments including nitpick and out-of-diff.

Queries GitHub API to extract comprehensive review information:
- Inline review comments
- Review-level comments
- Out-of-diff comments (CodeRabbit special handling)
- Nitpick comments
- Reviewer assignments

Usage:
    python3 tools/pr_monitor.py                    # All open PRs
    python3 tools/pr_monitor.py --pr 489           # Specific PR
    python3 tools/pr_monitor.py --export markdown  # Export format
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Comment severity levels."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


@dataclass
class ReviewComment:
    """A single review comment."""

    author: str
    body: str
    path: str | None = None
    line: int | None = None
    severity: Severity = Severity.UNKNOWN
    is_out_of_diff: bool = False
    is_nitpick: bool = False
    url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewComment":
        """Create from GitHub API response."""
        body = data.get("body", "")

        # Parse severity from CodeRabbit comment format
        severity = Severity.UNKNOWN
        if "🔴 Critical" in body or "CRITICAL" in body:
            severity = Severity.CRITICAL
        elif "🟠 Major" in body or "MAJOR" in body:
            severity = Severity.MAJOR
        elif "🟡 Minor" in body or "MINOR" in body:
            severity = Severity.MINOR
        elif "Info" in body or "INFO" in body:
            severity = Severity.INFO

        # Check for out-of-diff marker
        is_out_of_diff = "outside diff" in body.lower() or "out of diff" in body.lower()

        # Check for nitpick markers
        is_nitpick = "nitpick" in body.lower() or "nit:" in body.lower()

        return cls(
            author=data.get("author", {}).get("login", "unknown"),
            body=body[:500],  # Truncate for display
            path=data.get("path"),
            line=data.get("originalLine") or data.get("line"),
            severity=severity,
            is_out_of_diff=is_out_of_diff,
            is_nitpick=is_nitpick,
            url=data.get("url", ""),
        )


@dataclass
class PRInfo:
    """Information about a pull request."""

    number: int
    title: str
    branch: str
    state: str
    author: str
    created_at: str
    comments: list[ReviewComment] = field(default_factory=list)
    review_comments: list[ReviewComment] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    draft: bool = False
    mergeable: str | None = None
    check_status: str = "unknown"

    @property
    def total_comments(self) -> int:
        """Total number of comments."""
        return len(self.comments) + len(self.review_comments)

    @property
    def actionable_comments(self) -> list[ReviewComment]:
        """Comments that require action (excluding bots)."""
        bots = {"coderabbitai", "chatgpt-codex-connector", "github-actions"}
        return [
            c
            for c in self.review_comments
            if c.author not in bots and c.severity != Severity.INFO
        ]

    @property
    def critical_issues(self) -> list[ReviewComment]:
        """Critical severity comments."""
        return [c for c in self.review_comments if c.severity == Severity.CRITICAL]

    @property
    def out_of_diff_comments(self) -> list[ReviewComment]:
        """Comments outside the diff range."""
        return [c for c in self.review_comments if c.is_out_of_diff]


def run_gh(args: list[str]) -> dict[str, Any]:
    """Run gh CLI command and return parsed JSON output."""
    cmd = ["gh", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, env=os.environ.copy()
        )
        return json.loads(result.stdout) if result.stdout else {}
    except subprocess.CalledProcessError as e:
        print(f"gh command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            print(f"stdout: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"stderr: {e.stderr}", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}", file=sys.stderr)
        return {}


def get_open_prs(repo: str = "POWERFULMOVES/PMOVES.AI") -> list[dict[str, Any]]:
    """Get all open PRs."""
    result = run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,title,headRefName,state,author,createdAt,isDraft,mergeable,reviews,comments",
        ]
    )
    return result if isinstance(result, list) else [result]


def get_pr_review_comments(pr_number: int, repo: str = "POWERFULMOVES/PMOVES.AI") -> list[dict[str, Any]]:
    """Get all review comments for a PR (includes out-of-diff)."""
    result = run_gh(
        [
            "api",
            f"repos/{repo}/pulls/{pr_number}/comments",
        ]
    )
    return result if isinstance(result, list) else [result]


def get_pr_reviews(pr_number: int, repo: str = "POWERFULMOVES/PMOVES.AI") -> list[dict[str, Any]]:
    """Get all reviews for a PR."""
    result = run_gh(
        [
            "api",
            f"repos/{repo}/pulls/{pr_number}/reviews",
        ]
    )
    return result if isinstance(result, list) else [result]


def get_pr_check_status(pr_number: int, repo: str = "POWERFULMOVES/PMOVES.AI") -> str:
    """Get combined status of PR checks."""
    result = run_gh(
        [
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repo,
        ]
    )
    # Parse output to determine status
    if "fail" in result.lower():
        return "failing"
    elif "pass" in result.lower():
        return "passing"
    return "unknown"


def fetch_pr_info(pr_number: int, repo: str = "POWERFULMOVES/PMOVES.AI") -> PRInfo:
    """Fetch comprehensive information about a single PR."""
    # Get PR details
    pr_data = run_gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "number,title,headRefName,state,author,createdAt,isDraft,mergeable,reviews,comments",
        ]
    )

    if not pr_data:
        raise ValueError(f"Failed to fetch PR #{pr_number}")

    # Get review comments (includes out-of-diff)
    review_comments_data = get_pr_review_comments(pr_number, repo)
    review_comments = [ReviewComment.from_dict(c) for c in review_comments_data]

    # Get reviews
    reviews_data = get_pr_reviews(pr_number, repo)

    # Get regular PR comments
    pr_comments = pr_data.get("comments", [])

    return PRInfo(
        number=pr_data["number"],
        title=pr_data["title"],
        branch=pr_data["headRefName"],
        state=pr_data["state"],
        author=pr_data["author"]["login"],
        created_at=pr_data["createdAt"],
        comments=[],
        review_comments=review_comments,
        reviews=reviews_data,
        draft=pr_data.get("isDraft", False),
        mergeable=pr_data.get("mergeable"),
    )


def format_markdown(prs: list[PRInfo]) -> str:
    """Format PR information as Markdown."""
    lines = [
        "# PR Review Status",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"| PR | Title | Status | Comments | Actionable | Critical | Out-of-Diff |",
        f"|----|-------|--------|----------|------------|----------|-------------|",
    ]

    for pr in prs:
        status_emoji = "🔴" if pr.critical_issues else "🟡" if pr.actionable_comments else "🟢"
        draft_mark = " [DRAFT]" if pr.draft else ""

        lines.append(
            f"| {status_emoji} #{pr.number}{draft_mark} | {pr.title[:40]} | {pr.state.upper()} | "
            f"{pr.total_comments} | {len(pr.actionable_comments)} | {len(pr.critical_issues)} | "
            f"{len(pr.out_of_diff_comments)} |"
        )

    lines.extend(["", "## Detailed Review Comments", ""])

    for pr in prs:
        if pr.review_comments:
            lines.extend([
                f"### PR #{pr.number}: {pr.title}",
                "",
            ])

            # Group by severity
            for severity in [Severity.CRITICAL, Severity.MAJOR, Severity.MINOR]:
                comments = [c for c in pr.review_comments if c.severity == severity]
                if comments:
                    emoji = {Severity.CRITICAL: "🔴", Severity.MAJOR: "🟠", Severity.MINOR: "🟡"}[severity]
                    lines.append(f"#### {emoji} {severity.value} Issues ({len(comments)})")
                    lines.append("")

                    for comment in comments:
                        location = f"{comment.path}:{comment.line}" if comment.path else "General"
                        ood_marker = " **[OUT-OF-DIFF]**" if comment.is_out_of_diff else ""
                        lines.append(f"- **{location}**{ood_marker}")
                        lines.append(f"  - {comment.body[:200]}")
                        lines.append("")

            # Out-of-diff comments section
            if pr.out_of_diff_comments:
                lines.extend([
                    "#### ⚠️ Out-of-Diff Comments",
                    "",
                ])
                for comment in pr.out_of_diff_comments:
                    location = f"{comment.path}:{comment.line}" if comment.path else "Unknown"
                    lines.append(f"- **{location}**: {comment.body[:200]}")
                lines.append("")

    return "\n".join(lines)


def format_json(prs: list[PRInfo]) -> str:
    """Format PR information as JSON."""
    data = []
    for pr in prs:
        pr_dict = {
            "number": pr.number,
            "title": pr.title,
            "branch": pr.branch,
            "state": pr.state,
            "author": pr.author,
            "draft": pr.draft,
            "mergeable": pr.mergeable,
            "total_comments": pr.total_comments,
            "actionable_comments": len(pr.actionable_comments),
            "critical_issues": len(pr.critical_issues),
            "out_of_diff_comments": len(pr.out_of_diff_comments),
            "review_comments": [
                {
                    "author": c.author,
                    "path": c.path,
                    "line": c.line,
                    "severity": c.severity.value,
                    "is_out_of_diff": c.is_out_of_diff,
                    "body": c.body,
                }
                for c in pr.review_comments
            ],
        }
        data.append(pr_dict)
    return json.dumps(data, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor PR comments including nitpick and out-of-diff"
    )
    parser.add_argument(
        "--pr", type=int, help="Specific PR number to check (default: all open)"
    )
    parser.add_argument(
        "--format", choices=["markdown", "json", "table"], default="table", help="Output format"
    )
    parser.add_argument(
        "--repo", default="POWERFULMOVES/PMOVES.AI", help="GitHub repository"
    )
    parser.add_argument(
        "--export", help="Export to file (format determined by extension)"
    )

    args = parser.parse_args()

    # Fetch PR data
    if args.pr:
        prs = [fetch_pr_info(args.pr, args.repo)]
    else:
        open_prs = get_open_prs(args.repo)
        prs = []
        for pr_data in open_prs:
            pr_info = fetch_pr_info(pr_data["number"], args.repo)
            prs.append(pr_info)

    # Sort by critical issues first, then by PR number
    prs.sort(key=lambda p: (-len(p.critical_issues), -len(p.actionable_comments), p.number))

    # Output format
    if args.export:
        ext = Path(args.export).suffix.lower()
        output_format = "markdown" if ext == ".md" else "json"
    else:
        output_format = args.format

    if output_format == "table":
        # Simple table format
        print("PR Review Status")
        print("=" * 80)
        for pr in prs:
            status_emoji = "🔴" if pr.critical_issues else "🟡" if pr.actionable_comments else "🟢"
            print(f"\n{status_emoji} PR #{pr.number}: {pr.title}")
            print(f"  Branch: {pr.branch}")
            print(f"  State: {pr.state.upper()} {'[DRAFT]' if pr.draft else ''}")
            print(f"  Comments: {pr.total_comments} total, {len(pr.actionable_comments)} actionable")
            if pr.critical_issues:
                print(f"  ⚠️  CRITICAL ISSUES: {len(pr.critical_issues)}")
            if pr.out_of_diff_comments:
                print(f"  ⚠️  OUT-OF-DIFF: {len(pr.out_of_diff_comments)}")
            if pr.actionable_comments:
                print("  Action items:")
                for comment in pr.actionable_comments[:5]:
                    location = f"{comment.path}:{comment.line}" if comment.path else "General"
                    print(f"    - [{comment.severity.value}] {location}: {comment.body[:80]}")
    elif output_format == "markdown":
        print(format_markdown(prs))
    else:
        print(format_json(prs))

    # Export to file if requested
    if args.export:
        content = format_markdown(prs) if output_format == "markdown" else format_json(prs)
        Path(args.export).write_text(content)
        print(f"\nExported to: {args.export}", file=sys.stderr)

    # Return non-zero if there are critical issues
    return 1 if any(pr.critical_issues for pr in prs) else 0


if __name__ == "__main__":
    sys.exit(main())
