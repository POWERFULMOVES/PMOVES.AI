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
    author: str
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


# --- transport fallback -------------------------------------------------------
#
# GitHub enforces a SECONDARY rate limit that is separate from the documented
# hourly quota and INVISIBLE to `gh api rate_limit` -- that endpoint reports
# every bucket at full capacity while GraphQL refuses each request. It governs
# request rate and content-creating bursts, not volume, and it is scoped to the
# USER, so every node and agent sharing one PAT shares one budget.
#
# GraphQL trips first, and REST usually keeps working. Nearly everything this
# tool reads has a REST equivalent, so a throttled GraphQL endpoint should
# degrade the audit, not abort it. The one exception is review-thread
# RESOLUTION, which GitHub's REST API does not expose at all (confirmed against
# docs.github.com/en/rest/pulls/comments: a review comment carries no resolution
# field, and no REST endpoint returns thread state). That single gap is reported
# as UNMEASURED and blocks the merge -- never assumed to be zero.

_THROTTLE_MARKERS = (
    "rate limit",
    "secondary rate",
    "abuse detection",
    "submitted too quickly",
)


class ThreadsUnmeasured(RuntimeError):
    """Review-thread resolution could not be read. Never treated as 'none'."""


def _looks_throttled(text: str) -> bool:
    low = (text or "").casefold()
    return any(marker in low for marker in _THROTTLE_MARKERS)


def _rest(path: str, *extra: str) -> Any:
    return _run_json(["gh", "api", path, *extra])


def _rest_pages(path: str) -> List[Any]:
    """Every page of a paginated REST endpoint, as a list of page payloads.

    `--paginate` ALONE emits one JSON value PER PAGE, concatenated, and
    `json.loads` reads a single top-level value then chokes on the next. The
    gh manual is explicit: "Each page is a separate JSON array or object",
    and `--slurp` is what wraps them into one array.

    Without this the REST fallback aborts on any PR busy enough to paginate --
    which is precisely when an audit matters most.
    """
    payload = _run_json(["gh", "api", "--paginate", "--slurp", path])
    return payload if isinstance(payload, list) else []


def _pr_from_rest(repo: str, number: int) -> dict[str, Any]:
    """Rebuild the `gh pr view --json` shape from REST.

    Field-for-field, so every consumer downstream is unchanged. `state` and
    `mergeable` are re-spelled into GraphQL's vocabulary because the evaluator
    compares against MERGED/MERGEABLE/CONFLICTING.
    """
    pr = _rest(f"repos/{repo}/pulls/{number}")
    if not isinstance(pr, dict):
        raise RuntimeError(f"invalid REST PR payload for {repo}#{number}")

    if pr.get("merged"):
        state = "MERGED"
    else:
        state = "OPEN" if pr.get("state") == "open" else "CLOSED"

    mergeable_raw = pr.get("mergeable")
    mergeable = (
        "MERGEABLE" if mergeable_raw is True
        else "CONFLICTING" if mergeable_raw is False
        else "UNKNOWN"
    )

    # REST spells the merge state in lowercase with the same state names.
    merge_state = str(pr.get("mergeable_state") or "unknown").upper()

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("html_url"),
        "author": {"login": ((pr.get("user") or {}).get("login") or "")},
        "state": state,
        "isDraft": bool(pr.get("draft")),
        "baseRefName": (pr.get("base") or {}).get("ref"),
        "headRefOid": (pr.get("head") or {}).get("sha"),
        "mergeable": mergeable,
        "mergeStateStatus": merge_state,
        "reviewDecision": _review_decision_from_rest(repo, number),
        "body": pr.get("body") or "",
        # Left absent deliberately: required checks are fetched separately, and
        # a fabricated empty rollup would read as "no checks" rather than
        # "not fetched here".
        "statusCheckRollup": None,
    }


