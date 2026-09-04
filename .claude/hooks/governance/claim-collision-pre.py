#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
#
# The dependency is DECLARED here, not merely installed somewhere, because the
# configured hook command is a bare `uv run` from a directory with no
# pyproject.toml. Without this block uv hands the script an interpreter that
# has no PyYAML, `_load_lineage()` catches the ImportError, and the hook falls
# back to comparing owner strings exactly -- which is the defect this file was
# changed to remove. It degrades to a warning on stderr, so nothing fails and
# nothing reports failure.
#
# It is invisible on a developer box: the per-user site-packages directory is on
# sys.path for EVERY interpreter, so PyYAML looks universally present locally
# and is absent on a clean node. Reproduce the clean condition with
# `PYTHONNOUSERSITE=1 uv run --no-project ...`.
"""claim-collision-pre.py -- PreToolUse (Write/Edit/Bash matcher) governance hook.

Enforces the Village Rule: "one owner per branch at a time."

KEYED ON THE LANE, NOT THE CLAIMANT. The first cut keyed on the backticked
owner-ID, which inverted the rule it was written to enforce -- reproduced both
ways on 2026-08-25:

  * different owner, SAME branch -> 0 collisions. Two agents could claim one
    branch and the gate stayed silent. That is the exact event the register
    exists to prevent.
  * same owner, DIFFERENT branch -> 1 collision. A node running several lanes
    at once (the normal case here) was blocked from claiming unrelated work.

So it missed the hazard and blocked the routine case. Now a collision means
another owner already holds an open claim naming the same branch.

THREE-WAY VERDICT. A lane two nodes have DECLARED they share is not the event
this hook exists to catch. `co-owners:` on a row is that declaration, and the
gate reads it from BOTH sides:

  * neither row declares the other      -> block (exit 2)
  * the INCUMBENT declares the claimant -> allow, and say so on stderr
  * only the claimant declares          -> ask; attribution is not a handoff

A CLAIM THAT NAMES NO LANE IS REFUSED. The lane is extracted from freeform
scope prose, so the check only works when the claim names its branch. A claim
that names none cannot be compared against anything -- 78 rows in the live
register are in that state and none of them is enforceable. This used to warn
and exit 0, which left the raw shell write MORE permissive than
`register_append.py`, the tool every refusal message points at. Could not
measure is not a pass, here as everywhere else in this repo.

THE BASH PATH BLOCKS, AND IT ANSWERS THE SAME QUESTION THE WRITE PATH DOES.
It used to be advisory. Measured 2026-09-02, identical content against a
genuinely held lane: Write exited 2 and blocked; Bash exited 0 with
`permissionDecision: "ask"` -- and an "ask" is resolved by a permission
classifier reading the shell COMMAND, not the lane, to which `cat >> REG <<EOF`
looks entirely benign. Delivery agents in five consecutive sessions had NO Write
or Edit tool ("Write is disabled for this session, in subagents as well as
here"), so the advisory path was the only path they had, and every register
write in those sessions was unchecked.

WHY THE SHELL PATH IS AN ALLOWLIST NOW. The first fail-closed cut enumerated
the ways a command could WRITE the register -- redirects, `tee`, `sed -i`,
`cp|mv|install|rsync|truncate|dd`, and python inside a heredoc -- and shipped
with a 22-case matrix in which every one of those refused. An independent
reviewer then measured six shapes the enumeration never considered, all exit 0:

    python3 -c "open(REG,'a').write(ROW)"
    python3 -c "open(REG,'w').write('nuked')"      <- TRUNCATES an append-only ledger
    python3 -c 'import pathlib;pathlib.Path(REG).write_text("x")'
    node -e "require('fs').appendFileSync(REG, ROW)"
    ruby -e 'File.write(REG, ROW, mode:"a")'
    printf 'a\n<row>\n.\nw\n' | ed -s REG

Two more were found reproducing that report: deleting the register outright, and
`git checkout --ours -- REG`, which silently drops another node's provenance row
and is the exact hazard `.gitattributes` names. `bash -c`, `sh -c` and `perl -e`
WERE refused, which made the survivors look arbitrary rather than scoped -- the
tell that the question itself was wrong.

A denylist can only ever refuse the shapes its author thought of, and this file
exists because "observed passing" is not evidence. So the question changed:
every segment of a command that NAMES the register must be positively understood
as a READ, or it is could-not-measure and is refused. What is allowed is
enumerated (`_READ_ONLY_COMMANDS`, `_GIT_READ_SUBCOMMANDS`, the copy-verb
directionality rule, and the sanctioned tools); everything else -- every
interpreter, every future utility nobody has thought of -- falls to the deny.

WHAT THAT COSTS, STATED. An inline interpreter may no longer NAME the register,
even to read it: `python3 -c "print(open(REG).read())"` is refused, because
distinguishing that from `open(REG,'a')` means enumerating writes again. The
escape hatch is to feed the register in rather than name it --
`cat REG | python3 -c ...` -- which the refusal message says. Reads through
`cat`, `grep`, `sed -n`, `head`, `tail`, `wc`, `git show` and friends are
untouched; a prompt on every `grep` is how a gate gets switched off.

THE DENY IS ONLY DEFENSIBLE BECAUSE A SANCTIONED PATH EXISTS. Refusing shell
writes while agents have no Write tool would deadlock the fleet: nobody could
file a claim at all, which is strictly worse than the gap being closed. Every
refusal below names `make -C pmoves register-claim`, which appends through
validated code -- clock-read timestamp, collision check, O_APPEND -- and
`register-amend`, which is how an incumbent adds `co-owners:` to their own open
row without an in-place shell edit.

Owner-ID format in the register (per existing entries):
  `<ISO_TIMESTAMP>` CLAIM `<OWNER-ID>` scope: ...
  `<ISO_TIMESTAMP>` RELEASE `<OWNER-ID>` scope: ...

Exit codes:
  0  allow  (possibly with `permissionDecision: "ask"` on stdout)
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
#
# THE LOOKBEHIND IS LOAD-BEARING. With `:` optional and `\s*` permissive, the
# word "branch" INSIDE a code span -- "BRANCH_MARKER_RE keys on the word
# `branch`, so neither can fire..." -- matched, then captured everything up to
# the next backtick as a lane. Two CLAIM rows in the live register hold a
# phantom lane made of prose that way, and in an append-only file a phantom lane
# stays open forever: it is a lane nobody is working that blocks whoever tries.
# `(?<!`)` says a marker that is itself the tail of a code span is a MENTION.
BRANCH_MARKER_RE = re.compile(
    r'(?<!`)\bbranch\b[:=]?\s*`([^`]+)`',
    re.IGNORECASE,
)


def lanes_in(text: str) -> set:
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


def co_owners_in(text: str) -> set:
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


def _row_at(text: str, pos: int) -> str:
    """The single register row containing `pos`.

    A register entry is one line, and open_claims_in() has always read the
    EXISTING side that way. The PROPOSED side did not: co_owners_in() ran once
    over the whole edit and its result was attached to every CLAIM match in it,
    so one honest declaration on row 1 granted participation to every other row
    in the same write. Deleting the field from an unrelated row flipped a
    squatting row from ALLOW to BLOCK -- the field was being read from outside
    its own row's scope.

    The same un-scoped read survived one merge inside `evaluate_claims()`, where
    `lanes_in(proposed)` charged EVERY claimant in a multi-row payload with EVERY
    lane in it: an innocent row filed alongside a colliding one was reported as
    colliding, twice. It errs closed, which is why it is not a P1, but it makes
    the gate and the register disagree about who is on a lane -- worse than
    either being wrong alone, because the register looks correct while the gate
    acts on something else.

    `split`-on-newline semantics, for the reason open_claims_in() documents at
    length: the register carries vertical tabs and form feeds that
    `splitlines()` breaks on and no editor, grep or sed counts as a line.
    """
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:] if end == -1 else text[start:end]


def open_claims_in(text: str) -> dict:
    """Map canonical owner -> LIST of (line, lanes, as-written, participants).

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

    `split("\\n")`, NOT `splitlines()`: the latter also breaks on vertical tab
    (U+000B), form feed (U+000C), NEL, and U+2028/9, none of which grep, sed, or
    an editor counts as a line. The register carries 7 such characters today (2
    VT, 5 FF), so `splitlines()` reported a claim on line 2005 that every other
    tool puts on 1998. The drift is cumulative, so it grows down the file and
    hits exactly the newest entries -- the ones a collision message points at.
    A line number that does not resolve sends the reader hunting, and this hook
    only speaks when it is blocking someone.
    """
    open_claims = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        m = CLAIM_RE.search(line)
        if m:
            owner_key = canonical_owner(m.group(1))
            # PARTICIPANTS = the signing owner PLUS everyone the row declares as
            # a co-owner. This is the whole point of the field: a lane worked by
            # four bodies now says so, instead of naming one and losing three.
            participants = {owner_key} | co_owners_in(line)
            open_claims.setdefault(owner_key, []).append(
                (lineno, lanes_in(line), m.group(1), participants)
            )
            continue
        m = RELEASE_RE.search(line)
        if m:
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


# --------------------------------------------------------------------------
# RECOVERING WHAT A SHELL COMMAND WILL WRITE
#
# This module's original docstring said recovering "what will this write" from
# arbitrary shell "is not something to attempt in a PreToolUse hook". That is
# right about ARBITRARY shell and wrong about the common case, and the common
# case is the one every agent here actually uses: a heredoc body IS in the
# command string the hook already receives. `cat >> REG <<EOF ... EOF` carries
# its content in the payload. So the content is recoverable, the same collision
# check the Write path runs can run on it, and the shell-shaped hole closes.
#
# Everything else is could-not-measure. Per this repo's exit-code doctrine
# (0 clean / 1 findings / 3 could not measure -- NOT a pass, see
# docker_host_policy_check.py and mcp_toolkit_preflight.py) could-not-measure is
# not a pass, so it is denied with a message naming the sanctioned path rather
# than waved through as "ask".
#
# "Everything else" is now the DEFAULT, not a list. See the module docstring:
# the enumerate-the-writes cut passed a 22-case matrix and was bypassed by
# `python3 -c`. What follows enumerates the reads.
# --------------------------------------------------------------------------

HEREDOC_DELIM_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# `(>>?)` captured, because append and truncate are different acts against an
# append-only ledger and the gate has to be able to tell them apart.
# QUOTED FIRST, because the unquoted alternative stops at whitespace and a
# quoted path is the normal way to write one that contains a space. Without the
# quoted alternatives, `echo x > "C:\Users\Jane Doe\...\AGNOTE4482PHI.t1.md"`
# handed `"C:\Users\Jane` to `_is_register`, which is not the register, so
# `_segment_verdict` certified `echo` as read-only and the hook exited 0.
#
# This is redirect-specific and NOT spelling-specific: `tee` and `cp` route
# through `_tokens`, where shlex already understands quoting, and they refused
# the same paths correctly. Measured with a `Jane Doe` directory -- `>` after
# echo/printf/cat passed silently in BOTH "\" and "/" spellings, so it is a
# pre-existing hole in redirect parsing rather than part of the path-spelling
# defect this file's other fix addresses. `_is_register` strips the quotes it
# now receives.
REDIRECT_RE = re.compile(r"(>>?)\s*((?:\"[^\"]*\"|'[^']*'|\\.|[^\s;|&<>])+)")
# `\` followed by a line ending. Bash removes these before parsing, so the
# guard has to as well -- see the comment at the top of classify_shell_write.
CONTINUATION_RE = re.compile(r"\\\r?\n")
TEE_RE = re.compile(r"\btee\b((?:\s+-\S+)*)((?:\s+[^\s;|&<>]+)*)")
ECHO_LITERAL_RE = re.compile(
    r"\b(?:echo|printf)\b(?:\s+-\S+)*\s+(['\"])(.*?)\1", re.S
)
# Python WRITES, kept apart from python reads -- used ONLY to give a sharper
# refusal message, never to decide one. `open(p)` alone is ambiguous and a lone
# `open\s*\(` refused `print(open(REG).read())`, a read.
PY_WRITE_RE = re.compile(
    r"\.write\s*\(|\bwrite_text\s*\(|\bwriteFile|\bappendFile|"
    r"\bopen\s*\([^)]*['\"][aw]"
)
INTERPRETER_RE = re.compile(
    r"\b(?:python3?|perl|ruby|node|deno|bash|sh|zsh|awk|gawk|mawk|php|"
    r"lua|tclsh|Rscript|pwsh|powershell|osascript)\b"
)
# An unexpanded `$VAR`, `${...}`, `$(...)` or backtick means the text this hook
# can SEE is not the text that will be WRITTEN.
EXPANSION_RE = re.compile(r"[$`]")
ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)

SANCTIONED_PATH = (
    "make -C pmoves register-claim  (or register-release / register-amend)  -- "
    "see AGNOTE4482PHI.t1.md " + chr(167) + " Filing a row"
)

# ---- WHAT IS DELIBERATELY ALLOWED --------------------------------------------
#
# Every entry here is a command this hook asserts CANNOT modify the register in
# the form it is allowed in. Anything absent is refused, including things that
# are obviously harmless -- that asymmetry is the point. Adding a name here is a
# decision with a reason; forgetting to add one costs a refusal that says how to
# proceed, where forgetting to add a DENY costs an unchecked write to an
# append-only ledger.
_READ_ONLY_COMMANDS = frozenset({
    # read a file out
    "cat", "bat", "tac", "nl", "head", "tail", "rev", "less", "more",
    # search
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "pcregrep", "look",
    # count / slice / reshape a stream
    "wc", "cut", "tr", "sort", "uniq", "column", "fold", "join", "paste",
    "comm", "expand", "unexpand", "shuf", "split", "csplit",
    # compare
    "diff", "cmp", "diff3",
    # digest
    "md5sum", "sha1sum", "sha256sum", "sha512sum", "shasum", "cksum", "b2sum",
    # metadata
    "ls", "stat", "file", "du", "df", "realpath", "readlink", "basename",
    "dirname", "test", "[", "[[",
    # emit text (a redirect ONTO the register is caught before this point)
    "echo", "printf", "true", "false", ":",
    # binary views
    "xxd", "od", "strings", "hexdump",
    # structured readers -- guarded below for their in-place flags
    "jq", "yq",
})
# `sed` and `find` read by default and write with one flag; `git` is a whole
# command language. Each gets a guard rather than a blanket entry.
_SED_WRITES_RE = re.compile(
    r"(^|\s)-[a-zA-Z]*i\b|(^|\s)--in-place\b|[;{\s'\"][wW]\s+\S"
)
_FIND_WRITES_RE = re.compile(r"-(?:delete|exec|execdir|ok|okdir|fls|fprint\w*)\b")
_INPLACE_FLAG_RE = re.compile(r"(^|\s)(-i\b|--in-place\b)")
# Commands that READ by default but take an output FILE. They sat on
# `_READ_ONLY_COMMANDS` and were reachable at exit 0 with the register as the
# destination: `sort -o <register>` and `shuf -o <register>` TRUNCATE the
# append-only ledger, and `xxd -r dump <register>` rewrites it. The
# enumerate-the-reads cut fixed the interpreter class and then re-made the same
# mistake one layer in -- "usually a read" is not "certified not to write".
# Guarded the way `sed -i` and `jq -i` are: the flag present at all is
# could-not-measure, and could-not-measure is not a pass.
_OUTPUT_FLAG_RE = re.compile(r"(^|\s)(-o\b|--output(=|\s|$))")
_XXD_REVERSE_RE = re.compile(r"(^|\s)(-r\b|-revert\b)")
_OUTPUT_FLAG_COMMANDS = {"sort": _OUTPUT_FLAG_RE, "shuf": _OUTPUT_FLAG_RE,
                         "xxd": _XXD_REVERSE_RE}
# `split` flags that consume the NEXT token, so it is a value and not an operand.
_SPLIT_VALUE_FLAGS = frozenset({
    "-l", "--lines", "-b", "--bytes", "-C", "--line-bytes", "-a",
    "--suffix-length", "-n", "--number", "--additional-suffix", "--filter",
})
# git subcommands that cannot alter a file in the working tree. `add` stages an
# already-written file and is on the list; `checkout`, `restore`, `switch`,
# `stash`, `apply`, `reset` and `clean` are NOT -- `git checkout --ours -- REG`
# resolves a register conflict by SILENTLY DROPPING the other node's provenance
# rows, which is the hazard `.gitattributes` names in this repo, and it exited 0
# under the enumerate-the-writes cut.
_GIT_READ_SUBCOMMANDS = frozenset({
    "show", "diff", "diff-tree", "diff-index", "log", "blame", "grep",
    "cat-file", "ls-files", "ls-tree", "rev-parse", "rev-list", "describe",
    "shortlog", "name-rev", "status", "add", "hash-object", "check-ignore",
    "check-attr", "annotate", "whatchanged",
})
_GIT_SKIP_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree",
                                  "--namespace", "--exec-path"})
# Copy-shaped verbs: safe when the register is the SOURCE, refused when it is
# the destination. `cp REG REG.bak` -- taking a backup before a risky fixup --
# was refused by the enumerate-the-writes cut while `git checkout --ours`
# passed, which is coverage exactly inverted for the merge-conflict case that
# actually happens here.
#
# `mv` is NOT in this set and stays refused in both directions, deliberately:
# moving the register out of its path destroys it at that path just as surely as
# overwriting it. That is a partial acceptance of the reviewer's P2-3 and the
# half not accepted is named here rather than quietly dropped.
_COPY_VERBS = frozenset({"cp", "rsync", "install", "ln"})
_ALWAYS_DESTRUCTIVE = frozenset({"truncate", "shred", "mv", "rename"})
# Wrappers that prefix another command without changing what it does.
_WRAPPERS = frozenset({"sudo", "doas", "env", "command", "builtin", "nohup",
                       "time", "nice", "ionice", "stdbuf", "exec", "timeout",
                       "setsid", "chrt"})
_PY_INTERPRETERS = re.compile(r"^(?:python3?(?:\.\d+)?|uv|uvx)$")
_SANCTIONED_TOOL = "register_append.py"
_SANCTIONED_MAKE_TARGET_RE = re.compile(r"^register-(claim|release|docs|amend)$")


def split_heredocs(command: str):
    """Split `command` into its shell SKELETON and its heredoc bodies.

    Separating the two is what makes every check below trustworthy. Analysed as
    one blob, a heredoc body's own contents are indistinguishable from shell
    code: a row of register PROSE that happens to contain the word `cp`, or a
    `>` inside a quoted scope, reads to a regex as a write verb and a redirect.

    That is not a theoretical concern in this repo. The damage-control hook
    matches literal strings anywhere in a command INCLUDING inside heredoc
    content, and an agent had its own report blocked for merely quoting a
    phrase -- it happened twice more during the review of this file. The first
    cut of THIS function reproduced the same bug one layer down: a
    `cat > /tmp/notes.md` heredoc explaining "use cp to back up the register"
    was refused as an unmeasurable register write.

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
    skeleton_lines = []
    bodies = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        skeleton_lines.append(line)
        idx += 1
        # Every heredoc opened ON THIS LINE takes its body starting now, in the
        # order the operators appear -- the shell's own rule for `cmd <<A <<B`.
        for m in HEREDOC_DELIM_RE.finditer(line):
            quote, delim = m.group(1), m.group(2)
            body = []
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


