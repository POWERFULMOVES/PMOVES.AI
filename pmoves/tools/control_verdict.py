#!/usr/bin/env python3
"""Control-body verdict markers for the PMOVES.AI approval road.

The control body (Three-Body "control" seat, e.g. B850-CLAUDE) records the
outcome of an independent code review as a PR comment carrying one
machine-readable marker::

    <!-- pmoves-control-verdict: v=1 verdict=APPROVE head=<40-hex> reviewer=<body> -->

``control_approve.py`` reads these markers and only then lets the machine
user's token submit a GitHub APPROVE review. This module makes no API calls:
it works on plain comment dicts (id, user.login, created_at, updated_at,
html_url, body), so any actor -- a machine user or a GitHub App -- can reuse it.

Trust model (stated honestly, see MERGE_MECHANICS.md "Approval road"):
a marker proves that an account on the allowlist RECORDED a verdict for an
exact commit. It does not prove who performed the review, nor how well. The
independence of the review rests on the Three-Body process, not on this parse.

Parse rules -- ASYMMETRIC and fail-closed (review round 2, P1):

* marker shape: exact, single spaces, ``v=1`` only; ``verdict`` in
  {APPROVE, REQUEST_CHANGES}; ``head`` exactly 40 lowercase hex; ``reviewer``
  1-64 chars of ``[A-Za-z0-9._-]`` starting alphanumeric;
* a well-formed REQUEST_CHANGES marker counts ANYWHERE in the body -- inside
  backticks, a code fence, mid-line, anywhere. A block is never hidden by
  markdown context, because context detection can be wrong;
* anything that *looks like* a marker (case-insensitive ``CANDIDATE_RE``) but
  does not match the exact shape makes the comment MALFORMED (it may be a
  mistyped block), again regardless of context;
* an APPROVE marker counts ONLY when it stands alone on its own unindented
  line outside a CommonMark fenced code block. A quoted APPROVE (inline code,
  a fence, indented, mid-line) simply does not count. Fence detection can
  therefore only ever make an APPROVE not count; it can never hide a block.

Selection rules (``select_verdict``), over comments by allowlisted authors,
ordered by (created_at, id):

* a comment's verdict for the head is REQUEST_CHANGES if it carries any RC for
  that head, else APPROVE if it carries a counting APPROVE for that head;
  markers for other heads are ignored;
* the LATEST comment with a verdict for the head wins; it must be APPROVE,
  unedited (``updated_at == created_at``; missing timestamps count as edited)
  and not malformed;
* a malformed comment, or ANY edited comment, by an allowlisted author posted
  after the winner makes the result ambiguous (an edit may have removed a later
  REQUEST_CHANGES). Deleted comments are invisible and cannot be detected;
* markers from non-allowlisted accounts neither approve nor block.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable

MARKER_VERSION = 1
VERDICTS = ("APPROVE", "REQUEST_CHANGES")

HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MARKER_RE = re.compile(
    r"<!-- pmoves-control-verdict: v=1 "
    r"verdict=(?P<verdict>APPROVE|REQUEST_CHANGES) "
    r"head=(?P<head>[0-9a-f]{40}) "
    r"reviewer=(?P<reviewer>[A-Za-z0-9][A-Za-z0-9._-]{0,63}) -->"
)
# Anything that claims to be a marker. Case-insensitive and whitespace-lax on
# purpose, so near-misses are reported as malformed instead of silently skipped.
CANDIDATE_RE = re.compile(r"<!--\s*pmoves-control-verdict", re.IGNORECASE)
CLI_DESCRIPTION = "Control-body verdict markers for the PMOVES.AI approval road."


class VerdictFormatError(ValueError):
    """Raised when a marker cannot be formatted from the given fields."""


@dataclass(frozen=True)
class Verdict:
    verdict: str
    head: str
    reviewer: str
    version: int = MARKER_VERSION


@dataclass(frozen=True)
class MarkerComment:
    comment_id: int
    author: str
    created_at: str
    updated_at: str
    url: str
    verdicts: tuple[Verdict, ...]
    malformed_reason: str = ""

    @property
    def malformed(self) -> bool:
        return bool(self.malformed_reason)

    def verdict_for(self, head: str) -> Verdict | None:
        """REQUEST_CHANGES for ``head`` wins inside one comment; else its last APPROVE."""
        mine = [v for v in self.verdicts if v.head == head]
        for verdict in mine:
            if verdict.verdict == "REQUEST_CHANGES":
                return verdict
        return mine[-1] if mine else None

    @property
    def edited(self) -> bool:
        return _is_edited(self.created_at, self.updated_at)


@dataclass
class Selection:
    approved: bool
    reason: str
    kind: str = "no_marker"  # approve|request_changes|ambiguous|edited|no_marker|untrusted_only|no_allowlist
    chosen: MarkerComment | None = None
    chosen_verdict: Verdict | None = None
    ignored_other_heads: int = 0
    ignored_untrusted: list[str] = field(default_factory=list)
    malformed: list[MarkerComment] = field(default_factory=list)


def _is_edited(created_at: str, updated_at: str) -> bool:
    # Fail closed: a missing/empty timestamp cannot show the comment is unedited.
    return not created_at or not updated_at or updated_at != created_at


def format_marker(verdict: str, head: str, reviewer: str) -> str:
    """Return the canonical marker string, validating every field."""
    if verdict not in VERDICTS:
        raise VerdictFormatError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    if not HEAD_RE.match(head or ""):
        raise VerdictFormatError("head must be exactly 40 lowercase hex characters")
    if not REVIEWER_RE.match(reviewer or ""):
        raise VerdictFormatError("reviewer must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    marker = (
        f"<!-- pmoves-control-verdict: v={MARKER_VERSION} verdict={verdict} "
        f"head={head} reviewer={reviewer} -->"
    )
    # Round-trip guard: what we emit must be exactly what we accept.
    assert MARKER_RE.fullmatch(marker), marker
    return marker


_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


def fenced_lines(lines: list[str]) -> set[int]:
    """Indexes of lines inside (or delimiting) a CommonMark fenced code block.

    Opening fence: up to 3 spaces, then 3+ backticks or tildes; a backtick
    fence's info string may not contain a backtick (so a line starting with
    ```inline``` code is NOT a fence). Closing fence: same character, at least
    the opening length, nothing but spaces/tabs after it. An unclosed fence runs
    to the end of the body. Used ONLY to decide whether an APPROVE counts, so a
    misdetection can only make an APPROVE not count.
    """
    inside: set[int] = set()
    fence: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        text = line.rstrip("\r")
        if fence is None:
            opened = _FENCE_OPEN_RE.match(text)
            if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
                fence = (opened.group(1)[0], len(opened.group(1)))
                inside.add(index)
            continue
        inside.add(index)
        closing = _FENCE_CLOSE_RE.match(text)
        if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= fence[1]:
            fence = None
    return inside


@dataclass(frozen=True)
class ParsedBody:
    verdicts: tuple[Verdict, ...] = ()  # every REQUEST_CHANGES + every counting APPROVE
    malformed_reason: str = ""  # non-empty: a marker-like string that is not a marker
    ignored_approvals: int = 0  # well-formed APPROVE markers that did not count


def parse_body(body: str) -> ParsedBody | None:
    """Parse a comment body; ``None`` when it carries no marker-like text."""
    text = body or ""
    candidates = list(CANDIDATE_RE.finditer(text))
    if not candidates:
        return None
    lines = text.split("\n")
    line_starts: list[int] = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line) + 1
    fenced = fenced_lines(lines)

    verdicts: list[Verdict] = []
    malformed: list[str] = []
    ignored = 0
    for cand in candidates:
        match = MARKER_RE.match(text, cand.start())
        if match is None:
            malformed.append("a marker-like string does not match the strict v=1 shape")
            continue
        verdict = Verdict(match.group("verdict"), match.group("head"), match.group("reviewer"))
        if verdict.verdict == "REQUEST_CHANGES":
            verdicts.append(verdict)  # a block counts wherever it appears
            continue
        line_no = max(i for i, start in enumerate(line_starts) if start <= cand.start())
        own_line = MARKER_RE.fullmatch(lines[line_no].rstrip()) is not None
        if own_line and line_no not in fenced:
            verdicts.append(verdict)
        else:
            ignored += 1
    return ParsedBody(tuple(verdicts), "; ".join(dict.fromkeys(malformed)), ignored)


def parse_comment(comment: dict[str, Any]) -> MarkerComment | None:
    """Turn a GitHub issue-comment JSON object into a MarkerComment (or None)."""
    parsed = parse_body(str(comment.get("body") or ""))
    if parsed is None:
        return None
    user = comment.get("user") or {}
    return MarkerComment(
        comment_id=int(comment.get("id") or 0),
        author=str(user.get("login") or ""),
        created_at=str(comment.get("created_at") or ""),
        updated_at=str(comment.get("updated_at") or ""),
        url=str(comment.get("html_url") or ""),
        verdicts=parsed.verdicts,
        malformed_reason=parsed.malformed_reason,
    )


def _order_key(marker: MarkerComment) -> tuple[str, int]:
    # GitHub timestamps are ISO-8601 UTC ("2026-09-28T12:00:00Z"), which sort
    # lexically; the comment id breaks ties within the same second.
    return (marker.created_at, marker.comment_id)


def _where(marker: MarkerComment) -> str:
    return marker.url or f"comment {marker.comment_id}"


def select_verdict(
    comments: Iterable[dict[str, Any]],
    head: str,
    allowed_authors: Iterable[str],
) -> Selection:
    """Decide whether the recorded control verdict approves ``head``."""
    allowed = {a.strip().lower() for a in allowed_authors if a and a.strip()}
    comments = list(comments)
    markers = sorted(
        (m for m in (parse_comment(c) for c in comments) if m is not None),
        key=_order_key,
    )
    trusted = [m for m in markers if m.author.lower() in allowed]
    untrusted = sorted({m.author for m in markers if m.author.lower() not in allowed and m.verdict_for(head)})
    relevant = [m for m in trusted if m.verdict_for(head) is not None]

    selection = Selection(
        approved=False,
        reason="",
        kind="no_marker",
        ignored_other_heads=sum(
            1 for m in trusted for v in m.verdicts if v.head != head
        ),
        ignored_untrusted=untrusted,
        malformed=[m for m in markers if m.malformed],
    )

    if not allowed:
        selection.kind = "no_allowlist"
        selection.reason = "no allowed marker authors configured"
        return selection

    if not relevant:
        latest_malformed = [m for m in trusted if m.malformed]
        if latest_malformed:
            selection.kind = "ambiguous"
            selection.reason = (
                f"no control verdict for head {head}, and a malformed marker from an allowed "
                f"author exists ({_where(latest_malformed[-1])}: {latest_malformed[-1].malformed_reason})"
            )
        elif untrusted:
            selection.kind = "untrusted_only"
            selection.reason = (
                f"verdict marker(s) for head {head} exist but none was authored by an "
                f"allowed control identity (found authors: {', '.join(untrusted)}; "
                f"allowed: {', '.join(sorted(allowed))})"
            )
        else:
            selection.reason = (
                f"no control verdict marker for head {head} "
                f"({selection.ignored_other_heads} marker(s) for other heads ignored)"
            )
        return selection

    latest = relevant[-1]
    verdict = latest.verdict_for(head)
    assert verdict is not None
    selection.chosen = latest
    selection.chosen_verdict = verdict

    if verdict.verdict != "APPROVE":
        selection.kind = "request_changes"
        selection.reason = f"latest control verdict for head {head} is {verdict.verdict} ({_where(latest)})"
        return selection

    if latest.malformed:
        selection.kind = "ambiguous"
        selection.reason = (
            f"ambiguous: the APPROVE comment also carries a malformed marker ({_where(latest)}: "
            f"{latest.malformed_reason})"
        )
        return selection

    if latest.edited:
        selection.kind = "edited"
        selection.reason = (
            f"the APPROVE marker comment {_where(latest)} was edited after posting "
            "(or has no usable timestamps); post a fresh verdict comment instead of editing"
        )
        return selection

    later_malformed = [m for m in trusted if m.malformed and _order_key(m) > _order_key(latest)]
    if later_malformed:
        first = later_malformed[0]
        selection.kind = "ambiguous"
        selection.reason = (
            "ambiguous: a malformed verdict marker from an allowed author was posted after "
            f"the APPROVE marker ({_where(first)}: {first.malformed_reason})"
        )
        return selection

    # An edit to ANY later comment by an allowed author may have removed or
    # rewritten a REQUEST_CHANGES. The current body cannot tell us what it said,
    # so any such edit is ambiguous. Remedy: post a fresh verdict. Deletions
    # leave no trace in the comments API (see MERGE_MECHANICS.md 6.2).
    for raw in comments:
        author = str((raw.get("user") or {}).get("login") or "")
        if author.lower() not in allowed:
            continue
        key = (str(raw.get("created_at") or ""), int(raw.get("id") or 0))
        if key <= _order_key(latest):
            continue
        if _is_edited(str(raw.get("created_at") or ""), str(raw.get("updated_at") or "")):
            selection.kind = "ambiguous"
            selection.reason = (
                "ambiguous: a comment by an allowed author posted after the APPROVE marker was "
                f"edited ({raw.get('html_url') or raw.get('id')}); it may have withdrawn the "
                "verdict -- post a fresh verdict comment"
            )
            return selection

    selection.approved = True
    selection.kind = "approve"
    selection.reason = f"APPROVE by {latest.author} (reviewer={verdict.reviewer}) for head {head}"
    return selection


def main(argv: list[str] | None = None) -> int:
    # __doc__ is None under `python -OO`, so never derive the CLI text from it.
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    sub = parser.add_subparsers(dest="command", required=True)
    fmt = sub.add_parser("format", help="print a canonical verdict marker")
    fmt.add_argument("--verdict", required=True, choices=VERDICTS)
    fmt.add_argument("--head", required=True)
    fmt.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    try:
        print(format_marker(args.verdict, args.head, args.reviewer))
    except VerdictFormatError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
