"""Tests for the control approval road (control_verdict.py + control_approve.py).

GitHub is never contacted: ``urllib.request.urlopen`` is replaced by an
in-memory fake that records every request, so the real client code (headers,
pagination, error mapping) is what runs.
"""

from __future__ import annotations

import http.client
import io
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import types
import urllib.response
from email.message import Message

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import control_approve  # noqa: E402
import control_verdict  # noqa: E402

TOKEN = "ghp_TESTTOKEN_never_print_me_0123456789"
APPROVER = "acme-control"  # test fixture only; the real login comes from config
AUTHOR = "POWERFULMOVES"
REPO = "OWNER/REPO"
H = "a" * 40
H2 = "b" * 40
PR = 42


def marker(verdict: str = "APPROVE", head: str = H, reviewer: str = "B850-CLAUDE") -> str:
    return control_verdict.format_marker(verdict, head, reviewer)


def comment(cid: int, body: str, author: str = AUTHOR, created: str | None = None, updated: str | None = None) -> dict[str, Any]:
    created = created or f"2026-09-28T10:{cid:02d}:00Z"
    return {
        "id": cid,
        "body": body,
        "user": {"login": author},
        "created_at": created,
        "updated_at": updated or created,
        "html_url": f"https://github.com/{REPO}/pull/{PR}#issuecomment-{cid}",
    }


# --------------------------------------------------------------------------
# Fake GitHub
# --------------------------------------------------------------------------


class _Resp:
    def __init__(self, payload: Any, headers: dict[str, str] | None = None, raw: bytes | None = None, read_exc: Exception | None = None):
        self._raw = raw if raw is not None else (b"" if payload is None else json.dumps(payload).encode())
        self._read_exc = read_exc
        self.headers = headers or {}

    def read(self) -> bytes:
        if self._read_exc is not None:
            raise self._read_exc
        return self._raw

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class FakeGitHub:
    def __init__(self) -> None:
        self.login = APPROVER
        self.pr: dict[str, Any] = {
            "number": PR,
            "state": "open",
            "merged": False,
            "merged_at": None,
            "draft": False,
            "base": {"ref": "main"},
            "head": {"sha": H},
            "user": {"login": AUTHOR},
        }
        self.head_sequence: list[str] = []  # consumed per PR GET when set
        self.comments: list[dict[str, Any]] = [comment(1, "LGTM\n" + marker())]
        self.reviews: list[dict[str, Any]] = []
        self.post_mode = "ok"  # ok | reject | unreachable | vanish | stored-then-502
        self.post_status = 502
        self.dismiss_mode = "ok"  # ok | forbidden | ignore (answers 200, changes nothing)
        self.fail: dict[str, Any] = {}  # path-substring -> HTTPError code or "unreachable"
        self.page_size: int | None = None
        self.requests: list[dict[str, Any]] = []
        self.bad_body: dict[tuple[str, str], Any] = {}  # (method, path-substring) -> bytes | Exception
        self.comment_script: list[list[dict[str, Any]]] = []  # consumed per comments GET
        self.link_override: str | None = None  # a Link header returned on the comments list
        self.redirect_on: str | None = None  # path substring answered with a 302

    # urlopen replacement
    def __call__(self, req: urllib.request.Request, timeout: float | None = None) -> _Resp:
        url = req.full_url
        method = req.get_method()
        headers = {k.lower(): v for k, v in req.header_items()}
        data = req.data.decode() if req.data else ""
        self.requests.append({"method": method, "url": url, "headers": headers, "data": data})
        path = url.split("api.github.com", 1)[-1]
        if self.redirect_on and self.redirect_on in path:
            raise urllib.error.HTTPError(url, 302, "redirect refused (Found)", {"Location": "https://evil.example/x"}, io.BytesIO(b""))
        if self.link_override and "/comments" in path and method == "GET":
            return _Resp(self.comments, {"Link": self.link_override})
        for (m, needle), bad in self.bad_body.items():
            if m == method and needle in path:
                if method == "POST":
                    self.reviews.append({"id": 9700, "user": {"login": self.login}, "state": "APPROVED",
                                         "commit_id": json.loads(data)["commit_id"], "submitted_at": "2026-09-28T11:00:00Z"})
                if isinstance(bad, Exception):
                    return _Resp(None, read_exc=bad)
                return _Resp(None, raw=bad)
        for needle, how in self.fail.items():
            if needle in path and (method == "GET"):
                if how == "unreachable":
                    raise urllib.error.URLError("connection refused")
                raise urllib.error.HTTPError(url, how, "err", {}, io.BytesIO(f"Bad credentials {TOKEN}".encode()))
        if method == "GET" and path == "/user":
            return _Resp({"login": self.login})
        if method == "GET" and re.fullmatch(rf"/repos/{REPO}/pulls/{PR}", path):
            pr = json.loads(json.dumps(self.pr))
            if self.head_sequence:
                pr["head"]["sha"] = self.head_sequence.pop(0)
            return _Resp(pr)
        if method == "GET" and path.startswith(f"/repos/{REPO}/issues/{PR}/comments"):
            if self.comment_script:
                self.comments = self.comment_script.pop(0)
            return self._paged(self.comments, path)
        if method == "GET" and path.startswith(f"/repos/{REPO}/pulls/{PR}/reviews"):
            return self._paged(self.reviews, path)
        m_dismiss = re.fullmatch(rf"/repos/{REPO}/pulls/{PR}/reviews/(\d+)/dismissals", path)
        if method == "PUT" and m_dismiss:
            if self.dismiss_mode == "forbidden":
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(b"{}"))
            rid = int(m_dismiss.group(1))
            for r in self.reviews:
                if r["id"] == rid and self.dismiss_mode == "ok":
                    r["state"] = "DISMISSED"
            return _Resp({"id": rid, "state": "DISMISSED"})
        if method == "POST" and path == f"/repos/{REPO}/pulls/{PR}/reviews":
            body = json.loads(data)
            if self.post_mode == "stored-then-502":
                self.reviews.append(
                    {"id": 9500, "user": {"login": self.login}, "state": "APPROVED",
                     "commit_id": body["commit_id"], "submitted_at": "2026-09-28T11:00:00Z"}
                )
                raise urllib.error.HTTPError(url, self.post_status, "Bad Gateway", {}, io.BytesIO(b"<html>5xx</html>"))
            if self.post_mode == "reject":
                raise urllib.error.HTTPError(url, 422, "Unprocessable", {}, io.BytesIO(b'{"message":"Can not approve your own pull request"}'))
            if self.post_mode == "unreachable":
                raise urllib.error.URLError("reset by peer")
            review = {
                "id": 9000 + len(self.reviews),
                "user": {"login": self.login},
                "state": "APPROVED" if body["event"] == "APPROVE" else body["event"],
                "commit_id": body["commit_id"],
                "submitted_at": "2026-09-28T11:00:00Z",
            }
            if self.post_mode != "vanish":
                self.reviews.append(review)
            return _Resp(review)
        raise AssertionError(f"unexpected request {method} {url}")

    def _paged(self, items: list[Any], path: str) -> _Resp:
        if not self.page_size:
            return _Resp(items)
        page = 1
        m = re.search(r"[?&]page=(\d+)", path)
        if m:
            page = int(m.group(1))
        start = (page - 1) * self.page_size
        chunk = items[start : start + self.page_size]
        headers = {}
        if start + self.page_size < len(items):
            base = path.split("?")[0]
            headers["Link"] = f'<https://api.github.com{base}?per_page=100&page={page + 1}>; rel="next"'
        return _Resp(chunk, headers)

    def posts(self) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["method"] == "POST"]


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(control_approve, "_build_opener", lambda *extra: types.SimpleNamespace(open=fake))
    return fake


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "control_approval.yaml"
    path.write_text(
        f"version: 1\nrepo: {REPO}\nbase: main\napprover_login: {APPROVER}\nmarker_authors:\n  - {AUTHOR}\n",
        encoding="utf-8",
    )
    return path


