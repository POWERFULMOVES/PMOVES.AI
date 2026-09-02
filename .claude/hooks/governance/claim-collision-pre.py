#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
#
# The dependency is DECLARED here, not merely installed somewhere, because the
# configured hook command is a bare `uv run` from a directory with no
# pyproject.toml. Without this block uv hands the script an interpreter that
# has no PyYAML, `_load_folder()` catches the ImportError, and the hook falls
# back to comparing owner strings exactly -- which is the defect this file was
# changed to remove. It degrades to a warning on stderr, so nothing fails and
# nothing reports failure.
#
# It is invisible on a developer box: %APPDATA%\Python\Python3xx\site-packages
# is on sys.path for EVERY interpreter, so PyYAML looks universally present
# locally and is absent on a clean node. Reproduce the clean condition with
# `PYTHONNOUSERSITE=1 uv run --no-project ...`.
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

Wired via PreToolUse Write/Edit AND Bash matchers in .claude/settings.json.

THE BASH PATH IS ADVISORY, NOT A BLOCK. A shell command that writes the register
-- a heredoc, `tee`, `sed -i`, `>>` -- never reaches the Write/Edit matcher, so
for a while the gate had a shell-shaped hole and the agent that filed its own
CLAIM through a heredoc (this one) sailed straight through it.

It cannot be closed the same way. The Write/Edit path works because the proposed
TEXT is in the payload; a shell command only carries the command, and recovering
"what will this write" from arbitrary shell is not something to attempt in a
PreToolUse hook. So the Bash path does what it honestly can: it notices the
register is being written, surfaces which lanes are currently open, and asks.

That is also the right shape on the merits. The register is a shared ledger, not
a lock -- nodes go offline, work gets handed off, and more than one node on a
lane is the village working, not a violation. A gate that refuses cannot express
any of that. `permissionDecision: "ask"` puts the state in front of whoever is
deciding and lets them decide.

Owner-ID format in the register (per existing entries):
  `<ISO_TIMESTAMP>` CLAIM `<OWNER-ID>` [<field>: <value> · ...] scope: ...
  `<ISO_TIMESTAMP>` RELEASE `<OWNER-ID>` [<field>: <value> · ...] scope: ...

We treat the backtick-quoted token immediately following CLAIM/RELEASE as
the owner identifier — that is the canonical lane axis used throughout the
register.