_NAIVE_SEGMENT_RE = re.compile(r"\n|;|&&|\|\||\||&")


def _segments(text: str):
    """Split on shell separators WITHOUT splitting inside quotes.

    Quote-awareness is not tidiness. A multi-line quoted argument --

        echo 'first line
        ...AGNOTE4482PHI.t1.md on the second...' > /tmp/notes.md

    -- split naively on `\\n` produces a second "segment" whose first word is
    the register's own filename. Under an allowlist that segment has no
    recognised command and is refused: the literal-match-inside-content bug that
    blocked an agent's report, reproduced a third time and this time by the very
    check meant to be careful about it. Tracking quote state removes the class
    rather than special-casing the symptom.

    AN UNTERMINATED QUOTE FALLS BACK to the naive split. That is the fail-closed
    direction: naive splitting produces MORE segments, so more of them face the
    allowlist, so the verdict can only get stricter -- whereas letting one
    unbalanced quote swallow the rest of the command would hide a real write
    inside an earlier, allowed segment.
    """
    segs, buf, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < len(text):
            buf.append(ch)
            buf.append(text[i + 1])
            i += 2
            continue
        if text[i:i + 2] in ("&&", "||"):
            segs.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in ";|&\n":
            segs.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if quote is not None:
        return [s for s in _NAIVE_SEGMENT_RE.split(text) if s.strip()]
    segs.append("".join(buf))
    return [s for s in segs if s.strip()]