def run(config: Path, *, head: str = H, confirm: str | None = None, env: dict[str, str] | None = None, extra: list[str] | None = None) -> int:
    argv = [
        "--pr",
        str(PR),
        "--expected-head",
        head,
        "--confirm",
        confirm if confirm is not None else f"APPROVE #{PR} @ {head}",
        "--config",
        str(config),
        *(extra or []),
    ]
    assert all(TOKEN not in a for a in argv)
    environ = {"PMOVES_CONTROL_TOKEN": TOKEN}
    if env is not None:
        environ = env
    return control_approve.main(argv, env=environ)


def assert_token_hygiene(gh: FakeGitHub, out: str) -> None:
    assert TOKEN not in out
    for req in gh.requests:
        assert TOKEN not in req["url"]
        assert TOKEN not in req["data"]
        auth = req["headers"].get("authorization", "")
        assert auth == f"Bearer {TOKEN}"
        for name, value in req["headers"].items():
            if name != "authorization":
                assert TOKEN not in value


# --------------------------------------------------------------------------
# control_verdict: strict parse
# --------------------------------------------------------------------------


def verdicts_of(body: str) -> tuple[Any, ...]:
    parsed = control_verdict.parse_body(body)
    assert parsed is not None
    return parsed.verdicts


def test_format_round_trips() -> None:
    parsed = control_verdict.parse_body(marker())
    assert parsed == control_verdict.ParsedBody((control_verdict.Verdict("APPROVE", H, "B850-CLAUDE"),), "", 0)


@pytest.mark.parametrize(
    "bad",
    [
        f"<!-- pmoves-control-verdict: v=1 verdict=APPROVE head={'A' * 40} reviewer=x -->",
        f"<!-- pmoves-control-verdict: v=1 verdict=APPROVE head={'a' * 39} reviewer=x -->",
        f"<!-- pmoves-control-verdict: v=1 verdict=APPROVE head={'a' * 41} reviewer=x -->",
        f"<!-- pmoves-control-verdict: v=1 verdict=LGTM head={H} reviewer=x -->",
        f"<!-- pmoves-control-verdict: v=2 verdict=APPROVE head={H} reviewer=x -->",
        f"<!-- pmoves-control-verdict:  v=1 verdict=APPROVE head={H} reviewer=x -->",
        f"<!-- PMOVES-control-verdict: v=1 verdict=APPROVE head={H} reviewer=x -->",
        f"<!-- pmoves-control-verdict: v=1 verdict=APPROVE head={H} reviewer=-x -->",
        f"<!-- pmoves-control-verdict: v=1 verdict=APPROVE head={H} -->",
    ],
)
def test_strict_parse_marks_near_misses_malformed(bad: str) -> None:
    parsed = control_verdict.parse_body(bad)
    assert parsed is not None and parsed.verdicts == () and parsed.malformed_reason


def test_no_marker_is_none() -> None:
    assert control_verdict.parse_body("plain review text") is None


# -- review round 2, P1: a REQUEST_CHANGES is never hidden by markdown context --

def _rc() -> str:
    return marker("REQUEST_CHANGES")


REVIEWER_PROBES = {
    "stray-backtick": lambda: "see `make test\n" + _rc() + "\nand then ` again",
    "stray-backtick-blank-line": lambda: "see `make test\n\n" + _rc() + "\n\nand then ` again",
    "line-start-inline-triple": lambda: "```pytest -q``` fails on main\n" + _rc(),
    "tilde-line": lambda: "~~~\n" + _rc(),
    "tilde-line-blank-line": lambda: "~~~\n\n" + _rc() + "\n",
    "inline-code": lambda: "the block is `" + _rc() + "`",
    "fenced": lambda: "```\n" + _rc() + "\n```",
    "indented": lambda: "    " + _rc(),
}


@pytest.mark.parametrize("probe", sorted(REVIEWER_PROBES))
def test_request_changes_counts_in_any_markdown_context(probe: str) -> None:
    body = REVIEWER_PROBES[probe]()
    assert verdicts_of(body) == (control_verdict.Verdict("REQUEST_CHANGES", H, "B850-CLAUDE"),)
    s = sel([comment(1, marker()), comment(2, body)])
    assert s.approved is False and s.kind == "request_changes"


