#!/usr/bin/env python3
"""Submit a genuine GitHub APPROVE review after a recorded control verdict.

The approval road (MERGE_MECHANICS.md section 6): the control body reviews a
PR independently and records a ``pmoves-control-verdict`` marker comment for
the exact head it reviewed (see ``control_verdict.py``). This tool then lets a
PMOVES.AI-branded machine user -- never the PR author -- submit an APPROVE
review pinned to that same commit. That review counts toward the ruleset's
approving-review count. It does NOT satisfy the code-owner requirement until
the machine user is co-listed in CODEOWNERS (a follow-up, MERGE_MECHANICS.md
6.5 step 6). Merging is separate and still uses the bypass: the guarded merge
target passes --admin, and this personal-account repo has no merge queue
(MERGE_MECHANICS.md 6.7).

Refusal matrix (every row exits non-zero with an honest message):

  exit 2  EXPECTED_HEAD not 40 lowercase hex (usage)
  exit 1  CONFIRM != "APPROVE #<N> @ <EXPECTED_HEAD>"
  exit 3  approver login not configured / config unreadable
  exit 3  PMOVES_CONTROL_TOKEN missing
  exit 2  --api-base is not an https URL with a host
  exit 3  any GitHub read fails (network, 5xx, auth, a redirect, a Link URL
          on another host) -- could not measure
  exit 1  token's /user login != configured approver login
  exit 1  PR closed / merged / draft / base != configured base
  exit 1  PR head != EXPECTED_HEAD (checked twice: before and just before POST)
  exit 1  approving account == PR author
  exit 1  no allowlisted APPROVE marker for exactly this head, marker
          edited, or ambiguous (control_verdict.py)
  exit 1  latest verdict is REQUEST_CHANGES -- any standing APPROVED review by
          the approver on the head is DISMISSED first (verified by read-back)
  exit 3  ...and that dismissal failed or could not be verified
  exit 1  POST rejected by GitHub with a 4xx (e.g. 422)
  exit 3  POST outcome unknown: 5xx, network error, bad/partial body
  exit 1  post-verify: no APPROVED review by the approver on EXPECTED_HEAD
  exit 1  post-verify: PR head moved while approving (race)
  exit 1  the verdict comments are re-read just before the POST and again in
          the post-check; a verdict lost before the POST refuses, and one lost
          after it DISMISSES the approval just posted (exit 3 if that fails)
  exit 3  any unexpected error (always still ends with the VERDICT line)
  exit 0  APPROVED review by the approver on EXPECTED_HEAD read back from GitHub
  exit 0  --dry-run with every precondition passing: VERDICT: DRY-RUN-WOULD-APPROVE
          (nothing written; never printed as APPROVED)

``make`` collapses every nonzero exit to 2, so the last line of output is
always a structured ``VERDICT: <APPROVED|REFUSED|COULD-NOT-MEASURE> rc=<n>``.

Token delivery: preferably PMOVES_CONTROL_TOKEN_FILE, a 0600 file owned by the
invoking user (checked); PMOVES_CONTROL_TOKEN is accepted for one-off
invocations. It must NOT be delivered through the shared env tiers: anything
every delivery body loads would make the road self-serve (MERGE_MECHANICS 6.2).

Token handling: the token is read from that file or variable and only ever placed in
an ``Authorization`` request header via urllib, over https, to the configured
API host only: redirects are refused (urllib would forward the header) and
pagination Link URLs on any other scheme or host are refused. It is never an argv element,
never printed, and every message is passed through ``_redact`` as a backstop.

GitHub behaviours this relies on are tagged A1..A7 and listed in ONE place:
MERGE_MECHANICS.md "6.6 GitHub behaviours this road assumes".
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import control_verdict  # noqa: E402

API_BASE = "https://api.github.com"
TOKEN_ENV = "PMOVES_CONTROL_TOKEN"
TOKEN_FILE_ENV = "PMOVES_CONTROL_TOKEN_FILE"
LOGIN_ENV = "PMOVES_CONTROL_LOGIN"
MARKER_AUTHORS_ENV = "PMOVES_CONTROL_MARKER_AUTHORS"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "control_approval.yaml"
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
USER_AGENT = "pmoves-control-approve/1"

DRY_RUN_LABEL = "DRY-RUN-WOULD-APPROVE"
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNMEASURED = 3
_LABEL = {
    EXIT_OK: "APPROVED",
    EXIT_REFUSED: "REFUSED",
    EXIT_USAGE: "REFUSED",
    EXIT_UNMEASURED: "COULD-NOT-MEASURE",
}


class Outcome(Exception):
    """Terminal result carrying an exit code and an honest message."""

    def __init__(self, code: int, message: str, label: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.label = label


class ApiError(Exception):
    """GitHub answered with an HTTP error status."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class ApiUnreachable(Exception):
    """No usable HTTP answer: DNS/TLS/connection/timeout, a truncated body
    (http.client.IncompleteRead), or a body that is not the JSON we asked for."""