def _tokens(segment: str):
    """Whitespace tokens with quotes stripped, robust to unbalanced quoting.

    `shlex` raises on an unbalanced quote and this must never raise; a guard
    that dies stops guarding.
    """
    try:
        import shlex
        return shlex.split(segment, comments=True)
    except ValueError:
        return [t.strip("'\"") for t in segment.split() if t.strip()]


def _is_register(token: str) -> bool:
    """True when `token` names the register FILE -- a path test, not a substring.

    The substring form refused `<REG>.bak`, `<REG>.orig`, `<REG>.rej` and
    `<REG>.BACKUP.123` / `.LOCAL.123` / `.REMOTE.123`. Those last four are git's
    own merge-conflict artifacts, so it fired precisely in the merge-conflict
    scenario -- the one where `merge=union` and a careful hand-fixup are the
    whole recovery story.
    """
    token = token.strip().strip("'\"")
    if not token:
        return False

    # Split on EITHER separator, not os.sep. `os.path.basename` is
    # platform-dependent: on Linux it does not treat "\" as a separator, so a
    # Windows-spelled path reaching a Linux runner would arrive as one long
    # basename and miss. The guard has to answer the same way wherever it runs.
    # Quotes are stripped EVERYWHERE, not just at the ends. A redirect word can
    # mix quoted and unquoted spans -- bash concatenates them into one word --
    # and both directions were wrong before this:
    #
    #   > /tmp/"Jane Doe"/AGNOTE4482PHI.t1.md   under-matched: the basename was
    #                                           never reached, so a real
    #                                           truncate passed as read-only
    #   > "/tmp/AGNOTE4482PHI.t1.md".bak        over-matched: the quoted span
    #                                           alone looked like the register,
    #                                           so a git merge artifact was
    #                                           refused -- exactly the case the
    #                                           neighbour rule exists to permit
    #
    # Removing the quote characters first makes the token the path bash would
    # actually open, and both cases then fall out of the ordinary basename test.
    token = token.replace('"', "").replace("'", "")

    base = re.split(r"[\\/]", token.rstrip("/\\"))[-1]
    if base == REGISTER_NAME:
        return True

    # THE POSIX TOKENIZER ATE THE SEPARATORS. `_tokens` calls
    # `shlex.split(..., posix=True)` -- correct for bash, and it treats "\" as
    # an ESCAPE. So a Windows-spelled path is not merely split wrong, it comes
    # back with its separators deleted:
    #
    #   C:\Users\me\Temp\t0\AGNOTE4482PHI.t1.md
    #     -> C:UsersmeTempt0AGNOTE4482PHI.t1.md
    #
    # There is no separator left for any basename test to find. Measured on
    # Z890 (win32) against this file's own suite: with the register named in
    # Windows spelling, `cp`, `dd of=`, `install`, `csplit -f`,
    # `csplit --prefix=` and `split` ALL passed silently, where the identical
    # commands spelled with "/" were refused. Six write vectors, decided by
    # which slash the operator happened to type.
    #
    # `endswith` is the right shape for a guard here: it OVER-matches (a file
    # genuinely named `notes-AGNOTE4482PHI.t1.md` would be refused) and
    # over-matching is the safe direction. It still leaves the neighbour cases
    # alone -- `<REG>.bak`, `.orig`, `.rej`, `.BACKUP.123` all END with their
    # own suffix, not with the register name, so git's merge artifacts are
    # untouched. That distinction is what the substring form got wrong and is
    # preserved here deliberately.
    return token.endswith(REGISTER_NAME)