@pytest.mark.parametrize("probe", sorted(REVIEWER_PROBES))
def test_reviewer_probes_refuse_end_to_end(gh: FakeGitHub, config: Path, probe: str, capsys: pytest.CaptureFixture[str]) -> None:
    gh.comments = [comment(1, marker()), comment(2, REVIEWER_PROBES[probe]())]
    assert run(config) == 1
    assert gh.posts() == []
    assert "VERDICT: APPROVED" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "body",
    [
        "`<!-- PMOVES-control-verdict: v=1 verdict=REQUEST_CHANGES -->`",
        "```\n<!-- pmoves-control-verdict: v=1 verdict=REQUEST_CHANGES head=short -->\n```",
    ],
    ids=["inline", "fenced"],
)
def test_malformed_marker_in_code_still_makes_it_ambiguous(body: str) -> None:
    s = sel([comment(1, marker()), comment(2, body)])
    assert s.approved is False and s.kind == "ambiguous"


# -- APPROVE gets the strict test: own line, outside a real fence --


@pytest.mark.parametrize(
    "quoted",
    [
        lambda: "the format is `" + marker() + "` in a comment",
        lambda: "```\n" + marker() + "\n```",
        lambda: "~~~md\n" + marker() + "\n~~~",
        lambda: "````\n```\n" + marker() + "\n```\n````",
        lambda: "````\ncode\n```\n" + marker(),  # a shorter close does not close
        lambda: "```\n~~~\n" + marker(),  # a different char does not close
        lambda: "```\nunclosed fence runs to the end\n" + marker(),
        lambda: "    " + marker(),
        lambda: "> " + marker(),
        lambda: "text before " + marker(),
        lambda: marker() + " trailing text",
    ],
    ids=["inline", "fence", "tilde-fence", "nested-fence", "short-close", "other-char-close",
         "unclosed-fence", "indented", "blockquote", "prefix", "suffix"],
)
def test_quoted_or_embedded_approve_does_not_count(quoted: Any) -> None:
    body = quoted()
    parsed = control_verdict.parse_body(body)
    assert parsed is not None and parsed.verdicts == () and parsed.ignored_approvals == 1
    assert not sel([comment(1, body)]).approved


@pytest.mark.parametrize(
    "body",
    [
        lambda: "```pytest -q``` is green\n" + marker(),  # backticks in the info string: not a fence
        lambda: "```\ncode\n```\n" + marker(),  # closed fence, then the marker
        lambda: "````\ncode\n`````\n" + marker(),  # a longer close closes
        lambda: "notes\n\n" + marker() + "\n\nmore notes",
        lambda: marker() + "\r\n",
    ],
    ids=["inline-triple-not-fence", "after-closed-fence", "longer-close", "surrounded", "crlf"],
)
def test_own_line_approve_outside_fences_counts(body: Any) -> None:
    assert verdicts_of(body()) == (control_verdict.Verdict("APPROVE", H, "B850-CLAUDE"),)
    assert sel([comment(1, body())]).approved


@pytest.mark.parametrize(
    "disguise",
    [
        lambda m: m.replace("<!--", "&lt;!--"),
        lambda m: m.replace("pmoves-control", "pmoves\u200b-control"),
        lambda m: m.replace("pmoves-control", "pmoves\u2010control"),
        lambda m: m.replace("<!--", "<!\u2014"),
    ],
    ids=["html-escaped", "zero-width", "unicode-hyphen", "em-dash"],
)
def test_escaped_or_lookalike_markers_are_invisible(disguise: Any) -> None:
    # Documented limitation (MERGE_MECHANICS 6.2): such a REQUEST_CHANGES is
    # NOT recorded, and an earlier APPROVE still wins. This pins the behaviour
    # the doc warns about, so a change to it is a deliberate decision.
    rc = disguise(marker("REQUEST_CHANGES"))
    assert control_verdict.parse_body(rc) is None
    assert sel([comment(1, marker()), comment(2, rc)]).approved


def test_approve_and_request_changes_in_one_comment_is_a_block() -> None:
    s = sel([comment(1, marker() + "\n" + marker("REQUEST_CHANGES"))])
    assert not s.approved and s.kind == "request_changes"


def test_quoted_approve_does_not_supersede_an_earlier_block() -> None:
    s = sel([comment(1, marker("REQUEST_CHANGES")), comment(2, "`" + marker() + "`")])
    assert not s.approved and s.kind == "request_changes"


