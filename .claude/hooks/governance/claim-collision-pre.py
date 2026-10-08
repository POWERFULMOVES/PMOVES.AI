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


# The RECORD KIND of a register row: the word immediately after the backticked
# leading timestamp on an anchored bullet. `CLAIM`, `RELEASE`, `CLAIM+RELEASE`,
# and a long informational tail -- NOTE, REVIEW, UPDATE, HANDOFF, CORRECTION.
_ROW_KIND_RE = re.compile(
    r'^\s*[-*]\s+`[0-9]{4}-[0-9]{2}-[0-9]{2}[^`]*`\s+([A-Za-z][A-Za-z+-]*)'
)

# KINDS THAT RECORD A FACT AND TRANSITION NOTHING.
#
# WHY THIS SET EXISTS. Until now the register had no record type meaning "here
# is a fact", so a correction had to be filed as a RELEASE -- the only kind the
# sanctioned write tool accepted that was not a CLAIM. Combined with the bare-
# RELEASE convention below (a RELEASE naming no lane closes EVERYTHING that
# owner holds), filing a footnote under an owner with open lanes would have
# closed every one of them silently. That did not happen only because the owner
# in question had no open lanes at that moment; a hazard whose harm depends on
# ordering is untriggered, not safe.
#
# So NOTE rows are parsed as INERT: whatever their prose says, they neither open
# nor close a lane. That matters beyond the new write path, because these rows
# discuss claims and releases for a living -- a note reading "the RELEASE `X` on
# line 42 was mis-attributed" carries the exact byte sequence RELEASE_RE looks
# for, and would otherwise close every lane `X` holds.
#
# MEASURED BEFORE AND AFTER against the live register: 5 NOTE rows, 0 of which
# were being read as a CLAIM or a RELEASE today, so this changes no lane's state
# now and removes the trap for every note filed from here on. Only NOTE is
# listed: REVIEW / UPDATE / HANDOFF / CORRECTION carry the same latent hazard,
# and widening the set is a separate change owing its own measurement.
INERT_ROW_KINDS = frozenset({"NOTE"})


def row_kind(line: str) -> str:
    """The record kind of a register row, upper-cased. Empty if not a row."""
    m = _ROW_KIND_RE.match(line)
    return m.group(1).upper() if m else ""


def is_inert_row(line: str) -> bool:
    """True when this row records a fact and must not transition lane state."""
    return row_kind(line) in INERT_ROW_KINDS


_UNSET = object()
_FOLDER = _UNSET
_LINEAGE = _UNSET
_NODES = _UNSET


def _import_tool(name: str):
    """Import `pmoves/tools/<name>.py`, keeping sys.modules honest.

    The module MUST be in sys.modules while it executes: identity_lineage and
    node_identity define @dataclass, and dataclasses._is_type resolves the
    owning module via sys.modules[cls.__module__]. Unregistered, that is None
    and the import dies with a bare AttributeError about __dict__.

    Two hygiene rules ride on that registration:
      - REUSE an entry that is already this exact file. identity_lineage
        imports node_identity under the same name; loading it twice built two
        module objects and left whichever ran last in sys.modules.
      - On a FAILED exec, restore what was there before (or remove the entry).
        Left in place, a half-built module is what the next `import` returns,
        and it fails somewhere unrelated with no trace of the real error.
    """
    import importlib.util
    path = Path(__file__).resolve().parents[3] / "pmoves" / "tools" / f"{name}.py"
    previous = sys.modules.get(name)
    if previous is not None:
        try:
            if Path(previous.__file__).resolve() == path:
                return previous
        except (AttributeError, TypeError, OSError):
            pass
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is not None:
            sys.modules[name] = previous
        else:
            sys.modules.pop(name, None)
        raise
    return module


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
        module = _import_tool("identity_lineage")
        module.load_vocabulary()  # fail here, not on the first fold
        _LINEAGE = module
    except Exception as exc:  # noqa: BLE001 -- a guard must not die here
        sys.stderr.write(
            f"claim-collision-pre: identity vocabulary unavailable ({exc}); "
            "comparing owner strings exactly, as before. Spelling drift "
            "will not be folded, and declared co-owners will not be read.\n"
        )
    return _LINEAGE


def _load_nodes():
    """Return (node_identity module, alias index), or None if unavailable.

    The node half of the owner key. node_identity.py is the ONE reader of
    node-vocabulary.yaml (canonical names, aliases, and which entries are not a
    machine at all), so the gate asks it rather than keeping a second list.

    WHAT IS LOST WHEN THIS RETURNS None: owners fold to identity alone -- the
    behaviour before the node half existed. Two sessions of one identity on
    two machines then share a key again; that is the pre-#3313 state, stated
    rather than hidden, and no worse than it was.
    """
    global _NODES
    if _NODES is not _UNSET:
        return _NODES
    _NODES = None
    try:
        module = _import_tool("node_identity")
        _NODES = (module, module.load_vocabulary())
    except Exception as exc:  # noqa: BLE001 -- a guard must not die here
        sys.stderr.write(
            f"claim-collision-pre: node vocabulary unavailable ({exc}); owner "
            "keys fold to identity only, so one identity's sessions on two "
            "nodes are not told apart.\n"
        )
    return _NODES


def _machine(nodes, raw):
    """Canonical name of `raw` if it names one declared MACHINE, else None.

    A class (`jetson`), placeholder (`any`, `cloud`) or runner label is a
    declared non-machine: it says where something MAY run, not where a session
    DID, so it never splits a key.
    """
    if raw is None:
        return None
    module, index = nodes
    entry = index.get(module._norm(raw))
    return entry.canonical if entry is not None and entry.is_machine else None