def _assignments(skeleton: str) -> dict:
    """`VAR=value` set in THIS command, so `>> $VAR` can be resolved.

    Shell state does not survive between tool calls here, so a variable used as
    a redirect target is nearly always assigned in the same command. Resolving
    it turns an unmeasurable write into a measured one, which is strictly better
    than refusing it.
    """
    out = {}
    for seg in _segments(skeleton):
        for tok in _tokens(seg):
            m = ASSIGNMENT_RE.match(tok)
            if not m:
                break  # assignments only prefix a command
            out[m.group(1)] = m.group(2)
    return out


def _expand(target: str, assignments: dict) -> str:
    def sub(m):
        return assignments.get(m.group(1) or m.group(2), m.group(0))
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
                  sub, target)


def _tee_targets(segment: str):
    """(targets, appends) for any `tee` in `segment`."""
    targets = []
    appends = False
    for m in TEE_RE.finditer(segment):
        flags, rest = m.group(1) or "", m.group(2) or ""
        if re.search(r"-\w*a", flags):
            appends = True
        targets += rest.split()
    return targets, appends


def _register_redirects(segment: str, assignments: dict):
    """(appends_register, truncates_register) for one skeleton segment."""
    appends = truncates = False
    for op, target in REDIRECT_RE.findall(segment):
        if not _is_register(_expand(target, assignments)):
            continue
        if op == ">>":
            appends = True
        else:
            truncates = True
    tee_targets, tee_appends = _tee_targets(segment)
    if any(_is_register(_expand(t, assignments)) for t in tee_targets):
        if tee_appends:
            appends = True
        else:
            truncates = True
    return appends, truncates