def test_cli_works_when_docstrings_are_stripped(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # `python -OO` sets __doc__ to None; the CLI must not depend on it.
    monkeypatch.setattr(control_verdict, "__doc__", None)
    assert control_verdict.main(["format", "--verdict", "APPROVE", "--head", H, "--reviewer", "B850-CLAUDE"]) == 0
    assert capsys.readouterr().out.strip() == marker()


def test_format_validates_fields() -> None:
    with pytest.raises(control_verdict.VerdictFormatError):
        control_verdict.format_marker("APPROVE", H.upper(), "x")
    with pytest.raises(control_verdict.VerdictFormatError):
        control_verdict.format_marker("MAYBE", H, "x")


# --------------------------------------------------------------------------
# control_verdict: selection
# --------------------------------------------------------------------------


def sel(comments: list[dict[str, Any]], head: str = H) -> control_verdict.Selection:
    return control_verdict.select_verdict(comments, head, [AUTHOR])


def test_latest_request_changes_beats_earlier_approve() -> None:
    s = sel([comment(1, marker()), comment(2, marker("REQUEST_CHANGES"))])
    assert not s.approved and "REQUEST_CHANGES" in s.reason


def test_latest_approve_beats_earlier_request_changes() -> None:
    assert sel([comment(1, marker("REQUEST_CHANGES")), comment(2, marker())]).approved


def test_ordering_is_by_created_at_not_list_order() -> None:
    late_rc = comment(2, marker("REQUEST_CHANGES"), created="2026-09-28T12:00:00Z")
    early_ok = comment(3, marker(), created="2026-09-28T09:00:00Z")
    assert not sel([late_rc, early_ok]).approved


def test_marker_for_other_head_is_ignored() -> None:
    s = sel([comment(1, marker(head=H2))])
    assert not s.approved and s.ignored_other_heads == 1 and "no control verdict marker" in s.reason
    # and a REQUEST_CHANGES on another head does not block this head
    assert sel([comment(1, marker()), comment(2, marker("REQUEST_CHANGES", head=H2))]).approved


def test_untrusted_author_marker_refused_and_does_not_block() -> None:
    s = sel([comment(1, marker(), author="drive-by")])
    assert not s.approved and "none was authored by an allowed control identity" in s.reason
    assert sel([comment(1, marker()), comment(2, marker("REQUEST_CHANGES"), author="drive-by")]).approved


def test_author_allowlist_is_case_insensitive() -> None:
    assert sel([comment(1, marker(), author="powerfulmoves")]).approved


def test_edited_approve_marker_refused() -> None:
    s = sel([comment(1, marker(), updated="2026-09-28T13:00:00Z")])
    assert not s.approved and "edited" in s.reason


@pytest.mark.parametrize("field", ["updated_at", "created_at"])
@pytest.mark.parametrize("value", ["", None, "missing"])
def test_missing_or_empty_timestamps_count_as_edited(field: str, value: Any) -> None:
    c = comment(1, marker())
    if value == "missing":
        del c[field]
    else:
        c[field] = value
    s = sel([c])
    assert not s.approved and "edited" in s.reason


def test_malformed_trusted_marker_after_approve_is_ambiguous() -> None:
    bad = f"<!-- pmoves-control-verdict: v=1 verdict=REQUEST_CHANGES head={H.upper()} reviewer=x -->"
    s = sel([comment(1, marker()), comment(2, bad)])
    assert not s.approved and "ambiguous" in s.reason
    assert sel([comment(1, bad), comment(2, marker())]).approved


@pytest.mark.parametrize(
    "edited_body",
    ["withdrawn remark, marker removed", marker("REQUEST_CHANGES", head=H2), marker("APPROVE")],
    ids=["marker-removed", "moved-to-other-head", "rewritten-to-approve"],
)
def test_edit_of_a_later_allowed_comment_is_ambiguous(edited_body: str) -> None:
    # APPROVE c1, REQUEST_CHANGES c2, then c2 edited: must not revive the approval.
    c2 = comment(2, edited_body, updated="2026-09-28T13:00:00Z")
    s = sel([comment(1, marker()), c2])
    # refused either as ambiguous (later edited comment) or as an edited winner
    assert not s.approved and "edited" in s.reason


def test_edit_of_a_later_untrusted_comment_is_ignored() -> None:
    later = comment(2, "drive-by note", author="drive-by", updated="2026-09-28T13:00:00Z")
    assert sel([comment(1, marker()), later]).approved


def test_edit_of_an_earlier_comment_does_not_block_a_fresh_verdict() -> None:
    earlier = comment(1, "old note", updated="2026-09-28T13:00:00Z")
    assert sel([earlier, comment(2, marker())]).approved


def test_empty_allowlist_refuses() -> None:
    assert not control_verdict.select_verdict([comment(1, marker())], H, []).approved


# --------------------------------------------------------------------------
# control_approve: success paths
# --------------------------------------------------------------------------


def test_success_posts_pinned_review_and_verifies(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(config) == 0
    out = capsys.readouterr()
    posts = gh.posts()
    assert len(posts) == 1
    body = json.loads(posts[0]["data"])
    assert body["event"] == "APPROVE" and body["commit_id"] == H
    assert "issuecomment-1" in body["body"]
    assert "VERDICT: APPROVED rc=0" in out.out
    assert_token_hygiene(gh, out.out + out.err)


def test_already_approved_is_idempotent(gh: FakeGitHub, config: Path) -> None:
    gh.reviews.append({"id": 7, "user": {"login": APPROVER}, "state": "APPROVED", "commit_id": H, "submitted_at": "2026-09-28T09:00:00Z"})
    assert run(config) == 0
    assert gh.posts() == []


def test_dismissed_prior_approval_is_reposted(gh: FakeGitHub, config: Path) -> None:
    gh.reviews.append({"id": 7, "user": {"login": APPROVER}, "state": "DISMISSED", "commit_id": H, "submitted_at": "2026-09-28T09:00:00Z"})
    assert run(config) == 0
    assert len(gh.posts()) == 1


def test_dry_run_never_posts_and_has_its_own_label(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(config, extra=["--dry-run"]) == 0
    assert gh.posts() == []
    assert [r for r in gh.requests if r["method"] != "GET"] == []
    out = capsys.readouterr().out
    assert out.strip().splitlines()[-1] == "VERDICT: DRY-RUN-WOULD-APPROVE rc=0"
    assert "VERDICT: APPROVED" not in out


def test_dry_run_with_existing_approval_is_still_labelled_dry_run(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.reviews.append({"id": 7, "user": {"login": APPROVER}, "state": "APPROVED", "commit_id": H, "submitted_at": "2026-09-28T09:00:00Z"})
    assert run(config, extra=["--dry-run"]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "VERDICT: DRY-RUN-WOULD-APPROVE rc=0"


def test_paginated_comments_are_all_read(gh: FakeGitHub, config: Path) -> None:
    gh.page_size = 2
    # APPROVE on page 1; the later REQUEST_CHANGES lives on page 3. A reader that
    # stops at page 1 would approve -- pagination is what makes this refuse.
    gh.comments = [comment(1, marker())] + [comment(i, f"noise {i}") for i in range(2, 6)] + [comment(9, marker("REQUEST_CHANGES"))]
    assert run(config) == 1
    assert sum(1 for r in gh.requests if "/comments" in r["url"]) == 3
    assert gh.posts() == []


# --------------------------------------------------------------------------
# control_approve: refusal matrix
# --------------------------------------------------------------------------


def test_confirm_mismatch_refuses_before_any_request(gh: FakeGitHub, config: Path) -> None:
    assert run(config, confirm=f"APPROVE #{PR + 1} @ {H}") == 1
    assert gh.requests == []


def test_short_head_is_usage_error(gh: FakeGitHub, config: Path) -> None:
    assert run(config, head=H[:12]) == 2
    assert gh.requests == []


def test_missing_token_is_could_not_measure(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(config, env={}) == 3
    assert "COULD-NOT-MEASURE" in capsys.readouterr().out
    assert gh.requests == []


def _token_file(tmp_path: Path, mode: int, content: str = TOKEN + "\n") -> Path:
    path = tmp_path / "control.token"
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_token_file_0600_is_used(gh: FakeGitHub, config: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tf = _token_file(tmp_path, 0o600)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf)}) == 0
    out = capsys.readouterr()
    assert_token_hygiene(gh, out.out + out.err)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
@pytest.mark.parametrize("mode", [0o640, 0o604, 0o660, 0o644])
def test_token_file_readable_by_others_is_refused(gh: FakeGitHub, config: Path, tmp_path: Path, mode: int) -> None:
    tf = _token_file(tmp_path, mode)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf)}) == 1
    assert gh.requests == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks and modes")
@pytest.mark.parametrize("target_mode", [0o600, 0o644])
def test_token_file_symlink_is_refused(gh: FakeGitHub, config: Path, tmp_path: Path, target_mode: int, capsys: pytest.CaptureFixture[str]) -> None:
    real = _token_file(tmp_path, target_mode)
    link = tmp_path / "link.token"
    link.symlink_to(real)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(link)}) == 1
    assert "symlink" in capsys.readouterr().err
    assert gh.requests == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
