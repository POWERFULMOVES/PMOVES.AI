"""Tests for the fail-closed PR closeout evaluator."""

from __future__ import annotations

import subprocess
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


def test_fetch_required_checks_treats_gh_no_checks_result_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = subprocess.CompletedProcess(
        args=["gh", "pr", "checks"],
        returncode=1,
        stdout="",
        stderr="no required checks reported on the 'stale-branch' branch\n",
    )
    monkeypatch.setattr(pr_closeout, "_run", lambda *args, **kwargs: result)

    assert pr_closeout._fetch_required_checks("OWNER/REPO", 42) == []


def test_fetch_required_checks_preserves_unexpected_gh_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = subprocess.CompletedProcess(
        args=["gh", "pr", "checks"],
        returncode=1,
        stdout="",
        stderr="HTTP 401: Bad credentials\n",
    )
    monkeypatch.setattr(pr_closeout, "_run", lambda *args, **kwargs: result)

    with pytest.raises(RuntimeError, match="required-check query failed"):
        pr_closeout._fetch_required_checks("OWNER/REPO", 42)


def test_console_safe_escapes_unencodable_pr_text() -> None:
    assert (
        pr_closeout._console_safe("approve → publish", "cp1252")
        == "approve \\u2192 publish"
    )


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


# --- transport fallback: GraphQL throttled, REST still answers ----------------
#
# GitHub's SECONDARY rate limit is invisible to `gh api rate_limit` (every
# bucket reports full capacity while GraphQL refuses every request) and is
# scoped to the USER, so one throttled agent stops the whole fleet's merges.
# Most of what this tool reads has a REST equivalent. Review-thread RESOLUTION
# does not -- confirmed against GitHub's REST docs -- so that one gap must be
# reported, never assumed away.


def test_unmeasured_threads_block_the_merge():
    """An unread thread set is not an empty one."""
    report = pr_closeout.evaluate_closeout(
        _pr(), _required(), [], repo="o/r",
        allow_admin_review_bypass=True, expected_admin_author="POWERFULMOVES",
        threads_unmeasured="secondary rate limit",
    )
    assert not report.ready
    joined = " ".join(report.blockers)
    assert "COULD NOT MEASURE" in joined
    assert "Not assumed to be zero" in joined


def test_measured_empty_threads_do_not_block():
    """Negative control. Without this the blocker could fire unconditionally
    and the test above would still pass."""
    report = pr_closeout.evaluate_closeout(
        _pr(), _required(), [], repo="o/r",
        allow_admin_review_bypass=True, expected_admin_author="POWERFULMOVES",
        threads_unmeasured="",
    )
    assert not any("COULD NOT MEASURE" in b for b in report.blockers)


@pytest.mark.parametrize(
    "message",
    [
        "API rate limit already exceeded for user ID 142271328.",
        "You have exceeded a secondary rate limit",
        "was submitted too quickly",
        "triggered an abuse detection mechanism",
    ],
)
def test_throttle_messages_are_recognised(message):
    assert pr_closeout._looks_throttled(message)


@pytest.mark.parametrize(
    "message",
    ["Could not resolve to a PullRequest", "Bad credentials", "network unreachable", ""],
)
def test_other_failures_are_not_treated_as_throttle(message):
    """A real error must surface, not silently take the REST path — otherwise
    the fallback papers over bad auth and wrong PR numbers."""
    assert not pr_closeout._looks_throttled(message)


def test_rest_payload_is_respelled_into_the_graphql_vocabulary(monkeypatch):
    """The evaluator compares against MERGED/MERGEABLE, which REST does not use."""
    def fake_rest(path, *extra):
        if path.endswith("/reviews"):
            return []
        return {
            "number": 42, "title": "t", "html_url": "u", "user": {"login": "POWERFULMOVES"},
            "state": "open", "merged": False, "draft": False,
            "base": {"ref": "main"}, "head": {"sha": "b" * 40},
            "mergeable": True, "mergeable_state": "blocked", "body": "",
        }
    _install_rest(monkeypatch, fake_rest)
    pr = pr_closeout._pr_from_rest("o/r", 42)
    assert pr["state"] == "OPEN"
    assert pr["mergeable"] == "MERGEABLE"
    assert pr["mergeStateStatus"] == "BLOCKED"
    assert pr["headRefOid"] == "b" * 40