def _review_decision_from_rest(repo: str, number: int) -> str:
    """Derive reviewDecision, which REST does not expose directly.

    Latest review per reviewer wins, matching how GitHub computes it. Errs
    toward REVIEW_REQUIRED: this value can only ADD a blocker, so guessing low
    is safe and guessing high would let a PR through.
    """
    reviews = [r for page in _rest_pages(f"repos/{repo}/pulls/{number}/reviews")
               for r in (page if isinstance(page, list) else [])]
    if not reviews:
        return "REVIEW_REQUIRED"
    latest: dict[str, str] = {}
    for review in reviews:
        if not isinstance(review, dict):
            continue
        state = str(review.get("state") or "").upper()
        if state in {"COMMENTED", "PENDING"}:
            continue  # neither approves nor blocks
        login = str((review.get("user") or {}).get("login") or "")
        if login:
            latest[login] = state
    if "CHANGES_REQUESTED" in latest.values():
        return "CHANGES_REQUESTED"
    if "APPROVED" in latest.values():
        return "APPROVED"
    return "REVIEW_REQUIRED"


def _required_checks_from_rest(repo: str, number: int, head_sha: str) -> list[dict[str, Any]]:
    """Required contexts from branch protection, resolved against check-runs."""
    pr = _rest(f"repos/{repo}/pulls/{number}")
    base = (pr or {}).get("base", {}).get("ref") or "main"
    try:
        protection = _rest(f"repos/{repo}/branches/{base}/protection")
    except RuntimeError:
        return []
    contexts = (
        ((protection or {}).get("required_status_checks") or {}).get("contexts") or []
    )
    if not contexts:
        return []

    # A required context can be EITHER a check-run or a legacy commit status,
    # and GitHub serves them from different endpoints. Reading only check-runs
    # would report a passing status context as "pending" forever -- this repo
    # has at least one (CodeRabbit), so the gap is real, not hypothetical.
    by_name: dict[str, dict[str, Any]] = {}

    runs = [r for page in _rest_pages(f"repos/{repo}/commits/{head_sha}/check-runs")
            for r in ((page or {}).get("check_runs", []) if isinstance(page, dict) else [])]
    for run in runs:
        if isinstance(run, dict) and run.get("name"):
            by_name[str(run["name"])] = run

    status_payload = _rest(f"repos/{repo}/commits/{head_sha}/status")
    for status in (status_payload or {}).get("statuses", []) if isinstance(status_payload, dict) else []:
        if not isinstance(status, dict) or not status.get("context"):
            continue
        name = str(status["context"])
        if name in by_name:
            continue  # a check-run of the same name is the richer record
        state = str(status.get("state") or "").casefold()
        by_name[name] = {
            "name": name,
            "status": "completed" if state in {"success", "failure", "error"} else "in_progress",
            "conclusion": {"success": "success", "failure": "failure", "error": "failure"}.get(state),
            "html_url": status.get("target_url") or "",
        }

    resolved: list[dict[str, Any]] = []
    for name in contexts:
        run = by_name.get(str(name))
        if run is None:
            bucket = "pending"
        elif run.get("status") != "completed":
            bucket = "pending"
        elif str(run.get("conclusion")) in {"success", "neutral", "skipped"}:
            bucket = "pass"
        else:
            bucket = "fail"
        resolved.append(
            {
                "name": str(name),
                "state": str((run or {}).get("conclusion") or (run or {}).get("status") or "PENDING").upper(),
                "bucket": bucket,
                "link": str((run or {}).get("html_url") or ""),
                "workflow": "",
            }
        )
    return resolved


def _repo_name(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    payload = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    if isinstance(payload, dict) and payload.get("nameWithOwner"):
        return str(payload["nameWithOwner"])
    return DEFAULT_REPO


def _fetch_pr(repo: str, number: int) -> dict[str, Any]:
    command = [
        "gh",
        "pr",
        "view",
        str(number),
        "--repo",
        repo,
        "--json",
        (
            "number,title,url,author,state,isDraft,baseRefName,headRefOid,"
            "mergeable,mergeStateStatus,reviewDecision,body,statusCheckRollup"
        ),
    ]
    proc = _run(command, allow_failure=True)
    if proc.returncode == 0 and proc.stdout.strip():
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid PR payload for {repo}#{number}")
        return payload
    # `gh pr view --json` is GraphQL. Only a THROTTLE earns the REST path -- any
    # other failure (bad number, no auth, network) must still surface, or the
    # fallback would paper over real errors.
    if not _looks_throttled(proc.stderr):
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"{proc.stderr.strip()}"
        )
    print(
        "[pr-closeout] GraphQL is throttled; reading the PR over REST instead.",
        file=sys.stderr,
    )
    return _pr_from_rest(repo, number)