def _worn_off_home(lineage, vocab, owner: str, identity: str):
    """The node `owner` was signed on, when that is NOT its identity's home.

    None means "the home session" -- and is also every answer this cannot be
    sure of, because None is the previous behaviour:
      - no node named in the parenthetical (`(Opus 5)`) -> home, by default;
      - a non-node annotation (`(Knuckles, opus 4.7 1M)` names knuckles AND a
        model; the model is not a node) -> whatever node token is present;
      - an identity with no declared home (`claude-opus`, which "runs wherever
        it is launched") -> no home to be off, so its spellings keep folding;
      - the node vocabulary unreadable -> identity-only, as before.
    The parenthetical is parsed by identity_lineage.wearing(), the parser the
    ledger audit already uses; it resolves node aliases AND node_relations
    tokens (`Z890-mirror-on-5090` -> node 5090), so no regex lives here.
    """
    nodes = _load_nodes()
    if nodes is None:
        return None
    try:
        declared = vocab.index.get(lineage._norm(identity))
        home = _machine(nodes, declared.node if declared else None)
        if home is None:
            return None
        worn = _machine(nodes, lineage.wearing(owner, vocab).node)
    except Exception:  # noqa: BLE001 -- unparseable -> previous behaviour
        return None
    return worn if worn is not None and worn != home else None


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
    memo: dict = {}

    def _fold(owner: str) -> str:
        if owner in memo:
            return memo[owner]
        identity = module.canonical_identity(owner, vocab)
        if not identity:
            key = owner
        else:
            node = _worn_off_home(module, vocab, owner, identity)
            key = f"{identity} @ {node}" if node else identity
        memo[owner] = key
        return key

    _FOLDER = _fold
    return _FOLDER