@dataclass
class Settings:
    repo: str
    base: str
    approver_login: str
    marker_authors: list[str]


def _redact(text: str, secret: str | None) -> str:
    if secret and len(secret) >= 4:
        return str(text).replace(secret, "[REDACTED]")
    return str(text)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect.

    urllib's default handler re-sends request headers -- including
    Authorization -- to the Location target. The GitHub REST calls made here
    never need a redirect, so any 3xx is surfaced as an HTTPError instead.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise urllib.error.HTTPError(req.full_url, code, f"redirect refused ({msg})", headers, fp)


def _build_opener(*extra: Any) -> Any:
    return urllib.request.build_opener(_NoRedirect, *extra)


def validate_api_base(api_base: str) -> tuple[str, str]:
    """Return (base-url, lower-case host) or raise ValueError. https only, no userinfo."""
    parts = urllib.parse.urlsplit(api_base.strip())
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError(f"--api-base must be an https URL with a host, got {api_base!r}")
    if parts.query or parts.fragment:
        raise ValueError("--api-base must not carry a query or fragment")
    return api_base.strip().rstrip("/"), parts.netloc.lower()


class GitHubClient:
    """Minimal GitHub REST client. The token lives only in request headers,
    and is only ever sent over https to the configured API host."""

    def __init__(self, token: str, api_base: str = API_BASE, timeout: float = 30.0, opener: Any = None):
        self._token = token
        self._api_base, self._netloc = validate_api_base(api_base)
        self._timeout = timeout
        self._opener = opener if opener is not None else _build_opener()

    def _url(self, path: str) -> str:
        if "://" in path:
            # Absolute URLs only arrive via Link headers: pin them to our host.
            parts = urllib.parse.urlsplit(path)
            if parts.scheme != "https" or parts.netloc.lower() != self._netloc:
                raise ApiUnreachable(
                    f"refusing to send the token to {parts.scheme}://{parts.netloc} "
                    f"(pinned to https://{self._netloc})"
                )
            return path
        if not path.startswith("/"):
            raise ApiUnreachable(f"refusing a non-absolute API path {path!r}")
        return f"{self._api_base}{path}"

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self._url(path), data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", USER_AGENT)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                raw = resp.read()
                headers = {k.lower(): v for k, v in dict(resp.headers or {}).items()}
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                raise ApiUnreachable(f"HTTP {exc.code} redirect refused; the token is never forwarded") from None
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # noqa: BLE001 - detail is best-effort, status is reported
                detail = ""
            raise ApiError(exc.code, _redact(detail or str(exc.reason), self._token)) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            raise ApiUnreachable(_redact(f"{type(exc).__name__}: {exc}", self._token)) from None
        except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
            raise ApiUnreachable(_redact(f"unparseable response body ({type(exc).__name__})", self._token)) from None
        return payload, headers

    def get(self, path: str) -> Any:
        return self.request("GET", path)[0]

    def get_pages(self, path: str, max_pages: int = 50) -> list[Any]:
        sep = "&" if "?" in path else "?"
        url: str | None = f"{path}{sep}per_page=100"
        items: list[Any] = []
        for _ in range(max_pages):
            if url is None:
                return items
            payload, headers = self.request("GET", url)
            if not isinstance(payload, list):
                raise ApiError(0, f"expected a JSON list from {path}")
            items.extend(payload)
            url = _next_link(headers.get("link", ""))
        if url is not None:
            # Refuse to decide on a truncated read.
            raise ApiUnreachable(f"pagination for {path} exceeded {max_pages} pages")
        return items


