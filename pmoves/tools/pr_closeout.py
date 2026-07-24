#!/usr/bin/env python3
"""Fail-closed pull-request closeout audit and guarded merge.

This tool composes the repository's existing PR monitor and hedge-trim lanes
into the final merge gate. It never fixes or resolves review comments itself:
an actionable thread must be fixed, replied to, and resolved before this gate
can pass.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"
PASS_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
PASS_CONTEXT_STATES = {"SUCCESS"}
PASS_REQUIRED_BUCKETS = {"pass"}
UNCHECKED_TASK_RE = re.compile(r"(?im)^\s*[-*]\s+\[\s\]\s+(.+?)\s*$")


@dataclass
class ThreadBlocker:
    thread_id: str
    classification: str
    path: str
    line: int | None
    url: str
    is_outdated: bool


@dataclass
class CloseoutReport:
    repo: str
    pr_number: int
    title: str
    url: str
    state: str
    base: str
    head_sha: str
    expected_head_sha: str
    is_draft: bool
    mergeable: str
    merge_state_status: str
    review_decision: str
    required_checks: list[dict[str, str]] = field(default_factory=list)
    advisory_failures: list[dict[str, str]] = field(default_factory=list)
    unchecked_tasks: list[str] = field(default_factory=list)
    unresolved_threads: list[ThreadBlocker] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready"] = self.ready
        return payload


def _run(
    command: list[str],
    *,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    if proc.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"{proc.stderr.strip()}"
        )
    return proc


def _run_json(command: list[str], *, allow_failure: bool = False) -> Any:
    proc = _run(command, allow_failure=allow_failure)
    payload = proc.stdout.strip()
    if not payload:
        if proc.returncode != 0:
            raise RuntimeError(
                f"command returned no JSON ({proc.returncode}): {' '.join(command)}\n"
                f"{proc.stderr.strip()}"
            )
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"invalid JSON from {' '.join(command)}: {exc}\n{payload[:500]}"
        ) from exc


def _repo_name(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    payload = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    if isinstance(payload, dict) and payload.get("nameWithOwner"):
        return str(payload["nameWithOwner"])
    return DEFAULT_REPO


def _fetch_pr(repo: str, number: int) -> dict[str, Any]:
    payload = _run_json(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            (
                "number,title,url,state,isDraft,baseRefName,headRefOid,mergeable,"
                "mergeStateStatus,reviewDecision,body,statusCheckRollup"
            ),
        ]
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid PR payload for {repo}#{number}")
    return payload


def _fetch_required_checks(repo: str, number: int) -> list[dict[str, Any]]:
    payload = _run_json(
        [
            "gh",
            "pr",
            "checks",
            str(number),
            "--repo",
            repo,
            "--required",
            "--json",
            "name,state,bucket,link,workflow",
        ],
        allow_failure=True,
    )
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise RuntimeError(f"invalid required-check payload for {repo}#{number}")
    return [item for item in payload if isinstance(item, dict)]


def _fetch_threads(repo: str, number: int) -> list[Any]:
    # Import lazily so pure evaluator tests do not need a live GitHub session.
    from pr_hedge_trim import fetch_threads

    return fetch_threads(repo, number)


def _value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _first_thread_url(thread: Any) -> str:
    comments = _value(thread, "comments", [])
    if isinstance(comments, list) and comments:
        return str(_value(comments[0], "url", ""))
    return ""


def _append_blocker(blockers: list[str], message: str) -> None:
    if message not in blockers:
        blockers.append(message)


def _evaluate_rollup(
    rollup: Any,
    *,
    allowed_advisory_failures: set[str],
    report: CloseoutReport,
) -> None:
    if not isinstance(rollup, list):
        _append_blocker(report.blockers, "status check rollup is unavailable")
        return

    for item in rollup:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("__typename") or "")
        name = str(item.get("name") or item.get("context") or "unnamed-check")
        url = str(item.get("detailsUrl") or item.get("targetUrl") or "")

        if kind == "StatusContext" or "context" in item:
            state = str(item.get("state") or "").upper()
            if state in PASS_CONTEXT_STATES:
                continue
            detail = {"name": name, "state": state or "UNKNOWN", "url": url}
            if name in allowed_advisory_failures:
                report.advisory_failures.append(detail)
                continue
            if state in {"PENDING", "EXPECTED", ""}:
                _append_blocker(report.blockers, f"pending status context: {name}")
            else:
                _append_blocker(
                    report.blockers,
                    f"failed status context: {name} ({state or 'UNKNOWN'})",
                )
            continue

        status = str(item.get("status") or "").upper()
        conclusion = str(item.get("conclusion") or "").upper()
        if status != "COMPLETED":
            _append_blocker(report.blockers, f"pending check: {name}")
            continue
        if conclusion not in PASS_CONCLUSIONS:
            detail = {
                "name": name,
                "state": conclusion or "UNKNOWN",
                "url": url,
            }
            if name in allowed_advisory_failures:
                report.advisory_failures.append(detail)
                continue
            _append_blocker(
                report.blockers,
                f"failed check: {name} ({conclusion or 'UNKNOWN'})",
            )


def evaluate_closeout(
    pr: dict[str, Any],
    required_checks: Iterable[dict[str, Any]],
    threads: Iterable[Any],
    *,
    repo: str,
    expected_head_sha: str = "",
    expected_base: str = "main",
    allow_admin_review_bypass: bool = False,
    allowed_advisory_failures: Iterable[str] = (),
) -> CloseoutReport:
    """Evaluate a PR snapshot without mutating GitHub state."""

    head_sha = str(pr.get("headRefOid") or "")
    report = CloseoutReport(
        repo=repo,
        pr_number=int(pr.get("number") or 0),
        title=str(pr.get("title") or ""),
        url=str(pr.get("url") or ""),
        state=str(pr.get("state") or "UNKNOWN").upper(),
        base=str(pr.get("baseRefName") or ""),
        head_sha=head_sha,
        expected_head_sha=expected_head_sha,
        is_draft=bool(pr.get("isDraft")),
        mergeable=str(pr.get("mergeable") or "UNKNOWN").upper(),
        merge_state_status=str(pr.get("mergeStateStatus") or "UNKNOWN").upper(),
        review_decision=str(pr.get("reviewDecision") or "REVIEW_REQUIRED").upper(),
    )

    if report.state != "OPEN":
        _append_blocker(report.blockers, f"PR state is {report.state}, not OPEN")
    if report.is_draft:
        _append_blocker(report.blockers, "PR is still a draft")
    if report.base != expected_base:
        _append_blocker(
            report.blockers,
            f"base branch is {report.base or 'UNKNOWN'}, expected {expected_base}",
        )
    if not head_sha:
        _append_blocker(report.blockers, "head SHA is unavailable")
    if expected_head_sha and head_sha != expected_head_sha:
        _append_blocker(
            report.blockers,
            f"head SHA changed: expected {expected_head_sha}, found {head_sha}",
        )
    if report.mergeable != "MERGEABLE":
        _append_blocker(
            report.blockers,
            f"mergeable state is {report.mergeable}",
        )

    if report.merge_state_status == "BEHIND":
        _append_blocker(report.blockers, "branch is behind the current base")
    elif report.merge_state_status in {"DIRTY", "UNKNOWN", "DRAFT"}:
        _append_blocker(
            report.blockers,
            f"merge state is {report.merge_state_status}",
        )
    elif report.merge_state_status == "BLOCKED" and not allow_admin_review_bypass:
        _append_blocker(report.blockers, "merge state is BLOCKED")

    if report.review_decision == "CHANGES_REQUESTED":
        _append_blocker(report.blockers, "review changes are requested")
    elif report.review_decision != "APPROVED" and not allow_admin_review_bypass:
        _append_blocker(
            report.blockers,
            f"review decision is {report.review_decision}",
        )

    body = str(pr.get("body") or "")
    report.unchecked_tasks = [
        match.group(1).strip() for match in UNCHECKED_TASK_RE.finditer(body)
    ]
    if report.unchecked_tasks:
        _append_blocker(
            report.blockers,
            f"unchecked PR tasks: {len(report.unchecked_tasks)}",
        )

    for thread in threads:
        if bool(_value(thread, "is_resolved", False)):
            continue
        line_value = _value(thread, "first_line", None)
        line = int(line_value) if isinstance(line_value, int) else None
        report.unresolved_threads.append(
            ThreadBlocker(
                thread_id=str(_value(thread, "thread_id", "")),
                classification=str(_value(thread, "classification", "unknown")),
                path=str(_value(thread, "first_path", "")),
                line=line,
                url=_first_thread_url(thread),
                is_outdated=bool(_value(thread, "is_outdated", False)),
            )
        )
    if report.unresolved_threads:
        _append_blocker(
            report.blockers,
            f"unresolved review threads: {len(report.unresolved_threads)}",
        )

    required_list = list(required_checks)
    if not required_list:
        _append_blocker(report.blockers, "no required checks were reported")
    for item in required_list:
        name = str(item.get("name") or "unnamed-required-check")
        bucket = str(item.get("bucket") or "").lower()
        state = str(item.get("state") or "UNKNOWN").upper()
        report.required_checks.append(
            {
                "name": name,
                "bucket": bucket or "unknown",
                "state": state,
                "url": str(item.get("link") or ""),
            }
        )
        if bucket not in PASS_REQUIRED_BUCKETS:
            _append_blocker(
                report.blockers,
                f"required check is not green: {name} ({bucket or state})",
            )

    _evaluate_rollup(
        pr.get("statusCheckRollup"),
        allowed_advisory_failures={
            item.strip() for item in allowed_advisory_failures if item.strip()
        },
        report=report,
    )
    return report


def audit_pr(
    repo: str,
    number: int,
    *,
    expected_head_sha: str = "",
    expected_base: str = "main",
    allow_admin_review_bypass: bool = False,
    allowed_advisory_failures: Iterable[str] = (),
) -> CloseoutReport:
    pr = _fetch_pr(repo, number)
    required_checks = _fetch_required_checks(repo, number)
    threads = _fetch_threads(repo, number)
    return evaluate_closeout(
        pr,
        required_checks,
        threads,
        repo=repo,
        expected_head_sha=expected_head_sha,
        expected_base=expected_base,
        allow_admin_review_bypass=allow_admin_review_bypass,
        allowed_advisory_failures=allowed_advisory_failures,
    )


def _print_report(report: CloseoutReport) -> None:
    verdict = "READY" if report.ready else "BLOCKED"
    print(
        f"PR #{report.pr_number} closeout: {verdict}\n"
        f"  URL: {report.url}\n"
        f"  Head: {report.head_sha}\n"
        f"  Base: {report.base}\n"
        f"  Merge: {report.mergeable}/{report.merge_state_status}\n"
        f"  Review: {report.review_decision}\n"
        f"  Required checks: {len(report.required_checks)} green\n"
        f"  Unchecked tasks: {len(report.unchecked_tasks)}\n"
        f"  Unresolved threads: {len(report.unresolved_threads)}\n"
        f"  Allowed advisory failures: {len(report.advisory_failures)}"
    )
    if report.blockers:
        print("Blockers:")
        for blocker in report.blockers:
            print(f"  - {blocker}")
    if report.unresolved_threads:
        print("Unresolved threads:")
        for thread in report.unresolved_threads:
            location = thread.path or "unknown-path"
            if thread.line is not None:
                location = f"{location}:{thread.line}"
            print(
                f"  - [{thread.classification}] {location} "
                f"{thread.url or thread.thread_id}"
            )
    if report.unchecked_tasks:
        print("Unchecked tasks:")
        for task in report.unchecked_tasks:
            print(f"  - {task}")


def _write_json(report: CloseoutReport, path: str) -> None:
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if path == "-":
        print(payload, end="")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _merge(
    report: CloseoutReport,
    *,
    method: str,
    admin: bool,
    confirmation: str,
) -> dict[str, Any]:
    expected_confirmation = f"MERGE #{report.pr_number} @ {report.head_sha}"
    if confirmation != expected_confirmation:
        raise RuntimeError(
            f"confirmation mismatch; expected exactly: {expected_confirmation}"
        )
    if not report.ready:
        raise RuntimeError("refusing merge because the closeout audit is blocked")

    command = [
        "gh",
        "pr",
        "merge",
        str(report.pr_number),
        "--repo",
        report.repo,
        f"--{method}",
        "--match-head-commit",
        report.head_sha,
    ]
    if admin:
        command.append("--admin")
    _run(command)

    merged = _run_json(
        [
            "gh",
            "pr",
            "view",
            str(report.pr_number),
            "--repo",
            report.repo,
            "--json",
            "state,mergedAt,mergeCommit,url",
        ]
    )
    if not isinstance(merged, dict) or str(merged.get("state")) != "MERGED":
        raise RuntimeError("merge command returned without a confirmed MERGED state")
    return merged


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument(
        "--expected-head",
        default="",
        help="exact reviewed head SHA; required for merge",
    )
    parser.add_argument(
        "--base",
        default="main",
        help="expected base branch (default: main)",
    )
    parser.add_argument(
        "--allow-advisory-failure",
        action="append",
        default=[],
        help="non-required check/status name allowed to fail (repeatable)",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="write audit JSON to this path; use '-' for stdout",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default="",
        help="owner/repo override (default: detect current checkout)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="audit PR closeout readiness")
    _add_common_args(audit)
    audit.add_argument(
        "--admin-review-bypass",
        action="store_true",
        help="allow REVIEW_REQUIRED/BLOCKED when all non-review gates pass",
    )

    merge = sub.add_parser("merge", help="audit and merge an exact PR head")
    _add_common_args(merge)
    merge.add_argument(
        "--method",
        choices=["squash", "rebase", "merge"],
        default="squash",
    )
    merge.add_argument(
        "--admin",
        action="store_true",
        help="use the repository's sanctioned admin merge path",
    )
    merge.add_argument(
        "--confirm",
        required=True,
        help='must equal "MERGE #<PR> @ <full-head-sha>"',
    )

    args = parser.parse_args(argv)
    repo = _repo_name(args.repo)
    if args.command == "merge" and not args.expected_head:
        parser.error("merge requires --expected-head")

    admin_bypass = bool(
        getattr(args, "admin_review_bypass", False) or getattr(args, "admin", False)
    )
    report = audit_pr(
        repo,
        args.pr,
        expected_head_sha=args.expected_head,
        expected_base=args.base,
        allow_admin_review_bypass=admin_bypass,
        allowed_advisory_failures=args.allow_advisory_failure,
    )
    _print_report(report)
    if args.json_out:
        _write_json(report, args.json_out)

    if args.command == "audit":
        return 0 if report.ready else 1
    if not report.ready:
        return 1

    try:
        merged = _merge(
            report,
            method=args.method,
            admin=args.admin,
            confirmation=args.confirm,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"Merged PR #{report.pr_number}: "
        f"{(merged.get('mergeCommit') or {}).get('oid', 'unknown')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
