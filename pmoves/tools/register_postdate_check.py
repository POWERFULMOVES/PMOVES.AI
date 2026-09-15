#!/usr/bin/env python3
"""Assert every register row was filed no LATER than the commit carrying it.

THE INVARIANT: `row_timestamp <= commit_creation_time` (`%cI`).

A row records an event; a commit carries the row. The row cannot honestly claim
a moment that had not happened yet when it was written down. Anything failing
this was typed, not read off a clock.

AGAINST `%cI`, THE COMMITTER DATE, AND NOT `%aI`. The first cut compared against
the AUTHOR date and claimed to have no false-positive mode. It has one, and it
is the commonest git operation there is: `git commit --amend` preserves the
original author date and updates only the committer date, so a row filed at
11:30 by the clock-reading sanctioned path and folded into a commit authored at
10:00 was reported POSTDATED by 1h30m. Measured on a scratch repo, exit 1 -- a
required gate manufacturing the exact defect it was written to detect, against
a filer who did everything right. `git rebase` and `git cherry-pick` rewrite
the same way.

`%cI` is also the CORRECT bound rather than merely the forgiving one: it is when
this commit object came into existence, and the row was necessarily written
before that. The looser reading `row <= max(%aI, %cI)` was considered and
REJECTED -- an author date is settable to any value (`git commit --date=...`),
so max() would accept a row postdated to a future author date and call it
clean. That is postdating laundered through a flag, which is this check's whole
subject. `%cI` fixes the false failure without widening what passes.

WHY IT MATTERS. The register is provenance-bearing and feeds TTL-lateness
arithmetic: rows carry `**TTL 72h (expires <ts>)**` and lateness is measured
against the row's own timestamp. A postdated row moves its own expiry FORWARD,
so it makes lateness wrong in the direction that flatters the filer. That is
the direction that never gets reported by the person who benefits from it.

MEASURED BASELINE on `main` @ 94224d955: 41 of 404 rows (10.1%) violate this,
worst by 5h05m, across 8 owner identities. 361 of 404 rows (89.4%) carry `:00`
seconds and minutes cluster on :00/:15/:30/:45 -- these timestamps are
hand-rounded, not clock-read. Rounding accounts for 22 of the 41 (inside a
30-minute band); it cannot account for the 11 that exceed an hour.

Existing rows are REPORTED AND NOT REWRITTEN. They belong to other nodes, and
silently correcting another node's provenance record would be a worse act than
the drift it tidies. `--sweep` reports them; the gate below only judges rows a
PR actually adds, so the count can go down and cannot go up. Same ratchet shape
as validate-command-anchors / validate-composes / validate-dockerfile-paths.

The durable fix is upstream of this check: `pmoves/tools/register_append.py`
reads the clock, so a row filed through the sanctioned path cannot be
postdated at all. This is the backstop for rows that arrive another way.

Exit codes (repo doctrine, see docker_host_policy_check.py):
  0  clean
  1  findings
  3  could not measure -- NOT a pass
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"

EXIT_CLEAN, EXIT_FINDINGS, EXIT_UNMEASURED = 0, 1, 3

# A register row, as the grammar documents it:
#   - `<ISO_TIMESTAMP>` <KIND> `<OWNER-ID>` ... scope: ...
# `<KIND>` is `[A-Z+]+` -- CLAIM, RELEASE, CLAIM+RELEASE, UPDATE, REVIEW,
# HANDOFF are all in use, so the check is not narrowed to CLAIM. A postdated
# RELEASE is exactly as wrong, and lateness is computed from both.
ROW_RE = re.compile(
    r"^\s*[-*]\s+`(?P<ts>\d{4}-\d{2}-\d{2}[T ][\d:]{5,8}\s*(?:Z|[+-]\d{2}:?\d{2})?)`"
    r"\s+(?P<kind>[A-Z+]+)\s+`(?P<owner>[^`]+)`"
)


# The repo is a PARAMETER, not a constant. CI checks out to its own path, and
# the tests need a scratch repo with a real commit graph -- a postdate check
# that can only run against one hardcoded working tree cannot be tested against
# a POSTDATED row, and an assertion nobody has watched fail is not evidence.
_REPO = REPO_ROOT


def set_repo(root: Path) -> None:
    global _REPO
    _REPO = Path(root)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def parse_ts(raw: str) -> datetime | None:
    """Parse a register timestamp to an aware UTC datetime, or None.

    A naive timestamp is read as UTC because that is what the register means by
    a bare `...Z`-less stamp -- every dated row in the file is UTC by
    convention. Guessing local time would silently shift comparisons by the
    author's offset, which is the exact class of error being measured.
    """
    text = raw.strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def added_rows(sha: str) -> list[tuple[str, str, str]]:
    """(timestamp, kind, owner) for each register row ADDED by `sha`."""
    try:
        diff = _git("show", "--format=", "--unified=0", sha, "--", REGISTER)
    except subprocess.CalledProcessError:
        return []
    rows = []
    for line in diff.split("\n"):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        m = ROW_RE.match(line[1:])
        if m:
            rows.append((m.group("ts"), m.group("kind"), m.group("owner")))
    return rows


def commit_time(sha: str) -> datetime | None:
    """When this commit OBJECT was created -- `%cI`, not `%aI`.

    See the module docstring: `--amend`, `rebase` and `cherry-pick` all keep the
    author date and move the committer date, so `%aI` fails honest rows.
    """
    try:
        raw = _git("show", "-s", "--format=%cI", sha).strip()
    except subprocess.CalledProcessError:
        return None
    return parse_ts(raw)


def check(revs: list[str]) -> tuple[list[str], list[str]]:
    """(findings, unmeasured) across `revs`."""
    findings: list[str] = []
    unmeasured: list[str] = []
    for sha in revs:
        ctime = commit_time(sha)
        if ctime is None:
            unmeasured.append(f"{sha[:9]}: commit creation time unreadable")
            continue
        for raw_ts, kind, owner in added_rows(sha):
            rts = parse_ts(raw_ts)
            if rts is None:
                unmeasured.append(
                    f"{sha[:9]}: row timestamp `{raw_ts}` is not parseable, so "
                    f"the invariant could not be evaluated ({kind} by {owner})"
                )
                continue
            if rts > ctime:
                drift = rts - ctime
                total = int(drift.total_seconds())
                findings.append(
                    f"{sha[:9]}  {kind} by `{owner}`\n"
                    f"      row says   {rts:%Y-%m-%dT%H:%M:%SZ}\n"
                    f"      commit made {ctime:%Y-%m-%dT%H:%M:%SZ}\n"
                    f"      POSTDATED by {total // 3600}h{total % 3600 // 60:02d}m"
                )
    return findings, unmeasured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main",
                        help="merge base to diff from (default origin/main)")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", default=None,
                        help="repository root to check (default: this one)")
    parser.add_argument("--sweep", action="store_true",
                        help="report EVERY postdated row in the register's "
                             "whole history instead of gating a PR range")
    args = parser.parse_args(argv)
    if args.repo:
        set_repo(Path(args.repo))

    try:
        if args.sweep:
            revs = _git("log", "--format=%H", "--", REGISTER).split()
            scope = f"every commit touching {REGISTER}"
        else:
            base = _git("merge-base", args.base, args.head).strip()
            revs = _git("rev-list", "--reverse", f"{base}..{args.head}").split()
            scope = f"{args.base}..{args.head} ({len(revs)} commit(s))"
    except subprocess.CalledProcessError as exc:
        print("register-postdate: NOT MEASURED - git could not resolve the "
              f"range ({exc.stderr.strip() or exc}). Could not measure is not "
              "a pass.", file=sys.stderr)
        return EXIT_UNMEASURED

    findings, unmeasured = check(revs)

    print(f"register-postdate: checked {scope}")
    for note in unmeasured:
        print(f"  NOT MEASURED  {note}")
    if findings:
        print(f"\n{len(findings)} postdated row(s) "
              "-- row_timestamp is LATER than the commit that carried it:")
        for f in findings:
            print(f"  - {f}")
        print("\nA row cannot record a moment that had not happened when it was "
              "written. File through `make -C pmoves register-claim`, which "
              "reads the clock.")
        return EXIT_FINDINGS
    if unmeasured:
        return EXIT_UNMEASURED
    print("register-postdate: clean - every added row is at or before the "
          "commit that carried it.")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