def _next_link(link_header: str) -> str | None:
    for part in (link_header or "").split(","):
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"', part)
        if match:
            return match.group(1)
    return None


def load_settings(config_path: Path, env: dict[str, str], repo_override: str = "", base_override: str = "") -> Settings:
    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise Outcome(EXIT_UNMEASURED, f"cannot read {config_path}: PyYAML unavailable ({exc})") from None
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise Outcome(EXIT_UNMEASURED, f"cannot read {config_path}: {exc}") from None
        if not isinstance(loaded, dict):
            raise Outcome(EXIT_UNMEASURED, f"{config_path} is not a mapping")
        data = loaded
    elif not env.get(LOGIN_ENV):
        raise Outcome(EXIT_UNMEASURED, f"config {config_path} not found and {LOGIN_ENV} unset")

    approver = (env.get(LOGIN_ENV) or str(data.get("approver_login") or "")).strip()
    authors_env = env.get(MARKER_AUTHORS_ENV, "")
    if authors_env.strip():
        authors = [a.strip() for a in authors_env.split(",") if a.strip()]
    else:
        authors = [str(a).strip() for a in (data.get("marker_authors") or []) if str(a).strip()]
    settings = Settings(
        repo=(repo_override or str(data.get("repo") or "")).strip(),
        base=(base_override or str(data.get("base") or "main")).strip(),
        approver_login=approver,
        marker_authors=authors,
    )
    if not settings.approver_login:
        raise Outcome(
            EXIT_UNMEASURED,
            f"approver login not configured (set approver_login in {config_path} or {LOGIN_ENV}); "
            "the machine user may not exist yet",
        )
    if not settings.repo or "/" not in settings.repo:
        raise Outcome(EXIT_UNMEASURED, "repo not configured as owner/name")
    if not settings.marker_authors:
        raise Outcome(EXIT_UNMEASURED, "no marker_authors configured")
    return settings


def read_token_file(path: str) -> str:
    """Read the token from a restricted file (the preferred delivery path).

    Refuses a file that is not a regular file, is not owned by the current
    user, or is readable/writable by group or others. POSIX only: on Windows
    the mode bits carry no such meaning, so the check is skipped there and the
    file's ACL is the operator's responsibility.
    """
    try:
        st = os.stat(path)
    except OSError as exc:
        raise Outcome(EXIT_UNMEASURED, f"cannot stat {TOKEN_FILE_ENV}: {type(exc).__name__}") from None
    if not stat.S_ISREG(st.st_mode):
        raise Outcome(EXIT_REFUSED, f"{TOKEN_FILE_ENV} is not a regular file")
    if os.name != "nt":
        if st.st_uid != os.getuid():
            raise Outcome(EXIT_REFUSED, f"{TOKEN_FILE_ENV} is not owned by the current user")
        if st.st_mode & 0o077:
            raise Outcome(
                EXIT_REFUSED,
                f"{TOKEN_FILE_ENV} is accessible to group/others (mode {oct(st.st_mode & 0o777)}); chmod 600 it",
            )
    try:
        with open(path, encoding="utf-8") as handle:
            value = handle.read().strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise Outcome(EXIT_UNMEASURED, f"cannot read {TOKEN_FILE_ENV}: {type(exc).__name__}") from None
    if not value:
        raise Outcome(EXIT_UNMEASURED, f"{TOKEN_FILE_ENV} is empty")
    return value


def _read(action: str, fn: Callable[[], Any]) -> Any:
    """Run a GitHub read; any failure is could-not-measure, never a pass."""
    try:
        return fn()
    except ApiError as exc:
        raise Outcome(EXIT_UNMEASURED, f"could not {action}: {exc}") from None
    except ApiUnreachable as exc:
        raise Outcome(EXIT_UNMEASURED, f"could not {action}: {exc}") from None


