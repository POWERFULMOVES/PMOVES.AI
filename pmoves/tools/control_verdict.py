#!/usr/bin/env python3
"""Control-body verdict markers for the PMOVES.AI approval road.

The control body (Three-Body "control" seat, e.g. B850-CLAUDE) records the
outcome of an independent code review as a PR comment carrying one
machine-readable marker::

    <!-- pmoves-control-verdict: v=1 verdict=APPROVE head=<40-hex> reviewer=<body> -->

``control_approve.py`` reads these markers and only then lets the machine
user's token submit a GitHub APPROVE review.

Trust model (stated honestly, see MERGE_MECHANICS.md "Approval road"):
a marker proves that an account on the allowlist RECORDED a verdict for an
exact commit. It does not prove who performed the review, nor how well. The
independence of the review rests on the Three-Body process, not on this parse.

Parse rules (strict, fail-closed):

* exact shape, single spaces, ``v=1`` only;
* ``verdict`` in {APPROVE, REQUEST_CHANGES};
* ``head`` is exactly 40 lowercase hex characters;
* ``reviewer`` is 1-64 chars of ``[A-Za-z0-9._-]`` starting alphanumeric;
* the marker must stand alone on its own unindented line;
* markers inside inline code spans or fenced code blocks are quoted examples
  and are IGNORED (``strip_code``);
* anything else that *looks like* a marker (case-insensitive prefix) but does
  not match exactly is MALFORMED, and a comment carrying more than one marker
  is MALFORMED as a whole (a comment must say one thing).

Selection rules (``select_verdict``):

* markers are ordered by (comment created_at, comment id);
* only markers for the requested head are relevant: a marker for a different
  head is ignored;
* only markers authored by an allowlisted account count; the LATEST such
  marker for the head wins;
* the winner must be APPROVE and its comment must be unedited
  (``updated_at == created_at``) -- others with write access can edit a
  comment while it keeps its original author;
* ANY comment by an allowlisted author posted after the winner that has been
  edited makes the result ambiguous: the edit may have removed a later
  REQUEST_CHANGES. Deleted comments are invisible and cannot be detected;
* a malformed marker from an allowlisted author posted AFTER the winner makes
  the result ambiguous, and ambiguity refuses.
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
    verdict: Verdict | None
    malformed_reason: str = ""

    @property
    def malformed(self) -> bool:
        return self.verdict is None

    @property
    def edited(self) -> bool:
        return _is_edited(self.created_at, self.updated_at)


@dataclass
class Selection:
    approved: bool
    reason: str
    chosen: MarkerComment | None = None
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


_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE_RE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)", re.DOTALL)


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans (CommonMark-shaped).

    A marker quoted as an example -- in backticks or a ``` / ~~~ fence -- is
    documentation, not a vote. An unclosed fence runs to the end of the body,
    as it renders on GitHub. Indented code blocks are not stripped; they are
    caught instead by the own-line rule in ``parse_body``.
    """
    kept: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        if fence is None:
            opened = _FENCE_OPEN_RE.match(line)
            if opened:
                fence = opened.group(1)
                continue
            kept.append(line)
            continue
        closing = re.match(r"^ {0,3}(`{3,}|~{3,})\s*$", line)
        if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
            fence = None
    return _INLINE_CODE_RE.sub("", "".join(kept))


def parse_body(body: str) -> tuple[Verdict | None, str] | None:
    """Parse a comment body.

    Returns ``None`` when the body carries no marker-like text at all,
    ``(Verdict, "")`` for exactly one well-formed marker, and
    ``(None, reason)`` for anything malformed or ambiguous.
    """
    text = strip_code(body or "")
    candidates = list(CANDIDATE_RE.finditer(text))
    if not candidates:
        return None
    if len(candidates) > 1:
        return None, f"comment carries {len(candidates)} markers; exactly one is allowed"
    start = candidates[0].start()
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    line = text[line_start : len(text) if line_end == -1 else line_end].rstrip()
    match = MARKER_RE.fullmatch(line)
    if match is None:
        return None, "marker must stand alone on its own unindented line in the strict v=1 shape"
    return (
        Verdict(
            verdict=match.group("verdict"),
            head=match.group("head"),
            reviewer=match.group("reviewer"),
        ),
        "",
    )