@pytest.mark.parametrize(
    "content",
    [TOKEN + "\n\n", TOKEN + "\r\n", " " + TOKEN, TOKEN + " \n", TOKEN[:10] + "\n" + TOKEN[10:], TOKEN + "\t", TOKEN + "\x00"],
    ids=["two-newlines", "crlf", "leading-space", "trailing-space", "two-lines", "tab", "nul"],
)
def test_token_file_with_extra_whitespace_is_refused_without_echoing(
    gh: FakeGitHub, config: Path, tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]
) -> None:
    tf = _token_file(tmp_path, 0o600, content=content)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf)}) == 1
    out = capsys.readouterr()
    assert "no whitespace" in out.err and "content not shown" in out.err
    assert TOKEN[:10] not in out.out + out.err
    assert gh.requests == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFOs")
def test_token_file_fifo_is_refused_without_hanging(gh: FakeGitHub, config: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fifo = tmp_path / "token.fifo"
    os.mkfifo(fifo, 0o600)
    result: dict[str, int] = {}
    worker = threading.Thread(
        target=lambda: result.update(rc=run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(fifo)})),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=5)
    if worker.is_alive():
        # unblock the stuck open() so the daemon thread can finish, then fail
        with open(fifo, "w", encoding="utf-8"):
            pass
        pytest.fail("opening a FIFO token file hung (no O_NONBLOCK)")
    assert result["rc"] == 1
    assert "not a regular file" in capsys.readouterr().err
    assert gh.requests == []


def test_token_file_without_trailing_newline_is_fine(gh: FakeGitHub, config: Path, tmp_path: Path) -> None:
    tf = _token_file(tmp_path, 0o600, content=TOKEN)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf)}) == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_token_file_0400_is_accepted(gh: FakeGitHub, config: Path, tmp_path: Path) -> None:
    tf = _token_file(tmp_path, 0o400)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf)}) == 0


@pytest.mark.parametrize("value", [TOKEN + "\n", "a b", TOKEN + "\r"])
def test_env_token_with_whitespace_is_refused_without_echoing(gh: FakeGitHub, config: Path, value: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(config, env={"PMOVES_CONTROL_TOKEN": value}) == 1
    out = capsys.readouterr()
    assert "content not shown" in out.err and TOKEN[:10] not in out.out + out.err
    assert gh.requests == []


@pytest.mark.parametrize("value", ["", " ", "\n", " \t\r\n "])
def test_blank_env_token_is_no_token(gh: FakeGitHub, config: Path, value: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(config, env={"PMOVES_CONTROL_TOKEN": value}) == 3
    out = capsys.readouterr()
    assert "no token" in out.err
    assert out.out.strip().splitlines()[-1] == "VERDICT: COULD-NOT-MEASURE rc=3"
    assert gh.requests == []


def test_token_file_and_env_together_is_usage_error(gh: FakeGitHub, config: Path, tmp_path: Path) -> None:
    tf = _token_file(tmp_path, 0o600)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(tf), "PMOVES_CONTROL_TOKEN": TOKEN}) == 2
    assert gh.requests == []


@pytest.mark.parametrize("kind", ["missing", "empty", "directory"])
def test_token_file_unusable(gh: FakeGitHub, config: Path, tmp_path: Path, kind: str) -> None:
    if kind == "missing":
        path = tmp_path / "nope"
    elif kind == "empty":
        path = _token_file(tmp_path, 0o600, content="  \n")
    else:
        path = tmp_path / "dir"
        path.mkdir(mode=0o700)
    assert run(config, env={"PMOVES_CONTROL_TOKEN_FILE": str(path)}) in (1, 3)
    assert gh.requests == []


def test_unconfigured_approver_is_could_not_measure(gh: FakeGitHub, tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"repo: {REPO}\napprover_login: \"\"\nmarker_authors: [{AUTHOR}]\n", encoding="utf-8")
    assert run(cfg) == 3
    assert gh.requests == []


def test_env_overrides_login(gh: FakeGitHub, config: Path) -> None:
    gh.login = "other-bot"
    assert run(config, env={"PMOVES_CONTROL_TOKEN": TOKEN, "PMOVES_CONTROL_LOGIN": "other-bot"}) == 0


def test_token_for_wrong_account_refused(gh: FakeGitHub, config: Path) -> None:
    gh.login = "DARKXSIDE"
    assert run(config) == 1
    assert gh.posts() == []


def test_approver_equal_to_author_refused(gh: FakeGitHub, config: Path) -> None:
    gh.pr["user"]["login"] = APPROVER.upper()
    assert run(config) == 1
    assert gh.posts() == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda pr: pr.update(state="closed"),
        lambda pr: pr.update(merged=True, merged_at="2026-09-28T00:00:00Z"),
        lambda pr: pr.update(draft=True),
        lambda pr: pr["base"].update(ref="develop"),
        lambda pr: pr["head"].update(sha=H2),
    ],
    ids=["closed", "merged", "draft", "wrong-base", "head-mismatch"],
)
def test_pr_state_refusals(gh: FakeGitHub, config: Path, mutate: Any) -> None:
    mutate(gh.pr)
    assert run(config) == 1
    assert gh.posts() == []


@pytest.mark.parametrize(
    "mutate",
    [lambda pr: pr.update(draft=True), lambda pr: pr.update(state="closed"), lambda pr: pr["base"].update(ref="develop")],
    ids=["draft", "closed", "wrong-base"],
)
def test_pr_state_refusal_still_withdraws_on_request_changes(gh: FakeGitHub, config: Path, mutate: Any, capsys: pytest.CaptureFixture[str]) -> None:
    mutate(gh.pr)
    _standing(gh)
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 1
    assert gh.reviews[0]["state"] == "DISMISSED"
    assert "dismissed standing approval(s) [77]" in capsys.readouterr().err
    assert gh.posts() == []