def _strip_prefixes(tokens):
    """Drop leading `VAR=x` assignments and wrapper commands. Returns an index."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if ASSIGNMENT_RE.match(tok):
            i += 1
            continue
        if os.path.basename(tok) in _WRAPPERS:
            i += 1
            # A wrapper's own flags and simple operands (`timeout 5`, `nice -n 10`)
            while i < len(tokens) and (
                tokens[i].startswith("-")
                or ASSIGNMENT_RE.match(tokens[i])
                or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[smhd]?", tokens[i])
            ):
                i += 1
            continue
        break
    return i


def _git_verdict(rest):
    j = 0
    while j < len(rest):
        if rest[j] in _GIT_SKIP_WITH_VALUE:
            j += 2
            continue
        if rest[j].startswith("-"):
            j += 1
            continue
        break
    sub = rest[j] if j < len(rest) else ""
    if sub in _GIT_READ_SUBCOMMANDS:
        return True, ""
    return False, (
        "`git " + (sub or "<no subcommand>") + "` is not one of the git "
        "subcommands that provably leave a working-tree file alone. "
        "`git checkout --ours`/`--theirs` in particular RESOLVES a register "
        "conflict by silently dropping the other node's provenance rows -- the "
        "hazard .gitattributes names, which is why the register is `merge=union`."
    )


def _copy_verdict(cmd, rest):
    """Copy-shaped verbs: the register may be the SOURCE, never the destination."""
    if any(t == "-t" or t.startswith("--target-directory") for t in rest):
        return False, (
            "`" + cmd + " -t` names its destination as an option, so which file "
            "is written cannot be read positionally."
        )
    positionals = [t for t in rest if not t.startswith("-")]
    if len(positionals) < 2:
        return False, (
            "`" + cmd + "` here has no readable destination, so whether the "
            "register is written cannot be determined from the command."
        )
    if _is_register(positionals[-1]):
        return False, (
            "`" + cmd + "` writes the register as its DESTINATION, with content "
            "that is not in the command string."
        )
    return True, ""


def _dd_verdict(rest):
    outs = [t.split("=", 1)[1] for t in rest if t.startswith("of=")]
    if any(_is_register(o) for o in outs):
        return False, "`dd of=` writes the register with content this hook cannot see."
    return True, ""


def _output_flag_verdict(cmd, segment):
    """A read-by-default command carrying its own output-file flag."""
    if _OUTPUT_FLAG_COMMANDS[cmd].search(segment):
        return False, (
            "`" + cmd + "` here carries its output-file flag, so it can write "
            "the file it is pointed at rather than only read it. "
            "`sort -o <register>` and `shuf -o <register>` REPLACE the "
            "append-only ledger; `xxd -r` rewrites it from a dump."
        )
    return True, ""


def _split_verdict(cmd, rest):
    """`split`/`csplit` write files named from a PREFIX, never from stdin."""
    if cmd == "csplit":
        for j, tok in enumerate(rest):
            if tok in ("-f", "--prefix") and j + 1 < len(rest):
                if _is_register(rest[j + 1]):
                    return False, (
                        "`csplit -f <register>` names the register as its "
                        "output PREFIX, so it writes beside or onto it."
                    )
            if tok.startswith("--prefix=") and _is_register(tok.split("=", 1)[1]):
                return False, (
                    "`csplit --prefix=<register>` names the register as its "
                    "output PREFIX, so it writes beside or onto it."
                )
        return True, ""
    # `split [OPTION]... [FILE [PREFIX]]`. The PREFIX is the LAST operand and
    # only exists when there are two of them -- `split <register>` reads it.
    # Option VALUES are not operands: counting `-l 100` as one made a plain read
    # of the register look like a write, which is the false-refusal that gets a
    # gate switched off.
    operands = []
    j = 0
    while j < len(rest):
        tok = rest[j]
        if tok in _SPLIT_VALUE_FLAGS:
            j += 2
            continue
        if tok.startswith("-"):
            j += 1
            continue
        operands.append(tok)
        j += 1
    if len(operands) >= 2 and _is_register(operands[-1]):
        return False, (
            "`split` names the register as its output PREFIX, so it writes "
            "beside or onto it."
        )
    return True, ""


def _segment_verdict(segment, assignments):
    """(understood_as_not_writing_the_register, why_not).

    THE BURDEN OF PROOF SITS ON THE READ. Anything this function does not
    positively recognise returns False, and False is a refusal. The previous
    arrangement -- recognise the writes, allow the rest -- passed a 22-case
    matrix and was bypassed by `python3 -c`, `node -e`, `ruby -e`, `ed`, an
    outright delete, and `git checkout --ours`, every one of them exit 0.
    """
    tokens = _tokens(segment)
    i = _strip_prefixes(tokens)
    if i >= len(tokens):
        # Assignments alone, or an empty segment. Nothing is executed, so
        # nothing is written; a redirect hiding in here is caught separately by
        # the unresolved-target sweep.
        return True, ""

    # THE SANCTIONED TOOLS, named explicitly. They run the very check this hook
    # runs, so refusing them would leave the fleet with a gate and no door --
    # and a register row's own scope prose routinely names the register file.
    tail = tokens[i:]
    if any(t.endswith(_SANCTIONED_TOOL) for t in tail) and not any(
        t in ("-c", "-e", "-m", "--command") for t in tail
    ):
        return True, ""

    cmd = os.path.basename(tokens[i])
    rest = tokens[i + 1:]

    if cmd == "make":
        if any(_SANCTIONED_MAKE_TARGET_RE.match(t) for t in rest):
            return True, ""
        return False, (
            "`make` is only recognised here for the register-* targets, which "
            "append through validated code."
        )
    if cmd == "git":
        return _git_verdict(rest)
    if cmd in _ALWAYS_DESTRUCTIVE:
        return False, (
            "`" + cmd + "` destroys the register at its path. The ledger is "
            "append-only: every row is provenance, and a removal cannot be "
            "distinguished from a redaction after the fact."
        )
    if cmd in _COPY_VERBS:
        return _copy_verdict(cmd, rest)
    if cmd == "dd":
        return _dd_verdict(rest)
    if cmd == "sed":
        if _SED_WRITES_RE.search(segment):
            return False, (
                "`sed` here edits in place (or carries a `w` write command), so "
                "the resulting rows are not in the command string."
            )
        return True, ""
    if cmd == "find":
        if _FIND_WRITES_RE.search(segment):
            return False, (
                "`find` here carries an action that can modify or delete what "
                "it matches."
            )
        return True, ""
    if cmd in ("jq", "yq"):
        if _INPLACE_FLAG_RE.search(segment):
            return False, "`" + cmd + " -i` rewrites the file in place."
        return True, ""
    if cmd in _OUTPUT_FLAG_COMMANDS:
        return _output_flag_verdict(cmd, segment)
    if cmd in ("split", "csplit"):
        return _split_verdict(cmd, rest)
    if cmd in _READ_ONLY_COMMANDS:
        return True, ""

    if INTERPRETER_RE.search(cmd):
        return False, (
            "`" + cmd + "` is an interpreter and the register is named inside "
            "the code it runs, so what the code does to the file is not "
            "readable from the command string. `python3 -c \"open(REG,'a')\"`, "
            "`node -e`, `ruby -e` and `ed` all reached the ledger this way while "
            "the gate reported clean. To READ it from an interpreter, pipe it in "
            "instead of naming it: `cat <register> | " + cmd + " ...`."
        )
    return False, (
        "`" + cmd + "` is not a command this hook can certify as leaving the "
        "register alone, and could-not-measure is not a pass. What is allowed "
        "is enumerated deliberately -- the previous arrangement enumerated the "
        "WRITES and was bypassed by six shapes nobody had listed."
    )


class ShellWrite:
    """How a shell command writes the register, and what it will write.

    kind:
      "none"      -- the command does not write the register (it may read it)
      "append"    -- appends, and `text` is what will be appended
      "truncate"  -- rewrites the file wholesale
      "opaque"    -- may write it, and the content is NOT in the command string
    """

    def __init__(self, kind, text="", why=""):
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

    ORDER MATTERS, and it is: truncate, then every segment that does not resolve
    to an explicit register append must be a recognised READ, then interpreter
    heredoc bodies, then redirect targets that still cannot be resolved, then
    the recoverable append itself.
    """
    skeleton, bodies = split_heredocs(command)

    # BASH DELETES `\<newline>` BEFORE IT PARSES ANYTHING. So
    #
    #     echo x > pmoves/docs/AGENTS/AGNOTE4482PHI.t1.\
    #     md
    #
    # truncates the real register, while every check below looked at text where
    # the name is split across two lines: the literal-name gate three lines down
    # finds no contiguous `AGNOTE4482PHI.t1.md` and returns "none", and
    # `REDIRECT_RE`'s `\\.` cannot bridge it either because `.` does not match a
    # newline. Rejoining first means the rest of this function sees the same
    # command bash does.
    #
    # SKELETON ONLY, after `split_heredocs`. A heredoc body is literal text --
    # `\<newline>` inside a quoted delimiter is two real characters, not a
    # continuation -- so rejoining there would invent content. A continuation is
    # a shell-line construct and lives in the skeleton.
    #
    # Inside single quotes a `\<newline>` is also literal, so this
    # over-normalizes that one case. It is the safe direction for a guard: the
    # worst outcome is seeing a register name bash would not, which refuses a
    # write that was not going to happen. The reverse would miss a truncate.
    skeleton = CONTINUATION_RE.sub("", skeleton)

    executable = "\n".join(
        [skeleton] + [h["body"] for h in bodies if h["code"]]
    )
    if REGISTER_NAME not in executable:
        return ShellWrite("none")

    assignments = _assignments(skeleton)
    segs = _segments(skeleton)

    appends = []
    certified_reads = []
    for seg in segs:
        seg_appends, seg_truncates = _register_redirects(seg, assignments)
        if seg_truncates:
            return ShellWrite(
                "truncate",
                why="a single `>` (or a `tee` without `-a`) REPLACES the "
                    "register. It is append-only: every row is provenance, and "
                    "a rewrite cannot be distinguished from a redaction after "
                    "the fact.",
            )
        if seg_appends:
            # Positively understood: an explicit append whose content is
            # recovered and checked below. It does not need the allowlist.
            appends.append(seg)
            continue
        if REGISTER_NAME not in _expand(seg, assignments):
            # THE ALLOWLIST JUDGES SEGMENTS THAT NAME THE REGISTER, not every
            # segment of a command that mentions it somewhere. Judging all of
            # them broke the escape hatch this file's own refusal message
            # recommends: in `cat <register> | python3 -c ...` the interpreter
            # never names the file, which is exactly what makes it safe, and the
            # first cut refused it anyway. A segment that cannot see the
            # register can still write it through a variable -- that is what the
            # unresolved-redirect sweep below is for, and it still covers this
            # segment.
            continue
        ok, why = _segment_verdict(seg, assignments)
        if not ok:
            return ShellWrite("opaque", why=why)
        certified_reads.append(seg)

    for h in bodies:
        if not h["code"] or REGISTER_NAME not in h["body"]:
            continue
        if PY_WRITE_RE.search(h["body"]):
            return ShellWrite(
                "opaque",
                why="a `<<" + h["delim"] + "` heredoc opens the register for "
                    "writing in code, so any row it adds is computed at run "
                    "time and is not in the command string.",
            )
        return ShellWrite(
            "opaque",
            why="a `<<" + h["delim"] + "` heredoc names the register inside "
                "interpreter code. What that code does to the file is not "
                "readable from here. To read the register from an interpreter, "
                "pipe it in rather than naming it.",
        )

    # A redirect target that STILL will not resolve -- `cat >> $REG` where REG
    # is set outside this command -- is a write to somewhere unknown while the
    # register is named in the same breath. That is could-not-measure.
    #
    # Segments already certified as reads OF THE REGISTER are exempt:
    # `grep CLAIM <register> > "$OUT"` resolved every assignment in the command
    # and none of them named the register, so `$OUT` is some other file and
    # refusing it would be a false deny on an ordinary read.
    for seg in segs:
        if seg in certified_reads and REGISTER_NAME in seg:
            continue
        for _op, target in REDIRECT_RE.findall(seg):
            if EXPANSION_RE.search(_expand(target, assignments)):
                return ShellWrite(
                    "opaque",
                    why="the redirect target `" + target + "` is a shell "
                        "expansion this command does not set, so which file is "
                        "written cannot be determined.",
                )

    if not appends:
        return ShellWrite("none")

    # An append whose target is explicit. Recover the content -- but only text
    # that is genuinely LITERAL. `echo "$ROW" >> REG` recovers the string
    # `$ROW`, which contains no CLAIM and sailed through an earlier cut of this
    # function at exit 0: a fail-open produced by treating an unexpanded
    # variable as though it were the content. Anything carrying `$` or a
    # backtick is text this hook cannot see, which is could-not-measure.
    recovered = []
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