def test_a_merged_pr_reads_as_MERGED_not_CLOSED(monkeypatch):
    """REST spells merged as state=closed + merged=true. Collapsing that to
    CLOSED would break the post-merge verification."""
    def fake_rest(path, *extra):
        if path.endswith("/reviews"):
            return []
        return {"number": 1, "state": "closed", "merged": True, "head": {"sha": "c" * 40},
                "base": {"ref": "main"}, "user": {"login": "x"}, "mergeable": None}
    _install_rest(monkeypatch, fake_rest)
    assert pr_closeout._pr_from_rest("o/r", 1)["state"] == "MERGED"


def test_review_decision_errs_toward_REVIEW_REQUIRED(monkeypatch):
    """This value can only ADD a blocker, so guessing low is safe and guessing
    high would let a PR through."""
    _install_rest(monkeypatch, lambda p, *a: [])
    assert pr_closeout._review_decision_from_rest("o/r", 1) == "REVIEW_REQUIRED"


def test_changes_requested_beats_approval(monkeypatch):
    _install_rest(monkeypatch, lambda p, *a: [
        {"user": {"login": "a"}, "state": "APPROVED"},
        {"user": {"login": "b"}, "state": "CHANGES_REQUESTED"},
    ])
    assert pr_closeout._review_decision_from_rest("o/r", 1) == "CHANGES_REQUESTED"


def test_comments_are_not_approvals(monkeypatch):
    """A COMMENTED review neither approves nor blocks; counting it as approval
    would manufacture consent."""
    _install_rest(monkeypatch, lambda p, *a: [
        {"user": {"login": "a"}, "state": "COMMENTED"},
    ])
    assert pr_closeout._review_decision_from_rest("o/r", 1) == "REVIEW_REQUIRED"


def _rest_payload(protection_contexts, check_runs=(), statuses=()):
    def fake(path, *extra):
        if path.endswith("/protection"):
            return {"required_status_checks": {"contexts": list(protection_contexts)}}
        if "/check-runs" in path:
            return {"check_runs": list(check_runs)}
        if path.endswith("/status"):
            return {"statuses": list(statuses)}
        return {"base": {"ref": "main"}}
    return fake


def _install_rest(monkeypatch, payload_fn):
    """Stub BOTH REST entry points.

    `_rest_pages` returns a list of PAGE payloads, so the single-page stub is
    wrapped in one page -- mirroring what `gh api --paginate --slurp` actually
    returns. Stubbing only `_rest` would leave the paginated call sites hitting
    the network.
    """
    monkeypatch.setattr(pr_closeout, "_rest", payload_fn)
    monkeypatch.setattr(pr_closeout, "_rest_pages", lambda path: [payload_fn(path)])


def test_required_checks_resolve_from_check_runs(monkeypatch):
    _install_rest(monkeypatch, _rest_payload(
        ["python-tests"],
        check_runs=[{"name": "python-tests", "status": "completed",
                     "conclusion": "success", "html_url": "u"}],
    ))
    out = pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)
    assert [(c["name"], c["bucket"]) for c in out] == [("python-tests", "pass")]


def test_a_required_STATUS_context_is_not_reported_pending(monkeypatch):
    """The gap this closes: a required context can be a legacy commit status,
    served from a different endpoint than check-runs. Reading only check-runs
    reports a passing status as pending forever, and the merge never unblocks."""
    _install_rest(monkeypatch, _rest_payload(
        ["CodeRabbit"],
        check_runs=[],
        statuses=[{"context": "CodeRabbit", "state": "success", "target_url": "u"}],
    ))
    out = pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)
    assert [(c["name"], c["bucket"]) for c in out] == [("CodeRabbit", "pass")]


