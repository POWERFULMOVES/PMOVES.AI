#!/usr/bin/env python3
"""claim-collision-pre.py — PreToolUse (Write/Edit matcher) governance hook.

Enforces the Village Rule: "one owner per branch at a time."

KEYED ON THE LANE, NOT THE CLAIMANT. The first cut keyed on the backticked
owner-ID, which inverted the rule it was written to enforce -- reproduced both
ways on 2026-08-25:

  * different owner, SAME branch -> 0 collisions. Two agents could claim one
    branch and the gate stayed silent. That is the exact event the register
    exists to prevent.
  * same owner, DIFFERENT branch -> 1 collision. A node running several lanes
    at once (the normal case here; this node had five PRs open while writing
    this) was blocked from claiming unrelated work.

So it missed the hazard and blocked the routine case. Now a collision means
another owner already holds an open claim naming the same branch.

COVERAGE IS PARTIAL, AND DELIBERATELY VISIBLE. The lane is extracted from
freeform scope prose, so it only works when the claim names its branch: 53 of
131 historical claims do (55-70% of recent ones, where `Branch `x`` is becoming
convention). A claim that names no branch CANNOT be checked -- the hook says so
on stderr rather than exiting 0 as though it had verified something. Treat the
unkeyed path as unguarded, not as passing. The durable fix is an explicit
`lane:` field in the register format; until then this is a partial gate that
admits it.

OPT-IN: not wired by default. Operator activates via PreToolUse Write/Edit
matcher in .claude/settings.json.

Owner-ID format in the register (per existing entries):
  `<ISO_TIMESTAMP>` CLAIM `<OWNER-ID>` scope: ...
  `<ISO_TIMESTAMP>` RELEASE `<OWNER-ID>` scope: ...

We treat the backtick-quoted token immediately following CLAIM/RELEASE as
the owner identifier — that is the canonical lane axis used throughout the
register.

Exit codes:
  0  allow
  2  block (stderr fed back to Claude)
"""

import json
import os
import re
import sys
from pathlib import Path

REGISTER_NAME = "AGNOTE4482PHI.t1.md"
CLAIM_RE = re.compile(r'CLAIM\s+`([^`]+)`')
RELEASE_RE = re.compile(r'RELEASE\s+`([^`]+)`')
# A branch as the register writes it: conventional-commit prefix, backticked.
LANE_RE = re.compile(
    r'`((?:feat|fix|docs|chore|refactor|test|ci|perf|build)/[A-Za-z0-9._/-]+)`'
)


def open_claims_in(text: str) -> dict[str, tuple[int, set[str]]]:
    """Map owner -> (line number of their open CLAIM, lanes that CLAIM names).

    A CLAIM is "open" if no later RELEASE for the same owner-ID follows it.
    RELEASE still pairs by owner, because that is how the register closes a
    lane: a release must carry the exact string its claim was opened with.

    Line numbers are 1-based to match editor conventions.

    `split("\n")`, NOT `splitlines()`: the latter also breaks on vertical tab
    (U+000B), form feed (U+000C), NEL, and U+2028/9, none of which grep, sed, or
    an editor counts as a line. The register carries 7 such characters today (2
    VT, 5 FF), so `splitlines()` reported a claim on line 2005 that every other
    tool puts on 1998. The drift is cumulative, so it grows down the file and
    hits exactly the newest entries -- the ones a collision message points at.
    A line number that does not resolve sends the reader hunting, and this hook
    only speaks when it is blocking someone.
    """
    open_claims: dict[str, tuple[int, set[str]]] = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        if m := CLAIM_RE.search(line):
            open_claims[m.group(1)] = (lineno, set(LANE_RE.findall(line)))
        elif m := RELEASE_RE.search(line):
            open_claims.pop(m.group(1), None)
    return open_claims


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool = payload.get("tool_name", "")
    if tool not in ("Write", "Edit"):
        sys.exit(0)
    ti = payload.get("tool_input") or {}
    file_path = ti.get("file_path", "") or ""
    if not file_path.endswith(REGISTER_NAME):
        sys.exit(0)

    # Proposed-text source differs across tools.
    proposed = ti.get("new_string") if tool == "Edit" else ti.get("content")
    proposed = proposed or ""
    new_claims = [
        (m.group(1), set(LANE_RE.findall(proposed)))
        for m in CLAIM_RE.finditer(proposed)
    ]
    if not new_claims:
        sys.exit(0)

    register = Path(file_path)
    if not register.is_file():
        sys.exit(0)  # nothing to collide with yet
    try:
        existing = register.read_text(encoding="utf-8", errors="replace")
    except OSError:
        sys.exit(0)
    existing_open = open_claims_in(existing)

    # Collision == ANOTHER owner already holds an open claim naming this lane.
    # Same owner re-naming their own lane is not a collision: it is the node
    # that already holds it, and blocking that was the false positive this
    # hook shipped with.
    collisions = []
    unkeyed = []
    for owner, lanes in new_claims:
        if not lanes:
            unkeyed.append(owner)
            continue
        for other, (lineno, held) in existing_open.items():
            if other == owner:
                continue
            for lane in sorted(lanes & held):
                collisions.append((lane, other, lineno))

    if collisions:
        sys.stderr.write(
            "claim-collision-pre: refusing to add a CLAIM for a lane another owner holds.\n"
        )
        for lane, other, lineno in collisions:
            sys.stderr.write(
                f"  - lane `{lane}` is already claimed by `{other}` "
                f"(open CLAIM at line {lineno})\n"
            )
        sys.stderr.write(
            "Either coordinate a handoff, wait for their RELEASE, or pick a different "
            "branch (see Village Rule in AGNOTE4482PHI.t1.md).\n"
        )
        sys.exit(2)

    # Say plainly when the gate could not check, instead of exiting 0 as though
    # it had. An unkeyed claim is unguarded, not cleared.
    if unkeyed:
        for owner in unkeyed:
            sys.stderr.write(
                f"claim-collision-pre: NOT CHECKED - CLAIM by `{owner}` names no branch, "
                "so no lane could be compared. Add ``Branch `<name>``` to the scope to "
                "make this claim enforceable.\n"
            )
    sys.exit(0)


if __name__ == "__main__":
    main()