def _locate_register(payload: dict, command: str):
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


class ClaimVerdict:
    """Everything the gate concluded about one proposed payload.

    A NAMED OBJECT, not a tuple, and that is the point. This function used to
    return `(collisions, unkeyed)`; the three-way co-owner logic that landed on
    `main` needs four categories plus a `permissionDecision: "ask"`. Merging the
    two produced `ValueError: too many values to unpack (expected 3)` inside
    `register_append.py` -- the SANCTIONED path -- which meant the Bash path
    denied, the fleet had no Write tool, and the only remaining door crashed.
    A tuple return makes that failure silent until it is a deadlock; adding a
    field to an object cannot.
    """

    __slots__ = ("collisions", "shared", "one_sided", "unkeyed",
                 "unreadable_co_owners")

    def __init__(self):
        self.collisions = []   # nobody declared anything: block
        self.shared = []       # the INCUMBENT declared this claimant: allow, out loud
        self.one_sided = []    # only this row declared it: ask
        self.unkeyed = []      # no branch named: not checkable
        self.unreadable_co_owners = False

    def __bool__(self):
        return bool(self.collisions or self.shared or self.one_sided
                    or self.unkeyed or self.unreadable_co_owners)


def evaluate_claims(proposed: str, existing_open: dict) -> ClaimVerdict:
    """The three-way verdict for the CLAIM rows in `proposed`.

    THE ONE PLACE THE COLLISION VERDICT IS COMPUTED, for all three callers: the
    Write/Edit matcher, the Bash matcher, and `pmoves/tools/register_append.py`.
    It was previously inline in main(), reachable only from Write/Edit, while
    the Bash matcher ran a separate advisory that listed open lanes and never
    compared anything -- two paths into one register, one of which decided and
    one of which described, and the describing one was the only path an agent
    without a Write tool could use.

    Collision == ANOTHER owner already holds an open claim naming this lane and
    neither row declares the other. Same owner re-naming their own lane is not a
    collision: it is the node that already holds it.

    PER ROW, NOT PER PAYLOAD. Lanes and co-owners are read from the single row
    each CLAIM sits on. Reading lanes across the whole payload charged every
    claimant in a multi-row append with every lane in it -- an innocent row
    filed beside a colliding one was reported as colliding, twice. Reading
    co-owners across the whole payload was worse in kind: one honest declaration
    granted participation to every other row in the same write, so a squatting
    row could be waved through by its neighbour. `_row_at` is the fix for both,
    and it must not be undone by anything that "shares" this function again.

    The whole-payload read survives as a FALLBACK for LANES only, and only for a
    row that names no branch of its own: scoping without it would turn a claim
    whose branch sits on a neighbouring line from BLOCKED into "NOT CHECKED",
    a quiet downgrade. Co-owners get no fallback at all -- a declaration is the
    one thing that can SUPPRESS a collision, so inheriting one is the defect.
    """
    verdict = ClaimVerdict()
    payload_lanes = lanes_in(proposed)
    for m in CLAIM_RE.finditer(proposed):
        row = _row_at(proposed, m.start())
        owner = m.group(1)
        lanes = lanes_in(row) or payload_lanes
        declared = co_owners_in(row)
        if declares_unreadable_co_owners(row):
            verdict.unreadable_co_owners = True
        if not lanes:
            verdict.unkeyed.append(owner)
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
                    verdict.shared += [
                        (lane, other_as_written, lineno) for lane in overlap
                    ]
                    continue
                witnesses = sorted(mine & theirs)
                if witnesses:
                    # UNILATERAL. Something is shared -- this row says so, or
                    # both rows happen to name the same third party -- but the
                    # incumbent's row does not name this claimant back. That is
                    # attribution, not a handoff, and the difference is not
                    # decidable from inside a PreToolUse hook. Surface it.
                    verdict.one_sided += [
                        (owner, lane, other_as_written, lineno, witnesses)
                        for lane in overlap
                    ]
                    continue
                verdict.collisions += [
                    (lane, other_as_written, lineno) for lane in overlap
                ]
    return verdict


