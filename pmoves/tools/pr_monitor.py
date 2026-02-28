#!/usr/bin/env python3
"""Live PR monitor for merge readiness + review learnings."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List


SUCCESS_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED"}
BLOCKING_REVIEW_STATES = {"CHANGES_REQUESTED"}
BOT_REVIEW_LOGINS = {"coderabbitai[bot]", "chatgpt-codex-connector[bot]"}
NITPICK_TOKENS = ("nitpick", "nit:", "nits", "style-only")
ACTIONABLE_TOKENS = (
    "[p0",
    "[p1",
    "[p2",
    "error",
    "failing",
    "failed",
    "hard-fail",
    "missing",
    "must",
    "required",
    "security",
    "vulnerability",
    "unsafe",
    "leak",
    "injection",
    "conflict",
    "blocker",
    "invalid",
    "incompatible",
)


@dataclass
class CheckSummary:
    passed: int = 0
    failed: int = 0
    pending: int = 0


@dataclass
class ReviewSignal:
    source: str
    author: str
    is_bot: bool
    kind: str
    out_of_diff: bool
    url: str
    path: str
    category: str
    severity: str
    excerpt: str


@dataclass
class ReviewSummary:
    line_comments_total: int = 0
    issue_comments_total: int = 0
    reviews_total: int = 0
    out_of_diff_total: int = 0
    nitpick_total: int = 0
    actionable_total: int = 0
    actionable_blocking_total: int = 0
    bot_total: int = 0
    bot_out_of_diff_total: int = 0
    bot_nitpick_total: int = 0
    bot_actionable_total: int = 0
    actionable_signals: List[ReviewSignal] = field(default_factory=list)
    nitpick_signals: List[ReviewSignal] = field(default_factory=list)


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
    review: ReviewSummary
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


def _resolve_repo(explicit_repo: str, default_repo: str) -> str:
    """Honor explicit --repo; only inspect current checkout when omitted."""
    repo = explicit_repo.strip()
    if repo:
        return repo
    return _repo_name(default_repo)


def _repo_owner_name(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"invalid repo format: {repo!r} (expected owner/name)")
    owner, name = repo.split("/", 1)
    return owner.strip(), name.strip()


def _review_thread_flags(repo: str, number: int) -> dict[str, tuple[bool, bool]]:
    """Map review comment URL -> (is_resolved, is_outdated) from GraphQL review threads."""
    owner, name = _repo_owner_name(repo)
    flags: dict[str, tuple[bool, bool]] = {}
    cursor: str | None = None

    query = (
        "query($owner:String!,$name:String!,$number:Int!,$after:String){"
        "repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){"
        "reviewThreads(first:100,after:$after){"
        "nodes{isResolved isOutdated comments(first:100){nodes{url}}}"
        "pageInfo{hasNextPage endCursor}"
        "}}}}"
    )

    while True:
        cmd = [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
        ]
        if cursor:
            cmd.extend(["-F", f"after={cursor}"])
        payload = _run_json(cmd)
        if not isinstance(payload, dict):
            break
        data = payload.get("data")
        if not isinstance(data, dict):
            break
        repository = data.get("repository")
        if not isinstance(repository, dict):
            break
        pull_request = repository.get("pullRequest")
        if not isinstance(pull_request, dict):
            break
        review_threads = pull_request.get("reviewThreads")
        if not isinstance(review_threads, dict):
            break

        nodes = review_threads.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                is_resolved = bool(node.get("isResolved"))
                is_outdated = bool(node.get("isOutdated"))
                comments = node.get("comments")
                if not isinstance(comments, dict):
                    continue
                comment_nodes = comments.get("nodes")
                if not isinstance(comment_nodes, list):
                    continue
                for comment in comment_nodes:
                    if not isinstance(comment, dict):
                        continue
                    url = str(comment.get("url") or "").strip()
                    if not url:
                        continue
                    flags[url] = (is_resolved, is_outdated)

        page_info = review_threads.get("pageInfo")
        if not isinstance(page_info, dict):
            break
        has_next = bool(page_info.get("hasNextPage"))
        next_cursor = str(page_info.get("endCursor") or "").strip()
        if not has_next or not next_cursor:
            break
        cursor = next_cursor

    return flags


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


def _classify_comment(body: str) -> str:
    text = body.lower()
    if any(token in text for token in NITPICK_TOKENS):
        return "nitpick"
    if any(token in text for token in ACTIONABLE_TOKENS):
        return "actionable"
    return "info"


def _learning_category(body: str) -> str:
    text = body.lower()
    if any(token in text for token in ("security", "vulnerability", "unsafe", "injection", "leak", "auth")):
        return "Security & Validation"
    if any(token in text for token in ("audit-layers-static", "runtime", "gate", "ci", "workflow", "checks")):
        return "CI Gate Order"
    if any(token in text for token in ("network", "port", "compose", "container", "topology", "host reachability")):
        return "Runtime Port/Network Parity"
    if any(token in text for token in ("doc", "runbook", "comment", "readme")):
        return "Documentation Drift"
    return "General Quality"


def _severity(body: str) -> str:
    text = body.lower()
    if "[p0" in text:
        return "p0"
    if "[p1" in text:
        return "p1"
    if "[p2" in text:
        return "p2"
    return "unspecified"


def _excerpt(body: str, limit: int = 180) -> str:
    compact = " ".join((body or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _to_signal(
    *,
    source: str,
    author: str,
    body: str,
    url: str,
    path: str = "",
    out_of_diff: bool = False,
) -> ReviewSignal:
    kind = _classify_comment(body)
    return ReviewSignal(
        source=source,
        author=author,
        is_bot=author in BOT_REVIEW_LOGINS,
        kind=kind,
        out_of_diff=out_of_diff,
        url=url,
        path=path,
        category=_learning_category(body),
        severity=_severity(body),
        excerpt=_excerpt(body),
    )


def _collect_review_summary(repo: str, number: int, detail: dict[str, Any], *, head_sha: str) -> ReviewSummary:
    summary = ReviewSummary()
    signals: List[ReviewSignal] = []
    thread_flags = _review_thread_flags(repo, number)

    line_comments = _run_json(["gh", "api", f"repos/{repo}/pulls/{number}/comments"])
    if isinstance(line_comments, list):
        summary.line_comments_total = len(line_comments)
        for comment in line_comments:
            if not isinstance(comment, dict):
                continue
            user = comment.get("user")
            author = str(user.get("login") or "") if isinstance(user, dict) else ""
            body = str(comment.get("body") or "")
            url = str(comment.get("html_url") or "")
            path = str(comment.get("path") or "")
            is_resolved, is_thread_outdated = thread_flags.get(url, (False, False))
            if is_resolved:
                continue
            comment_commit = str(comment.get("commit_id") or "").strip().lower()
            is_stale_commit = bool(comment_commit and head_sha and comment_commit != head_sha.lower())
            out_of_diff = (
                comment.get("position") is None
                or comment.get("line") is None
                or is_stale_commit
                or is_thread_outdated
            )
            signals.append(
                _to_signal(
                    source="line_comment",
                    author=author,
                    body=body,
                    url=url,
                    path=path,
                    out_of_diff=out_of_diff,
                )
            )

    issue_comments = detail.get("comments")
    if isinstance(issue_comments, list):
        summary.issue_comments_total = len(issue_comments)
        for comment in issue_comments:
            if not isinstance(comment, dict):
                continue
            author_obj = comment.get("author")
            author = str(author_obj.get("login") or "") if isinstance(author_obj, dict) else ""
            body = str(comment.get("body") or "")
            url = str(comment.get("url") or "")
            signals.append(
                _to_signal(
                    source="issue_comment",
                    author=author,
                    body=body,
                    url=url,
                    out_of_diff=True,
                )
            )

    reviews = detail.get("reviews")
    if isinstance(reviews, list):
        summary.reviews_total = len(reviews)
        for review in reviews:
            if not isinstance(review, dict):
                continue
            author_obj = review.get("author")
            author = str(author_obj.get("login") or "") if isinstance(author_obj, dict) else ""
            body = str(review.get("body") or "")
            url = str(review.get("url") or "")
            if not body.strip():
                continue
            signals.append(
                _to_signal(
                    source="review_body",
                    author=author,
                    body=body,
                    url=url,
                    out_of_diff=True,
                )
            )

    for signal in signals:
        if signal.is_bot:
            summary.bot_total += 1
        if signal.out_of_diff:
            summary.out_of_diff_total += 1
            if signal.is_bot:
                summary.bot_out_of_diff_total += 1
        if signal.kind == "nitpick":
            summary.nitpick_total += 1
            summary.nitpick_signals.append(signal)
            if signal.is_bot:
                summary.bot_nitpick_total += 1
        if signal.kind == "actionable":
            summary.actionable_total += 1
            summary.actionable_signals.append(signal)
            if signal.is_bot:
                summary.bot_actionable_total += 1
            # Out-of-diff line comments are cataloged but non-blocking.
            if signal.source == "line_comment" and signal.out_of_diff:
                continue
            # Bot actionable comments block strict mode only for P0/P1.
            if signal.is_bot and signal.severity not in {"p0", "p1"}:
                continue
            summary.actionable_blocking_total += 1
    return summary


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
            "number,title,url,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup,comments,reviews",
        ]
    )
    if not isinstance(detail, dict):
        raise RuntimeError(f"invalid PR payload for #{number}")
    checks = _check_summary(detail.get("statusCheckRollup"))
    head_sha = str(detail.get("headRefOid") or "")
    review = _collect_review_summary(repo, number, detail, head_sha=head_sha)

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
    if review.actionable_blocking_total:
        blockers.append(f"actionable_comments={review.actionable_blocking_total}")

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
        review=review,
        blockers=blockers,
    )


def _print_table(items: list[PrSummary]) -> None:
    print(
        "| PR | Mergeable | Checks (P/F/Q) | Review (A/N/OOD) | Blockers | Title |",
        flush=True,
    )
    print("|---:|---|---|---|---|---|", flush=True)
    for item in items:
        checks = f"{item.checks.passed}/{item.checks.failed}/{item.checks.pending}"
        review = f"{item.review.actionable_total}/{item.review.nitpick_total}/{item.review.out_of_diff_total}"
        blockers = ", ".join(item.blockers) if item.blockers else "none"
        print(
            f"| #{item.number} | {item.mergeable}/{item.merge_state_status} | {checks} | {review} | {blockers} | {item.title} |",
            flush=True,
        )
    print("", flush=True)
    for item in items:
        print(f"#{item.number}: {item.url}", flush=True)


def _write_learnings(path: Path, items: list[PrSummary]) -> None:
    all_actionable: List[tuple[int, ReviewSignal]] = []
    all_nitpicks: List[tuple[int, ReviewSignal]] = []
    for item in items:
        all_actionable.extend((item.number, signal) for signal in item.review.actionable_signals)
        all_nitpicks.extend((item.number, signal) for signal in item.review.nitpick_signals)

    category_counts: dict[str, int] = {}
    for _, signal in all_actionable:
        category_counts[signal.category] = category_counts.get(signal.category, 0) + 1

    lines: list[str] = []
    lines.append("# PR Review Learnings Catalog")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## PR Summary")
    lines.append("")
    lines.append("| PR | Actionable | Nitpick | Out-of-Diff | Bot Actionable |")
    lines.append("|---:|---:|---:|---:|---:|")
    for item in items:
        lines.append(
            f"| #{item.number} | {item.review.actionable_total} | {item.review.nitpick_total} | "
            f"{item.review.out_of_diff_total} | {item.review.bot_actionable_total} |"
        )
    lines.append("")
    lines.append("## Actionable Learnings")
    lines.append("")
    if not all_actionable:
        lines.append("- No actionable review comments detected.")
    else:
        for pr_number, signal in all_actionable:
            source = signal.source
            ood = "out-of-diff" if signal.out_of_diff else "in-diff"
            loc = f" (`{signal.path}`)" if signal.path else ""
            lines.append(
                f"- PR #{pr_number} [{signal.category}] {source}/{ood} by `{signal.author}`{loc}: "
                f"{signal.excerpt} ({signal.url})"
            )
    lines.append("")
    lines.append("## Nitpick Queue")
    lines.append("")
    if not all_nitpicks:
        lines.append("- No nitpick comments detected.")
    else:
        for pr_number, signal in all_nitpicks:
            source = signal.source
            ood = "out-of-diff" if signal.out_of_diff else "in-diff"
            lines.append(
                f"- PR #{pr_number} {source}/{ood} by `{signal.author}`: {signal.excerpt} ({signal.url})"
            )
    lines.append("")
    lines.append("## Implementation Guidance")
    lines.append("")
    if not category_counts:
        lines.append("- No new implementation guidance required.")
    else:
        guidance_map = {
            "Security & Validation": "Apply allowlists, fail-closed auth, and error redaction patterns across services.",
            "CI Gate Order": "Keep static lanes dependency-free; move runtime probes to runtime certification targets.",
            "Runtime Port/Network Parity": "Resolve host ports from compose/docker inspect, avoid hardcoded host ports.",
            "Documentation Drift": "Update runbooks/MAKE targets when behavior or policy changes.",
            "General Quality": "Triaged as quality debt; schedule targeted cleanup PRs.",
        }
        for category, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True):
            guidance = guidance_map.get(category, guidance_map["General Quality"])
            lines.append(f"- `{category}` ({count}): {guidance}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default="",
        help="owner/repo override (default: auto-detect from current checkout, fallback POWERFULMOVES/PMOVES.AI)",
    )
    parser.add_argument("--base", default="PMOVES.AI-Edition-Hardened", help="base branch filter (default: PMOVES.AI-Edition-Hardened)")
    parser.add_argument("--state", default="open", choices=["open", "closed", "merged", "all"], help="PR state filter")
    parser.add_argument("--pr", dest="prs", action="append", type=int, default=[], help="monitor specific PR number (repeatable)")
    parser.add_argument("--json-out", type=Path, default=None, help="write full monitor payload as JSON")
    parser.add_argument("--learnings-out", type=Path, default=None, help="write actionable/nitpick learnings markdown")
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any PR has blockers")
    args = parser.parse_args(argv)

    repo = _resolve_repo(args.repo, "POWERFULMOVES/PMOVES.AI")
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
                "review": {
                    **asdict(item.review),
                    "actionable_signals": [asdict(signal) for signal in item.review.actionable_signals],
                    "nitpick_signals": [asdict(signal) for signal in item.review.nitpick_signals],
                },
            }
            for item in summaries
        ],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote JSON report: {args.json_out}")
    if args.learnings_out:
        _write_learnings(args.learnings_out, summaries)
        print(f"Wrote learnings report: {args.learnings_out}")

    if args.strict and any(item.blockers for item in summaries):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
