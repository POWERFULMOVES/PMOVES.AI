#!/usr/bin/env python3
"""Review Comment Collector — harvests GitHub PR review comments into Supabase.

Fetches review comments from merged/open PRs across the PMOVES repos and
inserts them into pmoves_core.review_comments for retro learning analysis.

The SPARK node reads this table, classifies comments (missed-signal,
fix-pattern, wrong-suggestion, already-addressed), and surfaces
actionable items to operators and agents.

Usage:
    # Collect from all open PRs on PMOVES.AI:
    python -m pmoves.tools.collect_review_comments --repo PMOVES.AI --state open

    # Collect from recently merged PRs:
    python -m pmoves.tools.collect_review_comments --repo PMOVES.AI --state merged --limit 20

    # Dry-run (print, don't insert):
    python -m pmoves.tools.collect_review_comments --repo PMOVES.AI --dry-run

    # Collect from a submodule fork:
    python -m pmoves.tools.collect_review_comments --repo Pmoves-cipher --state all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SUPABASE_URL = os.environ.get("SUPABASE_REST_URL", "http://localhost:8000/rest/v1")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SERVICE_ROLE_KEY", "")
GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")

SEVERITY_RE = re.compile(r"P(\d)\s+Badge|severity[:\s]*(P\d)", re.IGNORECASE)
BOT_AUTHORS = {"coderabbitai", "chatgpt-codex-connector", "github-actions", "dependabot"}


def gh_api(url: str) -> Any:
    """Call GitHub API with token."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def get_prs(repo: str, state: str, limit: int) -> list[dict]:
    """Get PRs from a repo."""
    gh_state = "open" if state == "open" else "closed"
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls?state={gh_state}&per_page={min(limit, 100)}&sort=updated&direction=desc"
    prs = gh_api(url)
    if state == "merged":
        prs = [pr for pr in prs if pr.get("merged_at")]
    return prs


def get_review_comments(repo: str, pr_number: int) -> list[dict]:
    """Get review comments (inline) for a PR."""
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls/{pr_number}/comments?per_page=100"
    try:
        return gh_api(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def get_pr_comments(repo: str, pr_number: int) -> list[dict]:
    """Get issue comments (general) for a PR."""
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/issues/{pr_number}/comments?per_page=100"
    try:
        return gh_api(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def extract_severity(body: str) -> str | None:
    """Extract P1/P2/P3 from comment body."""
    m = SEVERITY_RE.search(body)
    if m:
        for g in m.groups():
            if g and g.isdigit():
                return f"P{g}"
    low = body.lower()
    if "nitpick" in low:
        return "nitpick"
    if "praise" in low:
        return "praise"
    if "question" in low:
        return "question"
    return None


def classify_author(author: str) -> str:
    """Classify author as bot, human, or agent."""
    if author in BOT_AUTHORS:
        return "bot"
    if "[bot]" in author:
        return "bot"
    return "human"


def insert_comment(comment: dict[str, Any], dry_run: bool = False) -> bool:
    """Insert a review comment into Supabase."""
    if dry_run:
        safe_body = comment['body'][:60].encode('ascii', 'replace').decode()
        print(f"  [dry-run] {comment['repo']}#{comment['pr_number']} "
              f"{comment['author']} {comment.get('severity', '?')} "
              f"{safe_body}...")
        return True

    if not SUPABASE_KEY:
        print("  [skip] No SUPABASE_SERVICE_ROLE_KEY set")
        return False

    url = f"{SUPABASE_URL}/review_comments"
    body = json.dumps(comment).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "resolution=merge-duplicates",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return True
        print(f"  [error] {e.code}: {e.read()[:100]}")
        return False
    except Exception as e:
        print(f"  [error] {e}")
        return False


def collect_pr(repo: str, pr: dict, dry_run: bool) -> int:
    """Collect all comments from one PR."""
    pr_number = pr["number"]
    count = 0

    review_comments = get_review_comments(repo, pr_number)
    for rc in review_comments:
        body = rc.get("body", "")
        if not body.strip():
            continue
        severity = extract_severity(body)
        author = rc.get("user", {}).get("login", "unknown")
        comment = {
            "repo": repo,
            "pr_number": pr_number,
            "comment_id": rc.get("id"),
            "author": author,
            "author_type": classify_author(author),
            "path": rc.get("path"),
            "line": rc.get("line") or rc.get("original_line"),
            "severity": severity,
            "body": body,
            "is_resolved": False,
        }
        if insert_comment(comment, dry_run):
            count += 1

    issue_comments = get_pr_comments(repo, pr_number)
    for ic in issue_comments:
        body = ic.get("body", "")
        if not body.strip() or len(body) < 20:
            continue
        author = ic.get("user", {}).get("login", "unknown")
        if classify_author(author) != "bot":
            continue
        severity = extract_severity(body)
        comment = {
            "repo": repo,
            "pr_number": pr_number,
            "comment_id": ic.get("id"),
            "author": author,
            "author_type": "bot",
            "path": None,
            "line": None,
            "severity": severity,
            "body": body,
            "is_resolved": False,
        }
        if insert_comment(comment, dry_run):
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect GitHub PR review comments into Supabase")
    parser.add_argument("--repo", required=True, help="Repo name (e.g. PMOVES.AI, Pmoves-cipher)")
    parser.add_argument("--state", default="open", choices=["open", "merged", "closed", "all"])
    parser.add_argument("--limit", type=int, default=10, help="Max PRs to scan")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
        sys.exit(1)

    prs = get_prs(args.repo, args.state, args.limit)
    print(f"[collector] {args.repo}: {len(prs)} PRs ({args.state})")

    total = 0
    for pr in prs:
        pr_number = pr["number"]
        title = pr.get("title", "")[:60]
        count = collect_pr(args.repo, pr, args.dry_run)
        total += count
        print(f"  #{pr_number} ({title}): {count} comments")

    print(f"\n[collector] Total: {total} comments collected{' [dry-run]' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