def _report_collisions(collisions) -> None:
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


def _report_shared(shared) -> None:
    """NOTHING SUPPRESSED LEAVES NO TRACE.

    A consented share is allowed without a prompt -- that workflow has to stay
    frictionless or nobody uses the field -- but it is still announced. An allow
    that prints nothing cannot be told apart from a gate that did not run, and
    that is precisely the state a reviewer found this hook in.
    """
    for lane, other, lineno in shared:
        sys.stderr.write(
            f"claim-collision-pre: SHARED LANE - `{lane}` is held by `{other}` "
            f"(open CLAIM at line {lineno}), whose own row declares this claimant "
            "as a co-owner. Allowing: the incumbent declared the sharing.\n"
        )


def _report_unkeyed(unkeyed) -> None:
    """Refuse a CLAIM that names no lane. Exits 2; it does not return.

    THIS USED TO WARN AND EXIT 0, and that made the gate the most permissive
    door in the system. Measured at 776b429b9, same unenforceable claim by
    three routes:

        EXIT=0  Bash, echo-redirect      "NOT CHECKED ... names no branch"
        EXIT=0  Bash, heredoc            "NOT CHECKED ... names no branch"
        EXIT=0  Write                    "NOT CHECKED ... names no branch"
        EXIT=3  make register-claim      "a CLAIM must name --branch"

    So the sanctioned path -- the one every refusal message points people to --
    was STRICTER than the raw shell write it replaces. An agent told to stop
    using heredocs would find the heredoc accepted a row the tool rejects,
    which teaches the opposite of what the deny is for.

    An unkeyed claim is not a small documentation problem. It is a claim the
    Village Rule cannot enforce: no lane, nothing to compare, so two nodes can
    hold one branch and this gate stays silent. 78 rows in the live register
    are already in that state. Could-not-measure is not a pass, and this file
    applies that to a truncating redirect already; a claim with no lane is the
    same verdict arriving through the content instead of the verb.

    BOTH MATCHERS, deliberately. Refusing on Bash alone would restore the
    defect this PR removed -- same register, same row, a different answer
    depending on which tool the agent happened to have.
    """
    if not unkeyed:
        return
    for owner in unkeyed:
        sys.stderr.write(
            f"claim-collision-pre: REFUSED - CLAIM by `{owner}` names no branch, "
            "so no lane could be compared and the claim is unenforceable. Add "
            "``branch: `<name>``` to the row.\n"
        )
    sys.stderr.write(
        "Could not measure is NOT a pass (0 clean / 1 findings / 3 could not "
        "measure).\n"
        f"Sanctioned path, which requires the lane: {SANCTIONED_PATH}\n"
    )
    sys.exit(2)


