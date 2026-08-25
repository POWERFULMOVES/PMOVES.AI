#!/usr/bin/env python3
"""claim-collision-pre.py — PreToolUse (Write/Edit matcher) governance hook.

Enforces the Village Rule: "one owner per branch at a time." When Write/Edit
targets AGNOTE4482PHI.t1.md, scan the proposed content for a new CLAIM whose
owner-ID is still open (no matching RELEASE later in the existing file). If
found, block with the line number of the prior CLAIM so the agent can either
hand off or wait.

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


def open_claims_in(text: str) -> dict[str, int]:
    """Return {owner_id: line_no_of_latest_unmatched_claim}.

    A CLAIM is "open" if no later RELEASE for the same owner-ID follows it.
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
    open_claims: dict[str, int] = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        if m := CLAIM_RE.search(line):
            open_claims[m.group(1)] = lineno
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
    new_owners = {m.group(1) for m in CLAIM_RE.finditer(proposed)}
    if not new_owners:
        sys.exit(0)

    register = Path(file_path)
    if not register.is_file():
        sys.exit(0)  # nothing to collide with yet
    try:
        existing = register.read_text(encoding="utf-8", errors="replace")
    except OSError:
        sys.exit(0)
    existing_open = open_claims_in(existing)

    collisions = [(o, existing_open[o]) for o in new_owners if o in existing_open]
    if collisions:
        sys.stderr.write(
            "claim-collision-pre: refusing to add CLAIM that collides with an open lane.\n"
        )
        for owner, lineno in collisions:
            sys.stderr.write(f"  - owner `{owner}` already has an open CLAIM at line {lineno}\n")
        sys.stderr.write(
            "Either issue a RELEASE for the prior CLAIM first, or coordinate a handoff "
            "(see Village Rule in AGNOTE4482PHI.t1.md).\n"
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
