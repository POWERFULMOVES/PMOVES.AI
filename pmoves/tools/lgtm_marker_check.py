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
`// lgtm[js/xss-through-dom]`, `# lgtm[a/b, c/d]`. Matching is
case-INSENSITIVE: `# LGTM[py/path-injection]` is not an evasion attempt, it is
someone typing, and it suppresses exactly as much as the lowercase form.

Prose that MENTIONS the syntax is deliberately not a finding --
pmoves/tools/github_secret_capacity_audit.py explains this very defect and must
stay greppable. Two independent conditions protect it: the rule id must look
like `<lang>/<rule-name>` (prose writes `lgtm[...]`), and a backtick-quoted
occurrence is treated as prose. The backtick rule excludes the quoted SPAN, not
the whole line, so a real marker sharing a line with a quoted one is still
caught.

WHAT IS OUT OF SCOPE
--------------------
Submodule gitlinks (index mode 160000) are commit pointers, not files. They are
dropped during discovery rather than counted as "scanned", because opening one
yields a directory and judging it clean would assert coverage this gate does not
have. Submodule CONTENTS are scanned by that submodule's own CI, never here.

EXIT CODES (repo doctrine)
--------------------------
  0  clean -- no markers, and every in-scope file was actually read
  1  findings -- at least one marker
  3  could not measure -- NOT a pass; something went unjudged

Exit 3 matters. A gate that cannot enumerate the tree and returns 0 anyway is
the same class of defect it was built to catch: a green result that measured
nothing. That doctrine applies per FILE as well as per tree: a tracked file that
cannot be opened is not evidence of cleanliness, so it raises rather than
returning "no markers here".
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

# Vendored/binary trees never carry hand-written pragmas worth judging. These
# are matched as whole path SEGMENTS, not substrings: `myvendor/` is our code
# and must be scanned, while `third_party/vendor/` is not.
SKIP_PATH_SEGMENTS = frozenset({"node_modules", "vendor", ".git"})

# git index mode for a submodule gitlink -- a commit pointer, not a file.
GITLINK_MODE = "160000"

# `# lgtm[py/path-injection]`, `// lgtm [js/foo, js/bar]`. The rule id must be
# slash-shaped: prose writes `lgtm[...]`, which this deliberately misses.
#
# IGNORECASE is deliberate: the cheap-reject in scan() has always used
# `text.lower()`, and `# LGTM[...]` is the single most likely real-world
# spelling to reach a gate whose entire purpose is catching this comment.
#
# Comment prefixes cover the styles this repo actually tracks: `#` (py, sh,
# yaml, toml, Dockerfile), `//` and `/*` (js/ts/cs/c), `--` (sql, lua), `%`
# (matlab/erlang/tex) and `;` (ini, lisp, asm).
MARKER_RE = re.compile(
    r"(?:\#|//|--|/\*|%|;)\s*lgtm\s*\[\s*[A-Za-z][\w-]*/[\w./-]+"
    r"(?:\s*,\s*[A-Za-z][\w-]*/[\w./-]+)*\s*\]",
    re.IGNORECASE,
)

# A backticked occurrence is someone quoting the syntax, not using it. Same
# case rule as MARKER_RE so that prose writing `LGTM[js/foo]` stays prose.
BACKTICKED_RE = re.compile(r"`[^`]*lgtm\s*\[[^`]*`", re.IGNORECASE)


class UnreadableFile(Exception):
    """A tracked, in-scope file that could not be read.

    Distinct from "no markers found". Swallowing this and returning [] would
    count the file toward the clean total while never looking at a byte of it --
    the exact green-result-that-measured-nothing shape this gate exists to stop.
    """

    def __init__(self, path: str, cause: BaseException) -> None:
        super().__init__(f"{path}: {type(cause).__name__}: {cause}")
        self.path = path
        self.cause = cause


def is_judgeable(path: str) -> bool:
    """True if this gate should open `path` and judge its contents.

    Split out of discovery so the scope rules can be exercised directly. A test
    that asserts `".md" in SKIP_SUFFIXES` proves only that a constant contains a
    string; this is the predicate the gate actually consults.
    """
    if SKIP_PATH_SEGMENTS.intersection(path.split("/")):
        return False
    return Path(path).suffix.lower() not in SKIP_SUFFIXES


def discover_tracked_files() -> list[str]:
    """Tracked, judgeable files -- repo-relative, sorted.

    Raises on discovery failure so the caller can exit 3 rather than report a
    clean tree it never actually read.
    """
    # Bytes, not text=True: text=True decodes with the locale encoding (cp1252
    # on Windows) and this repo tracks paths holding bytes cp1252 cannot
    # represent. -z stops git quoting them; surrogateescape survives the trip.
    # -s adds the index mode, which is how gitlinks are identified exactly
    # rather than guessed from a failed open().
    out = subprocess.run(
        ["git", "ls-files", "-s", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")

    files = []
    for record in out.split("\0"):
        if not record:
            continue
        # `<mode> SP <object> SP <stage> TAB <path>`
        meta, tab, path = record.partition("\t")
        if not tab or not path:
            continue
        if meta.split(" ", 1)[0] == GITLINK_MODE:
            continue  # submodule pointer; its contents are that repo's CI job
        if not is_judgeable(path):
            continue
        files.append(path)
    return sorted(files)


def scan(path: str) -> list[tuple[int, str]]:
    """Return (line_no, line_text) for every marker in `path`.

    Raises UnreadableFile if the file cannot be opened or decoded at all. A file
    we could not read is never reported as clean.
    """
    full = REPO_ROOT / path
    try:
        # errors='replace': a stray non-UTF-8 byte should not crash the gate.
        text = io.open(full, encoding="utf-8", errors="replace").read()
    except (OSError, ValueError) as exc:
        raise UnreadableFile(path, exc) from exc

    # Cheap reject: most files never mention it at all.
    if "lgtm" not in text.lower():
        return []

    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        # Blank out backtick-quoted spans only, so a real marker sharing the
        # line with a quoted one is still judged.
        if MARKER_RE.search(BACKTICKED_RE.sub(" ", line)):
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
    unreadable: list[UnreadableFile] = []
    for path in files:
        try:
            hits = scan(path)
        except UnreadableFile as exc:
            unreadable.append(exc)
            continue
        for line_no, line in hits:
            findings.append((path, line_no, line))

    # Both are printed when both happen: an unreadable file does not make the
    # markers we DID find less actionable, and findings do not make the
    # unmeasured file readable. Exit 1 wins only because it is the more
    # specific instruction; either way the step fails and the merge is blocked.
    if findings:
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

    if unreadable:
        print(
            f"COULD NOT MEASURE -- {len(unreadable)} tracked file(s) could not be read,\n"
            "so they were NOT judged. An unreadable file is not a clean file:",
            file=sys.stderr,
        )
        for exc in unreadable:
            print(f"  {exc}", file=sys.stderr)
        print(
            "Fix the permissions or the broken link, then re-run. Do not treat this\n"
            "run as coverage of those paths.",
            file=sys.stderr,
        )

    if findings:
        return 1
    if unreadable:
        return 3

    print(
        f"OK -- no `lgtm[...]` suppression markers. Read {len(files)} tracked file(s);\n"
        "every one was opened. Submodule contents are OUT OF SCOPE: gitlinks are\n"
        "commit pointers, not files, and are excluded from this count rather than\n"
        "counted as scanned."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
