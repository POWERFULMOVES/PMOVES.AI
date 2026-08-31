#!/usr/bin/env python3
"""Fail the build on `# lgtm[<rule>]` markers, which suppress nothing.

WHY THIS GATE EXISTS
--------------------
`# lgtm[<rule>]` is LGTM.com syntax. LGTM.com was retired and folded into
GitHub code scanning, which does NOT honour the pragma. Every such marker in a
repository scanned by CodeQL advertises a suppression it does not perform: the
line still alerts, but the next reader sees a marker and believes the finding
was triaged. That is strictly worse than no comment at all, because it turns an
open HIGH alert into something that looks handled.

This is not theoretical here. On 2026-08-31 this repository carried 10 markers
across 5 files, and four of the marked lines held OPEN HIGH alerts at that exact
moment -- 334/335/336 (`launcher_profile_select.py`) and 265
(`inject_docker_hub_pat_from_cli.py`). Meanwhile two lines whose alerts were
dismissed through the real API (332/333, the media-video/media-audio
path-injection pair) were genuinely closed. Same repository, same rule family:
the mechanism worked, the marker did not.

THE ONLY REAL MECHANISMS
------------------------
  1. Fix the code.
  2. Dismiss the alert -- UI, or
     `gh api PATCH /repos/{owner}/{repo}/code-scanning/alerts/{n}` with
     `state=dismissed`, a `dismissed_reason`, and a `dismissed_comment` that
     records the justification where reviewers and auditors can read it.
  3. Exclude the path/query in `.github/codeql/*.yml` if it is out of scope.

A comment is documentation. Write the reasoning as a plain comment -- that is
valuable and this gate never objects to it -- but do not dress it up as a
pragma that a scanner will act on.

WHAT COUNTS AS A MARKER
-----------------------
A comment pragma naming a plausible rule id: `# lgtm[py/path-injection]`,
`// lgtm[js/xss-through-dom]`, `# lgtm[a/b, c/d]`. Prose that MENTIONS the
syntax is deliberately not a finding -- pmoves/tools/github_secret_capacity_audit.py
explains this very defect and must stay greppable. Two independent conditions
protect it: the rule id must look like `<lang>/<rule-name>` (prose writes
`lgtm[...]`), and a backtick-quoted occurrence is treated as prose.

EXIT CODES (repo doctrine)
--------------------------
  0  clean -- no markers
  1  findings -- at least one marker
  3  could not measure -- NOT a pass; discovery failed and nothing was judged

Exit 3 matters. A gate that cannot enumerate the tree and returns 0 anyway is
the same class of defect it was built to catch: a green result that measured
nothing.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Markdown is prose by definition; the audit dashboard and the AGNOTE register
# both narrate this defect in historical entries and must not be rewritten.
SKIP_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}

# Vendored/binary trees never carry hand-written pragmas worth judging.
SKIP_PATH_PARTS = ("node_modules/", "vendor/", ".git/")

# `# lgtm[py/path-injection]`, `// lgtm [js/foo, js/bar]`. The rule id must be
# slash-shaped: prose writes `lgtm[...]`, which this deliberately misses.
MARKER_RE = re.compile(
    r"(?:#|//|--|/\*)\s*lgtm\s*\[\s*[A-Za-z][\w-]*/[\w./-]+"
    r"(?:\s*,\s*[A-Za-z][\w-]*/[\w./-]+)*\s*\]"
)

# A backticked occurrence is someone quoting the syntax, not using it.
BACKTICKED_RE = re.compile(r"`[^`]*lgtm\s*\[[^`]*`")


def discover_tracked_files() -> list[str]:
    """Tracked, judgeable files -- repo-relative, sorted.

    Raises on discovery failure so the caller can exit 3 rather than report a
    clean tree it never actually read.
    """
    # Bytes, not text=True: text=True decodes with the locale encoding (cp1252
    # on Windows) and this repo tracks paths holding bytes cp1252 cannot
    # represent. -z stops git quoting them; surrogateescape survives the trip.
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")

    files = []
    for p in out.split("\0"):
        if not p:
            continue
        if any(part in p for part in SKIP_PATH_PARTS):
            continue
        if Path(p).suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(p)
    return sorted(files)


def scan(path: str) -> list[tuple[int, str]]:
    """Return (line_no, line_text) for every marker in `path`."""
    full = REPO_ROOT / path
    try:
        # errors='replace': a stray non-UTF-8 byte should not crash the gate.
        # A file that cannot be OPENED is skipped -- it is almost always a
        # submodule gitlink or a broken symlink, neither of which holds source.
        text = io.open(full, encoding="utf-8", errors="replace").read()
    except (OSError, ValueError):
        return []

    # Cheap reject: most files never mention it at all.
    if "lgtm" not in text.lower():
        return []

    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if BACKTICKED_RE.search(line):
            continue
        if MARKER_RE.search(line):
            hits.append((i, line.rstrip()))
    return hits


def main() -> int:
    try:
        files = discover_tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        print(
            "COULD NOT MEASURE -- `git ls-files` failed, so no file was judged.\n"
            f"  {type(exc).__name__}: {exc}\n"
            "This is NOT a pass. Run the gate from inside a git checkout.",
            file=sys.stderr,
        )
        return 3

    if not files:
        print(
            "COULD NOT MEASURE -- discovery returned zero tracked files.\n"
            "This is NOT a pass; an empty tree means the scan never ran.",
            file=sys.stderr,
        )
        return 3

    findings: list[tuple[str, int, str]] = []
    for path in files:
        for line_no, line in scan(path):
            findings.append((path, line_no, line))

    if not findings:
        print(f"OK -- no `lgtm[...]` suppression markers in {len(files)} tracked files.")
        return 0

    print(
        f"FOUND {len(findings)} `lgtm[...]` marker(s). Each one suppresses NOTHING:\n"
        "GitHub code scanning ignores LGTM.com pragmas, so the alert on that line\n"
        "is still open while the comment tells the next reader it was handled.\n"
    )
    for path, line_no, line in findings:
        print(f"  {path}:{line_no}")
        print(f"      {line.strip()}")
    print(
        "\nFix by doing one of these instead:\n"
        "  * fix the code;\n"
        "  * dismiss the alert for real --\n"
        "      gh api PATCH /repos/{owner}/{repo}/code-scanning/alerts/{n} \\\n"
        "        -f state=dismissed -f dismissed_reason='false positive' \\\n"
        "        -f dismissed_comment='<why this line is safe>'\n"
        "  * exclude the path or query in .github/codeql/*.yml.\n"
        "\nKeep the reasoning as a PLAIN comment -- that is welcome, and this gate\n"
        "does not object to it. Just do not shape it like a pragma that no tool reads."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
