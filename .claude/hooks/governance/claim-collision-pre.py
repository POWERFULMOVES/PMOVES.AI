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

THE BASH PATH NOW BLOCKS. It used to be advisory, and the paragraph here used to
say it "cannot be closed the same way" because "recovering what will this write
from arbitrary shell is not something to attempt in a PreToolUse hook."

That was right about ARBITRARY shell and wrong about the case every agent here
actually uses. A heredoc body IS in the command string this hook already
receives: `cat >> REG <<EOF ... EOF` carries its content in the payload. So the
content is recoverable, `evaluate_claims()` runs on it, and the shell path
refuses exactly what the Write path refuses, with the same message.

WHY IT MATTERED MORE THAN IT LOOKED. Measured 2026-09-02, identical content
against a genuinely held lane: Write exited 2 and blocked; Bash exited 0 with
`permissionDecision: "ask"` -- and an "ask" is resolved by a permission
classifier reading the shell COMMAND, not the lane, to which
`cat >> REG <<EOF` looks entirely benign. Four delivery agents in one session
had NO Write or Edit tool ("Write is disabled for this session, in subagents as
well as here"), so the advisory path was the only path they had, and every
register write in that session was unchecked.

WHAT IS STILL NOT RECOVERABLE is denied, not waved through: `sed -i`, a path in
a variable, content piped from another process, a python heredoc that computes
its row. Per this repo's exit-code doctrine -- 0 clean / 1 findings / 3 could
not measure, NOT a pass -- could-not-measure is a refusal. Exiting 0 with an
"ask" made could-not-measure indistinguishable from measured-clean on the only
surface that gates.

THE DENY IS ONLY DEFENSIBLE BECAUSE A SANCTIONED PATH EXISTS. Refusing shell
writes while agents have no Write tool would deadlock the fleet: nobody could
file a claim at all, which is strictly worse than the gap being closed. Every
refusal below names `make -C pmoves register-claim`, which appends through
validated code -- clock-read timestamp, collision check, O_APPEND.

The register is still a shared ledger and not a lock. What the block refuses is
an UNCHECKED write, not a shared lane; the ledger's own answer to "more than one
node on a lane is the village working" is the `co-owners:` field, not an
unguarded write path.

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
BRANCH_MARKER_RE = re.compile(
    r'\bbranch\b[:=]?\s*`([^`]+)`',
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


def _load_folder():
    """Return a name-folding callable, or None if it is unavailable."""
    global _FOLDER
    if _FOLDER is not _UNSET:
        return _FOLDER
    _FOLDER = None
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
        vocab = module.load_vocabulary()

        def _fold(owner: str) -> str:
            return module.canonical_identity(owner, vocab) or owner

        _FOLDER = _fold
    except Exception as exc:  # noqa: BLE001 -- a guard must not die here
        sys.stderr.write(
            f"claim-collision-pre: identity vocabulary unavailable ({exc}); "
            "comparing owner strings exactly, as before. Spelling drift "
            "will not be folded.\n"
        )
    return _FOLDER


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
    open_claims: dict[str, list[tuple[int, set[str], str]]] = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        if m := CLAIM_RE.search(line):
            open_claims.setdefault(canonical_owner(m.group(1)), []).append(
                (lineno, lanes_in(line), m.group(1))
            )
        elif m := RELEASE_RE.search(line):
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
                    (ln, lanes - released, raw)
                    for ln, lanes, raw in open_claims.get(owner, [])
                    if lanes - released
                ]
                if kept:
                    open_claims[owner] = kept
                else:
                    open_claims.pop(owner, None)
    return open_claims


# --------------------------------------------------------------------------
# RECOVERING WHAT A SHELL COMMAND WILL WRITE
#
# This module's previous docstring said recovering "what will this write" from
# arbitrary shell "is not something to attempt in a PreToolUse hook". That is
# right about ARBITRARY shell and wrong about the common case, and the common
# case is the one every agent here actually uses: a heredoc body IS in the
# command string the hook already receives. `cat >> REG <<EOF ... EOF` carries
# its content in the payload. So the content is recoverable, the same collision
# check the Write path runs can run on it, and the shell-shaped hole closes.
#
# What is genuinely NOT recoverable -- `sed -i`, a path in a variable, content
# piped from another process, a python heredoc that computes its row -- is
# could-not-measure. Per this repo's exit-code doctrine (0 clean / 1 findings /
# 3 could not measure -- NOT a pass, see docker_host_policy_check.py and
# mcp_toolkit_preflight.py) could-not-measure is not a pass, so it is denied
# with a message naming the sanctioned path rather than waved through as "ask".
# --------------------------------------------------------------------------

HEREDOC_DELIM_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# `(>>?)` captured, because append and truncate are different acts against an
# append-only ledger and the gate has to be able to tell them apart.
REDIRECT_RE = re.compile(r"(>>?)\s*([^\s;|&<>]+)")
TEE_RE = re.compile(r"\btee\b((?:\s+-\S+)*)((?:\s+[^\s;|&<>]+)*)")
ECHO_LITERAL_RE = re.compile(
    r"\b(?:echo|printf)\b(?:\s+-\S+)*\s+(['\"])(.*?)\1", re.S
)
# Shell write verbs whose CONTENT cannot be read out of the command string.
SHELL_OPAQUE_RE = re.compile(
    r"\bsed\b[^|;]*-i|"
    r"\bperl\b[^|;]*-[a-zA-Z]*i|"
    r"\b(?:cp|mv|install|rsync|truncate|dd)\b"
)
# Python WRITES, kept apart from python reads. `open(p)` alone is ambiguous and
# a lone `open\s*\(` refused `print(open(REG).read())` -- a read. A mode of
# `a`/`w`, or a `.write(`/`write_text(` call, is what distinguishes them.
PY_WRITE_RE = re.compile(
    r"\.write\s*\(|\bwrite_text\s*\(|"
    r"\bopen\s*\([^)]*['\"][aw]"
)
SEGMENT_SPLIT_RE = re.compile(r"\n|;|&&|\|\||\|")
INTERPRETER_RE = re.compile(
    r"\b(?:python3?|perl|ruby|node|deno|bash|sh|zsh|awk|php)\b"
)
# An unexpanded `$VAR`, `${...}`, `$(...)` or backtick means the text this hook
# can SEE is not the text that will be WRITTEN.
EXPANSION_RE = re.compile(r"[$`]")

SANCTIONED_PATH = (
    "make -C pmoves register-claim  (or register-release)  -- "
    "see AGNOTE4482PHI.t1.md " + chr(167) + " Filing a row"
)


def split_heredocs(command: str) -> tuple[str, list[dict]]:
    """Split `command` into its shell SKELETON and its heredoc bodies.

    Separating the two is what makes every check below trustworthy. Analysed as
    one blob, a heredoc body's own contents are indistinguishable from shell
    code: a row of register PROSE that happens to contain the word `cp`, or a
    `>` inside a quoted scope, reads to a regex as a write verb and a redirect.

    That is not a theoretical concern in this repo. The damage-control hook
    matches literal strings anywhere in a command INCLUDING inside heredoc
    content, and an agent had its own report blocked for merely quoting a
    phrase. The first cut of THIS function reproduced the same bug one layer
    down -- a `cat > /tmp/notes.md` heredoc explaining "use cp to back up the
    register" was refused as an unmeasurable register write. Found by running
    the gate, not by reading it.

    Each heredoc is returned with the line that OPENED it, because two
    properties that decide everything downstream can only be read there:

      * `code`    -- fed to an interpreter (its body is instructions ABOUT the
                     register) versus redirected to a file (its body IS the
                     register). Asking a data body whether it "writes the
                     register" is exactly the false positive above.
      * `literal` -- the delimiter was quoted, so the shell performs no
                     expansion and the body is byte-for-byte what lands. An
                     unquoted delimiter can expand a `$VAR` into a whole row
                     this hook never saw.

    Bodies are matched to delimiters IN ORDER, which is what the shell itself
    does. A delimiter that never terminates consumes the rest of the command:
    that over-approximates the body, and over-approximating the text to be
    CHECKED is the fail-closed direction -- more candidate rows are compared,
    never fewer.
    """
    if not HEREDOC_DELIM_RE.search(command):
        return command, []
    lines = command.split("\n")
    skeleton_lines: list[str] = []
    bodies: list[dict] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        skeleton_lines.append(line)
        idx += 1
        # Every heredoc opened ON THIS LINE takes its body starting now, in the
        # order the operators appear -- the shell's own rule for `cmd <<A <<B`.
        for m in HEREDOC_DELIM_RE.finditer(line):
            quote, delim = m.group(1), m.group(2)
            body: list[str] = []
            while idx < len(lines) and lines[idx].strip() != delim:
                body.append(lines[idx])
                idx += 1
            idx += 1  # consume the terminator line itself
            bodies.append({
                "delim": delim,
                "body": "\n".join(body),
                "opener": line,
                "literal": bool(quote),
                "code": bool(INTERPRETER_RE.search(line)),
            })
    return "\n".join(skeleton_lines), bodies


def _segments(text: str) -> list[str]:
    return [s for s in SEGMENT_SPLIT_RE.split(text) if s.strip()]


def _tee_targets(segment: str) -> tuple[list[str], bool]:
    """(targets, appends) for any `tee` in `segment`."""
    targets: list[str] = []
    appends = False
    for m in TEE_RE.finditer(segment):
        flags, rest = m.group(1) or "", m.group(2) or ""
        if re.search(r"-\w*a", flags):
            appends = True
        targets += rest.split()
    return targets, appends


def _register_redirects(segment: str) -> tuple[bool, bool]:
    """(appends_register, truncates_register) for one skeleton segment."""
    appends = truncates = False
    for op, target in REDIRECT_RE.findall(segment):
        if REGISTER_NAME not in target:
            continue
        if op == ">>":
            appends = True
        else:
            truncates = True
    tee_targets, tee_appends = _tee_targets(segment)
    if any(REGISTER_NAME in t for t in tee_targets):
        if tee_appends:
            appends = True
        else:
            truncates = True
    return appends, truncates


class ShellWrite:
    """How a shell command writes the register, and what it will write.

    kind:
      "none"      -- the command does not write the register (it may name it)
      "append"    -- appends, and `text` is what will be appended
      "truncate"  -- rewrites the file wholesale
      "opaque"    -- writes it, and the content is NOT in the command string
    """

    def __init__(self, kind: str, text: str = "", why: str = "") -> None:
        self.kind = kind
        self.text = text
        self.why = why


def classify_shell_write(command: str) -> ShellWrite:
    """Decide whether `command` writes the register, and recover the content.

    KEYED ON THE WRITE TARGET, NOT ON MENTION. The advisory this replaces
    triggered whenever the command NAMED the register and carried any write
    token anywhere, so writing an unrelated source file whose CONTENT mentions
    the register -- this hook's own source, a runbook, a test fixture -- raised
    an advisory listing the live fleet's open lanes. Harmless while the verdict
    was "ask". Fatal as a deny: it would refuse ordinary work that touches no
    ledger at all, and a gate that refuses ordinary work gets switched off.

    The question is asked of the EXECUTABLE text only -- the shell skeleton plus
    the bodies of heredocs fed to an interpreter. A register name appearing
    solely in DATA (a doc being written, a row being appended, a quoted scope)
    is a mention, not a write.

    EVERY "opaque" VERDICT REQUIRES POSITIVE EVIDENCE OF A WRITE. The first cut
    denied anything whose executable text named the register and offered no
    explicit redirect -- which is the shape of `grep -c CLAIM REG`. It refused
    a plain READ. That single case would have made the register unreadable from
    the shell, which is worse than the hole being closed and is precisely the
    deadlock class this lane exists to avoid. Found by probing the gate with a
    read, not by reading the code.
    """
    skeleton, bodies = split_heredocs(command)
    executable = "\n".join(
        [skeleton] + [h["body"] for h in bodies if h["code"]]
    )
    if REGISTER_NAME not in executable:
        return ShellWrite("none")

    appends: list[str] = []
    for seg in _segments(skeleton):
        seg_appends, seg_truncates = _register_redirects(seg)
        if seg_truncates:
            return ShellWrite(
                "truncate",
                why="a single `>` (or a `tee` without `-a`) REPLACES the "
                    "register. It is append-only: every row is provenance, and "
                    "a rewrite cannot be distinguished from a redaction after "
                    "the fact.",
            )
        if seg_appends:
            appends.append(seg)

    if not appends:
        # No redirect resolves to the register. Either this is not a write at
        # all, or it is a write whose target this hook cannot see. Only the
        # second is refused, and only on evidence.
        for seg in _segments(skeleton):
            if SHELL_OPAQUE_RE.search(seg) and REGISTER_NAME in seg:
                return ShellWrite(
                    "opaque",
                    why="`" + seg.strip()[:120] + "` writes the register with "
                        "content that is not in the command string.",
                )
        for h in bodies:
            if h["code"] and REGISTER_NAME in h["body"] \
                    and PY_WRITE_RE.search(h["body"]):
                return ShellWrite(
                    "opaque",
                    why="a `<<" + h["delim"] + "` heredoc opens the register "
                        "for writing in code, so any row it adds is computed "
                        "at run time and is not in the command string.",
                )
        # A redirect target the hook cannot resolve -- `cat >> $REG` -- is a
        # write to somewhere unknown while the register is named in the same
        # breath. That is could-not-measure, not clean.
        for op, target in REDIRECT_RE.findall(skeleton):
            if EXPANSION_RE.search(target):
                return ShellWrite(
                    "opaque",
                    why="the redirect target `" + target + "` is a shell "
                        "expansion, so which file is written cannot be "
                        "determined from the command.",
                )
        # Nothing writes the register. It is being read, or merely named.
        return ShellWrite("none")

    # An append whose target is explicit. Recover the content -- but only text
    # that is genuinely LITERAL. `echo "$ROW" >> REG` recovers the string
    # `$ROW`, which contains no CLAIM and sailed through the first cut of this
    # function at exit 0: a fail-open produced by treating an unexpanded
    # variable as though it were the content. Anything carrying `$` or a
    # backtick is text this hook cannot see, which is could-not-measure.
    recovered: list[str] = []
    for h in bodies:
        if h["code"]:
            continue
        if not h["literal"] and EXPANSION_RE.search(h["body"]):
            return ShellWrite(
                "opaque",
                why="the `<<" + h["delim"] + "` delimiter is unquoted and the "
                    "body contains a shell expansion, so the text written is "
                    "not the text in this command.",
            )
        recovered.append(h["body"])
    if not recovered:
        for seg in appends:
            # THE QUOTE DECIDES, not the presence of a `$` or a backtick.
            # Register rows are made of backticks -- every timestamp, owner and
            # lane is a code span -- so a blanket expansion test condemned
            # `echo '- `ts` CLAIM ...' >> REG`, an ordinary literal append, as
            # unmeasurable. Inside SINGLE quotes the shell expands nothing, so
            # those characters are content. Inside DOUBLE quotes they are not.
            leftover = seg
            for m in ECHO_LITERAL_RE.finditer(seg):
                quote, lit = m.group(1), m.group(2)
                if quote == '"' and EXPANSION_RE.search(lit):
                    return ShellWrite(
                        "opaque",
                        why="`" + seg.strip()[:120] + "` builds the appended "
                            "row from a variable or another process, so the "
                            "row itself is not in the command string.",
                    )
                recovered.append(lit)
                leftover = leftover.replace(m.group(0), " ", 1)
            # Anything expanding OUTSIDE the quoted literals is still unread.
            if EXPANSION_RE.search(leftover):
                return ShellWrite(
                    "opaque",
                    why="`" + seg.strip()[:120] + "` carries a shell expansion "
                        "outside its quoted content, so what lands in the "
                        "register is not what this command shows.",
                )

    text = "\n".join(recovered)
    if not text.strip():
        return ShellWrite(
            "opaque",
            why="the command appends to the register but no literal content "
                "could be recovered from it.",
        )
    return ShellWrite("append", text=text)


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


def evaluate_claims(
    proposed: str, existing_open: dict
) -> tuple[list, list]:
    """(collisions, unkeyed) for the CLAIM rows in `proposed`.

    THE ONE PLACE THE COLLISION VERDICT IS COMPUTED. It was previously inline
    in main(), reachable only from the Write/Edit matcher, while the Bash
    matcher ran a separate advisory that listed open lanes and never compared
    anything. Two paths into one register, one of which decided and one of
    which described -- and the describing one was the only path an agent
    without a Write tool could use.

    Both paths now call this. Anything that sharpens the verdict sharpens it
    for the shell too, by construction rather than by remembering.

    Collision == ANOTHER owner already holds an open claim naming this lane.
    Same owner re-naming their own lane is not a collision: it is the node that
    already holds it, and blocking that was the false positive this hook
    shipped with.
    """
    new_claims = [
        (m.group(1), lanes_in(proposed))
        for m in CLAIM_RE.finditer(proposed)
    ]
    collisions: list[tuple[str, str, int]] = []
    unkeyed: list[str] = []
    for owner, lanes in new_claims:
        if not lanes:
            unkeyed.append(owner)
            continue
        owner_key = canonical_owner(owner)
        for other_key, open_list in existing_open.items():
            # Canonical: re-claiming your own lane under a different
            # spelling of your own name is not a collision.
            if other_key == owner_key:
                continue
            for lineno, held, other_as_written in open_list:
                for lane in sorted(lanes & held):
                    collisions.append((lane, other_as_written, lineno))
    return collisions, unkeyed


def _report_collisions(collisions: list) -> None:
    """Write the block message. SHARED, so the two paths cannot drift apart.

    An agent that hits this on the shell path and the same agent hitting it on
    the Write path must be told the same thing; a gate whose refusal depends on
    which tool you reached for teaches that the tool is the variable.
    """
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


def _report_unkeyed(unkeyed: list) -> None:
    for owner in unkeyed:
        sys.stderr.write(
            f"claim-collision-pre: NOT CHECKED - CLAIM by `{owner}` names no branch, "
            "so no lane could be compared. Add ``Branch `<name>``` to the scope to "
            "make this claim enforceable.\n"
        )


def _gate_shell_write(payload: dict) -> None:
    """Gate a Bash command that writes the register. Exits 2 to refuse.

    THIS PATH USED TO BE ADVISORY. Measured on 2026-09-02 with identical
    content against a genuinely held lane: the Write path exited 2 and blocked;
    the Bash path exited 0 carrying `permissionDecision: "ask"`. The collision
    was never computed -- the advisory listed open lanes and handed the decision
    to a permission classifier that evaluates the shell COMMAND, and
    `cat >> REG <<EOF` looks entirely benign to one of those.

    That gap was load-bearing, not academic: four delivery agents in one
    session had no Write or Edit tool at all ("Write is disabled for this
    session, in subagents as well as here"), so the advisory path was the ONLY
    path any of them could file through, and every register write they made was
    unchecked.

    WHY THIS IS SAFE TO CLOSE NOW, and was not before: denying shell writes
    while agents have no Write tool would deadlock the fleet -- nobody could
    file a claim at all, which is strictly worse than the gap. The deny is only
    defensible because `make -C pmoves register-claim` exists as a sanctioned
    path that appends through validated code, and every refusal below names it.
    """
    command = ((payload.get("tool_input") or {}).get("command") or "")
    verdict = classify_shell_write(command)
    if verdict.kind == "none":
        return

    register = _locate_register(payload, command)
    if register is None:
        # The command writes a register this hook cannot find, so it cannot be
        # compared against anything. Could-not-measure is not a pass.
        sys.stderr.write(
            "claim-collision-pre: NOT MEASURED - this command writes "
            f"{REGISTER_NAME} but no such file resolved from the command's own "
            "cwd, so the proposed rows could not be compared against the open "
            "lanes. Refusing rather than assuming.\n"
            f"Sanctioned path: {SANCTIONED_PATH}\n"
        )
        sys.exit(2)
    try:
        existing_open = open_claims_in(
            register.read_text(encoding="utf-8", errors="replace")
        )
    except OSError as exc:
        sys.stderr.write(
            "claim-collision-pre: NOT MEASURED - the register could not be "
            f"read ({exc}), so nothing was compared. Refusing rather than "
            "assuming.\n"
            f"Sanctioned path: {SANCTIONED_PATH}\n"
        )
        sys.exit(2)

    if verdict.kind in ("truncate", "opaque"):
        sys.stderr.write(
            "claim-collision-pre: NOT MEASURED - refusing a register write "
            "this hook cannot check.\n"
            f"  {verdict.why}\n"
            "Could not measure is NOT a pass (0 clean / 1 findings / 3 could "
            "not measure), and the advisory this replaces treated it as one.\n"
            f"Sanctioned path, which does the check for you: {SANCTIONED_PATH}\n"
            "It reads the clock for the timestamp, refuses a lane another "
            "owner holds, and appends in O_APPEND so the file cannot be "
            "rewritten.\n"
        )
        sys.exit(2)

    # RECOVERED CONTENT -- the same check the Write path runs, on the same
    # register, reporting the same message.
    collisions, unkeyed = evaluate_claims(verdict.text, existing_open)
    if collisions:
        _report_collisions(collisions)
        sys.exit(2)
    _report_unkeyed(unkeyed)

def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool = payload.get("tool_name", "")
    if tool == "Bash":
        _gate_shell_write(payload)
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
    if not CLAIM_RE.search(proposed):
        sys.exit(0)

    register = Path(file_path)
    if not register.is_file():
        sys.exit(0)  # nothing to collide with yet
    try:
        existing = register.read_text(encoding="utf-8", errors="replace")
    except OSError:
        sys.exit(0)

    collisions, unkeyed = evaluate_claims(proposed, open_claims_in(existing))
    if collisions:
        _report_collisions(collisions)
        sys.exit(2)

    # Say plainly when the gate could not check, instead of exiting 0 as though
    # it had. An unkeyed claim is unguarded, not cleared.
    _report_unkeyed(unkeyed)
    sys.exit(0)


if __name__ == "__main__":
    main()
