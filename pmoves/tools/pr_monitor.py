#!/usr/bin/env python3
"""Live PR monitor for merge readiness (checks + review blockers)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, List


SUCCESS_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED"}
BLOCKING_REVIEW_STATES = {"CHANGES_REQUESTED"}
BOT_REVIEW_LOGINS = {"coderabbitai[bot]", "chatgpt-codex-connector[bot]"}


@dataclass
class CheckSummary:
    passed: int = 0
    failed: int = 0
    pending: int = 0


@dataclass
class PrSummary:
    number: int
    title: str
    url: str
    head: str
    base: str
    mergeable: str
    merge_state_status: str
    review_decision: str
    is_draft: bool
    checks: CheckSummary
    line_comments_total: int
    bot_line_comments: int
    blockers: List[str]


def _run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    payload = proc.stdout.strip()
    if not payload:
        return None
    return json.loads(payload)


def _repo_name(default_repo: str) -> str:
    try:
        data = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    except RuntimeError:
        return default_repo
    if isinstance(data, dict):
        candidate = data.get("nameWithOwner")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return default_repo


def _check_summary(status_rollup: Iterable[dict[str, Any]] | None) -> CheckSummary:
    summary = CheckSummary()
    for item in status_rollup or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("__typename") or "")
        if kind == "CheckRun":
            status = str(item.get("status") or "").upper()
            conclusion = str(item.get("conclusion") or "").upper()
            if status != "COMPLETED":
                summary.pending += 1
            elif conclusion in SUCCESS_STATES:
                summary.passed += 1
            else:
                summary.failed += 1
            continue
        if kind == "StatusContext":
            state = str(item.get("state") or "").upper()
            if state in SUCCESS_STATES:
                summary.passed += 1
            elif state in {"EXPECTED", "PENDING"}:
                summary.pending += 1
            else:
                summary.failed += 1
    return summary


def _line_comments(repo: str, number: int) -> tuple[int, int]:
    comments = _run_json(["gh", "api", f"repos/{repo}/pulls/{number}/comments"])
    if not isinstance(comments, list):
        return 0, 0
    total = len(comments)
    bot_count = 0
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        if not isinstance(user, dict):
            continue
        login = str(user.get("login") or "").strip()
        if login in BOT_REVIEW_LOGINS:
            bot_count += 1
    return total, bot_count


def _pr_numbers(repo: str, base: str, state: str, explicit_prs: list[int]) -> list[int]:
    if explicit_prs:
        return sorted(set(explicit_prs))
    rows = _run_json(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--base",
            base,
            "--json",
            "number",
        ]
    )
    if not isinstance(rows, list):
        return []
    out: list[int] = []
    for row in rows:
        if isinstance(row, dict):
            number = row.get("number")
            if isinstance(number, int):
                out.append(number)
    return sorted(set(out))


def _pr_summary(repo: str, number: int) -> PrSummary:
    detail = _run_json(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,url,headRefName,baseRefName,mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup",
        ]
    )
    if not isinstance(detail, dict):
        raise RuntimeError(f"invalid PR payload for #{number}")
    checks = _check_summary(detail.get("statusCheckRollup"))
    line_comments_total, bot_line_comments = _line_comments(repo, number)

    mergeable = str(detail.get("mergeable") or "UNKNOWN")
    merge_state_status = str(detail.get("mergeStateStatus") or "UNKNOWN")
    review_decision = str(detail.get("reviewDecision") or "REVIEW_REQUIRED")
    is_draft = bool(detail.get("isDraft"))
    blockers: list[str] = []
    if is_draft:
        blockers.append("draft")
    if mergeable != "MERGEABLE":
        blockers.append(f"mergeable={mergeable}")
    if merge_state_status not in {"CLEAN", "HAS_HOOKS", "UNSTABLE"}:
        blockers.append(f"merge_state={merge_state_status}")
    if review_decision.upper() in BLOCKING_REVIEW_STATES:
        blockers.append(f"review={review_decision}")
    if checks.failed:
        blockers.append(f"failed_checks={checks.failed}")
    if checks.pending:
        blockers.append(f"pending_checks={checks.pending}")
    if bot_line_comments:
        blockers.append(f"bot_line_comments={bot_line_comments}")

    return PrSummary(
        number=number,
        title=str(detail.get("title") or ""),
        url=str(detail.get("url") or ""),
        head=str(detail.get("headRefName") or ""),
        base=str(detail.get("baseRefName") or ""),
        mergeable=mergeable,
        merge_state_status=merge_state_status,
        review_decision=review_decision,
        is_draft=is_draft,
        checks=checks,
        line_comments_total=line_comments_total,
        bot_line_comments=bot_line_comments,
        blockers=blockers,
    )


def _print_table(items: list[PrSummary]) -> None:
    print(
        "| PR | Mergeable | Checks (P/F/Q) | Review | Bot Comments | Blockers | Title |",
        flush=True,
    )
    print("|---:|---|---|---|---:|---|---|", flush=True)
    for item in items:
        checks = f"{item.checks.passed}/{item.checks.failed}/{item.checks.pending}"
        blockers = ", ".join(item.blockers) if item.blockers else "none"
        print(
            f"| #{item.number} | {item.mergeable}/{item.merge_state_status} | {checks} | {item.review_decision} | "
            f"{item.bot_line_comments} | {blockers} | {item.title} |",
            flush=True,
        )
    print("", flush=True)
    for item in items:
        print(f"#{item.number}: {item.url}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="POWERFULMOVES/PMOVES.AI", help="owner/repo (default: POWERFULMOVES/PMOVES.AI)")
    parser.add_argument("--base", default="PMOVES.AI-Edition-Hardened", help="base branch filter (default: PMOVES.AI-Edition-Hardened)")
    parser.add_argument("--state", default="open", choices=["open", "closed", "merged", "all"], help="PR state filter")
    parser.add_argument("--pr", dest="prs", action="append", type=int, default=[], help="monitor specific PR number (repeatable)")
    parser.add_argument("--json-out", type=Path, default=None, help="write full monitor payload as JSON")
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any PR has blockers")
    args = parser.parse_args(argv)

    repo = _repo_name(args.repo)
    numbers = _pr_numbers(repo, args.base, args.state, args.prs)
    if not numbers:
        print(f"No PRs found for repo={repo} state={args.state} base={args.base}")
        return 0

    summaries = [_pr_summary(repo, number) for number in numbers]
    _print_table(summaries)

    payload = {
        "repo": repo,
        "state": args.state,
        "base": args.base,
        "count": len(summaries),
        "items": [
            {
                **asdict(item),
                "checks": asdict(item.checks),
            }
            for item in summaries
        ],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote JSON report: {args.json_out}")

    if args.strict and any(item.blockers for item in summaries):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