def test_a_failing_status_context_is_a_failure_not_a_pass(monkeypatch):
    """Negative control for the mapping above."""
    _install_rest(monkeypatch, _rest_payload(
        ["CodeRabbit"], statuses=[{"context": "CodeRabbit", "state": "failure"}],
    ))
    assert pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)[0]["bucket"] == "fail"


def test_a_missing_required_check_is_pending_never_pass(monkeypatch):
    """Absence must never read as success — that is how a gate says yes to
    something it did not measure."""
    _install_rest(monkeypatch, _rest_payload(["verify"]))
    assert pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)[0]["bucket"] == "pending"


def test_a_check_run_wins_over_a_same_named_status(monkeypatch):
    _install_rest(monkeypatch, _rest_payload(
        ["verify"],
        check_runs=[{"name": "verify", "status": "completed", "conclusion": "failure"}],
        statuses=[{"context": "verify", "state": "success"}],
    ))
    assert pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)[0]["bucket"] == "fail"


# --- pagination: gh emits one JSON value PER PAGE (review on #2826) ----------
#
# `gh api --paginate` alone concatenates a separate JSON array or object per
# page, and `json.loads` reads the first then chokes on the next. The fallback
# therefore aborted on any PR busy enough to paginate -- precisely when an
# audit matters most. `--slurp` wraps the pages; these pin the flattening.


def test_check_runs_are_flattened_across_pages(monkeypatch):
    monkeypatch.setattr(pr_closeout, "_rest", _rest_payload(["a", "b"]))
    monkeypatch.setattr(pr_closeout, "_rest_pages", lambda path: (
        [{"check_runs": [{"name": "a", "status": "completed", "conclusion": "success"}]},
         {"check_runs": [{"name": "b", "status": "completed", "conclusion": "success"}]}]
        if "/check-runs" in path else [{"statuses": []}]
    ))
    out = pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)
    got = {c["name"]: c["bucket"] for c in out}
    assert got == {"a": "pass", "b": "pass"}, (
        "a check on page 2 was not seen: pages were not flattened")


def test_a_check_on_a_later_page_is_not_reported_pending(monkeypatch):
    """The failure this prevents: page-2 checks read as absent, so a fully
    green PR is refused for checks that actually passed."""
    monkeypatch.setattr(pr_closeout, "_rest", _rest_payload(["late"]))
    monkeypatch.setattr(pr_closeout, "_rest_pages", lambda path: (
        [{"check_runs": []},
         {"check_runs": [{"name": "late", "status": "completed", "conclusion": "success"}]}]
        if "/check-runs" in path else [{"statuses": []}]
    ))
    assert pr_closeout._required_checks_from_rest("o/r", 1, "a" * 40)[0]["bucket"] == "pass"


def test_reviews_are_flattened_across_pages(monkeypatch):
    """CHANGES_REQUESTED on page 2 must still block."""
    monkeypatch.setattr(pr_closeout, "_rest", lambda p, *a: [])
    monkeypatch.setattr(pr_closeout, "_rest_pages", lambda path: [
        [{"user": {"login": "a"}, "state": "APPROVED"}],
        [{"user": {"login": "b"}, "state": "CHANGES_REQUESTED"}],
    ])
    assert pr_closeout._review_decision_from_rest("o/r", 1) == "CHANGES_REQUESTED"


def test_the_paginated_call_asks_gh_to_slurp(monkeypatch):
    """Structural: without --slurp the pages cannot be parsed at all, so this
    asserts on the ARGV rather than on behaviour a stub could fake."""
    seen = {}

    def fake(command, **kwargs):
        seen["argv"] = command
        return []

    monkeypatch.setattr(pr_closeout, "_run_json", fake)
    pr_closeout._rest_pages("repos/o/r/pulls/1/reviews")
    assert "--slurp" in seen["argv"], seen["argv"]
    assert "--paginate" in seen["argv"], seen["argv"]