CO-OWNERS: THE DURABLE FIX THIS DOCSTRING ASKED FOR IS NOW IN THE FORMAT.
The paragraph above about shared lanes ("more than one node on a lane is the
village working, not a violation") described what this hook BELIEVED and could
not act on, because the row grammar had room for exactly one owner. A lane
worked by four bodies could only be attributed to one, so a declared
collaboration and a genuine clash looked identical from here.

    co-owners: `4090-CLAUDE` (filed the blocker), `Z890-CLAUDE` (ran Windows)

Collisions key on PARTICIPANTS -- the signing owner plus everyone the row
declares -- intersected with the lane. An UNDECLARED overlap still blocks
exactly as before.

WHO DECLARED IT DECIDES WHAT HAPPENS, because a set intersection cannot tell
consent from assertion. The first cut of this feature tested `mine & theirs`,
which is symmetric, so "the incumbent invited me" and "I named the incumbent
without asking" were the same fact from here -- and BOTH exited 0 with empty
stderr. That is a self-issued exemption with no trace, and a gate with one of
those is not a gate. Worse, it is the locally cheapest move available to an
agent that just got blocked: the block message says "coordinate a handoff",
`co-owners:` is in the grammar, and typing the incumbent's name makes the red
text go away.

So the three cases are kept apart:

  * RECIPROCATED -- the incumbent's own open row names this claimant. The party
    who HOLDS the lane consented. Allowed, and announced on stderr: a
    suppressed collision that prints nothing is indistinguishable from a gate
    that never ran, which is exactly how the silent version shipped.
  * UNILATERAL -- only this row declares the sharing (or both rows merely name
    some third party). Not blocked and not waved through: raised as
    `permissionDecision: "ask"`, naming who declared whom. Refusing would be
    wrong -- an incumbent that went offline is precisely why the register is a
    ledger and not a lock -- but so is silence. The failure mode being removed
    here is silence, not permissiveness.
  * UNDECLARED -- nobody wrote anything down. Blocks, as before.

RELEASE pairing deliberately stays keyed on the SIGNING owner. A co-owner is
declared as having worked the lane, not as having authority to close someone
else's claim -- attribution and authority are different powers, and conflating
them would make the field a way to release work you do not own.

A row that announces `co-owners:` and names none the parser can read is
reported as NOT MEASURED on stderr AND raised as an `ask`. It is not treated as
a row with no co-owners: an attribution that satisfies a human reader and is
empty to every machine is the exact defect the field was added to remove, and
silently accepting it would reproduce that defect one layer down. Stderr alone
was not enough -- on exit 0 it is not fed back the way exit-2 stderr is, so the
signal was close to invisible on the path that actually gates.

Grammar and rationale: AGNOTE4482PHI.t1.md § Row grammar.
Parser: pmoves/tools/identity_lineage.py (co_owners_in).

Exit codes:
  0  allow -- possibly carrying `permissionDecision: "ask"` on stdout
  2  block (stderr fed back to Claude)

THERE IS NO EXIT 3 HERE, deliberately. identity_lineage.py's CLI uses 3 for
"could not measure", and the register documents that doctrine "across this
tooling" -- but a PreToolUse hook has a two-code vocabulary (0 allow, 2 block)
and reads anything else as a non-blocking error. Exiting 0 with only stderr
made could-not-measure indistinguishable from clean on the surface an agent
actually hits, so it is raised as an `ask` instead: a decision-carrying signal,
which is what the doctrine was after.
"""

import json
import os
import re
import sys
from pathlib import Path

REGISTER_NAME = "AGNOTE4482PHI.t1.md"
REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
CLAIM_RE = re.compile(r'CLAIM\s+`([^`]+)`')
RELEASE_RE = re.compile(r'RELEASE\s+`([^`]+)`')
# A branch as the register writes it: conventional-commit prefix, backticked.
LANE_RE = re.compile(
    r'`((?:feat|fix|docs|chore|refactor|test|ci|perf|build)/[A-Za-z0-9._/-]+)`'
)
# A backticked `docs/...` token is just as often a FILE as a branch, and scopes
# cite files constantly. Left unfiltered, `docs/superpowers/specs/x-design.md`
# registered as a claimed lane -- so two agents who merely referenced the same
# spec could collide on it, and the register showed lanes nobody was working.
# Found by running the advisory against the live register, not by reading it.
# Branches do not carry a file extension; paths in this repo reliably do.
FILE_SUFFIXES = (
    ".md", ".py", ".yaml", ".yml", ".json", ".sh", ".ts", ".tsx", ".js",
    ".toml", ".txt", ".sql", ".conf", ".bat", ".ps1",
)


# `Branch \`x\`` / `branch: \`x\`` -- how 68 claims in the live register already
# mark their lane. A token behind this marker is a DECLARED branch, so the
# suffix filter must not touch it: a real branch may end `.py` or `.md`, and
# dropping it left BOTH claims unkeyed, which let two owners hold one lane with
# no collision. The gate failed open, silently. The filter still applies to
# unmarked tokens, where a backticked `docs/...` really is usually a cited file.
#
# THE LOOKBEHIND IS LOAD-BEARING. With `:` optional and `\s*` permissive, the
# word "branch" INSIDE a code span -- "BRANCH_MARKER_RE keys on the word
# `branch`, so neither can fire..." -- matched, then captured everything up to
# the next backtick as a lane. Two CLAIM rows in the live register hold a
# phantom lane made of prose that way (L1949 on `main`, and the row that
# introduced the co-owners field), and in an append-only file a phantom lane
# stays open forever: it is a lane nobody is working that blocks whoever tries.
# `(?<!`)` says a marker that is itself the tail of a code span is a MENTION.
# Measured over the whole register: exactly 2 lane sets change, both of them
# these phantoms, and no real branch is lost on any row.
BRANCH_MARKER_RE = re.compile(
    r'(?<!`)\bbranch\b[:=]?\s*`([^`]+)`',
    re.IGNORECASE,
)


def lanes_in(text: str) -> set[str]:
    """Branch-shaped tokens in a line, with cited file paths excluded.

    Explicitly marked branches are kept whatever they end in; everything else
    must survive FILE_SUFFIXES to count as a lane.
    """
    declared = {lane for lane in BRANCH_MARKER_RE.findall(text) if lane.strip()}
    inferred = {
        lane for lane in LANE_RE.findall(text)
        if not lane.lower().endswith(FILE_SUFFIXES)
    }
    return declared | inferred


_UNSET = object()
_FOLDER = _UNSET
_LINEAGE = _UNSET


def _load_lineage():
    """Return the identity_lineage module, or None if it is unavailable.

    Both name-folding AND co-owner parsing come from here, so they share one
    import and one failure mode instead of two.

    WHAT IS LOST WHEN THIS RETURNS None, stated because the direction matters:
    co-owner declarations stop being parsed, so a lane two nodes have EXPLICITLY
    declared they share reads as a lane one node holds -- and the gate blocks
    the other. That is fail-CLOSED: noisy, not silent, and recoverable by the
    operator who reads the block message. The opposite arrangement -- assuming
    collaboration when you cannot read the declaration -- would let a real
    collision through while looking calm, which is the failure this hook exists
    to prevent.
    """
    global _LINEAGE
    if _LINEAGE is not _UNSET:
        return _LINEAGE
    _LINEAGE = None
    try:
        import importlib.util
        root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "identity_lineage",
            root / "pmoves" / "tools" / "identity_lineage.py",
        )
        module = importlib.util.module_from_spec(spec)
        # MUST be registered before exec_module: identity_lineage defines
        # @dataclass, and dataclasses._is_type resolves the owning module
        # via sys.modules[cls.__module__]. Unregistered, that is None and
        # the import dies with a bare AttributeError about __dict__.
        sys.modules["identity_lineage"] = module
        spec.loader.exec_module(module)
        module.load_vocabulary()  # fail here, not on the first fold
        _LINEAGE = module
    except Exception as exc:  # noqa: BLE001 -- a guard must not die here
        sys.stderr.write(
            f"claim-collision-pre: identity vocabulary unavailable ({exc}); "
            "comparing owner strings exactly, as before. Spelling drift "
            "will not be folded, and declared co-owners will not be read.\n"
        )
    return _LINEAGE


def _load_folder():
    """Return a name-folding callable, or None if it is unavailable."""
    global _FOLDER
    if _FOLDER is not _UNSET:
        return _FOLDER
    module = _load_lineage()
    if module is None:
        _FOLDER = None
        return _FOLDER
    vocab = module.load_vocabulary()

    def _fold(owner: str) -> str:
        return module.canonical_identity(owner, vocab) or owner

    _FOLDER = _fold
    return _FOLDER


def co_owners_in(text: str) -> set[str]:
    """Canonical identities declared as co-owners on a row.

    Co-owner IDs go through canonical_owner(), the SAME normalisation the
    signing owner gets. Anything less would let one identity appear as a
    co-owner under a spelling the gate does not recognise, and the declaration
    would then fail to do the one thing it is for.
    """
    module = _load_lineage()
    if module is None:
        return set()
    return {canonical_owner(name) for name, _note in module.co_owners_in(text)}


def declares_unreadable_co_owners(text: str) -> bool:
    """True when a row announces co-owners and names none a machine can read."""
    module = _load_lineage()
    return bool(module) and module.co_owner_field_is_unparseable(text)


def canonical_owner(owner: str) -> str:
    """Fold an owner string to its canonical identity.

    WHY: this hook compared owner strings with `==`, and one identity writes
    several. B850 alone appears as `(Knuckles)` x16, `(Knuckles, opus 4.7
    1M)` x7, `(Opus 5)` x2, `(Claude Opus 5)` x1 -- so a RELEASE under one
    spelling did not close a CLAIM opened under another, and a lane stayed
    open for a week (2026-08-25). The same equality also makes an identity
    collide with ITSELF as soon as its parenthetical changes.

    FAIL-SAFE: with no vocabulary this returns the string unchanged, which
    is exactly the previous behaviour. A guard that cannot fold keys is no
    worse than it was; a guard that raises stops guarding.
    """
    fold = _load_folder()
    return fold(owner) if fold else owner


def open_claims_in(text: str) -> dict[str, tuple[int, set[str], str]]:
    """Map canonical owner -> LIST of (line, lanes, as-written) still open.

    A LIST, not a single tuple. Keying one claim per owner silently forgot
    every lane but the newest: two open claims by one identity collapsed to
    one, and a later release dropped the survivor too -- so a lane another
    node genuinely held stopped colliding. That was true before
    canonicalisation for two claims under the SAME spelling, and folding
    spellings widened it to the whole identity.

    A CLAIM is "open" if no later RELEASE for the same owner follows it.
    Pairing is on the CANONICAL identity, not the literal string: a release
    no longer has to carry the exact spelling its claim was opened with,
    which is the defect that left a lane open for a week. The as-written
    string is kept for the message -- `B850-CLAUDE (Knuckles)` locates the
    entry and `b850-claude` does not.

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
    open_claims: dict[str, list[tuple[int, set[str], str, set[str]]]] = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        if m := CLAIM_RE.search(line):
            owner_key = canonical_owner(m.group(1))
            # PARTICIPANTS = the signing owner PLUS everyone the row declares as
            # a co-owner. This is the whole point of the field: a lane worked by
            # four bodies now says so, instead of naming one and losing three.
            participants = {owner_key} | co_owners_in(line)
            open_claims.setdefault(owner_key, []).append(
                (lineno, lanes_in(line), m.group(1), participants)
            )
        elif m := RELEASE_RE.search(line):
            # Pairing stays on the SIGNING owner, deliberately. A co-owner is
            # declared as having worked the lane, not as having authority to
            # close someone else's claim -- letting a co-worker's RELEASE close
            # the primary's lane would make the field a way to release work you
            # do not own. Attribution and authority are different powers.
            owner = canonical_owner(m.group(1))
            released = lanes_in(line)
            if not released:
                # A BARE release closes everything that owner holds. 99 of
                # the register's 120 RELEASE lines name no branch, so this
                # is the convention, not a guess -- a bare release is a
                # full handoff.
                open_claims.pop(owner, None)
            else:
                # A release that NAMES lanes closes only those. Anything
                # else the owner still holds stays held.
                kept = [
                    (ln, lanes - released, raw, participants)
                    for ln, lanes, raw, participants in open_claims.get(owner, [])
                    if lanes - released
                ]
                if kept:
                    open_claims[owner] = kept
                else:
                    open_claims.pop(owner, None)
    return open_claims


# Shell tokens that mean "this command can modify a file". Deliberately broad:
# a false positive costs one prompt, a false negative is the hole this closes.
WRITE_TOKENS = re.compile(
    r"\btee\b|"                    # tee / tee -a
    r"\bsed\b[^|]*-i|"             # sed -i
    r"\bdd\b|"
    # Replacement-style rewrites. These carry no redirect and no -i, so the
    # advisory was silent while the register was overwritten wholesale -- the
    # most ordinary way to replace a file walked straight through the gate.
    r"\b(?:cp|mv|install|rsync|truncate)\b|"
    r"\bperl\b[^|]*-[a-zA-Z]*i|"   # perl -pi / -i.bak
    r"\b(?:write_text|open)\s*\(|"  # python inside a heredoc
    r"\bcat\b[^|]*<<"              # heredoc
)

# Redirects are handled separately from the tokens above, because `>` alone
# says nothing about WHICH file is written. `cat REGISTER 2>/dev/null` and
# `grep REGISTER > report.txt` both name the register and both redirect, yet
# neither writes it. This hook runs on every Bash call, so those false asks are
# friction on ordinary reads -- and friction is what teaches people to click
# through the one prompt that matters.
REDIRECT_TARGET_RE = re.compile(r">>?\s*([^\s;|&<>]+)")


def _writes_the_register(command: str) -> bool:
    """True when `command` plausibly MODIFIES the register (not merely reads it)."""
    if WRITE_TOKENS.search(command):
        return True
    return any(
        REGISTER_NAME in target
        for target in REDIRECT_TARGET_RE.findall(command)
    )


def _advise_on_shell_write(payload: dict) -> None:
    """Ask (never block) when a shell command looks like it writes the register.

    Emits nothing at all unless the command names the register AND carries a
    write token, so ordinary `grep`/`sed -n` reads stay silent.
    """
    command = ((payload.get("tool_input") or {}).get("command") or "")
    if REGISTER_NAME not in command or not _writes_the_register(command):
        return

    register = _locate_register(payload, command)
    if register is None:
        return
    try:
        existing_open = open_claims_in(register.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return

    # open_claims_in maps owner -> LIST of (lineno, lanes, as-written), not a
    # single tuple: one identity can hold several lanes at once, and #2760 made
    # that explicit because keying one claim per owner silently forgot every
    # lane but the newest. Count and list CLAIMS, therefore, not owners.
    keyed = [c for claims in existing_open.values() for c in claims if c[1]]
    total_open = sum(len(claims) for claims in existing_open.values())
    lines = [
        "This shell command writes the claim register. The collision gate reads "
        "proposed text from Write/Edit payloads and cannot see inside a shell "
        "command, so it has NOT checked this one.",
        "",
        f"Open lanes right now ({total_open} total, {len(keyed)} naming a branch):",
    ]
    # Report the AS-WRITTEN owner, not the canonical key: `B850-CLAUDE
    # (Knuckles)` locates the entry in the register and `b850-claude` does not.
    for lineno, lanes, raw, participants in sorted(keyed, key=lambda c: c[0]):
        shared = sorted(participants - {canonical_owner(raw)})
        with_whom = f"  (shared with {', '.join(shared)})" if shared else ""
        lines.append(
            f"  L{lineno}  {raw} -> {', '.join(sorted(lanes))}{with_whom}"
        )
    unkeyed = total_open - len(keyed)
    if unkeyed:
        lines.append(
            f"  (+{unkeyed} open claim(s) naming no branch -- not comparable)"
        )
    lines += [
        "",
        "A lane held by another node is not a stop sign: nodes go offline, and "
        "more than one node on a lane is the village working. Coordinate, pick "
        "it up, or proceed -- but do it knowingly.",
    ]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "\n".join(lines),
        }
    }))


