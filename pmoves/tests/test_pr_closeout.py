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


# --- merge-queue mode -----------------------------------------------------------
#
# `gh pr merge --admin` BYPASSES a merge queue (gh pr merge --help), so the admin
# road stays direct. `--queue` is the approved-PR road: it relaxes ONLY the BEHIND
# gate (the queue re-tests on the latest base), never approval, and must refuse
# when the base has no active merge_queue rule instead of silently arming an
# auto-merge that waits forever.


def _approved_behind(**overrides: object) -> dict[str, object]:
    return _pr(mergeStateStatus="BEHIND", reviewDecision="APPROVED", **overrides)


def test_behind_blocks_direct_merge_but_not_queue_mode() -> None:
    direct = _evaluate(pr=_approved_behind(), admin=False)
    assert "branch is behind the current base" in direct.blockers

    queued = pr_closeout.evaluate_closeout(
        _approved_behind(),
        _required(),
        [],
        repo="POWERFULMOVES/PMOVES.AI",
        expected_head_sha="a" * 40,
        allowed_advisory_failures=("CodeRabbit",),
        queue_mode=True,
    )
    assert queued.ready, queued.blockers


def test_queue_mode_still_requires_approval() -> None:
    report = pr_closeout.evaluate_closeout(
        _pr(mergeStateStatus="BEHIND"),  # REVIEW_REQUIRED
        _required(),
        [],
        repo="POWERFULMOVES/PMOVES.AI",
        expected_head_sha="a" * 40,
        allowed_advisory_failures=("CodeRabbit",),
        queue_mode=True,
    )
    assert "review decision is REVIEW_REQUIRED" in report.blockers


def _queue_report() -> "pr_closeout.CloseoutReport":
    return pr_closeout.evaluate_closeout(
        _pr(mergeStateStatus="CLEAN", reviewDecision="APPROVED"),
        _required(),
        [],
        repo="POWERFULMOVES/PMOVES.AI",
        expected_head_sha="a" * 40,
        allowed_advisory_failures=("CodeRabbit",),
        queue_mode=True,
    )


def _rules(*types: str):
    # _rest_pages returns one payload PER PAGE; spread across two pages so a
    # merge_queue rule on a later page is proven to be seen.
    return lambda path: [[{"type": t} for t in types[:1]],
                         [{"type": t} for t in types[1:]]]


def _states(*states: dict):
    seq = list(states)
    return lambda repo, n: seq.pop(0)


def _gql(pr: dict | None):
    return {"data": {"repository": {"pullRequest": pr}}}


CONFIRM = f"MERGE #42 @ {'a' * 40}"
OPEN = {"state": "OPEN", "mergeQueueEntry": None, "autoMergeRequest": None}
QUEUED = {"state": "OPEN", "mergeQueueEntry": {"state": "QUEUED", "position": 1},
          "autoMergeRequest": None}
ARMED = {"state": "OPEN", "mergeQueueEntry": None,
         "autoMergeRequest": {"enabledAt": "2026-09-28T00:00:00Z"}}


def test_queue_refuses_when_no_merge_queue_rule(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("deletion", "pull_request"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    with pytest.raises(RuntimeError, match="no merge_queue rule"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           queue=True, confirmation=CONFIRM)
    assert calls == []


def test_merge_queue_rule_on_a_later_page_is_seen(monkeypatch) -> None:
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("deletion", "merge_queue"))
    assert pr_closeout._merge_queue_active("o/r", "main")


def test_queue_enqueues_with_auto_and_head_pin_never_admin(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("deletion", "merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(OPEN, QUEUED))
    result = pr_closeout._merge(_queue_report(), method="squash", admin=False,
                                queue=True, confirmation=CONFIRM)
    assert result["mergeQueueEntry"]["state"] == "QUEUED"
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[:4] == ["gh", "pr", "merge", "42"]
    assert "--auto" in cmd and "--admin" not in cmd
    assert cmd[cmd.index("--match-head-commit") + 1] == "a" * 40
    # The queue's configured method applies; passing one would be ignored noise.
    assert not {"--squash", "--merge", "--rebase"} & set(cmd)


def test_armed_but_not_queued_is_disarmed_and_fails(monkeypatch) -> None:
    calls: list[list[str]] = []

    def run(cmd, **k):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", run)
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(OPEN, ARMED))
    with pytest.raises(RuntimeError, match="NOT in the merge queue.*Auto-merge disarmed"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           queue=True, confirmation=CONFIRM)
    assert "--auto" in calls[0]
    assert calls[1][-1] == "--disable-auto" and calls[1][3] == "42"


def test_pre_armed_auto_merge_is_reported_not_counted_nor_disarmed(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(ARMED, ARMED))
    with pytest.raises(RuntimeError, match="already armed before this command"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           queue=True, confirmation=CONFIRM)
    assert "already armed" in capsys.readouterr().out
    assert len(calls) == 1 and "--disable-auto" not in calls[0]


def test_pre_armed_then_queued_succeeds_and_records_the_prior_arming(monkeypatch) -> None:
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: None)
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(ARMED, QUEUED))
    result = pr_closeout._merge(_queue_report(), method="squash", admin=False,
                                queue=True, confirmation=CONFIRM)
    assert result["preexisting_auto_merge"] == ARMED["autoMergeRequest"]