def _fetch_required_checks(repo: str, number: int, head_sha: str = "") -> list[dict[str, Any]]:
    command = [
        "gh",
        "pr",
        "checks",
        str(number),
        "--repo",
        repo,
        "--required",
        "--json",
        "name,state,bucket,link,workflow",
    ]
    proc = _run(command, allow_failure=True)
    raw_payload = proc.stdout.strip()
    if not raw_payload:
        if "no required checks reported" in proc.stderr.casefold():
            return []
        if proc.returncode != 0 and _looks_throttled(proc.stderr):
            # `gh pr checks` is GraphQL. Branch protection + check-runs give the
            # same answer over REST: the required CONTEXTS, resolved against the
            # runs on this head. Same fail-closed rule as elsewhere -- only a
            # throttle takes this path.
            print(
                "[pr-closeout] GraphQL is throttled; resolving required checks "
                "over REST instead.",
                file=sys.stderr,
            )
            return _required_checks_from_rest(repo, number, head_sha)
        if proc.returncode != 0:
            raise RuntimeError(
                f"required-check query failed ({proc.returncode}): "
                f"{' '.join(command)}\n{proc.stderr.strip()}"
            )
        return []
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"invalid required-check JSON for {repo}#{number}: {exc}\n"
            f"{raw_payload[:500]}"
        ) from exc
    if not isinstance(payload, list):
        raise RuntimeError(f"invalid required-check payload for {repo}#{number}")
    return [item for item in payload if isinstance(item, dict)]


def _fetch_threads(repo: str, number: int) -> list[Any]:
    """Review threads, or ThreadsUnmeasured when GraphQL will not answer.

    There is no REST fallback for this one: GitHub's REST API exposes review
    COMMENTS but never a thread's resolution state, so `isResolved` is
    reachable only through GraphQL. Returning [] here would read as "no
    unresolved threads" and let a PR merge over live review feedback, which is
    the single worst thing this tool could do. It refuses instead.
    """
    # Import lazily so pure evaluator tests do not need a live GitHub session.
    from pr_hedge_trim import fetch_threads

    try:
        return fetch_threads(repo, number)
    except Exception as exc:  # noqa: BLE001 - transport shape varies by caller
        if _looks_throttled(str(exc)):
            raise ThreadsUnmeasured(str(exc)) from exc
        raise


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