def test_pr_state_refusal_keeps_approval_when_verdict_is_clean(gh: FakeGitHub, config: Path) -> None:
    gh.pr["draft"] = True
    _standing(gh)
    assert run(config) == 1
    assert gh.reviews[0]["state"] == "APPROVED"
    assert [r for r in gh.requests if r["method"] == "PUT"] == []


def test_pr_state_refusal_with_failed_dismissal_is_still_stands(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.pr["draft"] = True
    _standing(gh)
    gh.dismiss_mode = "forbidden"
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 3
    assert "STILL STAND" in capsys.readouterr().err


def test_merged_pr_is_refused_without_touching_reviews(gh: FakeGitHub, config: Path) -> None:
    gh.pr.update(merged=True, merged_at="2026-09-28T00:00:00Z", state="closed")
    _standing(gh)
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 1
    assert [r for r in gh.requests if r["method"] != "GET"] == []


def test_no_marker_refused(gh: FakeGitHub, config: Path) -> None:
    gh.comments = [comment(1, "looks fine to me")]
    assert run(config) == 1
    assert gh.posts() == []


def test_marker_only_for_old_head_refused(gh: FakeGitHub, config: Path) -> None:
    gh.comments = [comment(1, marker(head=H2))]
    assert run(config) == 1
    assert gh.posts() == []


def test_latest_request_changes_refused(gh: FakeGitHub, config: Path) -> None:
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 1
    assert gh.posts() == []


def _standing(gh: FakeGitHub, rid: int = 77, head: str = H) -> None:
    gh.reviews.append({"id": rid, "user": {"login": APPROVER}, "state": "APPROVED", "commit_id": head, "submitted_at": "2026-09-28T09:30:00Z"})


def test_request_changes_dismisses_standing_approval(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _standing(gh)
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 1
    puts = [r for r in gh.requests if r["method"] == "PUT"]
    assert len(puts) == 1 and puts[0]["url"].endswith(f"/pulls/{PR}/reviews/77/dismissals")
    assert json.loads(puts[0]["data"])["event"] == "DISMISS"
    assert gh.reviews[0]["state"] == "DISMISSED"
    assert "dismissed standing approval(s) [77]" in capsys.readouterr().err
    assert gh.posts() == []


ROUND2_CASES = {
    # 3b: a later RC from the allowlist that is malformed
    "3b-malformed-later-rc": lambda: [
        comment(1, marker()),
        comment(2, f"<!-- pmoves-control-verdict: v=1 verdict=REQUEST_CHANGES head={H[:39]} reviewer=x -->"),
    ],
    # 3c: an edited later allowlisted comment (the "RC edited away" case)
    "3c-edited-later-comment": lambda: [comment(1, marker()), comment(2, "never mind", updated="2026-09-28T13:00:00Z")],
    # 3e: an edited APPROVE winner
    "3e-edited-winner": lambda: [comment(1, marker(), updated="2026-09-28T13:00:00Z")],
    "no-marker-for-head": lambda: [comment(1, marker(head=H2))],
}


@pytest.mark.parametrize("case", sorted(ROUND2_CASES))
def test_every_non_approve_outcome_dismisses_a_standing_approval(gh: FakeGitHub, config: Path, case: str, capsys: pytest.CaptureFixture[str]) -> None:
    _standing(gh)
    gh.comments = ROUND2_CASES[case]()
    assert run(config) == 1
    puts = [r for r in gh.requests if r["method"] == "PUT"]
    assert len(puts) == 1 and puts[0]["url"].endswith("/reviews/77/dismissals")
    assert gh.reviews[0]["state"] == "DISMISSED"
    assert "dismissed standing approval(s) [77]" in capsys.readouterr().err
    assert gh.posts() == []


@pytest.mark.parametrize("case", sorted(ROUND2_CASES))
def test_every_non_approve_outcome_with_failed_dismissal_is_still_stands(gh: FakeGitHub, config: Path, case: str, capsys: pytest.CaptureFixture[str]) -> None:
    _standing(gh)
    gh.dismiss_mode = "forbidden"
    gh.comments = ROUND2_CASES[case]()
    assert run(config) == 3
    assert "STILL STAND" in capsys.readouterr().err


@pytest.mark.parametrize("case", sorted(ROUND2_CASES))
def test_non_approve_on_the_pre_post_read_dismisses_too(gh: FakeGitHub, config: Path, case: str) -> None:
    # read 1 approves; read 2 (just before the POST) sees the case: no POST, and
    # the same withdrawal lookup runs (reviews are listed after the 2nd read).
    gh.comment_script = [list(APPROVE_ONLY), ROUND2_CASES[case]()]
    assert run(config) == 1
    assert gh.posts() == []
    urls = [r["url"] for r in gh.requests]
    second_read = [i for i, u in enumerate(urls) if "/comments" in u][1]
    assert any("/reviews" in u for u in urls[second_read + 1 :])


def test_request_changes_without_standing_approval_refuses_without_dismissing(gh: FakeGitHub, config: Path) -> None:
    _standing(gh, head=H2)  # an approval on another commit is not touched
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 1
    assert [r for r in gh.requests if r["method"] == "PUT"] == []


@pytest.mark.parametrize("mode", ["forbidden", "ignore"])
def test_request_changes_dismissal_failure_is_could_not_measure(gh: FakeGitHub, config: Path, mode: str, capsys: pytest.CaptureFixture[str]) -> None:
    _standing(gh)
    gh.dismiss_mode = mode
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config) == 3
    assert "77" in capsys.readouterr().err


def test_request_changes_reviews_unreadable_is_could_not_measure(gh: FakeGitHub, config: Path) -> None:
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    gh.fail["/reviews"] = 502
    assert run(config) == 3


def test_request_changes_dry_run_does_not_dismiss(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _standing(gh)
    gh.comments.append(comment(2, marker("REQUEST_CHANGES")))
    assert run(config, extra=["--dry-run"]) == 1
    assert [r for r in gh.requests if r["method"] == "PUT"] == []
    assert "would dismiss" in capsys.readouterr().err


def test_marker_by_unallowed_author_refused(gh: FakeGitHub, config: Path) -> None:
    gh.comments = [comment(1, marker(), author="drive-by")]
    assert run(config) == 1
    assert gh.posts() == []


def test_pr_author_different_from_marker_author_approves(gh: FakeGitHub, config: Path) -> None:
    # The common test shape has POWERFULMOVES in both roles; the road must not
    # depend on that. A PR by someone else, verdict recorded by the allowlist.
    gh.pr["user"]["login"] = "outside-contributor"
    assert run(config) == 0
    assert len(gh.posts()) == 1


def test_pr_author_cannot_record_a_verdict_unless_allowlisted(gh: FakeGitHub, config: Path) -> None:
    gh.pr["user"]["login"] = "outside-contributor"
    gh.comments = [comment(1, marker(), author="outside-contributor")]
    assert run(config) == 1
    assert gh.posts() == []


def test_marker_author_allowlist_env_override(gh: FakeGitHub, config: Path) -> None:
    gh.comments = [comment(1, marker(), author="control-recorder")]
    env = {"PMOVES_CONTROL_TOKEN": TOKEN, "PMOVES_CONTROL_MARKER_AUTHORS": "control-recorder"}
    assert run(config, env=env) == 0


@pytest.mark.parametrize("how", [401, 500, "unreachable"])
def test_read_failures_are_could_not_measure(gh: FakeGitHub, config: Path, how: Any, capsys: pytest.CaptureFixture[str]) -> None:
    gh.fail["/user"] = how
    assert run(config) == 3
    out = capsys.readouterr()
    assert "VERDICT: COULD-NOT-MEASURE rc=3" in out.out
    # the fake error body echoes the token; it must be redacted
    assert_token_hygiene(gh, out.out + out.err)


def test_comment_read_failure_is_could_not_measure(gh: FakeGitHub, config: Path) -> None:
    gh.fail["/comments"] = 403
    assert run(config) == 3
    assert gh.posts() == []


def test_post_rejected_is_refused(gh: FakeGitHub, config: Path) -> None:
    gh.post_mode = "reject"
    assert run(config) == 1


@pytest.mark.parametrize("status", [500, 502, 504])
def test_post_5xx_is_could_not_measure_not_refused(gh: FakeGitHub, config: Path, status: int, capsys: pytest.CaptureFixture[str]) -> None:
    gh.post_mode = "stored-then-502"
    gh.post_status = status
    assert run(config) == 3
    out = capsys.readouterr()
    assert "VERDICT: COULD-NOT-MEASURE rc=3" in out.out
    assert "may have been stored" in out.err
    # the probe from review round 1: the review WAS stored despite the 5xx
    assert any(r["state"] == "APPROVED" for r in gh.reviews)


@pytest.mark.parametrize(
    "method,needle,bad",
    [
        ("GET", "/user", b"<html>not json</html>"),
        ("GET", "/comments", b"\xff\xfe not utf-8"),
        ("GET", "/pulls/42", http.client.IncompleteRead(b"{\"state\":")),
        ("POST", "/reviews", b"not json"),
        ("POST", "/reviews", http.client.IncompleteRead(b"{")),
    ],
    ids=["user-html", "comments-bytes", "pr-incomplete", "post-bad-json", "post-incomplete"],
)
def test_bad_bodies_are_could_not_measure_with_verdict_line(
    gh: FakeGitHub, config: Path, method: str, needle: str, bad: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.bad_body[(method, needle)] = bad
    assert run(config) == 3
    out = capsys.readouterr()
    assert out.out.strip().splitlines()[-1] == "VERDICT: COULD-NOT-MEASURE rc=3"
    assert "Traceback" not in out.err
    assert_token_hygiene(gh, out.out + out.err)


def test_unexpected_error_still_prints_verdict_line(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.reviews.append({"id": "not-an-int", "user": {"login": APPROVER}, "state": "APPROVED", "commit_id": H})
    assert run(config) == 3
    out = capsys.readouterr()
    assert out.out.strip().splitlines()[-1] == "VERDICT: COULD-NOT-MEASURE rc=3"
    assert "unexpected ValueError" in out.err


def test_post_unreachable_is_could_not_measure(gh: FakeGitHub, config: Path) -> None:
    gh.post_mode = "unreachable"
    assert run(config) == 3


def test_post_verify_failure_is_refused(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.post_mode = "vanish"  # POST answers 200 but GitHub holds no such review
    assert run(config) == 1
    assert "post-verify failed" in capsys.readouterr().err


def test_head_moves_before_post_aborts_without_posting(gh: FakeGitHub, config: Path) -> None:
    gh.head_sequence = [H, H2]
    assert run(config) == 1
    assert gh.posts() == []


def test_head_moves_between_post_and_verify_is_refused(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # check, pre-POST re-check, then the head moves before the final read.
    gh.head_sequence = [H, H, H2]
    assert run(config) == 1
    posts = gh.posts()
    assert len(posts) == 1
    # commit_id pinning: the review is attached to the reviewed commit, not the new head
    assert json.loads(posts[0]["data"])["commit_id"] == H
    assert gh.reviews[-1]["commit_id"] == H
    assert "head moved" in capsys.readouterr().err


# --------------------------------------------------------------------------
# token hygiene beyond the request layer
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link",
    [
        '<https://evil.example/repos/OWNER/REPO/issues/42/comments?page=2>; rel="next"',
        '<http://api.github.com/repos/OWNER/REPO/issues/42/comments?page=2>; rel="next"',
        '<https://api.github.com.evil.example/x?page=2>; rel="next"',
    ],
    ids=["other-host", "plain-http", "suffix-host"],
)
def test_link_urls_off_the_pinned_host_are_refused(gh: FakeGitHub, config: Path, link: str) -> None:
    gh.link_override = link
    assert run(config) == 3
    assert all(r["url"].startswith("https://api.github.com/") for r in gh.requests)
    assert gh.posts() == []


def test_redirect_is_could_not_measure(gh: FakeGitHub, config: Path) -> None:
    gh.redirect_on = "/user"
    assert run(config) == 3
    assert len(gh.requests) == 1


@pytest.mark.parametrize(
    "base",
    ["http://api.github.com", "api.github.com", "https://", "https://user:pw@api.github.com", "ftp://api.github.com"],
)
def test_api_base_must_be_https_with_host(gh: FakeGitHub, config: Path, base: str) -> None:
    assert run(config, extra=["--api-base", base]) == 2
    assert gh.requests == []


def test_real_opener_refuses_redirects_without_forwarding_the_token() -> None:
    """End-to-end through urllib's own handler chain: a 302 must not be followed."""
    seen: list[tuple[str, str | None]] = []

    class FakeHTTPS(urllib.request.BaseHandler):
        handler_order = 100  # ahead of the default HTTPSHandler

        def https_open(self, req: urllib.request.Request) -> Any:
            seen.append((req.full_url, req.get_header("Authorization")))
            headers = Message()
            headers["Location"] = "https://evil.example/steal"
            resp = urllib.response.addinfourl(io.BytesIO(b""), headers, req.full_url, code=302)
            resp.msg = "Found"  # type: ignore[attr-defined]  # HTTPErrorProcessor reads .msg
            return resp

    client = control_approve.GitHubClient(TOKEN, opener=control_approve._build_opener(FakeHTTPS))
    with pytest.raises(control_approve.ApiUnreachable, match="redirect refused"):
        client.get("/user")
    assert [u for u, _ in seen] == ["https://api.github.com/user"]
    # control: urllib's DEFAULT redirect handler would have forwarded the header
    stock = urllib.request.build_opener(FakeHTTPS)
    seen.clear()
    with pytest.raises(Exception):
        stock.open(urllib.request.Request("https://api.github.com/user", headers={"Authorization": "Bearer x"}))
    assert any(u.startswith("https://evil.example") for u, _ in seen)


RC_LATER = [comment(1, marker()), comment(2, marker("REQUEST_CHANGES"))]
APPROVE_ONLY = [comment(1, marker())]


def test_success_reads_the_verdict_three_times(gh: FakeGitHub, config: Path) -> None:
    assert run(config) == 0
    assert sum(1 for r in gh.requests if "/comments" in r["url"]) == 3


def test_post_body_links_the_marker_read_two_selected(gh: FakeGitHub, config: Path) -> None:
    newer = comment(3, marker(reviewer="B850-CLAUDE-2"))
    gh.comment_script = [list(APPROVE_ONLY), APPROVE_ONLY + [newer], APPROVE_ONLY + [newer]]
    assert run(config) == 0
    body = json.loads(gh.posts()[0]["data"])["body"]
    assert "issuecomment-3" in body and "reviewer=B850-CLAUDE-2" in body
    assert "issuecomment-1" not in body


def test_request_changes_landing_before_the_post_prevents_it(gh: FakeGitHub, config: Path) -> None:
    gh.comment_script = [APPROVE_ONLY, RC_LATER]
    assert run(config) == 1
    assert gh.posts() == []


def test_request_changes_landing_after_the_post_dismisses_our_approval(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.comment_script = [APPROVE_ONLY, APPROVE_ONLY, RC_LATER]
    assert run(config) == 1
    assert len(gh.posts()) == 1
    puts = [r for r in gh.requests if r["method"] == "PUT"]
    assert len(puts) == 1
    assert gh.reviews[-1]["state"] == "DISMISSED"
    assert "changed while approving" in capsys.readouterr().err


def test_verdict_lost_after_post_for_any_reason_dismisses(gh: FakeGitHub, config: Path) -> None:
    edited_later = [comment(1, marker()), comment(2, "note", updated="2026-09-28T13:00:00Z")]
    gh.comment_script = [APPROVE_ONLY, APPROVE_ONLY, edited_later]
    assert run(config) == 1
    assert gh.reviews[-1]["state"] == "DISMISSED"


def test_verdict_lost_after_post_and_dismissal_fails_is_could_not_measure(gh: FakeGitHub, config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gh.comment_script = [APPROVE_ONLY, APPROVE_ONLY, RC_LATER]
    gh.dismiss_mode = "forbidden"
    assert run(config) == 3
    assert "STILL STANDS" in capsys.readouterr().err


def test_tool_does_not_shell_out() -> None:
    source = (TOOLS / "control_approve.py").read_text(encoding="utf-8")
    assert "subprocess" not in source and "os.system" not in source


def test_make_recipe_never_passes_the_token() -> None:
    mk = (TOOLS.parent / "mk" / "preflight.mk").read_text(encoding="utf-8")
    recipe = mk.split("pr-control-approve:", 1)[1].split("\n\n", 1)[0]
    assert "tools/control_approve.py" in recipe
    assert "TOKEN" not in recipe


def test_docs_do_not_overclaim_what_the_approval_buys() -> None:
    root = TOOLS.parents[1]
    skill = (root / ".claude" / "skills" / "pmoves-pr-merge" / "SKILL.md").read_text(encoding="utf-8")
    doc = (TOOLS.parent / "docs" / "operations" / "MERGE_MECHANICS.md").read_text(encoding="utf-8")
    tool_doc = control_approve.__doc__ or (TOOLS / "control_approve.py").read_text(encoding="utf-8")
    assert "no bypass" not in skill.lower()
    assert "reviewDecision should now be APPROVED" not in doc
    assert "actually met rather than bypassed" not in doc
    assert "genuinely satisfies" not in tool_doc
    # the code-owner caveat is stated wherever the approval is described
    for text in (skill, doc, tool_doc):
        assert "CODEOWNERS" in text


def test_docstring_lists_every_verdict_label() -> None:
    doc = control_approve.__doc__ or ""
    labels = set(control_approve._LABEL.values()) | {control_approve.DRY_RUN_LABEL}
    line = next(l for l in doc.splitlines() if l.startswith("``VERDICT:"))
    for label in labels:
        assert label in line, label


def test_operator_docs_contain_no_parseable_marker_candidate() -> None:
    # Copying the docs into a PR comment must never create a (malformed) marker.
    root = TOOLS.parents[1]
    for path in (
        TOOLS.parent / "docs" / "operations" / "MERGE_MECHANICS.md",
        root / ".claude" / "skills" / "pmoves-pr-merge" / "SKILL.md",
    ):
        assert control_verdict.CANDIDATE_RE.search(path.read_text(encoding="utf-8")) is None, path


def test_config_ships_without_a_hardcoded_login() -> None:
    import yaml

    cfg = yaml.safe_load((TOOLS.parent / "configs" / "control_approval.yaml").read_text(encoding="utf-8"))
    assert cfg["approver_login"] == ""
    source = (TOOLS / "control_approve.py").read_text(encoding="utf-8")
    assert "pmoves-ai-control" not in source
    assert re.search(r"pmoves-control(?![-\w])", source) is None