def parse_comment(comment: dict[str, Any]) -> MarkerComment | None:
    """Turn a GitHub issue-comment JSON object into a MarkerComment (or None)."""
    parsed = parse_body(str(comment.get("body") or ""))
    if parsed is None:
        return None
    verdict, reason = parsed
    user = comment.get("user") or {}
    return MarkerComment(
        comment_id=int(comment.get("id") or 0),
        author=str(user.get("login") or ""),
        created_at=str(comment.get("created_at") or ""),
        updated_at=str(comment.get("updated_at") or ""),
        url=str(comment.get("html_url") or ""),
        verdict=verdict,
        malformed_reason=reason,
    )


def _order_key(marker: MarkerComment) -> tuple[str, int]:
    # GitHub timestamps are ISO-8601 UTC ("2026-09-28T12:00:00Z"), which sort
    # lexically; the comment id breaks ties within the same second.
    return (marker.created_at, marker.comment_id)


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
    malformed = [m for m in markers if m.malformed]
    wellformed = [m for m in markers if not m.malformed]

    other_heads = [m for m in wellformed if m.verdict and m.verdict.head != head]
    relevant = [m for m in wellformed if m.verdict and m.verdict.head == head]
    trusted = [m for m in relevant if m.author.lower() in allowed]
    untrusted = sorted({m.author for m in relevant if m.author.lower() not in allowed})

    selection = Selection(
        approved=False,
        reason="",
        ignored_other_heads=len(other_heads),
        ignored_untrusted=untrusted,
        malformed=malformed,
    )

    if not allowed:
        selection.reason = "no allowed marker authors configured"
        return selection

    if not trusted:
        if untrusted:
            selection.reason = (
                f"verdict marker(s) for head {head} exist but none was authored by an "
                f"allowed control identity (found authors: {', '.join(untrusted)}; "
                f"allowed: {', '.join(sorted(allowed))})"
            )
        else:
            selection.reason = (
                f"no control verdict marker for head {head} "
                f"({len(other_heads)} marker(s) for other heads ignored, "
                f"{len(malformed)} malformed)"
            )
        return selection

    latest = trusted[-1]
    selection.chosen = latest
    assert latest.verdict is not None
    if latest.verdict.verdict != "APPROVE":
        selection.reason = (
            f"latest control verdict for head {head} is {latest.verdict.verdict} "
            f"({latest.url or 'comment ' + str(latest.comment_id)})"
        )
        return selection

    if latest.edited:
        selection.reason = (
            f"the APPROVE marker comment {latest.url or latest.comment_id} was edited after "
            "posting; post a fresh verdict comment instead of editing"
        )
        return selection

    trusted_malformed_after = [
        m
        for m in malformed
        if m.author.lower() in allowed and _order_key(m) > _order_key(latest)
    ]
    if trusted_malformed_after:
        first = trusted_malformed_after[0]
        selection.reason = (
            "ambiguous: a malformed verdict marker from an allowed author was posted after "
            f"the APPROVE marker ({first.url or first.comment_id}: {first.malformed_reason})"
        )
        return selection

    # An edit to ANY later comment by an allowed author may have removed or
    # rewritten a REQUEST_CHANGES (e.g. APPROVE c1, REQUEST_CHANGES c2, then c2
    # edited to drop the marker or point it at another head). The current body
    # cannot tell us what it said, so any such edit is ambiguous. Remedy: post a
    # fresh verdict. Deletions leave no trace in the comments API (see
    # MERGE_MECHANICS.md 6.2).
    for raw in comments:
        author = str((raw.get("user") or {}).get("login") or "")
        if author.lower() not in allowed:
            continue
        key = (str(raw.get("created_at") or ""), int(raw.get("id") or 0))
        if key <= _order_key(latest):
            continue
        if _is_edited(str(raw.get("created_at") or ""), str(raw.get("updated_at") or "")):
            selection.reason = (
                "ambiguous: a comment by an allowed author posted after the APPROVE marker was "
                f"edited ({raw.get('html_url') or raw.get('id')}); it may have withdrawn the "
                "verdict -- post a fresh verdict comment"
            )
            return selection

    selection.approved = True
    selection.reason = (
        f"APPROVE by {latest.author} (reviewer={latest.verdict.reviewer}) for head {head}"
    )
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
