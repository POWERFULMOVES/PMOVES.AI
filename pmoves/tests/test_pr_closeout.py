"""Tests for the fail-closed PR closeout evaluator."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

pr_closeout = pytest.importorskip("pr_closeout")


@dataclass
class Comment:
    url: str


@dataclass
class Thread:
    thread_id: str = "THREAD_1"
    is_resolved: bool = False
    is_outdated: bool = False
    classification: str = "actionable"
    first_path: str = "pmoves/example.py"
    first_line: int | None = 10
    comments: list[Comment] | None = None

    def __post_init__(self) -> None:
        if self.comments is None:
            self.comments = [Comment("https://example.test/thread/1")]


def _pr(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "number": 42,
        "title": "fix: example",
        "url": "https://github.com/POWERFULMOVES/PMOVES.AI/pull/42",
        "author": {"login": "POWERFULMOVES"},
        "state": "OPEN",
        "isDraft": False,
        "baseRefName": "main",
        "headRefOid": "a" * 40,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": "REVIEW_REQUIRED",
        "body": "## Checklist\n\n- [x] tests passed\n",
        "statusCheckRollup": [
            {
                "__typename": "CheckRun",
                "name": "python-tests",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "detailsUrl": "https://example.test/check/1",
            },
            {
                "__typename": "StatusContext",
                "context": "CodeRabbit",
                "state": "FAILURE",
                "targetUrl": "",
            },
        ],
    }
    payload.update(overrides)
    return payload


def _required(bucket: str = "pass") -> list[dict[str, str]]:
    return [
        {
            "name": "python-tests",
            "state": "SUCCESS" if bucket == "pass" else "FAILURE",
            "bucket": bucket,
            "link": "https://example.test/check/1",
            "workflow": "Merge Gate",
        }
    ]


def _evaluate(
    *,
    pr: dict[str, object] | None = None,
    required: list[dict[str, str]] | None = None,
    threads: list[Thread] | None = None,
    admin: bool = True,
    expected_admin_author: str = "POWERFULMOVES",
    expected_head: str = "a" * 40,
    allowed_advisories: tuple[str, ...] = ("CodeRabbit",),
) -> pr_closeout.CloseoutReport:
    return pr_closeout.evaluate_closeout(
        pr or _pr(),
        _required() if required is None else required,
        [] if threads is None else threads,
        repo="POWERFULMOVES/PMOVES.AI",
        expected_head_sha=expected_head,
        expected_base="main",
        allow_admin_review_bypass=admin,
        expected_admin_author=expected_admin_author,
        allowed_advisory_failures=allowed_advisories,
    )


def test_admin_closeout_allows_review_required_but_not_other_gates() -> None:
    report = _evaluate()

    assert report.ready
    assert report.blockers == []
    assert report.advisory_failures == [
        {"name": "CodeRabbit", "state": "FAILURE", "url": ""}
    ]


def test_normal_closeout_requires_approval() -> None:
    report = _evaluate(admin=False)

    assert not report.ready
    assert "merge state is BLOCKED" in report.blockers
    assert "review decision is REVIEW_REQUIRED" in report.blockers


def test_admin_closeout_requires_matching_pr_author() -> None:
    report = _evaluate(pr=_pr(author={"login": "dependabot[bot]"}))

    assert not report.ready
    assert (
        "admin review bypass denied: PR author dependabot[bot] does not match "
        "expected author POWERFULMOVES"
    ) in report.blockers
    assert "merge state is BLOCKED" in report.blockers
    assert "review decision is REVIEW_REQUIRED" in report.blockers


def test_changes_requested_blocks_even_admin_closeout() -> None:
    report = _evaluate(pr=_pr(reviewDecision="CHANGES_REQUESTED"))

    assert not report.ready
    assert "review changes are requested" in report.blockers


def test_unchecked_tasks_unresolved_threads_and_stale_head_block() -> None:
    report = _evaluate(
        pr=_pr(
            body="- [ ] publish evidence\n* [ ] finish runbook\n",
            headRefOid="b" * 40,
            mergeStateStatus="BEHIND",
        ),
        threads=[Thread()],
    )

    assert not report.ready
    assert "branch is behind the current base" in report.blockers
    assert any(item.startswith("head SHA changed:") for item in report.blockers)
    assert "unchecked PR tasks: 2" in report.blockers
    assert "unresolved review threads: 1" in report.blockers
    assert report.unchecked_tasks == ["publish evidence", "finish runbook"]
    assert report.unresolved_threads[0].path == "pmoves/example.py"


def test_required_and_nonrequired_failures_block() -> None:
    failing_rollup = [
        {
            "__typename": "CheckRun",
            "name": "CodeQL",
            "status": "COMPLETED",
            "conclusion": "FAILURE",
            "detailsUrl": "https://example.test/check/2",
        }
    ]
    report = _evaluate(
        pr=_pr(statusCheckRollup=failing_rollup),
        required=_required("fail"),
        allowed_advisories=(),
    )

    assert not report.ready
    assert "required check is not green: python-tests (fail)" in report.blockers
    assert "failed check: CodeQL (FAILURE)" in report.blockers


def test_pending_check_blocks() -> None:
    report = _evaluate(
        pr=_pr(
            statusCheckRollup=[
                {
                    "__typename": "CheckRun",
                    "name": "CodeQL",
                    "status": "IN_PROGRESS",
                    "conclusion": "",
                }
            ]
        )
    )

    assert not report.ready
    assert "pending check: CodeQL" in report.blockers


def test_pending_advisory_status_context_still_blocks() -> None:
    report = _evaluate(
        pr=_pr(
            statusCheckRollup=[
                {
                    "__typename": "StatusContext",
                    "context": "CodeRabbit",
                    "state": "PENDING",
                }
            ]
        )
    )

    assert not report.ready
    assert "pending status context: CodeRabbit" in report.blockers
    assert report.advisory_failures == []


def test_missing_required_checks_fails_closed() -> None:
    report = _evaluate(required=[])

    assert not report.ready
    assert "no required checks were reported" in report.blockers


def test_resolved_threads_do_not_block() -> None:
    report = _evaluate(threads=[Thread(is_resolved=True)])

    assert report.ready
    assert report.unresolved_threads == []


def test_confirmation_is_pinned_to_full_head_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _evaluate()
    called = False

    def unexpected_run(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(pr_closeout, "_run", unexpected_run)

    with pytest.raises(RuntimeError, match="confirmation mismatch"):
        pr_closeout._merge(
            report,
            method="squash",
            admin=True,
            confirmation="MERGE #42 @ short-sha",
        )
    assert not called