def _console_safe(value: object, encoding: str | None) -> str:
    text = str(value)
    if not encoding:
        return text
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def _print_console(value: object = "") -> None:
    print(_console_safe(value, getattr(sys.stdout, "encoding", None)))


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
            if state in {"PENDING", "EXPECTED", ""}:
                _append_blocker(report.blockers, f"pending status context: {name}")
            elif name in allowed_advisory_failures:
                report.advisory_failures.append(detail)
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
    expected_admin_author: str = "",
    allowed_advisory_failures: Iterable[str] = (),
    threads_unmeasured: str = "",
) -> CloseoutReport:
    """Evaluate a PR snapshot without mutating GitHub state.

    ``threads_unmeasured``, when non-empty, means review-thread resolution
    could not be READ (GraphQL unavailable, and REST does not expose it). It
    becomes a blocker in its own right, because an unread thread set is not an
    empty one.
    """

    head_sha = str(pr.get("headRefOid") or "")
    author_data = pr.get("author")
    author = (
        str(author_data.get("login") or "")
        if isinstance(author_data, dict)
        else str(author_data or "")
    )
    report = CloseoutReport(
        repo=repo,
        pr_number=int(pr.get("number") or 0),
        title=str(pr.get("title") or ""),
        url=str(pr.get("url") or ""),
        author=author,
        state=str(pr.get("state") or "UNKNOWN").upper(),
        base=str(pr.get("baseRefName") or ""),
        head_sha=head_sha,
        expected_head_sha=expected_head_sha,
        is_draft=bool(pr.get("isDraft")),
        mergeable=str(pr.get("mergeable") or "UNKNOWN").upper(),
        merge_state_status=str(pr.get("mergeStateStatus") or "UNKNOWN").upper(),
        review_decision=str(pr.get("reviewDecision") or "REVIEW_REQUIRED").upper(),
    )
    admin_bypass_authorized = bool(
        allow_admin_review_bypass
        and expected_admin_author
        and report.author.casefold() == expected_admin_author.casefold()
    )

    if allow_admin_review_bypass and not admin_bypass_authorized:
        _append_blocker(
            report.blockers,
            "admin review bypass denied: "
            f"PR author {report.author or 'UNKNOWN'} does not match "
            f"expected author {expected_admin_author or 'UNSET'}",
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
    elif report.merge_state_status == "BLOCKED" and not admin_bypass_authorized:
        _append_blocker(report.blockers, "merge state is BLOCKED")

    if report.review_decision == "CHANGES_REQUESTED":
        _append_blocker(report.blockers, "review changes are requested")
    elif report.review_decision != "APPROVED" and not admin_bypass_authorized:
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
    if threads_unmeasured:
        _append_blocker(
            report.blockers,
            "unresolved review threads: COULD NOT MEASURE -- GitHub REST does "
            "not expose thread resolution and GraphQL was unavailable "
            f"({threads_unmeasured}). Not assumed to be zero.",
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
    expected_admin_author: str = "",
    allowed_advisory_failures: Iterable[str] = (),
) -> CloseoutReport:
    pr = _fetch_pr(repo, number)
    required_checks = _fetch_required_checks(repo, number, str(pr.get("headRefOid") or ""))
    try:
        threads = _fetch_threads(repo, number)
        threads_unmeasured = ""
    except ThreadsUnmeasured as exc:
        # GraphQL is throttled and REST cannot answer this. Report it as a
        # blocker naming the gap -- the rest of the audit still runs, so the
        # operator sees which checks are green and exactly what is unknown,
        # instead of the whole tool aborting on one unavailable transport.
        threads = []
        threads_unmeasured = str(exc)[:160] or "GraphQL unavailable"
    return evaluate_closeout(
        pr,
        required_checks,
        threads,
        repo=repo,
        expected_head_sha=expected_head_sha,
        expected_base=expected_base,
        allow_admin_review_bypass=allow_admin_review_bypass,
        expected_admin_author=expected_admin_author,
        allowed_advisory_failures=allowed_advisory_failures,
        threads_unmeasured=threads_unmeasured,
    )


def _print_report(report: CloseoutReport) -> None:
    verdict = "READY" if report.ready else "BLOCKED"
    _print_console(
        f"PR #{report.pr_number} closeout: {verdict}\n"
        f"  URL: {report.url}\n"
        f"  Author: {report.author}\n"
        f"  Head: {report.head_sha}\n"
        f"  Base: {report.base}\n"
        f"  Merge: {report.mergeable}/{report.merge_state_status}\n"
        f"  Review: {report.review_decision}\n"
        f"  Required checks: {sum(1 for c in report.required_checks if c.get('bucket') in PASS_REQUIRED_BUCKETS)}/{len(report.required_checks)} green\n"
        f"  Unchecked tasks: {len(report.unchecked_tasks)}\n"
        f"  Unresolved threads: {len(report.unresolved_threads)}\n"
        f"  Allowed advisory failures: {len(report.advisory_failures)}"
    )
    if report.blockers:
        _print_console("Blockers:")
        for blocker in report.blockers:
            _print_console(f"  - {blocker}")
    if report.unresolved_threads:
        _print_console("Unresolved threads:")
        for thread in report.unresolved_threads:
            location = thread.path or "unknown-path"
            if thread.line is not None:
                location = f"{location}:{thread.line}"
            _print_console(
                f"  - [{thread.classification}] {location} "
                f"{thread.url or thread.thread_id}"
            )
    if report.unchecked_tasks:
        _print_console("Unchecked tasks:")
        for task in report.unchecked_tasks:
            _print_console(f"  - {task}")


def _write_json(report: CloseoutReport, path: str) -> None:
    if path == "-":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=True))
        return
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
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
        "--admin-author",
        default="",
        help="required PR author login when using an admin review bypass",
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
    if admin_bypass and not args.admin_author:
        parser.error("admin review bypass requires --admin-author")
    report = audit_pr(
        repo,
        args.pr,
        expected_head_sha=args.expected_head,
        expected_base=args.base,
        allow_admin_review_bypass=admin_bypass,
        expected_admin_author=args.admin_author,
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
