"""Citations into `Pmoves-cipher/src/pmoves/auth.ts` must resolve at the PINNED commit.

Line numbers are a fragile provenance mechanism and this repo has now been bitten
by that twice in one week:

  * #3023 cited `auth.ts` line numbers read off a working tree parked on the head
    of an UNMERGED fork PR. Four of nine were wrong for everyone else.
  * merging that same fork PR (#19, `Accept-Profile: pmoves_core`) inserted three
    lines at :67 and moved the same four citations again — `e24f1323` -> `975e02e6`:

        !token.startsWith('cipher_')    46  ->  46   (+0)
        agentId: 'bootstrap'            49  ->  49   (+0)
        records.length === 0            79  ->  82   (+3)
        !legacyToken && skipIfUnset    103  -> 106   (+3)
  * #3103 bumped the pin again — `975e02e6` -> `c88b009a2` (cipher build fix
    #21 + installer #20). Neither commit touches `auth.ts`, so all nine
    citations re-verified at the same lines and only PIN moved. This is the
    boring case this test exists to keep boring.
  * #3152 bumped the pin — `c88b009a2` -> `750878ab` (fork PR #27, per-request
    MCP identity + CIPHER_MCP_ENFORCE). It touches `mcp-sse.ts`,
    `rest-server.ts` and the pmoves README, not `auth.ts`; all nine citations
    re-verified at the same lines. NOTE: `750878ab` is the head of an UNMERGED
    fork PR at the time of pinning — if #27 is squash-merged the SHA changes and
    this PIN must follow the merge commit.

Re-numbering by hand each time is not a fix; it is the same manual step failing
again on a schedule. This test makes the citation machine-checkable in three
directions, so a drift fails loudly instead of quietly becoming a lie:

  1. the superproject gitlink still equals the pin these numbers were read at;
  2. each cited LINE still contains its ANCHOR text in the pinned file;
  3. the docs and tools that quote these numbers quote THESE numbers.

Anchors, not numbers, are the real citation. The numbers are a convenience for a
human reader, and this file is what keeps the convenience honest.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SUBMODULE = "Pmoves-cipher"
AUTH_TS = REPO_ROOT / SUBMODULE / "src" / "pmoves" / "auth.ts"

# The commit these line numbers were read at. Advancing the gitlink without
# updating this constant is the drift this file exists to catch.
PIN = "750878ab7de921129b2e98cb159be577d37f266a"

# line -> a fragment that must appear on it. Keep in sync with the tables in
# TAC_CIPHER.md, cipher_identity.py and the cipher-memory SKILL.
CITATIONS = {
    44: "Single-token mode",
    46: "!token.startsWith('cipher_')",
    49: "agentId: 'bootstrap'",
    54: "Per-agent token mode",
    60: "token.slice(7)",
    82: "records.length === 0",
    84: "const record = records[0]",
    106: "!legacyToken && skipIfUnset",
    108: "req.agentId = undefined",
}

# Files that quote the numbers above, and the substrings that must be present.
# A doc citing `:79` after the pin moved to c88b009a2 is pointing a reviewer at
# the wrong statement — which is exactly how the first round went wrong.
DOC_CITATIONS = {
    Path("pmoves") / "docs" / "TAC" / "TAC_CIPHER.md": ["`:46`", "`:49`", "`:82`", "`:106`"],
    Path("pmoves") / "tools" / "cipher_identity.py": ["auth.ts:46", "auth.ts:49"],
}

STALE_MARKERS = {
    Path("pmoves") / "docs" / "TAC" / "TAC_CIPHER.md": ["`:79`", "`:103`"],
}


def _gitlink() -> str | None:
    """The commit the superproject pins for the submodule. None if unavailable."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "HEAD", SUBMODULE],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    parts = out.stdout.split()
    return parts[2] if len(parts) >= 3 else None


def test_gitlink_matches_the_pin_these_numbers_were_read_at():
    link = _gitlink()
    if link is None:
        pytest.skip("gitlink unreadable (not a git checkout, or git unavailable)")
    assert link == PIN, (
        f"{SUBMODULE} gitlink is {link[:9]}, but the citations in this repo were "
        f"read at {PIN[:9]}. Re-resolve the anchors against the new commit and "
        "update PIN, CITATIONS and the docs together — line numbers move whenever "
        "the pin does, and four of these moved by +3 the last time it did."
    )


@pytest.mark.parametrize("line,anchor", sorted(CITATIONS.items()))
def test_each_cited_line_still_carries_its_anchor(line: int, anchor: str):
    if not AUTH_TS.is_file():
        pytest.skip(
            f"{SUBMODULE} not populated (git submodule update --init -- {SUBMODULE})"
        )
    lines = AUTH_TS.read_text(encoding="utf-8", errors="replace").splitlines()
    assert line <= len(lines), (
        f"auth.ts has {len(lines)} lines; citation :{line} is past the end"
    )
    actual = lines[line - 1]
    assert anchor in actual, (
        f"auth.ts:{line} no longer contains {anchor!r}.\n"
        f"  found: {actual.strip()[:90]!r}\n"
        "The citation is stale — find the anchor's new line and update CITATIONS "
        "and every doc that quotes it."
    )


def test_the_working_tree_is_not_ahead_of_the_pin():
    """A submodule parked on an open PR reads as current and is not.

    This is how the first round of citations went wrong: the checkout sat on
    `fix/per-agent-token-profile-header`, three lines longer than the gitlink,
    so every number below :67 was right and every number above it was wrong.
    Fail-open by design — an unpopulated or detached submodule is not an error,
    an UNDECLARED DIFFERENCE is.
    """
    if not (REPO_ROOT / SUBMODULE / ".git").exists():
        pytest.skip(f"{SUBMODULE} not populated")
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT / SUBMODULE), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    if out.returncode != 0:
        pytest.skip("submodule HEAD unreadable")
    head = out.stdout.strip()
    assert head == PIN, (
        f"{SUBMODULE} working tree is at {head[:9]} but the pin is {PIN[:9]}. "
        "Anything read from this checkout is not what the fleet runs. Run "
        f"`git -C {SUBMODULE} checkout {PIN[:9]}` before quoting a line number."
    )


@pytest.mark.parametrize("rel,needles", sorted(DOC_CITATIONS.items(), key=lambda kv: str(kv[0])))
def test_docs_quote_the_current_numbers(rel: Path, needles: list):
    path = REPO_ROOT / rel
    if not path.is_file():
        pytest.skip(f"{rel} not present")
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [n for n in needles if n not in text]
    assert not missing, (
        f"{rel} no longer cites {missing} — either the doc drifted from the pin, "
        "or the pin moved and the doc was not updated with it"
    )


@pytest.mark.parametrize("rel,stale", sorted(STALE_MARKERS.items(), key=lambda kv: str(kv[0])))
def test_docs_do_not_carry_the_pre_pin_numbers(rel: Path, stale: list):
    """NEGATIVE CONTROL for the test above.

    Asserting the NEW numbers are present does not prove the OLD ones are gone —
    a half-finished edit leaves both, and a reviewer following the stale one is
    sent to the wrong statement with no warning. These are the exact numbers that
    were correct at `e24f1323` and are wrong since `975e02e6`.
    """
    path = REPO_ROOT / rel
    if not path.is_file():
        pytest.skip(f"{rel} not present")
    text = path.read_text(encoding="utf-8", errors="replace")
    found = [s for s in stale if s in text]
    assert not found, (
        f"{rel} still carries pre-pin citations {found}; those line numbers were "
        f"correct at e24f1323 and point at the wrong statement at {PIN[:9]}"
    )