def test_already_queued_runs_no_command(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(QUEUED))
    result = pr_closeout._merge(_queue_report(), method="squash", admin=False,
                                queue=True, confirmation=CONFIRM)
    assert result["already_queued"] and calls == []


def test_queue_neither_entry_nor_arming_is_an_error(monkeypatch) -> None:
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: None)
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(OPEN, OPEN))
    with pytest.raises(RuntimeError, match="without a merge-queue entry"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           queue=True, confirmation=CONFIRM)


def test_unreadable_pre_state_refuses_before_mutating(monkeypatch) -> None:
    calls: list[list[str]] = []

    def boom(repo, n):
        raise RuntimeError("graphql throttled")

    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(pr_closeout, "_queue_state", boom)
    with pytest.raises(RuntimeError, match="refusing to enqueue"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           queue=True, confirmation=CONFIRM)
    assert calls == []


@pytest.mark.parametrize("payload,expected", [
    (_gql(QUEUED), QUEUED),
    (_gql(ARMED), ARMED),
    (_gql(OPEN), OPEN),
])
def test_queue_state_parses_the_graphql_payload(monkeypatch, payload, expected) -> None:
    seen: list[list[str]] = []

    def fake(cmd, **k):
        seen.append(cmd)
        return payload

    monkeypatch.setattr(pr_closeout, "_run_json", fake)
    assert pr_closeout._queue_state("POWERFULMOVES/PMOVES.AI", 42) == expected
    assert "number=42" in seen[0] and "owner=POWERFULMOVES" in seen[0]
    assert any("mergeQueueEntry" in a and "autoMergeRequest" in a for a in seen[0])


@pytest.mark.parametrize("payload", [None, {}, _gql(None), {"errors": [{"message": "x"}]}])
def test_queue_state_unreadable_payload_raises(monkeypatch, payload) -> None:
    monkeypatch.setattr(pr_closeout, "_run_json", lambda cmd, **k: payload)
    with pytest.raises(RuntimeError, match="could not read"):
        pr_closeout._queue_state("POWERFULMOVES/PMOVES.AI", 42)


def test_direct_non_admin_merge_on_a_queue_branch_refuses_before_mutating(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("merge_queue"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: calls.append(cmd))
    with pytest.raises(RuntimeError, match="requires a merge queue.*ENQUEUE or ARM"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           confirmation=CONFIRM)
    assert calls == []


def test_direct_merge_that_got_enqueued_names_what_happened(monkeypatch) -> None:
    # The rule was not visible at check time (e.g. added mid-flight).
    monkeypatch.setattr(pr_closeout, "_rest_pages", _rules("deletion"))
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: None)
    monkeypatch.setattr(pr_closeout, "_run_json", lambda cmd, **k: {"state": "OPEN"})
    monkeypatch.setattr(pr_closeout, "_queue_state", _states(QUEUED))
    with pytest.raises(RuntimeError, match="ENQUEUED in the merge queue, not merged"):
        pr_closeout._merge(_queue_report(), method="squash", admin=False,
                           confirmation=CONFIRM)


def test_admin_merge_skips_the_queue_rule_read(monkeypatch) -> None:
    def no_rules(path):
        raise AssertionError("admin path must not depend on the rules read")

    monkeypatch.setattr(pr_closeout, "_rest_pages", no_rules)
    monkeypatch.setattr(pr_closeout, "_run", lambda cmd, **k: None)
    monkeypatch.setattr(pr_closeout, "_run_json", lambda cmd, **k: {"state": "MERGED"})
    assert pr_closeout._merge(_queue_report(), method="squash", admin=True,
                              confirmation=CONFIRM)["state"] == "MERGED"


def test_queue_and_admin_are_mutually_exclusive() -> None:
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        pr_closeout._merge(
            _queue_report(), method="squash", admin=True, queue=True,
            confirmation=f"MERGE #42 @ {'a' * 40}",
        )


def test_cli_rejects_queue_with_admin() -> None:
    with pytest.raises(SystemExit) as exc:
        pr_closeout.main([
            "--repo", "POWERFULMOVES/PMOVES.AI", "merge", "--pr", "42",
            "--expected-head", "a" * 40, "--confirm", "x",
            "--queue", "--admin", "--admin-author", "POWERFULMOVES",
        ])
    assert exc.value.code == 2
