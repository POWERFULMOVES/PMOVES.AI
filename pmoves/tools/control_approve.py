#!/usr/bin/env python3
"""Submit a genuine GitHub APPROVE review after a recorded control verdict.

The approval road (MERGE_MECHANICS.md section 5): the control body reviews a
PR independently and records a ``pmoves-control-verdict`` marker comment for
the exact head it reviewed (see ``control_verdict.py``). This tool then lets a
PMOVES.AI-branded machine user -- never the PR author -- submit an APPROVE
review pinned to that same commit, so the PR can satisfy the ruleset's
approval + code-owner requirements without an admin bypass.

Refusal matrix (every row exits non-zero with an honest message):

  exit 2  EXPECTED_HEAD not 40 lowercase hex (usage)
  exit 1  CONFIRM != "APPROVE #<N> @ <EXPECTED_HEAD>"
  exit 3  approver login not configured / config unreadable
  exit 3  PMOVES_CONTROL_TOKEN missing
  exit 3  any GitHub read fails (network, 5xx, auth) -- could not measure
  exit 1  token's /user login != configured approver login
  exit 1  PR closed / merged / draft / base != configured base
  exit 1  PR head != EXPECTED_HEAD (checked twice: before and just before POST)
  exit 1  approving account == PR author
  exit 1  no allowlisted APPROVE marker for exactly this head, latest is
          REQUEST_CHANGES, marker edited, or ambiguous (control_verdict.py)
  exit 1  POST rejected by GitHub (e.g. 422)
  exit 3  POST outcome unknown (network error after send)
  exit 1  post-verify: no APPROVED review by the approver on EXPECTED_HEAD
  exit 1  post-verify: PR head moved while approving (race)
  exit 0  APPROVED review by the approver on EXPECTED_HEAD read back from GitHub

``make`` collapses every nonzero exit to 2, so the last line of output is
always a structured ``VERDICT: <APPROVED|REFUSED|COULD-NOT-MEASURE> rc=<n>``.

Token handling: the token is read from the environment and only ever placed in
an ``Authorization`` request header via urllib. It is never an argv element,
never printed, and every message is passed through ``_redact`` as a backstop.

GitHub behaviours this relies on are tagged A1..A7 and listed in ONE place:
MERGE_MECHANICS.md "5.6 GitHub behaviours this road assumes".
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
LOGIN_ENV = "PMOVES_CONTROL_LOGIN"
MARKER_AUTHORS_ENV = "PMOVES_CONTROL_MARKER_AUTHORS"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "control_approval.yaml"
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
USER_AGENT = "pmoves-control-approve/1"

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

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ApiError(Exception):
    """GitHub answered with an HTTP error status."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class ApiUnreachable(Exception):
    """No HTTP answer at all (DNS, TLS, connection, timeout)."""


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


class GitHubClient:
    """Minimal GitHub REST client. The token lives only in request headers."""

    def __init__(self, token: str, api_base: str = API_BASE, timeout: float = 30.0):
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            return path
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
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
                headers = {k.lower(): v for k, v in dict(resp.headers or {}).items()}
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # noqa: BLE001 - detail is best-effort, status is reported
                detail = ""
            raise ApiError(exc.code, _redact(detail or str(exc.reason), self._token)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ApiUnreachable(_redact(str(exc), self._token)) from None
        payload = json.loads(raw.decode("utf-8")) if raw else None
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

    comments = _read(
        "list PR comments",
        lambda: client.get_pages(f"/repos/{owner_repo}/issues/{pr_number}/comments"),
    )
    selection = control_verdict.select_verdict(comments, expected_head, settings.marker_authors)
    if not selection.approved or selection.chosen is None:
        raise Outcome(EXIT_REFUSED, f"control verdict: {selection.reason}")
    marker = selection.chosen
    emit(f"control verdict: {selection.reason} ({marker.url})")

    reviews = _read("list reviews", lambda: client.get_pages(f"{pr_path}/reviews"))
    existing = _approver_reviews_on(reviews, token_login, expected_head)
    already = bool(existing) and str(existing[-1].get("state") or "") == "APPROVED"

    posted_id: int | None = None
    if already:
        posted_id = int(existing[-1].get("id") or 0)
        emit(f"an APPROVED review by {token_login} on {expected_head} already exists (id {posted_id}); not posting")
    elif dry_run:
        emit("dry-run: all preconditions pass; would POST an APPROVE review pinned to EXPECTED_HEAD")
        return EXIT_OK
    else:
        # Narrow the race window: re-read the head immediately before posting.
        pr_again = _read(f"re-read PR #{pr_number}", lambda: client.get(pr_path)) or {}
        _check_pr(pr_again, settings, expected_head, token_login)
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
            raise Outcome(EXIT_REFUSED, f"GitHub rejected the review: {exc}") from None
        except ApiUnreachable as exc:
            raise Outcome(
                EXIT_UNMEASURED,
                f"review POST outcome unknown ({exc}); read the PR reviews before retrying",
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
    try:
        if not HEAD_RE.match(args.expected_head or ""):
            raise Outcome(EXIT_USAGE, "EXPECTED_HEAD must be the full 40-character lowercase commit sha")
        settings = load_settings(Path(args.config), env, args.repo, args.base)
        if not token.strip():
            raise Outcome(EXIT_UNMEASURED, f"{TOKEN_ENV} is not set; cannot approve")
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
        stream = sys.stdout if code == EXIT_OK else sys.stderr
        print(_redact(f"{_LABEL.get(code, 'REFUSED')}: {outcome.message}", token), file=stream)
    print(f"VERDICT: {_LABEL.get(code, 'REFUSED')} rc={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
