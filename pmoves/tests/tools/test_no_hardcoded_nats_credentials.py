"""No committed NATS credentials anywhere in tracked source.

History of this guard, because it is instructive:

1. The original guard (test_bpm_encoder_nats.TestNatsClientNoHardcodedDefault)
   checked exactly ONE module's DEFAULT_NATS_URL. It was green while 194
   occurrences sat in 140 files.
2. The first version of THIS guard scoped itself to ``pmoves/**`` and matched
   only the credential-inside-a-URL form. Review found it blind to 48 further
   occurrences in 32 files outside pmoves/, and to 16 in bare-assignment form --
   reproducing the exact failure it was written to replace.

So: the corpus is the whole tracked repo, both credential shapes are matched,
and the corpus control asserts a floor PER GLOB, because a union floor passes
even when one glob silently breaks.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Shape 1: credential embedded in a nats:// URL.
URL_CREDENTIAL = re.compile(r"nats://([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)@")
# Shape 2: the password alone -- the directly usable form, and the one the
# first version of this guard could not see at all.
BARE_CREDENTIAL = re.compile(r"NATS_PASSWORD(?::-|=)([A-Za-z0-9_.-]+)")

LEAKED_PASSWORD = "pmoves"

# Documentation placeholders. These SHOULD stay: they teach the URL shape
# without shipping a secret.
PLACEHOLDERS = {("user", "pass"), ("u", "p"), ("USER", "PASS"), ("username", "password")}

# Synthetic fixtures that redaction/parsing tests MUST contain to mean anything.
# Deliberately a narrow allowlist of passwords, not "any credential in a test
# file" -- that broader rule would hide the NEXT real credential forever.
SYNTHETIC_TEST_PASSWORDS = {"secret", "secret123", "p4ss", "s3cr3t", "pw", "hunter2"}

# Per-glob floors. A union floor cannot detect one glob breaking.
SEARCH_GLOBS = {
    "**/*.py": 1200,
    "**/*.yaml": 200,
    "**/*.yml": 50,
    "**/*.sh": 150,
    "**/*.example": 1,
}

# ROTATION BACKLOG -- the remaining exposure, enumerated so it stays countable.
#
# Every path listed still contains the leaked credential. They are docs, skills,
# kilo commands, TAC trees, agent profiles, compose files and the CHIT manifest.
# Deleting the value from live config would break authenticated connections, and
# deleting it from documentation does not un-publish it. The credential has been
# public, so ONLY ROTATION closes this. This file is the work item for that
# rotation and should shrink to empty afterwards.
ROTATION_BACKLOG = set(
    (Path(__file__).with_name("nats_rotation_backlog.txt")).read_text().split()
)


def _tracked(glob: str):
    out = subprocess.run(
        ["git", "ls-files", "--", glob],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _all_tracked():
    seen = []
    for glob in SEARCH_GLOBS:
        seen.extend(_tracked(glob))
    return sorted(set(seen))


def _is_test_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (
        "/tests/" in rel
        or rel.startswith("pmoves/tests/")
        or name.startswith("test_")
        or name == "conftest.py"
    )


def _offenders():
    hits = []
    for rel in _all_tracked():
        if rel in ROTATION_BACKLOG:
            continue
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in URL_CREDENTIAL.finditer(line):
                pair = (m.group(1), m.group(2))
                if pair in PLACEHOLDERS:
                    continue
                if _is_test_file(rel) and m.group(2) in SYNTHETIC_TEST_PASSWORDS:
                    continue
                hits.append(f"{rel}:{lineno}: {m.group(0)}")
            for m in BARE_CREDENTIAL.finditer(line):
                if m.group(1) == LEAKED_PASSWORD:
                    hits.append(f"{rel}:{lineno}: NATS_PASSWORD={m.group(1)}")
    return hits


def test_each_glob_matches_files():
    """Control: a silently broken glob makes the guard scan nothing and pass.

    Production change that would make this fail: a typo'd glob or a wrong
    REPO_ROOT -- neither of which a union-total floor would catch.
    """
    for glob, floor in SEARCH_GLOBS.items():
        count = len(_tracked(glob))
        assert count >= floor, f"glob {glob!r} matched {count} files, expected >= {floor}"


def test_no_committed_nats_credentials_outside_the_rotation_backlog():
    """Production change that would make this fail: introducing the leaked
    credential into any tracked file not already in the rotation backlog."""
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} committed NATS credential(s) outside the backlog "
        f"(corpus: {len(_all_tracked())} tracked files):\n  "
        + "\n  ".join(offenders[:25])
        + ("\n  ..." if len(offenders) > 25 else "")
    )


def test_rotation_backlog_has_no_stale_entries():
    """The backlog must shrink, not rot. A listed path that no longer contains
    the credential is a stale exemption hiding future regressions."""
    stale = []
    for rel in sorted(ROTATION_BACKLOG):
        path = REPO_ROOT / rel
        if not path.exists():
            stale.append(f"{rel} (file gone)")
            continue
        if LEAKED_PASSWORD not in path.read_text(encoding="utf-8", errors="replace"):
            stale.append(f"{rel} (credential already removed)")
    assert not stale, "stale rotation-backlog entries:\n  " + "\n  ".join(stale)
