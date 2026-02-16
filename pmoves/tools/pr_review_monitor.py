#!/usr/bin/env python3
"""Capture PR checks/reviews/comments into local evidence files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "pmoves" / "docs" / "evidence" / "pr_monitor"


@dataclass
class SnapshotResult:
    payload: dict[str, Any]
    checks_pending: int
    checks_failed: int
    checks_total: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="POWERFULMOVES/PMOVES.AI", help="OWNER/REPO")
    parser.add_argument("--pr", type=int, default=0, help="PR number. Auto-detect current branch PR when omitted.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for evidence files.")
    parser.add_argument("--watch-seconds", type=int, default=0, help="Watch duration (seconds). 0 captures once.")
    parser.add_argument("--interval", type=float, default=15.0, help="Polling interval for watch mode.")
    parser.add_argument("--include-comments", action="store_true", help="Include issue/review/inline comments.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero if checks fail (or remain pending in watch mode).")
    return parser.parse_args()


def run_gh(args: list[str]) -> str:
    cmd = ["gh", *args]
    proc = subprocess.run(cmd, capture_output=True, text=False, check=False)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        msg = stderr.strip() or stdout.strip() or "unknown gh error"
        raise RuntimeError(f"gh command failed ({proc.returncode}): {' '.join(cmd)} :: {msg}")
    return stdout


def gh_json(args: list[str]) -> Any:
    raw = run_gh(args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON for gh {' '.join(args)}: {exc}") from exc


def detect_pr_number(repo: str) -> int:
    data = gh_json(
        [
            "pr",
            "view",
            "--repo",
            repo,
            "--json",
            "number",
        ]
    )
    number = data.get("number")
    if not isinstance(number, int):
        raise RuntimeError("Unable to auto-detect PR number from current branch. Pass --pr <number>.")
    return number


def count_checks(status_rollup: list[dict[str, Any]]) -> tuple[int, int, int]:
    pending = 0
    failed = 0
    total = 0
    for item in status_rollup:
        typename = item.get("__typename", "")
        total += 1
        if typename == "CheckRun":
            status = str(item.get("status", "")).upper()
            conclusion = str(item.get("conclusion", "")).upper()
            if status != "COMPLETED":
                pending += 1
            elif conclusion not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
                failed += 1
        elif typename == "StatusContext":
            state = str(item.get("state", "")).upper()
            if state in {"PENDING", ""}:
                pending += 1
            elif state not in {"SUCCESS"}:
                failed += 1
    return pending, failed, total


def fetch_snapshot(repo: str, pr: int, include_comments: bool) -> SnapshotResult:
    pr_view = gh_json(
        [
            "pr",
            "view",
            str(pr),
            "--repo",
            repo,
            "--json",
            "number,title,state,headRefName,baseRefName,reviewDecision,statusCheckRollup,latestReviews,author,url",
        ]
    )

    issue_comments: list[dict[str, Any]] = []
    review_comments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    if include_comments:
        issue_comments = gh_json(["api", f"repos/{repo}/issues/{pr}/comments?per_page=100"])
        review_comments = gh_json(["api", f"repos/{repo}/pulls/{pr}/comments?per_page=100"])
        reviews = gh_json(["api", f"repos/{repo}/pulls/{pr}/reviews?per_page=100"])

    status_rollup = pr_view.get("statusCheckRollup", [])
    if not isinstance(status_rollup, list):
        status_rollup = []
    pending, failed, total = count_checks(status_rollup)

    payload: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "pr": pr,
        "summary": {
            "checks_total": total,
            "checks_pending": pending,
            "checks_failed": failed,
            "checks_passed": max(0, total - pending - failed),
        },
        "pr_view": pr_view,
        "reviews": reviews,
        "issue_comments": issue_comments,
        "review_comments": review_comments,
    }
    return SnapshotResult(payload=payload, checks_pending=pending, checks_failed=failed, checks_total=total)


def render_md(result: SnapshotResult) -> str:
    payload = result.payload
    pr_view = payload["pr_view"]
    summary = payload["summary"]
    checks = pr_view.get("statusCheckRollup", [])
    lines = [
        "# PR Monitor Snapshot",
        "",
        f"- Captured at: `{payload['captured_at']}`",
        f"- Repo: `{payload['repo']}`",
        f"- PR: `#{payload['pr']}`",
        f"- Title: `{pr_view.get('title', '')}`",
        f"- Branch: `{pr_view.get('headRefName', '')}` -> `{pr_view.get('baseRefName', '')}`",
        f"- State: `{pr_view.get('state', '')}`",
        f"- Review decision: `{pr_view.get('reviewDecision', '')}`",
        f"- URL: {pr_view.get('url', '')}",
        "",
        "## Checks",
        f"- Total: **{summary['checks_total']}**",
        f"- Passed: **{summary['checks_passed']}**",
        f"- Pending: **{summary['checks_pending']}**",
        f"- Failed: **{summary['checks_failed']}**",
        "",
        "| Name | Type | Status | Conclusion/State | Details |",
        "| --- | --- | --- | --- | --- |",
    ]

    for check in checks:
        typename = check.get("__typename", "")
        name = str(check.get("name", ""))
        if typename == "CheckRun":
            status = str(check.get("status", ""))
            conclusion = str(check.get("conclusion", ""))
            details = str(check.get("detailsUrl", ""))
            lines.append(f"| `{name}` | `CheckRun` | `{status}` | `{conclusion}` | {details} |")
        else:
            state = str(check.get("state", ""))
            target = str(check.get("targetUrl", ""))
            lines.append(f"| `{name}` | `StatusContext` | `n/a` | `{state}` | {target} |")

    issue_comments = payload.get("issue_comments", [])
    review_comments = payload.get("review_comments", [])
    reviews = payload.get("reviews", [])
    lines.extend(
        [
            "",
            "## Review Artifacts",
            f"- Reviews: **{len(reviews)}**",
            f"- PR issue comments: **{len(issue_comments)}**",
            f"- Inline review comments: **{len(review_comments)}**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, pr: int, result: SnapshotResult) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"pr-{pr}-{stamp}.json"
    md_path = out_dir / f"pr-{pr}-{stamp}.md"
    latest_json = out_dir / f"pr-{pr}-latest.json"
    latest_md = out_dir / f"pr-{pr}-latest.md"

    json_text = json.dumps(result.payload, indent=2, sort_keys=False)
    md_text = render_md(result)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text + "\n", encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def main() -> int:
    args = parse_args()
    try:
        pr = args.pr if args.pr > 0 else detect_pr_number(args.repo)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    deadline = time.time() + args.watch_seconds if args.watch_seconds > 0 else 0.0
    last_result: SnapshotResult | None = None
    while True:
        try:
            result = fetch_snapshot(args.repo, pr, include_comments=args.include_comments)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 2
        last_result = result
        json_path, md_path = write_outputs(args.out_dir, pr, result)
        print(
            "snapshot"
            f" pr=#{pr}"
            f" checks={result.checks_total}"
            f" pending={result.checks_pending}"
            f" failed={result.checks_failed}"
            f" -> {json_path}"
        )
        print(f"summary -> {md_path}")

        if args.watch_seconds <= 0:
            break
        if result.checks_pending == 0:
            break
        if time.time() >= deadline:
            break
        time.sleep(max(1.0, args.interval))

    if last_result is None:
        return 2
    if args.strict:
        if last_result.checks_failed > 0:
            return 2
        if args.watch_seconds > 0 and last_result.checks_pending > 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