def _locate_register(payload: dict, command: str) -> Path | None:
    """Resolve the register THIS command writes -- or nothing.

    Relative to the payload's cwd first. An earlier cut resolved bare filenames
    against the hook's own cwd, missed, and fell through to the repo's real
    register -- so it would have reported the live fleet's open lanes for a
    command writing an unrelated file somewhere else. Reporting state from a
    different file than the one being written is worse than reporting none.
    """
    cwd = Path(payload.get("cwd") or os.getcwd())
    for token in re.findall(r"[\w./~-]*" + re.escape(REGISTER_NAME), command):
        raw = Path(token).expanduser()
        for candidate in ((cwd / raw), raw, (REPO_ROOT_GUESS / raw)):
            if candidate.is_file():
                return candidate
    # The command names the register but no token resolved to a real file (a
    # variable, a generated path). Fall back ONLY to a register under the
    # command's own cwd -- never to the repo's.
    hit = cwd / "pmoves" / "docs" / "AGENTS" / REGISTER_NAME
    return hit if hit.is_file() else None


def _row_at(text: str, pos: int) -> str:
    """The single register row containing `pos`.

    A register entry is one line, and open_claims_in() has always read the
    EXISTING side that way. The PROPOSED side did not: co_owners_in() ran once
    over the whole edit and its result was attached to every CLAIM match in it,
    so one honest declaration on row 1 granted participation to every other row
    in the same write. Deleting the field from an unrelated row flipped a
    squatting row from ALLOW to BLOCK -- the field was being read from outside
    its own row's scope.

    That is not only an adversarial case. Multi-row appends here are routine,
    and the result was that the gate and the register disagreed about who is on
    a lane -- worse than either being wrong alone, because the register looked
    correct while the gate acted on something else.

    `split`-on-newline semantics, for the reason open_claims_in() documents at
    length: the register carries vertical tabs and form feeds that
    `splitlines()` breaks on and no editor, grep or sed counts as a line.
    """
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:] if end == -1 else text[start:end]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool = payload.get("tool_name", "")
    if tool == "Bash":
        _advise_on_shell_write(payload)
        sys.exit(0)
    if tool not in ("Write", "Edit"):
        sys.exit(0)
    ti = payload.get("tool_input") or {}
    file_path = ti.get("file_path", "") or ""
    if not file_path.endswith(REGISTER_NAME):
        sys.exit(0)

    # Proposed-text source differs across tools.
    proposed = ti.get("new_string") if tool == "Edit" else ti.get("content")
    proposed = proposed or ""
    new_claims = []
    for m in CLAIM_RE.finditer(proposed):
        row = _row_at(proposed, m.start())
        # LANES per row, with the whole-edit read kept as a FALLBACK for a row
        # that names no branch of its own. Scoping alone would have made this
        # blinder than it was: a claim whose branch is written on a
        # neighbouring line would stop being compared and start reporting
        # "NOT CHECKED", which is a quiet downgrade from blocking. Fail-closed
        # is the direction to err in, so the row is taken at its word when it
        # gives one and inherits the edit's lanes when it does not.
        lanes = lanes_in(row) or lanes_in(proposed)
        # CO-OWNERS strictly per row, NO fallback. A declaration is the one
        # thing that can SUPPRESS a collision, so inheriting one from a
        # neighbouring row is the entire defect. A row that declares nothing
        # declares nothing.
        new_claims.append((m.group(1), lanes, co_owners_in(row)))
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
    collisions = []   # nobody declared anything: block
    shared = []       # the INCUMBENT declared this claimant: allow, out loud
    one_sided = []    # only this row declared it: ask
    unkeyed = []
    for owner, lanes, declared in new_claims:
        if not lanes:
            unkeyed.append(owner)
            continue
        owner_key = canonical_owner(owner)
        # The claimant's own participant set: itself, plus anyone it declares it
        # is working with.
        mine = {owner_key} | declared
        for other_key, open_list in existing_open.items():
            for lineno, held, other_as_written, theirs in open_list:
                overlap = sorted(lanes & held)
                if not overlap:
                    continue
                if other_key == owner_key:
                    # The node that already holds it, under any spelling. Not a
                    # collision, and not worth a word: this is the routine case
                    # the first cut of the hook broke.
                    continue
                if owner_key in theirs:
                    # RECIPROCATED. The party who HOLDS the lane named this
                    # claimant on their own open row, so the sharing was
                    # consented to by the side that had something to give up.
                    shared += [(lane, other_as_written, lineno) for lane in overlap]
                    continue
                witnesses = sorted(mine & theirs)
                if witnesses:
                    # UNILATERAL. Something is shared -- this row says so, or
                    # both rows happen to name the same third party -- but the
                    # incumbent's row does not name this claimant back. That is
                    # attribution, not a handoff, and the difference is not
                    # decidable from inside a PreToolUse hook. Surface it.
                    one_sided += [
                        (owner, lane, other_as_written, lineno, witnesses)
                        for lane in overlap
                    ]
                    continue
                collisions += [
                    (lane, other_as_written, lineno) for lane in overlap
                ]

    # NOTHING SUPPRESSED LEAVES NO TRACE. A consented share is allowed without
    # a prompt -- that workflow has to stay frictionless or nobody uses the
    # field -- but it is still announced. An allow that prints nothing cannot be
    # told apart from a gate that did not run, and that is precisely the state
    # the reviewer found this hook in.
    for lane, other, lineno in shared:
        sys.stderr.write(
            f"claim-collision-pre: SHARED LANE - `{lane}` is held by `{other}` "
            f"(open CLAIM at line {lineno}), whose own row declares this claimant "
            "as a co-owner. Allowing: the incumbent declared the sharing.\n"
        )

    asks = []
    for owner, lane, other, lineno, witnesses in one_sided:
        # As-written where we have it, for the reason the advisory documents:
        # `4090-CLAUDE` locates the row and `4090-claude` does not. The
        # canonical key is only shown for a third party whose own spelling
        # lives on neither of these two rows.
        named = ", ".join(
            f"`{other if canonical_owner(other) == w else w}`" for w in witnesses
        )
        asks.append(
            f"  - `{owner}` claims lane `{lane}`, held by `{other}` "
            f"(open CLAIM at line {lineno}).\n"
            f"    Shared participant(s) {named} are declared by THIS row; "
            f"`{other}`'s open row does not declare `{owner}` back, so the "
            "sharing is UNILATERAL."
        )

    # A row that ANNOUNCES co-owners and names none the parser can read is
    # UNMEASURED, not clean. Silently treating it as "no co-owners" would let an
    # attribution that satisfies a human reader be empty to every machine --
    # which is the exact defect this field was added to remove.
    if declares_unreadable_co_owners(proposed):
        sys.stderr.write(
            "claim-collision-pre: NOT MEASURED - this row declares `co-owners:` "
            "but no backticked ID could be parsed from it, so the shared-lane "
            "check ran WITHOUT them. Write each ID in backticks, e.g. "
            "co-owners: `4090-CLAUDE` (filed the blocker).\n"
        )
        asks.append(
            "  - a row declares `co-owners:` and names none the parser can "
            "read, so the shared-lane check ran WITHOUT them. Could not "
            "measure is not the same as clean."
        )

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

    if asks:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "\n".join([
                    "This CLAIM does not collide only because of something "
                    "written in the edit itself. Nobody on the other side has "
                    "said so:",
                    "",
                    *asks,
                    "",
                    "A one-sided declaration is attribution, not a handoff, and "
                    "this hook cannot tell the two apart from here. If you have "
                    "coordinated -- or the incumbent is offline and you are "
                    "picking the lane up -- proceed. If you have not, coordinate "
                    "first or pick a different branch. Asking rather than "
                    "refusing is deliberate: the register is a shared ledger, "
                    "not a lock, and more than one node on a lane is often the "
                    "village working.",
                ]),
            }
        }))

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