def canonical_owner(owner: str) -> str:
    """Fold an owner string to its owner key: (canonical identity, node).

    WHY THE FOLD: this hook compared owner strings with `==`, and one identity
    writes several. B850 alone appears as `(Knuckles)` x16, `(Knuckles, opus
    4.7 1M)` x7, `(Opus 5)` x2, `(Claude Opus 5)` x1 -- so a RELEASE under one
    spelling did not close a CLAIM opened under another, and a lane stayed
    open for a week (2026-08-25). The same equality also makes an identity
    collide with ITSELF as soon as its parenthetical changes.

    WHY THE NODE (#3313): the fold went one step too far once an identity
    could be WORN off its home node. node_identity.resolve_register_name()
    signs such a session `<BASE> (<node>)` -- `B850-CLAUDE (spark)`, or a
    declared node_relations token, `Z890-CLAUDE (Z890-mirror-on-5090)` --
    precisely so two concurrent sessions of one identity on two machines do
    not share an owner string. Folding identity alone merged them anyway: a
    bare RELEASE on spark closed the lanes Knuckles still held, and a spark
    CLAIM on a Knuckles branch read as a self-reclaim. So the key carries the
    node too, and the node DEFAULTS TO HOME: every home spelling --
    `(Knuckles)`, `(Knuckles, opus 4.7 1M)`, `(Opus 5)`, the bare base --
    returns the bare canonical identity, exactly the key it returned before,
    so the 2026-08-25 fold is intact. Only a parenthetical naming a declared
    machine other than the home node yields a distinct key,
    `<identity> @ <node>`. See _worn_off_home() for every case that stays home.

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


# --------------------------------------------------------------------------
# WHO A RELEASE CLOSES -- per the accords
#
# The keystone docs govern this, and they say lanes are shared, not locked:
#
#   pmoves/docs/AGENTS/AGNOTE4482.md:1699: "This ledger is an awareness
#     surface, not a claim registry".
#   pmoves/docs/AGENTS/AGNOTE4482.md:1709-1713: "Shared lanes are the point.
#     Multiple idents may sign the same lane or scope"; "Rows are reversible
#     adsorptions ... nothing here is carved in stone." (Its "supersede your
#     own rows" is about your OWN rows; the authority to close a shared row
#     comes from "Shared lanes" plus KK:12, not from that phrase.)
#   pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md:12: "One branch, one active owner
#     at a time unless explicit overlay handoff is recorded". KK:13-16 says
#     what recorded means for a cross-agent transition: a Graphiti trail
#     entry, the claim/release update in the register, AND a PR comment.
#
# So a RELEASE closes the open rows of every PARTICIPANT of the lanes it names
# (participants = owner U declared co-owners, computed per CLAIM below):
#   * the signer's own rows (unchanged);
#   * rows whose `co-owners:` declare the signer -- the signer worked that
#     lane, and its release is a release of the shared lane;
#   * rows of a holder the release NAMES with `baton-from: <holder>` -- the
#     peer handoff when the holder is not running.
# Closing a row someone else opened is a reversible adsorption: the release
# row is the REGISTER part of the recorded handoff (who FILED it, under which
# identity, on whose behalf) -- the trail entry and PR comment KK:13-16 also
# asks for are not machine-checked here -- and the owner re-CLAIMing the lane
# supersedes it. Nothing
# here authenticates who typed a row -- a row proves only the identity it was
# filed under. register-status shows every such close as "released by X on
# behalf of Y" and whether Y has been heard from since; it shows, it does not
# block.
#
# Until this change, pairing stayed on the signing owner alone. That rule came
# in with the co-owners field (ad63bb8c5, #2858) as an uncited precaution and
# cites no accord; the accords above never required it.
#
# A BARE release (no lane) keeps its legacy meaning exactly: it closes every
# row the SIGNER owns, and nothing of anyone else's. A release that names no
# lane cannot say which shared lane it means.
#
# A PEER CLOSE IS HELD TO THE BATON PATH'S GUARDS. The legacy RELEASE reader
# matches `RELEASE <owner>` anywhere on a line and infers lanes from prose;
# that reading is kept EXACTLY for the signer's own rows (monotonicity). A
# close that reaches anyone else's row -- through `co-owners:` or
# `baton-from:` -- needs an actual RELEASE row head (column 0, outside any
# fence) signed by that identity, and only lanes DECLARED with `branch:`.
#
# WHO COUNTS AS THE CO-OWNER: identities are compared after the vocabulary
# fold (canonical_owner), the same fold that decides whose OWN rows a release
# closes. So a co-owner declaration matches every spelling in that fold: a row
# declaring `CRUSH-GLM52 (Knuckles)` can be closed by any identity folding to
# `crush` (identity_vocabulary.yaml merges CRUSH, CRUSH-GLM52 and
# CRUSH-SPARK (KIMI) as one signer). Exact-string matching was not chosen: it
# would make a co-owner stricter than an owner, and miss the parenthetical
# variants the fold exists for. To narrow it, split the vocabulary entry.
#
# FAIL-CLOSED, NEVER FAIL-BROAD, for `baton-from:` rows. A row that declares
# `baton-from:` and is malformed -- no holder in backticks, two holders, not a
# real ledger RELEASE row, no declared lane -- closes NOTHING. It is never read
# as an ordinary release: a lane-less ordinary RELEASE closes everything the
# signer holds, and "the baton was malformed, so close all of MY lanes" is the
# silent broadening this register has been bitten by. The refusal is recorded
# as a BatonEvent with its reason, so it is not silent.
# --------------------------------------------------------------------------

# The marker is detected WITHOUT the identity vocabulary, on purpose. If
# detection needed the vocabulary, a node without PyYAML would not see the
# marker at all and would read the row as an ordinary RELEASE by the signer --
# the exact fallback the paragraph above forbids.
BATON_MARKER_RE = re.compile(r'\bbaton[-_ ]from\b\s*:', re.IGNORECASE)
BATON_FROM_RE = re.compile(r'\bbaton[-_ ]from\b\s*:\s*`([^`]+)`', re.IGNORECASE)
# A DECLARED lane: `branch:` WITH its colon. BRANCH_MARKER_RE makes the colon
# optional because history wrote ``Branch `x` `` before the marker existed; a
# baton row is a new row type with no such history, and the bare word "branch"
# occurs in prose ("I am keeping branch `x`"). Same reasoning as the
# `co-owners:` marker (identity_lineage.py:114): the noun alone never declares.
DECLARED_LANE_RE = re.compile(r'(?<!`)\bbranch:\s*`([^`]+)`', re.IGNORECASE)
# A LEDGER ROW HEAD: bullet at column 0, timestamp, kind, owner. Indented
# bullets (a sub-bullet quoting an example inside another row) and anything in
# a ``` fence are prose ABOUT rows, not rows. Measured on origin/main: 753 heads
# at column 0, 2 indented, 36 fenced. Applied to baton rows only; the legacy
# CLAIM/RELEASE reading is unchanged.
_ROW_HEAD_RE = re.compile(
    r'^[-*]\s+`([0-9]{4}-[0-9]{2}-[0-9]{2}[^`]*)`\s+([A-Za-z][A-Za-z+-]*)\s+`([^`]+)`'
)
# Any row head, for "has this owner been heard from since" -- informational,
# so it reads the register as loosely as the legacy reader does.
_ANY_HEAD_RE = re.compile(
    r'^\s*[-*]\s+`[0-9]{4}-[0-9]{2}-[0-9]{2}[^`]*`\s+[A-Za-z][A-Za-z+-]*\s+`([^`]+)`'
)


class BatonEvent:
    """What one `baton-from:` RELEASE did, or why it did nothing.

    `closed` is the lanes actually closed on the holder's rows; `not_held` is
    the declared lanes the holder held no open row on (a no-op for those lanes,
    reported rather than swallowed). `problem` is set when the row was refused
    outright and closed nothing.
    """

    __slots__ = ("lineno", "signer", "holder", "holder_key", "lanes",
                 "closed", "not_held", "problem")

    def __init__(self, lineno, signer, holder=""):
        self.lineno = lineno
        self.signer = signer
        self.holder = holder
        self.holder_key = ""
        self.lanes = set()
        self.closed = set()
        self.not_held = set()
        self.problem = ""

    def as_dict(self) -> dict:
        return {"line": self.lineno, "signer": self.signer, "holder": self.holder,
                "lanes": sorted(self.lanes), "closed": sorted(self.closed),
                "not_held": sorted(self.not_held), "problem": self.problem,
                "warning": self.warning}

    @property
    def warning(self) -> str:
        """One line for a human, or "" when the baton did exactly what it said."""
        if self.problem:
            return (f"line {self.lineno}: baton RELEASE by `{self.signer}` "
                    f"closed NOTHING - {self.problem}")
        if self.not_held:
            lanes = ", ".join(f"`{x}`" for x in sorted(self.not_held))
            return (f"line {self.lineno}: baton RELEASE by `{self.signer}` names "
                    f"{lanes}, which `{self.holder}` holds no open row on - "
                    "no-op for that lane")
        return ""


class PeerClose:
    """One open row closed by a RELEASE filed under ANOTHER identity.

    `via` is "baton-from" (the release named the owner) or "co-owner" (the
    owner's row declared the signer). `heard_from` is True when the owner has
    filed any row after the release -- the owner is back, and has seen it.
    """

    __slots__ = ("release_line", "signer", "owner_key", "owner", "claim_line",
                 "lanes", "via", "heard_from")

    def __init__(self, release_line, signer, owner_key, owner, claim_line,
                 lanes, via):
        self.release_line = release_line
        self.signer = signer
        self.owner_key = owner_key
        self.owner = owner
        self.claim_line = claim_line
        self.lanes = set(lanes)
        self.via = via
        self.heard_from = False

    def as_dict(self) -> dict:
        return {"release_line": self.release_line, "released_by": self.signer,
                "owner": self.owner, "claim_line": self.claim_line,
                "lanes": sorted(self.lanes), "via": self.via,
                "owner_heard_from_since": self.heard_from}

    def __str__(self) -> str:
        lanes = ", ".join(f"`{x}`" for x in sorted(self.lanes))
        tail = ("" if self.heard_from
                else f" (`{self.owner}` not heard from since)")
        return (f"line {self.release_line}: {lanes} released by `{self.signer}` "
                f"on behalf of owner `{self.owner}` (CLAIM line "
                f"{self.claim_line}, via {self.via}){tail}")


def _outside_code_spans(text: str, regex):
    """Matches of `regex` whose START is not inside a Markdown code span.

    A row that QUOTES the grammar -- ``baton-from: `X` `` in a double-backtick
    example -- is a mention, not a declaration; this register describes its own
    fields constantly. Uses the identity module's run-length span matcher when
    it is available. Without it every match counts, which errs toward READING a
    baton -- and a malformed baton closes nothing, so that error is a no-op,
    never a broadening.
    """
    module = _load_lineage()
    spans = module._code_spans(text) if module is not None else []
    return [m for m in regex.finditer(text)
            if not any(a <= m.start() < b for a, b in spans)]


def baton_declared(line: str) -> bool:
    """True when a row declares a `baton-from:` field (not merely quotes one)."""
    return bool(_outside_code_spans(line, BATON_MARKER_RE))


def parse_baton(line: str):
    """(holder_as_written, problem) for a `baton-from:` row."""
    holders = {m.group(1).strip() for m in _outside_code_spans(line, BATON_FROM_RE)}
    holders.discard("")
    if len(holders) > 1:
        return "", ("names more than one `baton-from:` holder ("
                    + ", ".join(sorted(holders)) + ")")
    if not holders:
        return "", "declares `baton-from:` but names no holder in backticks"
    return holders.pop(), ""


def declared_lanes(line: str) -> set:
    """Lanes a `baton-from:` row DECLARES with `branch:` -- and nothing else.

    NOT lanes_in(). That also infers every backticked branch-shaped token in
    the prose, so a row reading "passing `feat/a`; I am KEEPING `fix/b`" would
    close `fix/b` too (found in review of #3242). The legacy RELEASE reading
    keeps lanes_in() for its history; a baton row is a new row type with none.
    Several lanes means several `branch:` markers on the row. The holder value
    is removed first so a branch-shaped holder string cannot become a lane.
    """
    line = BATON_FROM_RE.sub(" ", line)
    return {m.group(1).strip()
            for m in _outside_code_spans(line, DECLARED_LANE_RE)
            if m.group(1).strip()}


def real_row_heads(lines) -> list:
    """Per line: the _ROW_HEAD_RE match if it is a real ledger row, else None.

    Real = a head at column 0 and outside a ``` fence. One pass, so the cost is
    paid once per register read rather than once per baton.
    """
    heads, fenced = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            heads.append(None)
            continue
        heads.append(None if fenced else _ROW_HEAD_RE.match(line))
    return heads


def _close_participant_rows(open_claims, lineno, signer, signer_key, lanes,
                            holder_key, peer_closes, peer_lanes=None):
    """Close every open row on `lanes` that this release may close.

    A row is closed when it is the signer's own, when its participants include
    the signer (co-owners), or when its owner is the `baton-from:` holder.
    `lanes` applies to the signer's OWN rows; `peer_lanes` (default: `lanes`)
    to everyone else's, so the legacy reader can keep its own-row reading while
    a peer close is held to declared lanes on a real row head.
    Returns the lanes closed on the holder's rows (empty when no holder).
    """
    if peer_lanes is None:
        peer_lanes = lanes
    holder_closed = set()
    for owner_key in list(open_claims):
        kept = []
        for ln, row_lanes, raw, participants in open_claims[owner_key]:
            hit = row_lanes & (lanes if owner_key == signer_key else peer_lanes)
            if owner_key == signer_key:
                via = ""
            elif holder_key and owner_key == holder_key:
                via = "baton-from"
            elif signer_key in participants:
                via = "co-owner"
            else:
                hit = set()
            if hit:
                if owner_key == holder_key:
                    holder_closed |= hit
                if via:
                    peer_closes.append(PeerClose(lineno, signer, owner_key,
                                                 raw, ln, hit, via))
            rest = row_lanes - hit
            if owner_key == signer_key:
                # The signer's own rows exactly as before this change: a row
                # left with no lane is dropped -- INCLUDING an unkeyed claim
                # that named no lane at all, which any named release by its
                # owner has always closed.
                if rest:
                    kept.append((ln, rest, raw, participants))
            elif rest or not hit:
                kept.append((ln, rest if hit else row_lanes, raw, participants))
        if kept:
            open_claims[owner_key] = kept
        else:
            open_claims.pop(owner_key, None)
    return holder_closed


def _apply_baton(open_claims, lineno, line, heads, peer_closes):
    """A `baton-from:` RELEASE. Returns a BatonEvent; closes nothing if malformed."""
    head = heads[lineno - 1]
    signer = head.group(3) if head else (RELEASE_RE.search(line) or [None, ""])[1]
    holder, problem = parse_baton(line)
    event = BatonEvent(lineno, signer, holder=holder)
    event.lanes = declared_lanes(line)
    if head is None or head.group(2).upper() != "RELEASE":
        # A REVIEW row whose prose reads `RELEASE X ... baton-from:`, a headless
        # continuation line, a fenced or nested example: none is a release
        # filed by X.
        problem = ("is not a ledger RELEASE row (a baton must be its own "
                   "RELEASE row: bullet at column 0, timestamp, outside any "
                   "fence)")
    if not problem and not event.lanes:
        problem = ("declares no lane. A baton passes lanes NAMED with "
                   "`branch:`; there is no bare baton that closes everything "
                   "a peer holds")
    if problem:
        event.problem = problem
        return event
    event.holder_key = canonical_owner(holder)
    held = set().union(*(r[1] for r in open_claims.get(event.holder_key, [])))
    event.closed = _close_participant_rows(
        open_claims, lineno, signer, canonical_owner(signer), event.lanes,
        event.holder_key, peer_closes)
    event.not_held = event.lanes - held
    return event


def _mark_heard_from(lines, peer_closes) -> None:
    """Set PeerClose.heard_from: has the owner filed any row after the release?"""
    if not peer_closes:
        return
    last = {}
    for lineno, line in enumerate(lines, start=1):
        m = _ANY_HEAD_RE.match(line)
        if m:
            last[canonical_owner(m.group(1))] = lineno
    for pc in peer_closes:
        pc.heard_from = last.get(pc.owner_key, 0) > pc.release_line


def open_claims_in(text: str) -> dict:
    """Map canonical owner -> LIST of (line, lanes, as-written, participants).

    The open-lane part of `_pair_register()`, the register's ONE pairing
    implementation. `register_status`, `register_append` and this hook all read
    lane state through here, so there is no second pairing to drift from it.
    """
    return _pair_register(text)[0]


def baton_events_in(text: str) -> list:
    """Every `baton-from:` RELEASE in the register, as BatonEvents, in file order."""
    return _pair_register(text)[1]


def peer_closes_in(text: str) -> list:
    """Every open row a RELEASE closed on behalf of ANOTHER owner, in file order."""
    return _pair_register(text)[2]


def _pair_register(text: str):
    """(open claims, baton events, peer closes). THE pairing; every reader uses it.

    Open claims map canonical owner -> LIST of (line, lanes, as-written,
    participants). A LIST, not a single tuple. Keying one claim per owner
    silently forgot every lane but the newest: two open claims by one identity collapsed to
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
    batons = []
    peer_closes = []
    lines = text.split("\n")
    heads = None  # computed on the first RELEASE row; read-only after that
    for lineno, line in enumerate(lines, start=1):
        if is_inert_row(line):
            # A NOTE records a fact. It opens nothing and closes nothing, and
            # this skip is what makes that true of its PROSE as well as its
            # intent -- these rows quote `CLAIM` and `RELEASE` constantly.
            continue
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
        if m and baton_declared(line):
            # A `baton-from:` row closes the NAMED holder's rows on the
            # DECLARED lanes (plus every other participant row on them), and
            # a malformed one closes nothing -- never an ordinary release.
            if heads is None:
                heads = real_row_heads(lines)
            batons.append(_apply_baton(open_claims, lineno, line, heads,
                                       peer_closes))
            continue
        if m:
            # Pairing is on PARTICIPANTS of the named lane, per the accords
            # (AGNOTE4482.md:1709-1713 "Shared lanes are the point ... Rows
            # are reversible adsorptions"; KRISS_KROSS_ACCORD.md:12 "unless
            # explicit overlay handoff is recorded" -- the release row is the
            # register part of that record). It used to stay on the signing
            # owner alone, a rule introduced with the co-owners field
            # (ad63bb8c5, #2858) that cites no accord. See WHO A RELEASE
            # CLOSES above.
            owner = canonical_owner(m.group(1))
            released = lanes_in(line)
            # The PEER half is held to the baton path's guards: an actual
            # RELEASE row head (column 0, outside fences) signed by the
            # identity RELEASE_RE matched, and lanes DECLARED with `branch:`.
            # Without them a REVIEW row quoting `RELEASE <co-owner>`, an
            # indented example, or prose naming a lane the release is not
            # about would close another owner's row (delta review of #3242,
            # P2-1). The signer's OWN rows keep the legacy reading exactly.
            if heads is None:
                heads = real_row_heads(lines)
            head = heads[lineno - 1]
            peer_lanes = (declared_lanes(line)
                          if head is not None
                          and head.group(2).upper() == "RELEASE"
                          and canonical_owner(head.group(3)) == owner
                          else set())
            if not released:
                # A BARE release closes everything that owner holds. 99 of
                # the register's 120 RELEASE lines name no branch, so this
                # is the convention, not a guess -- a bare release is a
                # full handoff. It names no lane, so it reaches no one
                # else's shared row.
                open_claims.pop(owner, None)
            else:
                # A release that NAMES lanes closes those lanes on the
                # signer's own rows and on every row that declares the
                # signer a co-owner. Anything else stays held.
                _close_participant_rows(open_claims, lineno, m.group(1), owner,
                                        released, "", peer_closes, peer_lanes)
    _mark_heard_from(lines, peer_closes)
    return open_claims, batons, peer_closes


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

# EVERY PATH ABOVE IS A WRITE, and for a while that was the whole list. An
# agent that ran an interpreter to ask `open_claims_in()` WHETHER A LANE WAS
# FREE got refused and then handed three ways to write -- a refusal with no
# answer to the question actually asked, which is a dead end wearing a gate's
# clothes. The read is NOT loosened to fix that: a command line cannot be
# trusted to declare its own intent, which is the entire reason the allowlist
# enumerates what it positively recognises. The question is ANSWERED instead,
# and the answer is named in every refusal below beside the write path.
SANCTIONED_READ_PATH = (
    "make -C pmoves register-status  (add BRANCH=<lane> OWNER='<you>' to ask "
    "whether one lane is free) -- read-only; 0 clean / 1 findings / 3 could "
    "not measure"
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
# THE SANCTIONED TOOLS ARE FILES, NOT NAMES.
#
# These two names used to be a `str.endswith` tuple tested against EVERY token
# of the command, which made the FILENAME the credential: any argument ending
# in `register_status.py`, anywhere in argv, approved the whole segment before
# anything asked which program would actually run. Measured on the parent
# revision of this line:
#
#     python3 /tmp/register_status.py pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
#
# exited the hook at 0. That is an arbitrary script, chosen by the caller,
# handed the register as argv[1] with the gate's blessing -- it can truncate
# the ledger. #2879 made this path fail closed precisely because a shell hole
# let agents write the register unchecked; a trusted filename is the same hole
# wearing the door's clothes.
#
# So the allowance is keyed on the RESOLVED FILE. A token is the sanctioned
# tool only when it resolves to the same real path as this repository's copy --
# the repository being located from THIS FILE, which is the one path in the
# command's environment the caller does not choose. A symlink to the real tool
# passes, because it IS the real tool; a byte-identical copy outside the repo
# does not, because "same content today" is not "runs the gate's own code".
_SANCTIONED_TOOL_NAMES = ("register_append.py", "register_status.py")
_SANCTIONED_TOOL_DIR = REPO_ROOT_GUESS / "pmoves" / "tools"
_SANCTIONED_TOOL_REAL = frozenset(
    os.path.realpath(str(_SANCTIONED_TOOL_DIR / n)) for n in _SANCTIONED_TOOL_NAMES
)
_SANCTIONED_MAKE_DIR_REAL = os.path.realpath(str(REPO_ROOT_GUESS / "pmoves"))
# `sync` ADDED 2026-09-28, DELIBERATELY, operator-requested (fix/register-sync-road).
# It is the one sanctioned road that REMOVES lines -- and only lines the target
# ref already carries (byte-identical, or re-filed with a `first filed at <ts>`
# marker by the same owner on the same lane); every other line is kept
# byte-exact, and the tool refuses anything but a pure append over HEAD. Without
# it a `main` checkout holding uncommitted rows could never fast-forward: this
# hook refuses `git checkout`, interpreters and compound commands on the
# register, and every other register-* target only appends. The same `-C` /
# `-f` directory checks below apply to it unchanged.
_SANCTIONED_MAKE_TARGET_RE = re.compile(
    r"^register-(claim|release|note|docs|amend|status|sync)$")
# `-c`/`-e`/`-m`/`--command` anywhere alongside the tool means an interpreter
# was asked to run something OTHER than the file named, so the file named stops
# being evidence of what runs.
_INLINE_CODE_FLAGS = frozenset({"-c", "-e", "-m", "--command"})
# Interpreter flags that CONSUME the next token, so that token is a value and
# not the script operand. `uv run --with pyyaml <script>` is the shape the
# repo's own docs use, and counting `pyyaml` as the script would refuse it.
# A flag NOT listed here whose value looks like an operand fails to resolve and
# is refused -- the fail-closed direction.
_INTERPRETER_VALUE_FLAGS = frozenset({
    "-X", "-W", "--check-hash-based-pycs",                     # python
    "--with", "--with-requirements", "--with-editable",        # uv
    "--python", "-p", "--directory", "--project", "--index",
    "--index-url", "--extra-index-url", "--find-links",
    "--constraints", "--overrides", "--refresh-package",
})
_MAKE_DIR_FLAGS = frozenset({"-C", "--directory"})
_MAKE_FILE_FLAGS = frozenset({"-f", "--file", "--makefile"})


def _resolve_from_cwd(token: str, cwd):
    """Real path of `token` THE WAY THE SHELL WILL RESOLVE IT.

    Against the command's own cwd and nothing else. Falling back to the repo
    root when the cwd-relative path does not exist would re-open the hole this
    resolution exists to close, one indirection along: an agent standing in
    `/tmp/x` that writes its own `pmoves/tools/register_status.py` runs THAT
    file, while a hook resolving the same token against the repo would approve
    the repository's. The two must name the same file or the check is measuring
    a program that is not the one about to run.
    """
    token = token.strip().strip("'\"")
    if not token:
        return None
    try:
        base = Path(cwd) if cwd else Path.cwd()
        real = os.path.realpath(str(Path(token) if Path(token).is_absolute()
                                   else base / token))
    except OSError:
        return None
    return real if os.path.exists(real) else None


def _is_sanctioned_tool(token: str, cwd) -> bool:
    """True only for THIS repository's register tool, resolved on disk."""
    if os.path.basename(token.strip().strip("'\"")) not in _SANCTIONED_TOOL_NAMES:
        return False
    real = _resolve_from_cwd(token, cwd)
    return real is not None and real in _SANCTIONED_TOOL_REAL and os.path.isfile(real)


def _runs_sanctioned_tool(tail, cwd) -> bool:
    """True when `tail` runs the repository's register tool, in a shape whose
    argv is readable from the command string.

    Two shapes are recognised and no others:

        <repo>/pmoves/tools/register_status.py ...      (shebang, executed)
        python3|uv|uvx [interpreter flags] <that file> ...

    The interpreter must reach the tool as its SCRIPT operand. Anything else
    -- the tool's name as an argument to `rm`, to `cp`, to a second script, or
    to an interpreter that also carries `-c` -- is not this shape and falls
    through to the allowlist like any other command.
    """
    if not tail or any(t in _INLINE_CODE_FLAGS for t in tail):
        return False
    if _is_sanctioned_tool(tail[0], cwd):
        return True
    if not _PY_INTERPRETERS.match(os.path.basename(tail[0].strip().strip("'\""))):
        return False
    j = 1
    while j < len(tail):
        tok = tail[j]
        if tok in _INTERPRETER_VALUE_FLAGS:
            j += 2
            continue
        if tok.startswith("-"):
            j += 1
            continue
        # `uv run [python] <script>`: still interpreter machinery, not the
        # script operand.
        if tok == "run" or _PY_INTERPRETERS.match(os.path.basename(tok)):
            j += 1
            continue
        return _is_sanctioned_tool(tok, cwd)   # the FIRST operand decides
    return False


def _make_verdict(rest, cwd):
    """`make` is allowed only when it runs THIS repository's register targets.

    The target name alone was the test, which had the same defect the tool
    suffix had one layer up: `make -C /tmp/evil register-status ARGS=<register>`
    names a sanctioned target in an arbitrary Makefile. A target is only
    validated code if the Makefile defining it is the repo's.
    """
    if not any(_SANCTIONED_MAKE_TARGET_RE.match(t) for t in rest):
        return False, (
            "`make` is only recognised here for the register-* targets, which "
            "append through validated code."
        )
    if any(t in _MAKE_FILE_FLAGS or t.startswith("--file=")
           or t.startswith("--makefile=") for t in rest):
        return False, (
            "`make -f` chooses which makefile defines the target, so the "
            "register-* target name stops being evidence of what runs."
        )
    directory = None
    for j, tok in enumerate(rest):
        if tok in _MAKE_DIR_FLAGS and j + 1 < len(rest):
            directory = rest[j + 1]
        elif tok.startswith("--directory="):
            directory = tok.split("=", 1)[1]
    if directory is None:
        return False, (
            "`make` here must name the directory explicitly, as "
            + SANCTIONED_PATH.split("  ")[0] + " does. Without `-C` the target "
            "resolves against whatever directory the shell happens to be in, "
            "and which makefile defines `register-*` is then not readable from "
            "the command."
        )
    real = _resolve_from_cwd(directory, cwd)
    if real != _SANCTIONED_MAKE_DIR_REAL:
        return False, (
            "`make -C " + directory + "` is not this repository's `pmoves` "
            "directory, so the `register-*` target it runs is not the "
            "validated one."
        )
    return True, ""


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

        # REBUILD THE LOGICAL LINE FIRST. A `\<newline>` joins this line to the
        # next before the shell sees either, so
        #
        #     python3 \
        #     <<'PY'
        #
        # is ONE command line -- but read physically, the line carrying the
        # `<<` operator contains no interpreter, `code` comes out False, the
        # body is classified as data, and it is then excluded from the
        # detection string entirely. The body still reaches python and still
        # truncates the register.
        #
        # This has to happen HERE rather than in the caller: `code` is decided
        # from the opener inside this loop, so a caller that normalizes after
        # the split has already lost. Bodies are untouched -- the join only
        # runs while we are positioned on a skeleton line, which is precisely
        # the region where a continuation is a shell construct.
        while line.endswith("\\") and idx < len(lines):
            line = line[:-1] + lines[idx]
            skeleton_lines[-1] = line
            idx += 1

        # Every heredoc opened ON THIS LINE takes its body starting now, in the
        # order the operators appear -- the shell's own rule for `cmd <<A <<B`.
        for m in HEREDOC_DELIM_RE.finditer(line):
            quote, delim = m.group(1), m.group(2)
            body = []
            # FOLD CONTINUATIONS WHEN LOOKING FOR THE TERMINATOR, but only for
            # an UNQUOTED delimiter -- that is precisely where bash performs
            # expansion and line-joining while reading the body. With a quoted
            # delimiter the body is taken byte-for-byte and `EO\` + newline +
            # `F` is not a terminator, so folding there would end the heredoc
            # early and hand the rest of the body to the shell parser as code.
            #
            # Unfolded, this hides a whole COMMAND rather than a path:
            #
            #     cat >> REG <<EOF
            #     ...
            #     EO\
            #     F
            #     echo DESTROYED > REG
            #
            # bash rejoins `EOF`, closes the heredoc, and runs the truncate.
            # The hook saw the heredoc as unterminated, absorbed the truncate
            # as inert body data, and returned 0.
            term_lines = 1
            while idx < len(lines):
                cand = lines[idx]
                n = 1
                if not quote:
                    while cand.endswith("\\") and idx + n < len(lines):
                        cand = cand[:-1] + lines[idx + n]
                        n += 1
                if cand.strip() == delim:
                    term_lines = n
                    break
                body.append(lines[idx])
                idx += 1
            idx += term_lines  # consume the terminator, however many lines it spans
            bodies.append({
                "delim": delim,
                "body": "\n".join(body),
                "opener": line,
                "literal": bool(quote),
                "code": bool(INTERPRETER_RE.search(line)),
            })
    return "\n".join(skeleton_lines), bodies


_NAIVE_SEGMENT_RE = re.compile(r"\n|;|&&|\|\||\||&")


_MAX_SUBSTITUTION_DEPTH = 8


def _substitution_body(text: str, i: int):
    """Return (body, index_after) for the substitution starting at `i`, or (None, i).

    Handles `$( ... )` with nesting and `` ` ... ` `` without. Returns None when
    the construct is unterminated, so the caller keeps the character as literal
    text and the segment faces the allowlist unchanged -- an unbalanced `$(`
    must not swallow the rest of the command.
    """
    if text[i:i + 2] == "$(":
        depth, j = 1, i + 2
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if not depth:
                    return text[i + 2:j], j + 1
            j += 1
        return None, i
    if text[i] == "`":
        j = text.find("`", i + 1)
        if j == -1:
            return None, i
        return text[i + 1:j], j + 1
    return None, i


def _segments(text: str, depth: int = 0):
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

    A COMMAND SUBSTITUTION IS A COMMAND, and is emitted as its own segment.
    Without this, `$(` and `)` stayed glued to the adjacent tokens and BOTH
    directions of the verdict were wrong (measured 2026-09-15):

        N=$(env cp /tmp/x <register>)   -> ALLOWED
        env cp /tmp/x <register>        -> blocked, "cp writes the register as
                                           its DESTINATION"

      `N=$(env` matched ASSIGNMENT_RE on its `N=` prefix, so the whole token was
      consumed as an assignment and `env` was never seen by the wrapper-stripper.
      The destination then arrived as `<register>)` -- with the paren attached --
      so `_is_register` said no and the copy-verb guard never fired. Wrapping a
      blocked write in `$( )` plus one leading word turned BLOCK into ALLOW. The
      header above records six shapes that bypassed the previous design; this was
      a seventh, inside the allowlist.

        N=$(git show origin/main:<register>)  -> refused as "`show` is not a
                                                 command", though `show` IS in
                                                 _GIT_READ_SUBCOMMANDS

      Same fault: `git` was eaten with the `N=`, so the SUBCOMMAND was judged as
      if it were the command. `git diff` survived only by accident -- `diff` also
      exists as a top-level read-only command -- which made the documented
      read path work for the wrong reason.

    The body is segmented RECURSIVELY and the substitution is removed from the
    outer text, leaving a bare `N=` that names no command. Arithmetic `$((...))`
    is NOT a command substitution and is preserved verbatim.
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
        # Arithmetic expansion first: `$((` is not a command substitution, and
        # treating it as one would judge `1` or `+` as a command name.
        if text[i:i + 3] == "$((":
            close = text.find("))", i + 3)
            if close == -1:
                buf.append(ch)
                i += 1
                continue
            buf.append(text[i:close + 2])
            i = close + 2
            continue
        if text[i:i + 2] == "$(" or ch == "`":
            body, nxt = _substitution_body(text, i)
            if body is None:
                buf.append(ch)
                i += 1
                continue
            if depth < _MAX_SUBSTITUTION_DEPTH:
                segs.extend(_segments(body, depth + 1))
            else:
                # Refuse to stop looking. An over-nested substitution becomes one
                # unparseable segment, which the allowlist refuses -- rather than
                # silently vanishing from the text the way it used to.
                segs.append(body)
            i = nxt
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


def _segment_verdict(segment, assignments, cwd):
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

    # THE SANCTIONED TOOLS, identified by the FILE THEY RUN. They run the very
    # check this hook runs, so refusing them would leave the fleet with a gate
    # and no door -- and a register row's own scope prose routinely names the
    # register file. The allowance is not a name: see `_runs_sanctioned_tool`,
    # which resolves the script operand against this repository's own copy,
    # because keying it on the filename made the filename a password.
    tail = tokens[i:]
    if _runs_sanctioned_tool(tail, cwd):
        return True, ""

    cmd = os.path.basename(tokens[i])
    rest = tokens[i + 1:]

    if cmd == "make":
        return _make_verdict(rest, cwd)
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
            "the gate reported clean.\n"
            "  To ASK WHAT IS OPEN -- usually the actual question -- use "
            + SANCTIONED_READ_PATH + ".\n"
            "  To read the raw file from an interpreter anyway, pipe it in "
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


def classify_shell_write(command: str, cwd=None) -> ShellWrite:
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

    # CODE heredoc bodies too, and the reasoning above is why they are a
    # SEPARATE case rather than the same one. A body is literal to bash -- but
    # a body marked `code` is handed to an interpreter, and python, node and
    # ruby all fold `\<newline>` inside a string literal exactly as bash folds
    # it in a command. So
    #
    #     python3 <<'PY'
    #     open('/tmp/AGNOTE4482PHI.t1.\
    #     md', 'w').write('')
    #     PY
    #
    # opens the real register while the literal-name gate below sees no
    # contiguous name and returns "none". With an UNQUOTED delimiter bash
    # performs the join itself before the interpreter is even reached, so the
    # bypass does not depend on which interpreter it is.
    #
    # Normalizing the body is over-eager for the one case where the sequence is
    # genuinely two characters to the interpreter (a python raw string). Same
    # trade as the skeleton: over-matching refuses a write that was not going
    # to happen; under-matching misses one that was. Non-code bodies are left
    # alone -- they are data, nothing interprets them, and they are not part of
    # the detection string.
    for h in bodies:
        if h["code"]:
            h["body"] = CONTINUATION_RE.sub("", h["body"])

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
        ok, why = _segment_verdict(seg, assignments, cwd)
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
        if is_inert_row(row):
            # Symmetry with open_claims_in(). A NOTE in the PROPOSED write is
            # inert too, so a note whose prose quotes a CLAIM is not charged as
            # one. Without this the two sides disagree about what a row is,
            # which is worse than either being wrong alone.
            continue
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
    verdict = classify_shell_write(command, payload.get("cwd"))
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
            f"To WRITE, the sanctioned path does the check for you: "
            f"{SANCTIONED_PATH}\n"
            f"To READ, the sanctioned path answers without an interpreter: "
            f"{SANCTIONED_READ_PATH}\n"
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