def _check_pr(pr: dict[str, Any], settings: Settings, expected_head: str, approver: str) -> str:
    """Validate PR state; return the author login."""
    author = str((pr.get("user") or {}).get("login") or "")
    if pr.get("merged") or pr.get("merged_at"):
        raise Outcome(EXIT_REFUSED, "PR is already merged")
    if str(pr.get("state") or "") != "open":
        raise Outcome(EXIT_REFUSED, f"PR is not open (state={pr.get('state')!r})")
    if pr.get("draft"):
        raise Outcome(EXIT_REFUSED, "PR is a draft")
    base = str((pr.get("base") or {}).get("ref") or "")
    if base != settings.base:
        raise Outcome(EXIT_REFUSED, f"PR targets {base!r}, not {settings.base!r}")
    head = str((pr.get("head") or {}).get("sha") or "")
    if head != expected_head:
        raise Outcome(
            EXIT_REFUSED,
            f"PR head is {head or '<unknown>'}, not EXPECTED_HEAD {expected_head}; "
            "re-review the new head and record a new verdict",
        )
    if not author:
        raise Outcome(EXIT_UNMEASURED, "PR author login missing from API response")
    if author.lower() == approver.lower():
        raise Outcome(EXIT_REFUSED, f"approving account {approver} is the PR author; self-approval does not count (A7)")
    return author


def _approver_reviews_on(reviews: list[dict[str, Any]], approver: str, head: str) -> list[dict[str, Any]]:
    mine = [
        r
        for r in reviews
        if str((r.get("user") or {}).get("login") or "").lower() == approver.lower()
        and str(r.get("commit_id") or "") == head
    ]
    return sorted(mine, key=lambda r: (str(r.get("submitted_at") or ""), int(r.get("id") or 0)))


def _withdraw_standing_approvals(
    client: GitHubClient,
    pr_path: str,
    approver: str,
    head: str,
    why: str,
    dry_run: bool,
) -> str:
    """Dismiss every standing APPROVED review by ``approver`` on ``head``.

    Returns a note for the refusal message. Any failure to establish that no
    approval stands is COULD-NOT-MEASURE: a REQUEST_CHANGES verdict with an
    approval still counting is exactly the state an operator must not miss.
    """
    reviews = _read(
        "list reviews to find a standing approval (one may still count)",
        lambda: client.get_pages(f"{pr_path}/reviews"),
    )
    standing = [
        int(r.get("id") or 0)
        for r in _approver_reviews_on(reviews, approver, head)
        if str(r.get("state") or "") == "APPROVED"
    ]
    if not standing:
        return f"no standing approval by {approver} on {head}"
    if dry_run:
        return f"dry-run: would dismiss standing approval(s) {standing} by {approver}"
    for review_id in standing:
        try:
            client.request(
                "PUT",
                f"{pr_path}/reviews/{review_id}/dismissals",
                {"message": f"Withdrawn by the PMOVES.AI control road: {why}", "event": "DISMISS"},
            )
        except (ApiError, ApiUnreachable) as exc:
            raise Outcome(
                EXIT_UNMEASURED,
                f"{why}, but APPROVED review {review_id} by {approver} STILL STANDS on {head} and could "
                f"not be dismissed ({exc}); dismiss it by hand before anything merges",
            ) from None
    after = _read(
        "read reviews back after dismissing (an approval may still stand)",
        lambda: client.get_pages(f"{pr_path}/reviews"),
    )
    still = [
        int(r.get("id") or 0)
        for r in after
        if int(r.get("id") or 0) in standing and str(r.get("state") or "") == "APPROVED"
    ]
    if still:
        raise Outcome(
            EXIT_UNMEASURED,
            f"{why}; dismissal was requested but review(s) {still} still read APPROVED; "
            "dismiss by hand before anything merges",
        )
    return f"dismissed standing approval(s) {standing} by {approver}"


