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
  * #3152 bumped the pin — `c88b009a2` -> `36b28d0f` (fork PR #27, per-request
    MCP identity + CIPHER_MCP_ENFORCE, merged as a merge commit on
    PMOVES.AI-Edition-Hardened; its second parent is the reviewed head
    `750878ab`, and the two trees are identical). It touches `mcp-sse.ts`,
    `rest-server.ts`, `app.ts` and the pmoves README, not `auth.ts` (blob
    `b006246b` at both); all nine citations re-verified at the same lines.
  * #3189 bumped the pin — `36b28d0f` -> `a0ee2314` (fork PR #28, squash-merged;
    tree identical to the reviewed head `151a6bfb`). This one REWROTE
    `resolveToken()` (three-outcome result, `UUID_RE`, per-call env reads), so
    every citation moved, by +49 to +85 lines:

        Single-token mode               44  ->  93
        !token.startsWith('cipher_')    46  ->  95
        agentId: 'bootstrap'            49  ->  98
        Per-agent token mode            54  -> 104
        token.slice(7)                  60  -> 105
        records.length === 0            82  -> 150
        const record = records[0]       84  -> 155
        !legacyToken && skipIfUnset    106  -> 191
        req.agentId = undefined        108  -> 193

    It also moved what the preflight's log rule-out greps for. The
    backend-failure lines are now built from a `reason` variable (see
    AUTH_EMIT_SITES), so this file now also derives the emitted text from
    the pinned source and checks the rule-out against it.

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

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SUBMODULE = "Pmoves-cipher"
AUTH_TS = REPO_ROOT / SUBMODULE / "src" / "pmoves" / "auth.ts"

# The commit these line numbers were read at. Advancing the gitlink without
# updating this constant is the drift this file exists to catch.
PIN = "2a45a1a0c238902af478ec58685e2e1fc187a4bf"

# line -> a fragment that must appear on it. Keep in sync with the tables in
# TAC_CIPHER.md, cipher_identity.py and the cipher-memory SKILL.
CITATIONS = {
    93: "Single-token mode",
    95: "!token.startsWith('cipher_')",
    98: "agentId: 'bootstrap'",
    104: "Per-agent token mode",
    105: "token.slice(7)",
    150: "records.length === 0",
    155: "const record = records[0]",
    191: "!legacyToken && skipIfUnset",
    193: "req.agentId = undefined",
}

# Every `pmoves-auth:` stderr line resolveToken() emits at PIN. These are what
# the preflight / launcher rule-out (`grep pmoves-auth`) must catch, and each
# of them answered with a revocation-shaped 401 before fork PR #28.
AUTH_EMIT_SITES = {
    117: "SUPABASE_SERVICE_KEY not set",   # `pmoves-auth: ${reason} — cannot resolve …`
    137: "token lookup returned HTTP",     # `pmoves-auth: Supabase ${reason}`
    145: "a non-array body",               # `pmoves-auth: Supabase ${reason}`
    160: "a row with no agent_id",         # `pmoves-auth: Supabase ${reason}`
    170: "token resolution failed",        # `pmoves-auth: token resolution failed — ${error}`
}

# Files that quote the numbers above, and the substrings that must be present.
# A doc citing `:79` after the pin moved to c88b009a2 is pointing a reviewer at
# the wrong statement — which is exactly how the first round went wrong.
DOC_CITATIONS = {
    Path("pmoves") / "docs" / "TAC" / "TAC_CIPHER.md": ["`:95`", "`:98`", "`:150`", "`:191`"],
    Path("pmoves") / "tools" / "cipher_identity.py": ["auth.ts:95", "auth.ts:98", "auth.ts:93-102", "auth.ts:191-194"],
    Path("pmoves") / "tests" / "tools" / "test_cipher_identity.py": ["auth.ts:95", "auth.ts:98", "auth.ts:105", "auth.ts:191"],
    Path("pmoves") / "docs" / "PMOVESCHIT" / "CHIT_FORKS.md": ["auth.ts:95,98"],
    Path(".claude") / "skills" / "pmoves-cipher-memory" / "SKILL.md": ["auth.ts:95", "`a0ee2314`"],
}