def _build_asks(verdict: ClaimVerdict):
    asks = []
    for owner, lane, other, lineno, witnesses in verdict.one_sided:
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
    if verdict.unreadable_co_owners:
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
    return asks


def _emit_ask(asks) -> None:
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


def _apply_verdict(verdict: ClaimVerdict) -> None:
    """Speak the verdict. Exits 2 on a collision; otherwise returns.

    BOTH MATCHERS CALL THIS. The shell path had no notion of "ask" at all, so a
    unilateral co-owner declaration filed through a heredoc -- the only way an
    agent with no Write tool can file anything -- would have been a silent
    exit 0 while the identical Write payload prompted. Same register, same row,
    different answer depending on which tool you happened to have.
    """
    _report_shared(verdict.shared)
    if verdict.collisions:
        _report_collisions(verdict.collisions)
        sys.exit(2)
    # BEFORE the ask, not after. A row this gate cannot check is refused on its
    # own account; putting a question to a human about some OTHER row first
    # would emit `permissionDecision: "ask"` on stdout and then exit 2 -- two
    # contradictory answers in one response.
    _report_unkeyed(verdict.unkeyed)
    asks = _build_asks(verdict)
    if asks:
        _emit_ask(asks)


def _gate_shell_write(payload: dict) -> None:
    """Gate a Bash command that writes the register. Exits 2 to refuse.

    THIS PATH USED TO BE ADVISORY. Measured on 2026-09-02 with identical
    content against a genuinely held lane: the Write path exited 2 and blocked;
    the Bash path exited 0 carrying `permissionDecision: "ask"`. The collision
    was never computed -- the advisory listed open lanes and handed the decision
    to a permission classifier that evaluates the shell COMMAND, and
    `cat >> REG <<EOF` looks entirely benign to one of those.

    That gap was load-bearing, not academic: delivery agents in five consecutive
    sessions had no Write or Edit tool at all ("Write is disabled for this
    session, in subagents as well as here"), so the advisory path was the ONLY
    path any of them could file through, and every register write they made was
    unchecked.

    WHY THIS IS SAFE TO CLOSE, and was not before: denying shell writes while
    agents have no Write tool would deadlock the fleet -- nobody could file a
    claim at all, which is strictly worse than the gap. The deny is only
    defensible because `make -C pmoves register-claim` (and `register-amend`,
    for adding co-owners to a row already filed) exists as a sanctioned path
    that appends through validated code, and every refusal below names it.
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
    # register, reporting the same message, and now including the same
    # three-way co-owner verdict and the same "ask".
    _apply_verdict(evaluate_claims(verdict.text, existing_open))


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

    _apply_verdict(evaluate_claims(proposed, open_claims_in(existing)))
    sys.exit(0)


if __name__ == "__main__":
    main()