def approve(
    *,
    pr_number: int,
    expected_head: str,
    confirm: str,
    settings: Settings,
    client: GitHubClient,
    emit: Callable[[str], None],
    dry_run: bool = False,
) -> int:
    expected_confirm = f"APPROVE #{pr_number} @ {expected_head}"
    if confirm != expected_confirm:
        raise Outcome(EXIT_REFUSED, f"CONFIRM mismatch: expected exactly {expected_confirm!r}")

    owner_repo = settings.repo
    pr_path = f"/repos/{owner_repo}/pulls/{pr_number}"

    me = _read("read the token's identity (GET /user)", lambda: client.get("/user")) or {}
    token_login = str(me.get("login") or "")
    if not token_login:
        raise Outcome(EXIT_UNMEASURED, "GET /user returned no login")
    if token_login.lower() != settings.approver_login.lower():
        raise Outcome(
            EXIT_REFUSED,
            f"token belongs to {token_login!r}, not the configured approver {settings.approver_login!r}",
        )
    emit(f"approver: {token_login} (matches configured login)")

    pr = _read(f"read PR #{pr_number}", lambda: client.get(pr_path)) or {}
    author = _check_pr(pr, settings, expected_head, token_login)
    emit(f"PR #{pr_number}: open, base={settings.base}, head={expected_head}, author={author}")

    def current_verdict(action: str) -> control_verdict.Selection:
        comments = _read(
            action,
            lambda: client.get_pages(f"/repos/{owner_repo}/issues/{pr_number}/comments"),
        )
        return control_verdict.select_verdict(comments, expected_head, settings.marker_authors)

    def refuse(selection: control_verdict.Selection, *, withdraw_any: bool, prefix: str = "control verdict") -> None:
        reason = f"{prefix}: {selection.reason}"
        chosen = selection.chosen
        is_rc = chosen is not None and chosen.verdict is not None and chosen.verdict.verdict == "REQUEST_CHANGES"
        if is_rc or withdraw_any:
            # A REQUEST_CHANGES verdict must withdraw an approval this road already
            # gave, not merely stop future runs (review round 1, P2-3). After our
            # own POST, ANY loss of the verdict withdraws what we just posted.
            reason += "; " + _withdraw_standing_approvals(
                client, pr_path, token_login, expected_head, reason, dry_run,
            )
        raise Outcome(EXIT_REFUSED, reason)

    selection = current_verdict("list PR comments")
    if not selection.approved or selection.chosen is None:
        refuse(selection, withdraw_any=False)
    assert selection.chosen is not None
    marker = selection.chosen
    emit(f"control verdict: {selection.reason} ({marker.url})")

    reviews = _read("list reviews", lambda: client.get_pages(f"{pr_path}/reviews"))
    existing = _approver_reviews_on(reviews, token_login, expected_head)
    already = bool(existing) and str(existing[-1].get("state") or "") == "APPROVED"

    if dry_run:
        state = (
            f"an APPROVED review by {token_login} already exists on it (id {existing[-1].get('id')})"
            if already
            else "would POST an APPROVE review pinned to EXPECTED_HEAD"
        )
        raise Outcome(EXIT_OK, f"dry-run: all preconditions pass; {state}; nothing was written", label=DRY_RUN_LABEL)

    posted_id: int | None = None
    if already:
        posted_id = int(existing[-1].get("id") or 0)
        emit(f"an APPROVED review by {token_login} on {expected_head} already exists (id {posted_id}); not posting")
    else:
        # Narrow the race window: re-read the head immediately before posting.
        pr_again = _read(f"re-read PR #{pr_number}", lambda: client.get(pr_path)) or {}
        _check_pr(pr_again, settings, expected_head, token_login)
        # ...and the verdict: a REQUEST_CHANGES may have landed since the first read.
        again = current_verdict("re-read PR comments before approving")
        if not again.approved or again.chosen is None:
            refuse(again, withdraw_any=False, prefix="control verdict changed before approving")
        body = (
            f"Approved via the PMOVES.AI control approval road for `{expected_head}`.\n\n"
            f"Control verdict: {marker.url} (reviewer={marker.verdict.reviewer if marker.verdict else '?'}, "
            f"recorded by {marker.author}).\n\n"
            "This approval is pinned to that commit (A4); any new push dismisses it "
            "(dismiss_stale_reviews_on_push, A5) and needs a fresh verdict."
        )
        try:
            created, _ = client.request(
                "POST",
                f"{pr_path}/reviews",
                {"commit_id": expected_head, "event": "APPROVE", "body": body},
            )
        except ApiError as exc:
            # Only a 4xx is a rejection. A 5xx (502/504 from the edge) can arrive
            # AFTER GitHub stored the review, so its outcome is unknown.
            if 400 <= exc.status < 500:
                raise Outcome(EXIT_REFUSED, f"GitHub rejected the review: {exc}") from None
            raise Outcome(
                EXIT_UNMEASURED,
                f"review POST outcome unknown ({exc}); the review may have been stored -- "
                "read the PR reviews before retrying",
            ) from None
        except ApiUnreachable as exc:
            raise Outcome(
                EXIT_UNMEASURED,
                f"review POST outcome unknown ({exc}); the review may have been stored -- "
                "read the PR reviews before retrying",
            ) from None
        posted_id = int((created or {}).get("id") or 0)
        emit(f"posted review id {posted_id}")

    # Post-verify: read back what GitHub actually holds.
    after = _read("read reviews back", lambda: client.get_pages(f"{pr_path}/reviews"))
    mine = _approver_reviews_on(after, token_login, expected_head)
    match = [r for r in mine if str(r.get("state") or "") == "APPROVED" and (not posted_id or int(r.get("id") or 0) == posted_id)]
    if not match:
        states = [str(r.get("state")) for r in mine]
        raise Outcome(
            EXIT_REFUSED,
            f"post-verify failed: no APPROVED review by {token_login} on {expected_head} "
            f"(reviews by approver on that commit: {states or 'none'})",
        )
    pr_final = _read(f"re-read PR #{pr_number} after approving", lambda: client.get(pr_path)) or {}
    final_head = str((pr_final.get("head") or {}).get("sha") or "")
    if final_head != expected_head:
        raise Outcome(
            EXIT_REFUSED,
            f"head moved to {final_head or '<unknown>'} while approving: the approval is pinned to "
            f"{expected_head} (A4) and is dismissed or does not count for the new head (A5); "
            "re-review the new head",
        )
    final = current_verdict("re-read PR comments after approving")
    if not final.approved or final.chosen is None:
        refuse(final, withdraw_any=True, prefix="control verdict changed while approving")
    emit(f"verified: review {match[-1].get('id')} APPROVED by {token_login} on {expected_head}")
    return EXIT_OK


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    parser = argparse.ArgumentParser(description="Submit a control-road APPROVE review (see module docstring).")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--repo", default="", help="owner/name; default from config")
    parser.add_argument("--base", default="", help="required base branch; default from config")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--dry-run", action="store_true", help="run every check, do not POST")
    args = parser.parse_args(argv)

    token = env.get(TOKEN_ENV, "")

    def emit(line: str) -> None:
        print(_redact(line, token))

    code: int
    label = ""
    try:
        try:
            validate_api_base(args.api_base)
        except ValueError as exc:
            raise Outcome(EXIT_USAGE, str(exc)) from None
        if not HEAD_RE.match(args.expected_head or ""):
            raise Outcome(EXIT_USAGE, "EXPECTED_HEAD must be the full 40-character lowercase commit sha")
        settings = load_settings(Path(args.config), env, args.repo, args.base)
        token_file = env.get(TOKEN_FILE_ENV, "").strip()
        if token_file:
            if token.strip():
                raise Outcome(EXIT_USAGE, f"set only one of {TOKEN_FILE_ENV} and {TOKEN_ENV}")
            token = read_token_file(token_file)
        if not token.strip():
            raise Outcome(
                EXIT_UNMEASURED, f"no token: set {TOKEN_FILE_ENV} (preferred) or {TOKEN_ENV}; cannot approve"
            )
        client = GitHubClient(token.strip(), api_base=args.api_base)
        code = approve(
            pr_number=args.pr,
            expected_head=args.expected_head,
            confirm=args.confirm,
            settings=settings,
            client=client,
            emit=emit,
            dry_run=args.dry_run,
        )
    except Outcome as outcome:
        code = outcome.code
        label = outcome.label
        stream = sys.stdout if code == EXIT_OK else sys.stderr
        print(_redact(f"{label or _LABEL.get(code, 'REFUSED')}: {outcome.message}", token), file=stream)
    except Exception as exc:  # noqa: BLE001 - the VERDICT line must always be printed
        # Anything unexpected (bad data shapes, a bug) is could-not-measure: it may
        # have happened after the POST, so "refused" would be a false statement.
        code = EXIT_UNMEASURED
        print(
            _redact(f"COULD-NOT-MEASURE: unexpected {type(exc).__name__}: {exc}", token),
            file=sys.stderr,
        )
    print(f"VERDICT: {label or _LABEL.get(code, 'REFUSED')} rc={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