# Exact citation text that was correct at an EARLIER pin. TAC_CIPHER.md's pin
# history table legitimately mentions old numbers, so these are the live
# citation table's cell texts, not bare numbers.
STALE_MARKERS = {
    Path("pmoves") / "docs" / "TAC" / "TAC_CIPHER.md": [
        "`:79`", "`:103`",                                   # e24f1323
        "| `:46` `if", "`:54`–`:60` per-agent", "`:82`–`:84`", "`:106`–`:108` |",  # 975e02e6..36b28d0f
    ],
    Path("pmoves") / "tools" / "cipher_identity.py": [
        "auth.ts:46", "auth.ts:49", "auth.ts:44-52", "auth.ts:54-91", "auth.ts:106-109",
    ],
    Path("pmoves") / "tests" / "tools" / "test_cipher_identity.py": [
        "auth.ts:46", "auth.ts:49", "auth.ts:60", "auth.ts:106",
    ],
    Path("pmoves") / "docs" / "PMOVESCHIT" / "CHIT_FORKS.md": ["file: Pmoves-cipher/src/pmoves/auth.ts:46,49"],
}


def _pinned_auth_ts() -> list[str] | None:
    """auth.ts AT PIN, from the real object store, never a copy.

    The populated submodule working tree when it sits at PIN; otherwise the
    submodule's object store (a worktree or unpopulated checkout still shares
    `<common-dir>/modules/Pmoves-cipher`). None when neither is available.
    """
    rel = "src/pmoves/auth.ts"
    try:
        head = subprocess.run(
            ["git", "-C", str(REPO_ROOT / SUBMODULE), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        if head.returncode == 0 and head.stdout.strip() == PIN and AUTH_TS.is_file():
            return AUTH_TS.read_text(encoding="utf-8", errors="replace").splitlines()
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
        if common.returncode != 0:
            return None
        modules = Path(common.stdout.strip()) / "modules" / SUBMODULE
        if not modules.is_dir():
            return None
        shown = subprocess.run(
            ["git", "--git-dir", str(modules), "show", f"{PIN}:{rel}"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if shown.returncode != 0:
        return None
    return shown.stdout.splitlines()


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
    lines = _pinned_auth_ts()
    if lines is None:
        pytest.skip(
            f"auth.ts at {PIN[:9]} unavailable (git submodule update --init -- {SUBMODULE})"
        )
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


def _emitted_text(lines: list[str], line: int) -> str:
    """The text a `pmoves-auth:` stderr write emits, with `${reason}` resolved.

    `reason` is the nearest `const reason = ...` above the write, as the code
    reads; `${resp.status}` / `${error}` stay as placeholders.
    """
    src = lines[line - 1]
    m = re.search(r"write\(`(pmoves-auth:[^`]*)`\)", src)
    assert m, f"auth.ts:{line} is not a pmoves-auth stderr write: {src.strip()[:90]!r}"
    text = m.group(1).replace("\\n", "")
    if "${reason}" in text:
        for back in range(line - 2, max(line - 6, -1), -1):
            r = re.search(r"const reason = ['`]([^'`]*)['`]", lines[back])
            if r:
                text = text.replace("${reason}", r.group(1))
                break
        else:
            raise AssertionError(f"auth.ts:{line} uses ${{reason}} with no const reason above it")
    return text


def _preflight_grep() -> str:
    spec = importlib.util.spec_from_file_location(
        "cipher_preflight", REPO_ROOT / "pmoves" / "tools" / "cipher_preflight.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AUTH_LOG_GREP


def test_every_backend_failure_line_at_the_pin_is_cited():
    """No pmoves-auth write exists at PIN that AUTH_EMIT_SITES does not list."""
    lines = _pinned_auth_ts()
    if lines is None:
        pytest.skip(f"auth.ts at {PIN[:9]} unavailable")
    found = {i + 1 for i, l in enumerate(lines) if "pmoves-auth:" in l and "write(" in l}
    assert found == set(AUTH_EMIT_SITES), (
        f"pmoves-auth writes at {PIN[:9]} are on lines {sorted(found)}, "
        f"AUTH_EMIT_SITES cites {sorted(AUTH_EMIT_SITES)}"
    )


@pytest.mark.parametrize("line,anchor", sorted(AUTH_EMIT_SITES.items()))
def test_the_log_rule_out_catches_what_the_pinned_code_emits(line: int, anchor: str):
    """Against the pinned SOURCE, not a copied string: what the running code
    writes at each backend-failure site must be matched by the rule-out the
    preflight and launcher print (`grep <AUTH_LOG_GREP>`)."""
    lines = _pinned_auth_ts()
    if lines is None:
        pytest.skip(f"auth.ts at {PIN[:9]} unavailable")
    text = _emitted_text(lines, line)
    assert anchor in text, f"auth.ts:{line} now emits {text!r}"
    pattern = _preflight_grep()
    assert re.search(pattern, text), f"grep {pattern!r} misses auth.ts:{line}: {text!r}"
