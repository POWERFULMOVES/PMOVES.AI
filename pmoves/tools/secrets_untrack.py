#!/usr/bin/env python3
"""Untrack a leaked generated secret env file — the remediation Known Road.

`secrets_hardening_audit.py` check #9 *detects* the leak class (a generated,
gitignored secret env file that got committed — e.g. env.tier-media #1988/#1992,
env.shared.pre-funnel #1996). This tool is the paired *remediation*: it runs
`git rm --cached` (index-only; the file stays on disk) so the generated file
stops being tracked, without an operator having to run raw git by hand.

Safety is enforced HERE, not by the damage-control guard (which chitBypass-allows
this tool). Three gates before it will untrack anything:
  1. the path must match a known generated-secret shape (ALLOWED_GLOBS) — never an
     arbitrary file, and never a `.example` template;
  2. the path must actually be git-tracked (else it's a no-op);
  3. the path must already be gitignored — so untracking can only ever remove a
     file that was never supposed to be tracked, never a live source file.

It never deletes from disk and never rotates keys — rotation is a separate
operator step (pmoves/docs/handoffs/SECRET_ROTATION_RUNBOOK.md §4).
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Generated-secret path shapes eligible for untracking. Mirrors the detection set
# in secrets_hardening_audit.py check #9. `.example` templates are always excluded.
ALLOWED_GLOBS = (
    "pmoves/env.shared",
    "pmoves/env.shared.*",
    "pmoves/env.tier-*",
    "pmoves/.env",
    "pmoves/.env.*",
)


def _rel(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def is_allowed(rel: str) -> bool:
    """True only for known generated-secret paths, never a .example template."""
    if not rel or rel.endswith(".example"):
        return False
    return any(fnmatch.fnmatch(rel, glob) for glob in ALLOWED_GLOBS)


def _git_out(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout


def is_tracked(rel: str) -> bool:
    return bool(_git_out(["ls-files", "--", rel]).strip())


def is_gitignored(rel: str) -> bool:
    # `git check-ignore -q` exits 0 when the path matches an ignore rule.
    # `--no-index` is essential: without it, git reports an already-TRACKED file as
    # not-ignored (tracked files override ignores), but the whole point here is a
    # file that is tracked YET covered by a gitignore rule (the accidental-leak case).
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", "--", rel],
            cwd=REPO_ROOT,
            check=False,
        ).returncode
        == 0
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="repo-relative path to untrack")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would happen; change nothing"
    )
    args = parser.parse_args(argv)
    rel = _rel(args.file)

    if not is_allowed(rel):
        print(
            f"REFUSED: {rel!r} is not an untrackable generated-secret path.\n"
            f"  Allowed shapes: {', '.join(ALLOWED_GLOBS)} (.example templates excluded).",
            file=sys.stderr,
        )
        return 2
    if not is_tracked(rel):
        print(f"OK (no-op): {rel} is not git-tracked — nothing to untrack.")
        return 0
    if not is_gitignored(rel):
        print(
            f"REFUSED: {rel} is tracked but NOT gitignored. A generated secret file must be "
            f"gitignored first so untracking is provably safe — add it to .gitignore, then re-run.",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        print(f"DRY-RUN: would run `git rm --cached {rel}` (file stays on disk).")
        return 0

    result = subprocess.run(
        ["git", "rm", "--cached", "--", rel],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode
    print(
        f"Untracked {rel} via `git rm --cached` — file remains on disk (gitignored).\n"
        f"Next: commit the removal, then ROTATE any exposed keys "
        f"(pmoves/docs/handoffs/SECRET_ROTATION_RUNBOOK.md §4)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
