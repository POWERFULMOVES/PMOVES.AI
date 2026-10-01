#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml", "pydantic>=2"]
# ///
#
# DECLARED HERE TOO, not only in the hook. This tool imports
# `claim-collision-pre.py` to run the gate's own check, and that hook needs
# PyYAML to read `identity_vocabulary.yaml`. A PEP 723 block is honoured by the
# script `uv run --script` is pointed AT, so the hook's own block does nothing
# for an interpreter chosen by this file's caller. Without it the gate degrades
# to comparing owner strings exactly, one identity that spells itself several
# ways stops recognising its own open claims, and nothing fails.
"""Append a CLAIM, RELEASE or NOTE row to the AGNOTE4482 claim register, safely.

THE SANCTIONED WRITE PATH. It exists because the collision gate now REFUSES
shell writes it cannot check, and a refusal with no alternative is a deadlock,
not a gate.

That is not a hypothetical. Four delivery agents in one session had no Write
and no Edit tool -- "Write is disabled for this session, in subagents as well
as here" -- so a shell append was the only way any of them could file a row.
Denying that path without providing this one would have stopped the fleet from
claiming work at all, which is strictly worse than the unguarded path it
replaces. The deny and this tool are one change; neither is correct alone.

What this does that a heredoc cannot:

  * READS THE CLOCK. The timestamp is generated here, so it cannot be
    postdated. A sweep of the register found 41 of 404 rows (10.1%) asserting a
    time LATER than the commit that introduced them, the worst by 5h05m, and
    361 of 404 rows (89.4%) carry `:00` seconds -- hand-rounded, not read.
    Rounding explains 22 of the 41; it cannot explain the 11 over an hour. The
    register feeds TTL-lateness arithmetic, so a postdated row makes lateness
    wrong in the direction that flatters the filer.
  * CHECKS THE LANE, using the collision gate's own functions rather than a
    second implementation that would drift from it.
  * APPENDS IN O_APPEND, so the write cannot truncate or rewrite history even
    if two nodes file at once -- and takes an EXCLUSIVE LOCK across the whole
    read-check-append, because O_APPEND orders bytes and does not order
    decisions. Without the lock two filers both read a free lane and both
    append to it, and the tool built to enforce one owner per lane produces
    two (see `register_lock`).
  * EMITS THE ROW GRAMMAR CORRECTLY -- backticked timestamp, backticked owner,
    ``branch: `x` `` where the gate can actually see it. 78 of the register's
    historical claims name no branch at all and are unenforceable as a result.

Exit codes follow this repo's doctrine (see docker_host_policy_check.py):
  0  appended
  1  refused -- the lane is held by another owner, or the content was refused
     (absorbed-expansion symptoms in the prose; nothing was written, and the
     message names the override for deliberately-quoted literal assignments)
  3  could not measure -- refused, and NOT a pass
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import hashlib
import importlib.util
import json
import re
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

try:  # POSIX. Absent on this fleet's Windows nodes, which get the fallback below.
    import fcntl
except ImportError:  # pragma: no cover -- exercised on Windows, not here
    fcntl = None

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"

EXIT_OK, EXIT_REFUSED, EXIT_UNMEASURED = 0, 1, 3


def _load_gate():
    """Import the collision hook so this tool checks what the gate checks.

    Deliberately the hook itself and not a copy. A sanctioned path that
    implements its own idea of a collision is a second gate that will disagree
    with the first one, and the disagreement will be discovered by whoever gets
    blocked at an inconvenient moment.
    """
    spec = importlib.util.spec_from_file_location("claim_collision_pre", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["claim_collision_pre"] = module
    spec.loader.exec_module(module)
    # SAY IT ONCE, PLAINLY, AND NAME THE CONSEQUENCE. The hook's own message
    # for this is "identity vocabulary unavailable ... comparing owner strings
    # exactly, as before", which reads like a note about internals. What it
    # actually means on THIS road is that the caller's identity may not match
    # the spelling on their own open row, so a RELEASE can fail to close the
    # CLAIM it is closing and a re-CLAIM can be refused as another owner's.
    # Forced here rather than left lazy so the warning arrives before the
    # verdict it qualifies, not after.
    if module._load_lineage() is None:
        print("register-append: DEGRADED - the identity vocabulary could not be "
              "loaded (PyYAML missing from this interpreter?), so owner IDs are "
              "compared as exact strings. A RELEASE filed under a different "
              "spelling of your own ID will NOT close your CLAIM, and a re-CLAIM "
              "may be refused as another owner's lane. Run this through "
              "`make -C pmoves register-claim`, which picks an interpreter that "
              "has it.", file=sys.stderr)
    return module


def baton_refusal(gate, owner: str, baton_from: str) -> str:
    """Why a baton by `owner` passing `baton_from`'s lanes is refused, or "".

    The identity half of the baton check, through the gate's OWN resolver so
    the write road and every reader agree on who is a registered peer.
    """
    problem, holder_key = gate.baton_identity_problem(owner, baton_from)
    if problem:
        return problem
    if gate.canonical_owner(owner) == holder_key:
        return (f"`{owner}` and `{baton_from}` are the same identity. Closing your "
                "own lane is an ordinary release -- drop BATON_FROM/RULING.")
    return ""


def grant_refusal(gate, owner: str, baton_from: str, baton_to: str) -> str:
    """Why a grant NOTE by `owner` is refused, or "". Identity half only.

    A grant is useful only if the reader will honour it, so this refuses the
    grants the reader would reject anyway: one signed by neither the holder nor
    an operator identity, or naming an unregistered party.
    """
    problem, receiver_key = gate.baton_identity_problem(owner, baton_to)
    if problem:
        return problem.replace("holder", "receiver", 1)
    signer_key = gate.canonical_owner(owner)
    if baton_from:
        problem, holder_key = gate.baton_identity_problem(owner, baton_from)
        if problem:
            return problem
        if signer_key != holder_key and signer_key not in gate.BATON_OPERATOR_IDENTITIES:
            return (f"`{owner}` is neither the holder `{baton_from}` nor an "
                    "operator identity ("
                    + ", ".join(sorted(gate.BATON_OPERATOR_IDENTITIES))
                    + "), so no reader would honour this grant")
    else:
        holder_key = signer_key
    if holder_key == receiver_key:
        return "the receiver is the holder; there is no baton to pass"
    return ""


def _committed_register_text() -> str | None:
    """The register as origin/main has it, or None if git cannot say.

    NOT fetched: the caller's view of origin/main is what is checked, and the
    refusal message says so. A grant must be MERGED -- reviewed -- before it
    can authorise closing another peer's lane; a grant that exists only in a
    working tree or a feature branch is invisible to the fleet.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"origin/main:{REGISTER_REL}"],
            capture_output=True, text=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _ttl_delta(ttl: str) -> timedelta | None:
    ttl = (ttl or "").strip().lower()
    if not ttl or ttl in ("n/a", "none"):
        return None
    if ttl.endswith("h") and ttl[:-1].isdigit():
        return timedelta(hours=int(ttl[:-1]))
    if ttl.endswith("d") and ttl[:-1].isdigit():
        return timedelta(days=int(ttl[:-1]))
    raise ValueError(f"unparseable TTL {ttl!r} (use e.g. 72h, 7d, or n/a)")


# --- absorbed-expansion symptoms -------------------------------------------
#
# SYMPTOMS, NOT CAUSES. A guard inside this tool cannot catch the CAUSE of a
# shell or Make expansion, because the expansion happens BEFORE this tool is
# invoked: bash expands "${X}" inside a double-quoted SCOPE=, and make consumes
# a dollar of its own (a literal one needs doubling), so python only ever
# receives post-expansion text and never sees a dollar-brace to guard. Two
# register rows have already absorbed an expansion this way -- a make variable
# expanded into a full compose invocation with its whole env-file chain, and a
# shell parameter expansion swallowed to empty -- and the register is
# APPEND-ONLY, so both are uncorrectable. What a validator CAN do is detect
# the SYMPTOM in the text it is handed, and refuse before it is written.
#
# Thresholds calibrated against the live register (469 ledger rows at
# measurement time), not invented:
#   * longest legitimate single token in any row: 153 chars (a signature
#     string) -> LONG_TOKEN_LIMIT = 300 carries 2x margin;
#   * the empty-assignment pattern matches 3 occurrences in live rows, and all
#     three are rows deliberately QUOTING env/command text as evidence -- so
#     the refusal names --literal-assignments rather than dead-ending the one
#     legitimate use of the pattern;
#   * a compose invocation carrying >= 2 --env-file flags matches 0 live rows.
_EMPTY_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_`/])[A-Z][A-Z0-9_]*=(?=[\s$]|$|[,;)])")
_COMPOSE_INVOCATION_RE = re.compile(r"docker[\s+-]compose\b")
LONG_TOKEN_LIMIT = 300

# --- row shape ---------------------------------------------------------------
#
# STDLIB, AND UNCONDITIONAL. These were pydantic validators only, which meant
# the guarantee vanished wherever pydantic is absent -- and it IS absent in
# `validate-register-postdate.yml`, which installs `pytest pytest-asyncio
# pyyaml` and nothing else, as well as on any offline fleet node. A row could
# therefore be forged by exactly the environment least able to notice.
#
# So the rules live here and `build_row` always calls them. `RegisterRow` adds
# the typed surface on top and calls the same functions, so the two cannot
# disagree about what a row may contain.
ROW_KINDS = ("CLAIM", "RELEASE", "UPDATE")


def assert_no_control_characters(field: str, value: str) -> None:
    """A ledger row is ONE LINE of text.

    A newline in a field forges a second row -- every reader of this file
    parses by line, and a forged row is indistinguishable from a filed one.
    A NUL makes the whole file read as binary to grep and to GitHub, which is
    the corruption repaired in 8b040956e. TAB is allowed; it is whitespace.
    """
    bad = sorted({c for c in value if ord(c) < 0x20 and c != "\t"})
    if bad:
        raise ValueError(
            f"{field} contains control character(s) "
            + ", ".join(hex(ord(c)) for c in bad)
            + " -- a ledger row is one line of text. This is the signature of "
            "terminal output or a multi-line command captured into a field; "
            "re-file it as clean prose, or via --scope-file so it never joins "
            "a command string.")


def assert_row_shape(kind: str, owner: str, branch: str, ttl: str,
                     scope: str) -> None:
    """Everything about a row that no waiver may override.

    Prose symptoms are separate and DO have an override (see
    `assert_prose_clean`); shape does not. A control character or an
    unparseable TTL is damage under every flag.
    """
    # NOTE is INERT, not unparsed: the collision gate carries INERT_ROW_KINDS
    # = {"NOTE"} (claim-collision-pre.py:203), and register_status reads NOTE
    # rows without treating them as lanes. It is accepted here under the same
    # name so the sanctioned note path (append_note) cannot be refused by the
    # shape validator for being a kind the ledger deliberately supports.
    if kind not in ROW_KINDS and kind != "NOTE":
        raise ValueError(
            f"kind {kind!r} is not one of {', '.join(ROW_KINDS + ('NOTE',))}. Only those "
            "verbs are parsed by register_status, identity_lineage and the "
            "collision gate (NOTE as an inert, lane-free kind), so a row filed "
            "under any other one appends cleanly and is then invisible to every "
            "reader of the ledger.")
    for field, value in (("owner", owner), ("branch", branch),
                         ("ttl", ttl), ("scope", scope)):
        assert_no_control_characters(field, value)
    if not owner.strip():
        raise ValueError("owner is empty -- a row with no owner is unenforceable")
    for field, value in (("owner", owner), ("branch", branch)):
        if len(value) > LONG_TOKEN_LIMIT:
            raise ValueError(
                f"{field} is {len(value)} characters (limit {LONG_TOKEN_LIMIT};"
                " the longest legitimate token in the live register is 153)")
    _ttl_delta(ttl)  # raises on an unparseable TTL, before anything is rendered


# A grant reference: a ledger row timestamp, exactly as row heads write it.
# Mirrors BATON_REF_RE in the gate; the gate's reading is the one that counts,
# and _check_release_reading() reads every baton back through it.
_BATON_REF_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def assert_baton_shape(kind: str, branch: str, baton_from: str, ruling: str,
                       handoff: str, baton_to: str = "") -> None:
    """The shape of the two baton rows: the GRANT (a NOTE) and the BATON.

    GRANT  -- NOTE  ... branch: `<lane>` · [baton-from: `<holder>` ·]
              baton-to: `<receiver>`
    BATON  -- RELEASE ... branch: `<lane>` · baton-from: `<holder>` ·
              ruling|handoff: `<grant timestamp>`

    Shape only. Identities, and whether the cited grant really authorises the
    baton, need the vocabulary and the register; `baton_refusal()`,
    `grant_refusal()` and the gate's own reading check those. Every refusal
    here is a row that would otherwise have been written as something else: a
    `ruling:` with no `baton-from:` reads as an ordinary release by the
    signer, and free-text authority would let any identity close any lane.
    """
    for field, value in (("baton-from", baton_from), ("baton-to", baton_to),
                         ("ruling", ruling), ("handoff", handoff)):
        assert_no_control_characters(field, value)
        if "`" in value:
            raise ValueError(f"{field} may not contain a backtick -- it is "
                             "rendered inside one, and a stray backtick ends "
                             "the field early")
        if len(value) > LONG_TOKEN_LIMIT:
            raise ValueError(f"{field} is {len(value)} characters (limit "
                             f"{LONG_TOKEN_LIMIT})")
    authority = [(name, value.strip()) for name, value in
                 (("ruling", ruling), ("handoff", handoff)) if value.strip()]

    if kind == "NOTE":
        if authority:
            raise ValueError("--ruling/--handoff belong on the baton RELEASE, "
                             "not on the grant NOTE it cites")
        if baton_from.strip() and not baton_to.strip():
            raise ValueError("a grant NOTE must name the receiving identity: "
                             "--baton-to (BATON_TO=)")
        if baton_to.strip() and not branch.strip():
            raise ValueError("a grant NOTE must name the lane it passes: "
                             "--branch (BRANCH=)")
        return
    if baton_to.strip():
        raise ValueError(f"--baton-to belongs on the grant NOTE; a {kind} does "
                         "not grant anything")
    if not baton_from.strip():
        if authority:
            raise ValueError(
                f"--{authority[0][0]} given without --baton-from. Authority "
                "with no holder would be written as an ordinary RELEASE "
                "closing only the signer's own lanes -- name the holder whose "
                "lane is being passed (BATON_FROM=).")
        return
    if kind != "RELEASE":
        raise ValueError(f"--baton-from on a {kind} passes no lane. To pick a "
                         "lane UP, file the baton RELEASE first and then your "
                         "own CLAIM.")
    if not authority:
        raise ValueError(
            "a baton RELEASE needs its authority: --ruling <timestamp of an "
            "operator grant NOTE> or --handoff <timestamp of the holder's "
            "grant NOTE> (RULING= / HANDOFF=). Nothing was written.")
    if len(authority) > 1:
        raise ValueError("give ONE authority, --ruling or --handoff, not both")
    if not _BATON_REF_RE.match(authority[0][1]):
        raise ValueError(
            f"--{authority[0][0]} `{authority[0][1]}` is free text. Authority "
            "is a REFERENCE: the timestamp of a committed grant NOTE, as its "
            "row head writes it (e.g. 2026-10-01T12:00:00Z). Free text would "
            "let any identity close any lane by asserting it.")
    if not branch.strip():
        raise ValueError(
            "a baton RELEASE must name --branch. A baton passes NAMED lanes "
            "only; there is no bare baton that closes everything a peer "
            "holds.")


def expansion_symptoms(text: str) -> list[str]:
    """Every absorbed-expansion symptom found in `text`, as human strings.

    Pure and stdlib-only so enforcement never depends on an import that an
    offline interpreter may lack. `text` is scope prose or a docs block --
    free text a filer handed this tool AFTER whatever shell or make layer
    surrounded the invocation has already had its way with it.
    """
    symptoms: list[str] = []
    # ``double-backticked`` spans are a row quoting its OWN grammar; the
    # corpus strips them before branch matching for the same reason.
    scanned = _QUOTED_EXAMPLE_RE.sub(" ", text)
    for m in _EMPTY_ASSIGNMENT_RE.finditer(scanned):
        symptoms.append(
            f"empty assignment {m.group(0)!r} (uppercase name, `=`, then "
            "whitespace or end of field) -- the signature of a shell "
            "parameter expansion swallowed to empty")
    if (_COMPOSE_INVOCATION_RE.search(scanned)
            and scanned.count("--env-file") >= 2):
        symptoms.append(
            "a docker compose invocation carrying its whole --env-file chain "
            "-- the signature of a make variable expanded into a full command")
    for tok in scanned.split():
        if len(tok) > LONG_TOKEN_LIMIT:
            symptoms.append(
                f"a {len(tok)}-character single token (limit {LONG_TOKEN_LIMIT};"
                " the longest legitimate token in the live register is 153)")
    return symptoms


def assert_prose_clean(text: str, literal_assignments: bool = False) -> None:
    """Raise ValueError naming every symptom, unless explicitly overridden.

    `literal_assignments` is the escape hatch for the one legitimate use of
    the empty-assignment pattern: a row that QUOTES env or command text as
    evidence ("env.tier-ui had empty SUPABASE_ANON_KEY= entries" is a real
    row, and a bare refusal would be a dead end rather than a gate). The
    override is per-invocation and named in the refusal message, so a filer
    reaches it without reading source. It does NOT waive the compose-chain or
    long-token symptoms -- those have no legitimate quoted-literal use.
    """
    if RegisterProse is not None:
        try:
            RegisterProse(text=text, literal_assignments=literal_assignments)
        except Exception as exc:  # pydantic ValidationError subclasses ValueError
            raise ValueError(_first_refusal(exc)) from None
        return

    # Offline fallback. LOUD, because a second copy of the rules enforcing
    # silently is how two validators drift into disagreeing about what is
    # legal -- the failure this module already warns about for PyYAML.
    # THE REMEDY MUST NOT BE THE THING YOU JUST RAN. This used to say "run
    # this through `make -C pmoves register-claim`, which picks an interpreter
    # that has it" -- and register-claim expands the SAME $(REGISTER_PYTHON) as
    # register-release, whose probe tested `import yaml` and nothing else. So
    # the notice named itself as its own fix, every time, on both targets. A
    # degradation warning whose remedy is a no-op teaches people to skip
    # warnings, which costs more than the degradation it reports.
    print(f"register-append: DEGRADED - pydantic is not importable in "
          f"{sys.executable}, so prose is validated by the stdlib fallback "
          "rather than by the RegisterProse model. The two are pinned against "
          "the same fixtures, but only the model is the declared contract. "
          "Fix: install pydantic>=2 into that interpreter, or install `uv` -- "
          "the make targets prefer an interpreter carrying BOTH pyyaml and "
          "pydantic, and fall back to `uv run --script`, which reads the "
          "PEP 723 block at the top of this file and now declares both.",
          file=sys.stderr)
    symptoms = expansion_symptoms(text)
    if literal_assignments:
        symptoms = [s for s in symptoms if "empty assignment" not in s]
    if symptoms:
        raise ValueError(_expansion_refusal(symptoms))


def _expansion_refusal(symptoms: list[str]) -> str:
    """The refusal wording, in one place so both paths cannot drift apart.

    Shared WORDING, not shared verdicts: the model decides, this renders.
    """
    return (
        "the prose shows symptoms of an absorbed shell/Make expansion: "
        + "; ".join(symptoms)
        + ". The register is append-only, so a row that absorbs an expansion"
        " is UNCORRECTABLE -- refused now so it is re-filed properly. Expansion"
        " happens BEFORE this tool runs: single-quote SCOPE= at the make"
        " invocation (double quotes let the shell expand it first), or pass the"
        " prose via --scope-file / REGISTER_TEXT_FILE so it never becomes part"
        " of a command string. If these assignments are quoted LITERALLY as"
        " evidence, re-run with --literal-assignments.")


def _first_refusal(exc: Exception) -> str:
    """Unwrap pydantic's envelope back to the message a filer needs to read.

    A ValidationError renders as a multi-line report with a docs URL. That is
    right for a schema violation and wrong for this one, where the whole value
    of the refusal is the sentence telling the filer how to re-file.
    """
    errors = getattr(exc, "errors", None)
    if callable(errors):
        for err in errors():
            msg = str(err.get("msg", ""))
            # pydantic prefixes ValueError messages raised in validators.
            return msg.split("Value error, ", 1)[-1]
    return str(exc)


# THE TYPED SURFACE IS THE ENFORCEMENT, and it did not used to be.
#
# The first cut of this block wrapped `expansion_symptoms()` in a
# `@field_validator` and called the result "a pydantic layer". It validated
# nothing of its own: the model delegated to the stdlib function, so the test
# that pinned them together -- comparing `expansion_symptoms(text)` against
# `RegisterProse(text=text)` raising -- evaluated the SAME function on both
# sides and could never fail. A test that copies the logic cannot catch the
# logic breaking.
#
# The stated reason for stdlib-only enforcement does not hold either. It reads
# "the sanctioned path must run on the interpreter the Makefile picks for
# PyYAML alone, which offline may not carry pydantic" -- but
# `.github/requirements-tests.txt` installs BOTH `pydantic` and `pyyaml`, and
# that is the file the merge gate runs on. In the environment that decides
# whether this lands, pydantic is present.
#
# So the model owns the invariant and the CLI calls it. The stdlib path remains
# for a genuinely offline node, and degrades LOUDLY there rather than silently
# enforcing a second copy of the rules -- the same treatment `_load_lineage()`
# already gives a missing PyYAML a few lines up.
#
# What pydantic does NOT buy here, stated rather than papered over: no
# declarative constraint expresses "no whitespace-delimited token longer than
# N" or "no uppercase assignment followed by whitespace". Those stay validator
# bodies in any design. What the model does own is the field typing, the
# override as a real field rather than a positional flag, and one place where
# the invariant is declared.
try:
    from pydantic import (  # type: ignore[import-untyped]
        BaseModel, ConfigDict, StringConstraints, model_validator,
    )

    class RegisterProse(BaseModel):
        """Scope/docs prose carrying no absorbed-expansion symptom.

        `literal_assignments` is a field, not an argument, so the waiver
        travels with the value it applies to and shows up in the model dump
        that a caller logs. It waives ONLY the empty-assignment symptom -- the
        compose chain and the long token have no legitimate quoted use.
        """

        model_config = ConfigDict(extra="forbid")

        text: str
        literal_assignments: bool = False

        @model_validator(mode="after")
        def _no_absorbed_expansion(self) -> "RegisterProse":
            symptoms = expansion_symptoms(self.text)
            if self.literal_assignments:
                symptoms = [s for s in symptoms if "empty assignment" not in s]
            if symptoms:
                raise ValueError(_expansion_refusal(symptoms))
            return self

    class RegisterRow(BaseModel):
        """One ledger row, as typed fields rather than as a format string.

        `expansion_symptoms()` detects damage AFTER a value has been built.
        This makes a class of damage UNREPRESENTABLE instead:

        * `kind` is a `Literal`, so a row cannot be filed under a verb the
          readers do not parse. `build_row` accepted any string, and
          `register_status`/`identity_lineage` only match CLAIM/RELEASE/UPDATE
          -- so a typo produced a line that appended cleanly and was invisible
          to every reader of the ledger.
        * no field may contain a newline or a control character. The two rows
          that provoked this whole lane absorbed a shell/Make expansion; a
          multi-line compose invocation with its env-file chain cannot be a
          `branch` or an `owner` here, because the type refuses it before the
          row is rendered.
        * `ttl` must parse. It was rendered into `**TTL ... (expires ...)**`
          via `_ttl_delta`, which raises -- but only after the row string had
          already been assembled around it.

        The bounds are the measured ones: the longest legitimate single token
        in the live register is 153 characters (LONG_TOKEN_LIMIT carries 2x
        margin at 300), so 300 is the field cap too rather than a new number.
        """

        model_config = ConfigDict(extra="forbid")

        kind: Literal["CLAIM", "RELEASE", "UPDATE", "NOTE"]
        owner: Annotated[str, StringConstraints(
            strip_whitespace=True, min_length=1, max_length=LONG_TOKEN_LIMIT)]
        scope: str
        branch: Annotated[str, StringConstraints(
            strip_whitespace=True, max_length=LONG_TOKEN_LIMIT)] = ""
        ttl: Annotated[str, StringConstraints(strip_whitespace=True)] = ""
        co_owners: list[str] = []

        @model_validator(mode="after")
        def _shape_is_legal(self) -> "RegisterRow":
            # The SAME functions `build_row` calls unconditionally, so the
            # typed surface and the stdlib path cannot disagree about what a
            # row may contain. pydantic contributes the Literal, the length
            # constraints and the field typing; the control-character scan has
            # no declarative equivalent and lives in one place rather than two.
            assert_row_shape(self.kind, self.owner, self.branch, self.ttl,
                             self.scope)
            return self

        # DELIBERATELY NOT re-running expansion_symptoms() on `scope` here.
        # The CLI already validates prose through `RegisterProse`, which owns
        # the `--literal-assignments` waiver. A second check on this model
        # cannot see that waiver, so it refused the one legitimate case the
        # override exists for -- a row quoting `SUPABASE_ANON_KEY=` as
        # evidence. Two validators, one blind to the escape hatch, is how an
        # override stops working; pinned by
        # test_literal_assignments_override_files_quoted_evidence.
        #
        # What this model owns is what a waiver must never reach: the row's
        # SHAPE. A control character or an unparseable TTL is damage under
        # every override.

except ImportError:  # pragma: no cover -- exercised only off-venv
    RegisterProse = None  # type: ignore[assignment,misc]
    RegisterRow = None  # type: ignore[assignment,misc]


def build_row(
    kind: str,
    owner: str,
    branch: str,
    scope: str,
    ttl: str = "",
    co_owners: list[str] | None = None,
    now: datetime | None = None,
    baton_from: str = "",
    ruling: str = "",
    handoff: str = "",
    baton_to: str = "",
) -> str:
    """Render one register row. Pure, so the tests can pin the grammar.

    Validation happens BEFORE rendering, through `RegisterRow`, so a field that
    cannot legally appear in a row never becomes part of a row string. The
    previous order assembled the line first and validated fragments of it
    afterwards -- `_ttl_delta` raised only once the row was already built
    around the bad TTL, and `kind` was never checked at all.
    """
    # UNCONDITIONAL. Not inside the `RegisterRow is not None` branch, because
    # pydantic is absent in validate-register-postdate.yml and on offline
    # nodes, and a row's shape must hold there too.
    assert_row_shape(kind, owner, branch, ttl, scope)
    assert_baton_shape(kind, branch, baton_from, ruling, handoff, baton_to)

    if RegisterRow is not None:
        try:
            validated = RegisterRow(
                kind=kind, owner=owner, branch=branch, scope=scope, ttl=ttl,
                co_owners=list(co_owners or []),
            )
        except Exception as exc:  # pydantic ValidationError subclasses ValueError
            raise ValueError(_first_refusal(exc)) from None
        kind = validated.kind
        owner = validated.owner
        branch = validated.branch
        scope = validated.scope
        ttl = validated.ttl
        co_owners = validated.co_owners

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now = now.replace(microsecond=0)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    fields = [f"branch: `{branch}`"] if branch else []
    delta = _ttl_delta(ttl)
    if delta is not None:
        expires = (now + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        fields.append(f"**TTL {ttl} (expires `{expires}`)**")
    if co_owners:
        rendered = []
        for spec in co_owners:
            # `ID` or `ID:contribution note`
            ident, _, note = spec.partition(":")
            ident = ident.strip()
            note = note.strip()
            rendered.append(f"`{ident}` ({note})" if note else f"`{ident}`")
        fields.append("co-owners: " + ", ".join(rendered))
    # BOTH identities on the row: the signer in the head (who carried this
    # leg) and the holder here (whose leg it was), plus the authority.
    if baton_from.strip():
        fields.append(f"baton-from: `{baton_from.strip()}`")
    if baton_to.strip():
        fields.append(f"baton-to: `{baton_to.strip()}`")
    if ruling.strip():
        fields.append(f"ruling: `{ruling.strip()}`")
    elif handoff.strip():
        fields.append(f"handoff: `{handoff.strip()}`")

    head = f"- `{ts}` {kind} `{owner}`"
    middle = (" " + " · ".join(fields)) if fields else ""
    return f"{head}{middle} · scope: {scope}\n"


def append_row(row: str, register: Path | None = None) -> None:
    """Append one row. O_APPEND, so it cannot truncate and cannot interleave.

    `register=None` and resolved at CALL time, deliberately. It was a default
    argument bound to the module global, which python evaluates once at import.
    A caller that redirected `REGISTER` -- the test suite, and anything else
    pointing this tool at a different register -- still wrote to the ORIGINAL
    path, so the first run of these tests appended three junk rows to the live
    fleet register. A late-binding bug in the one function whose entire job is
    "write to the right file".

    `os.open` with O_APPEND rather than a plain `open(..., "a")` because the
    flag is the point: every write is positioned at end-of-file by the kernel
    at write time, so a concurrent filer on another node cannot land inside an
    existing row. The register is append-only; this makes that a property of
    the syscall rather than of everyone's good intentions.

    THAT IS A BYTE GUARANTEE AND NOT A TRANSACTION GUARANTEE, which an earlier
    version of this docstring blurred. Deciding whether a row MAY be appended
    happens in the caller, against a read that O_APPEND knows nothing about.
    Callers hold `register_lock` across read, check and append; this function
    stays a primitive and takes no lock of its own, so it can be called from
    inside one without deadlocking against itself.
    """
    if not row.endswith("\n"):
        row += "\n"
    target = REGISTER if register is None else register
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(target, flags, 0o644)
    try:
        os.write(fd, row.encode("utf-8"))
    finally:
        os.close(fd)


LOCK_TIMEOUT_SECONDS = 30.0


class LockUnavailable(RuntimeError):
    """The register transaction lock could not be taken inside the timeout."""


@contextlib.contextmanager
def register_lock(target, timeout: float | None = None):
    """Serialize one whole read-check-write transaction against the register.

    O_APPEND IS NOT ENOUGH, and the docstring on `append_row` overstated what
    it buys. O_APPEND makes each individual write land at end-of-file, so two
    filers cannot interleave BYTES. It does nothing for the transaction this
    tool actually performs, which is read-the-register, decide, then write:

        A reads (lane free) -> B reads (lane free) -> A appends -> B appends

    Both rows are accepted and one lane has two owners -- under exactly the
    concurrent-filing scenario the sanctioned path exists to support. Not
    hypothetical: this session ran six delivery agents in one repository, of
    which several filed rows.

    Two other roads are worse than that, and Codex named only the first:
    `insert_docs` and `amend_co_owners` are read-modify-WRITE over the whole
    file, so a row appended between their read and their `write_text` is not
    duplicated, it is DESTROYED -- silent row loss on an append-only ledger.
    All three transactions take this lock.

    fcntl.flock, on a descriptor of the register itself. Advisory, which is the
    honest scope: it serializes the filers who take it, and no lock available to
    a userland tool could stop an unrelated shell redirect. That is what the
    collision gate is for; this closes the window between two SANCTIONED filers.
    The lock is per open-file-description, so two descriptors contend even
    inside one process -- which is what makes the race testable without spawning
    anything.

    NON-BLOCKING WITH A DEADLINE, never a bare blocking flock: a wedged holder
    would otherwise hang the fleet's only write path forever with no message. On
    timeout this raises, and the caller reports could-not-measure (3) -- never 1,
    which in this tool means "the lane is held by another owner".
    """
    target = Path(target)
    # LATE-BOUND, for the reason `append_row` records about its own default:
    # a module global captured in a default argument is read once at import, so
    # a caller that lowers the timeout -- the tests, and any operator with a
    # slow shared filesystem -- would still get the value from import time.
    timeout = LOCK_TIMEOUT_SECONDS if timeout is None else timeout
    deadline = time.monotonic() + timeout

    if fcntl is not None:
        fd = os.open(target, os.O_RDONLY | os.O_CREAT, 0o644)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    if time.monotonic() >= deadline:
                        raise LockUnavailable(
                            f"another filer has held the register lock on "
                            f"{target} for more than {timeout:.0f}s, so this "
                            "row was NOT checked and NOT written"
                        )
                    time.sleep(0.02)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        return

    # NO fcntl (Windows). O_EXCL creation is atomic on every filesystem this
    # fleet uses, so the lockfile IS the lock. A crashed holder leaves it
    # behind; that surfaces as could-not-measure naming the file to remove,
    # which is a bad five minutes rather than a silently unlocked write.
    lockfile = target.with_name(target.name + ".lock")
    while True:
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockUnavailable(
                    f"{lockfile} still exists after {timeout:.0f}s. Another "
                    "filer holds the register lock, or one died holding it -- "
                    "if no filer is running, remove that file. Nothing was "
                    "checked and nothing was written"
                )
            time.sleep(0.02)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(lockfile)
        except OSError:
            pass


def _ledger_rows(text: str) -> list[str]:
    """Every CLAIM/RELEASE-shaped row, in order. The thing that must not move."""
    return [
        line for line in text.split("\n")
        if re.match(r"^\s*[-*]\s+`[0-9]{4}-[0-9]{2}-[0-9]{2}", line)
    ]


def insert_docs(anchor: str, block: str, register: Path | None = None) -> int:
    """Insert prose immediately BEFORE `anchor`, provably without touching rows.

    WHY THIS EXISTS. The collision gate now refuses shell writes to the register
    it cannot check -- which is correct for rows and has a cost: it also refuses
    a shell edit to the file's own DOCUMENTATION, because a PreToolUse hook
    cannot see what a mid-file rewrite will produce. An agent with no Write tool
    could therefore file rows and not maintain the prose describing how.

    The answer is the same one the append path uses: do it in validated code.
    The new content is built as a pure INSERTION into the original string, so
    deletion is structurally impossible rather than merely checked for, and the
    ledger rows are then compared before and after as a belt-and-braces
    assertion that the operation did what its shape says it did.
    """
    target = REGISTER if register is None else register
    with register_lock(target):
        original = target.read_text(encoding="utf-8")
        if anchor not in original:
            print(f"register-append: NOT MEASURED - anchor {anchor!r} not found in "
                  "the register, so nothing was inserted.", file=sys.stderr)
            return EXIT_UNMEASURED
        if original.count(anchor) > 1:
            print(f"register-append: NOT MEASURED - anchor {anchor!r} occurs "
                  f"{original.count(anchor)} times; it must be unique to place the "
                  "insertion unambiguously.", file=sys.stderr)
            return EXIT_UNMEASURED

        idx = original.index(anchor)
        updated = original[:idx] + block + original[idx:]

        # Structural: the write IS the original with one insertion, nothing else.
        if updated.replace(block, "", 1) != original:
            print("register-append: NOT MEASURED - the rendered file is not the "
                  "original plus one insertion. Refusing.", file=sys.stderr)
            return EXIT_UNMEASURED
        before, after = _ledger_rows(original), _ledger_rows(updated)
        if before != after:
            print(f"register-append: refusing - the ledger changed "
                  f"({len(before)} rows before, {len(after)} after). The register "
                  "is append-only; prose edits must not touch rows.",
                  file=sys.stderr)
            return EXIT_REFUSED

        target.write_text(updated, encoding="utf-8")
        print(f"register-append: inserted {len(block.splitlines())} line(s) before "
              f"{anchor!r}; {len(after)} ledger rows unchanged.", file=sys.stderr)
        return EXIT_OK


def _render_co_owners(specs):
    """`ID` or `ID:contribution note` -> the register's own rendering."""
    out = []
    for spec in specs:
        ident, _, note = spec.partition(":")
        ident, note = ident.strip(), note.strip()
        out.append(f"`{ident}` ({note})" if note else f"`{ident}`")
    return ", ".join(out)


# A ``double-backticked`` span is how these rows quote the register's OWN
# grammar -- e.g. ``branch: `chore/x` \xb7 **TTL n/a**`` cited as an example.
_QUOTED_EXAMPLE_RE = re.compile(r"``.*?``")


def _without_quoted_examples(row: str) -> str:
    """The row with its ``quoted examples`` removed.

    Amend is a WRITE and must not be aimed by a branch marker the row merely
    CITES. Measured against the live register: `amend --branch
    chore/cli-prereq-preflight` matched a row whose own lane is
    `feat/register-co-owner-attribution` and which quotes that branch as an
    example inside a ``...`` span -- the row that really held the lane was
    already released, so the citing row was the only "open claim" left.

    Scoped by code span rather than by position, because the row grammar is not
    uniform: hand-filed rows put `scope:` BEFORE `branch:`, so "everything up to
    `scope:`" would refuse the very rows an incumbent most needs to amend.

    Collision detection deliberately still reads the WHOLE row. A cited branch
    there causes an over-block, which is safe; narrowing it would trade a false
    refusal for a missed collision.
    """
    return _QUOTED_EXAMPLE_RE.sub(" ", row)


def _row_header(row: str) -> str:
    """The part of a row BEFORE `scope:` -- the fields, not the free prose.

    Used only to decide whether the row ALREADY carries a `co-owners:` field.
    These rows discuss the field in prose constantly, and matching the prose
    occurrence inserted the new IDs into the middle of a sentence, left the real
    field unset, and reported success -- the purity check cannot catch it,
    because inserting in the wrong place is still an insertion.
    """
    idx = row.find("scope:")
    return row if idx == -1 else row[:idx]


def amend_co_owners(owner, branch, co_owners, register=None, gate=None):
    """Add `co-owners:` to the caller's OWN open CLAIM row, in validated code.

    THE NEXT DEADLOCK INSTANCE, closed. The collision gate refuses shell writes
    to the register it cannot check. That is correct for rows, and it left the
    three-way co-owner workflow with no door: reciprocation requires the
    INCUMBENT to add `co-owners:` to a row they already filed, which is an
    in-place edit of one line. `sed -i` and `perl -pi` are refused (rightly --
    a PreToolUse hook cannot see what a mid-file rewrite produces),
    `register-claim` only appends, and `register-docs` refuses anything that
    changes a ledger row. So the field that SUPPRESSES a collision could only be
    set by the one tool nobody in this fleet has had for five sessions.

    Same answer as the append path: do it in validated code, and make the
    dangerous outcome structurally impossible rather than merely checked for.

      * YOUR OWN ROW ONLY. The row is located through the gate's own
        `open_claims_in`, keyed on the CANONICAL identity, and a row whose owner
        does not fold to the caller is not amendable. Attribution and authority
        are different powers -- you may declare who worked WITH you, never edit
        someone else's declaration of who worked with them.
      * ONE OPEN ROW, or nothing. Two open claims by the same identity on the
        same lane is ambiguous, and guessing which to amend is how a gate starts
        editing rows nobody asked it to.
      * PURE INSERTION. The new row is the old row with one substring added, and
        that is asserted by removing the substring again and comparing. Every
        other ledger row must be byte-identical, and the row COUNT must not move.
    """
    target = REGISTER if register is None else register
    with register_lock(target):
        original = target.read_text(encoding="utf-8")
        gate = gate or _load_gate()

        key = gate.canonical_owner(owner)
        lines_all = original.split("\n")

        def _declares(c):
            """The row's OWN branch marker, not one its prose merely cites."""
            row = lines_all[c[0] - 1] if 0 < c[0] <= len(lines_all) else ""
            return branch in gate.lanes_in(_without_quoted_examples(row))

        mine = [c for c in gate.open_claims_in(original).get(key, [])
                if _declares(c)]
        if not mine:
            print(f"register-append: refusing - no OPEN CLAIM by `{owner}` naming "
                  f"branch `{branch}`. You may only amend a row you filed and have "
                  "not released. To declare co-owners on a NEW lane, use "
                  "`make -C pmoves register-claim CO_OWNER=...`.", file=sys.stderr)
            return EXIT_REFUSED
        if len(mine) > 1:
            print(f"register-append: NOT MEASURED - `{owner}` has {len(mine)} open "
                  f"CLAIM rows naming branch `{branch}` (lines "
                  f"{', '.join(str(c[0]) for c in mine)}). Which one to amend is "
                  "ambiguous, so nothing was changed.", file=sys.stderr)
            return EXIT_UNMEASURED

        lineno = mine[0][0]
        lines = original.split("\n")
        row = lines[lineno - 1]
        rendered = _render_co_owners(co_owners)
        if not rendered:
            print("register-append: amend needs at least one --co-owner.",
                  file=sys.stderr)
            return EXIT_UNMEASURED

        if "co-owners:" in _row_header(row):
            inserted = rendered + ", "
            new_row = re.sub(r"(co-owners:\s*)", lambda m: m.group(1) + inserted,
                             row, count=1)
        else:
            # THE ROW GRAMMAR IS NOT UNIFORM AND THE TOOL MUST NOT ASSUME IT IS.
            # `build_row` emits ` \xb7 scope:`, and the first cut of this function
            # keyed on that -- which works for 18 of the register's 264 CLAIM rows
            # and refuses the other 246, every one of them filed by hand before this
            # tool existed. Those are precisely the rows an incumbent would need to
            # amend. Found by running the amend against a copy of the LIVE register
            # rather than a fixture built to the grammar the tool writes.
            mid = " " + chr(183) + " "
            canonical = mid + "scope:"
            if canonical in row:
                inserted = mid + "co-owners: " + rendered
                new_row = row.replace(canonical, inserted + canonical, 1)
            elif "scope:" in row:
                idx = row.index("scope:")   # the first one: the field, not a mention
                inserted = chr(183) + " co-owners: " + rendered + " " + chr(183) + " "
                new_row = row[:idx] + inserted + row[idx:]
            else:
                # A row with no scope field at all (1 of 264). Appending keeps the
                # insertion pure, which is the property the checks below assert.
                inserted = mid + "co-owners: " + rendered
                new_row = row.rstrip() + inserted

        if new_row.replace(inserted, "", 1) != row:
            print("register-append: NOT MEASURED - the amended row is not the "
                  "original plus one insertion. Refusing.", file=sys.stderr)
            return EXIT_UNMEASURED

        lines[lineno - 1] = new_row
        updated = "\n".join(lines)
        before, after = _ledger_rows(original), _ledger_rows(updated)
        if len(before) != len(after):
            print(f"register-append: refusing - the ledger changed length "
                  f"({len(before)} rows before, {len(after)} after).",
                  file=sys.stderr)
            return EXIT_REFUSED
        if row not in before:
            # `open_claims_in` accepts a row whose timestamp is not an ISO date;
            # `_ledger_rows` requires one. A row in that gap used to reach
            # `before.index(row)` and raise. Exit 3 either way, but a sanctioned road
            # should say what happened instead of printing a traceback at it.
            print("register-append: NOT MEASURED - the located row is not a "
                  "CLAIM/RELEASE-shaped ledger row (its timestamp is not an ISO "
                  "date), so the no-other-row-moved check cannot be made. Nothing "
                  "was written.", file=sys.stderr)
            return EXIT_UNMEASURED
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        if changed != [before.index(row)] or len(changed) != 1:
            print(f"register-append: refusing - {len(changed)} ledger rows changed; "
                  "an amend must touch exactly one.", file=sys.stderr)
            return EXIT_REFUSED

        target.write_text(updated, encoding="utf-8")
        print(new_row)
        print(f"register-append: amended line {lineno}; {len(after)} ledger rows, "
              "one row changed by insertion only.", file=sys.stderr)
        return EXIT_OK


def append_note(row: str, gate, register: Path | None = None) -> int:
    """Append a row that records a FACT and transitions no lane state.

    THE MISSING RECORD TYPE, and the reason the trap existed. This tool used to
    accept `claim`, `release`, `docs` and `amend` -- no way to say "here is a
    fact about the register". The register itself has always had one: 5 rows
    read `NOTE`, all hand-inserted before this tool existed, alongside REVIEW,
    UPDATE, HANDOFF and CORRECTION.

    With no `note`, recording a correction meant filing a `release`, because it
    was the only non-CLAIM kind available. And a RELEASE that names no lane
    closes EVERY lane its owner holds -- 142 rows in the live register use it
    that way, so the convention is real and load-bearing. Put together: an agent
    appending a footnote under an owner with open lanes would have closed all of
    them while believing it was adding a comment. Observed live; harmless only
    because that owner's lanes happened to be closed already.

    INERTNESS IS PROVED, NOT ASSERTED. The kind is parsed as inert by the gate
    (`INERT_ROW_KINDS`), and this function additionally computes the open-lane
    map before and after the proposed append and REFUSES if it moved. Two
    independent guarantees, because the prose in these rows quotes `CLAIM` and
    `RELEASE` for a living and a parser change alone is a promise about one
    file's contents.
    """
    target = REGISTER if register is None else register
    with register_lock(target):
        existing = target.read_text(encoding="utf-8", errors="replace")
        # A register whose last byte is not a newline would GLUE the appended
        # row onto the previous one -- for the check and for the write alike.
        # Normalised here so the simulated file is the file that would result.
        joined = existing if (not existing or existing.endswith("\n")) else existing + "\n"
        try:
            before = gate.open_claims_in(joined)
            after = gate.open_claims_in(joined + row)
        except Exception as exc:  # noqa: BLE001 -- report, never guess
            print("register-append: NOT MEASURED - the collision gate raised "
                  f"{type(exc).__name__}: {exc} while checking that this NOTE "
                  "changes no lane. Nothing was written.", file=sys.stderr)
            return EXIT_UNMEASURED

        if after != before:
            print("register-append: refusing - this NOTE would CHANGE the open "
                  "lanes, which a note must never do. Its prose almost certainly "
                  "quotes a `CLAIM `owner`` or `RELEASE `owner`` sequence that the "
                  "gate reads as a real row. Rewrite the prose (name the row by "
                  "line number, or drop the backticks around the owner) and file "
                  "it again.", file=sys.stderr)
            _print_lane_delta(before, after)
            return EXIT_REFUSED

        append_row(row, target)
        print(row.rstrip("\n"))
        try:
            where = target.relative_to(REPO_ROOT)
        except ValueError:
            where = target
        print(f"register-append: appended a NOTE to {where}; "
              f"{sum(len(v) for v in before.values())} open lane(s), unchanged.",
              file=sys.stderr)
        return EXIT_OK


# --- sync: recover a checkout whose register carries uncommitted rows --------
#
# THE RECOVERY ROAD. A checkout on `main` that appended rows and never committed
# them cannot fast-forward: git refuses to overwrite the dirty register, and the
# collision gate -- correctly -- refuses `git checkout`, interpreters and
# compound commands on the register. Every other sanctioned road only APPENDS,
# so no agent could drop a row, and the checkout was stuck (measured 2026-09-28:
# 21 behind main, 8 uncommitted rows, 5 of them already re-filed on main by
# #3205). The gate's own header: "THE DENY IS ONLY DEFENSIBLE BECAUSE A
# SANCTIONED PATH EXISTS." This is that path.
#
# What it may drop, and nothing else:
#
#   ON-MAIN   a byte-identical LEDGER ROW already exists on the target ref
#             (prose lines on the ref do not count -- a row quoted in the docs
#             is not a live row)
#   RE-FILED  a ledger row on the ref with the SAME kind, SAME owner (exact
#             string) and SAME header branch whose text says `first filed at
#             <this row's timestamp>` -- the marker the re-filing convention
#             writes. The header branch is read only when the row carries the
#             ` · scope:` separator; without it the row is KEEP.
#   KEEP      everything else, including every non-ledger line. Never dropped,
#             never guessed about. A timestamp one second off is KEEP.
#
# BYTES, NOT TEXT. The register is classified and written as bytes, split on
# b"\n" only. Text is decoded (surrogateescape, lossless) solely to MATCH, and
# nothing decoded is ever written back: a KEEP line carrying a stray \xff byte,
# or a U+2028 inside a scope, round-trips byte-exact and stays one row.
#
# The sequence when KEEP is non-empty and main changed the register:
#
#   make -C pmoves register-sync HOLD=1 APPLY=1           # register -> HEAD, KEEP to sidecar
#   git pull --ff-only --no-recurse-submodules
#   make -C pmoves register-sync REAPPLY=<sidecar> APPLY=1  # KEEP back onto the tail
#
# REAPPLY FACES THE SAME ROW CHECKS AS register-claim. What the manifest proves
# is INTEGRITY, NOT AUTHORSHIP: the `.keep.md` must sit under the sidecar
# directory and match the sha256 in its manifest, and the pre-image must match
# too -- but anyone who can write that directory can write a consistent set.
# So every row is ALSO checked on its own: it must be a CLAIM, RELEASE or NOTE
# that round-trips byte-identically through `build_row` (the renderer the append
# roads use) and passes the expansion-residue check; its timestamp must lie in
# [held_at - 30d, held_at]; it must be a line of the pre-image; a bare RELEASE
# is refused; rows now ON-MAIN or RE-FILED are skipped; and CLAIMs face the
# gate's collision verdict SEQUENTIALLY (a RELEASE earlier in the payload frees
# its lane for a later CLAIM), with --i-have-coordinated as on register-claim.
# All-or-nothing. `register-postdate-check` remains the timestamp backstop.
#
# Every mode is a DRY RUN unless APPLY=1 / --apply. It never fetches: the target
# ref is whatever the local ref says, and its sha is printed. Exit: 0 done (or
# dry run); 1 reapply refused because a lane is held by another owner (this
# tool's meaning of 1 everywhere); 3 refused / could not measure.

REGISTER_REL = "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"
SYNC_SIDECAR_REL = "pmoves/data/register-sync"
ON_MAIN, RE_FILED, KEEP = "ON-MAIN", "RE-FILED", "KEEP"

_SYNC_ROW_RE = re.compile(
    r"^\s*[-*]\s+`(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z)`\s+"
    r"(?P<kind>[A-Z]+)\s+`(?P<owner>[^`]+)`")
_SYNC_BRANCH_RE = re.compile(r"branch:\s*`([^`]+)`")
_SCOPE_SEP = " · scope:"


class SyncRefused(RuntimeError):
    """The sync could not establish what it would change. Exit 3, never 1."""


class SyncLaneHeld(SyncRefused):
    """A reapplied CLAIM names a lane another owner holds. Exit 1, as register-claim."""


def _git(repo: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    except OSError as exc:
        raise SyncRefused(f"git could not be run ({exc})") from exc
    if proc.returncode != 0:
        raise SyncRefused(
            f"`git {' '.join(args)}` failed (rc {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _split_lines(data: bytes) -> list[bytes]:
    """Lines split on b"\\n" ONLY, each keeping its terminator. Never str.splitlines,
    which also splits on U+2028, \\x0c, \\x1c.. and would tear one row in two."""
    if not data:
        return []
    parts = data.split(b"\n")
    lines = [p + b"\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _as_text(line: bytes) -> str:
    """For MATCHING only. surrogateescape is lossless; nothing decoded is written."""
    return line.rstrip(b"\n").decode("utf-8", "surrogateescape")


def _row_key(text: str):
    """(ts, kind, owner, header-branch) of a ledger row, or None.

    The branch is read from the HEADER only -- the fields before ` · scope:` --
    because a scope routinely names other branches. A row with no separator has
    no readable header, so its branch is None and it cannot be RE-FILED.
    """
    m = _SYNC_ROW_RE.match(text)
    if not m:
        return None
    branch = None
    if _SCOPE_SEP in text:
        b = _SYNC_BRANCH_RE.search(text.split(_SCOPE_SEP, 1)[0])
        branch = b.group(1) if b else None
    return m.group("ts"), m.group("kind"), m.group("owner"), branch


def classify_uncommitted(lines: list[bytes], *ref_blobs: bytes) -> list[tuple[str, bytes]]:
    """Class of each uncommitted line against the LEDGER ROWS of the given blobs."""
    ref_rows = [t for blob in ref_blobs for t in map(_as_text, _split_lines(blob))
                if _SYNC_ROW_RE.match(t)]
    ref_set = set(ref_rows)
    ref_keys = [(_row_key(r), r) for r in ref_rows]
    out = []
    for line in lines:
        text = _as_text(line)
        key = _row_key(text)
        if key is None:
            out.append((KEEP, line))          # not a ledger row: never guessed about
            continue
        if text in ref_set:
            out.append((ON_MAIN, line))
            continue
        ts, kind, owner, branch = key
        markers = (f"first filed at {ts}", f"first filed at `{ts}`")
        refiled = branch is not None and any(
            rk[1] == kind and rk[2] == owner and rk[3] == branch
            and any(mk in r for mk in markers)
            for rk, r in ref_keys)
        out.append((RE_FILED if refiled else KEEP, line))
    return out


def _snapshot(repo: Path, ref: str) -> dict:
    """HEAD sha, ref sha, and both blobs -- read together so they can be compared."""
    head_sha = _git(repo, "rev-parse", "HEAD").decode().strip()
    ref_sha = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    return {
        "head_sha": head_sha, "ref_sha": ref_sha,
        "head": _git(repo, "cat-file", "blob", f"{head_sha}:{REGISTER_REL}"),
        "ref_blob": _git(repo, "cat-file", "blob", f"{ref_sha}:{REGISTER_REL}"),
    }


def _sync_measure(repo: Path, ref: str) -> dict:
    """Read HEAD, the index, the working tree and the ref; refuse anything not a
    pure append over HEAD."""
    register = repo / REGISTER_REL
    if not register.is_file():
        raise SyncRefused(f"no register at {register}")
    snap = _snapshot(repo, ref)
    # THE INDEX TOO. A staged change to the register blocks the pull exactly as
    # a working-tree one does, and restoring the working file would not clear it.
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet", "HEAD", "--", REGISTER_REL],
        capture_output=True)
    if staged.returncode != 0:
        raise SyncRefused(
            "the register's INDEX differs from HEAD (a staged change). This tool "
            "only repairs the working tree; nothing was classified or written")
    head, work = snap["head"], register.read_bytes()
    # A PURE APPEND: HEAD's bytes are a prefix, and HEAD's last line was already
    # complete (otherwise the first "appended" byte modifies an existing line).
    if not work.startswith(head) or (head and not head.endswith(b"\n")
                                     and len(work) > len(head)):
        raise SyncRefused(
            "the working register is not HEAD plus appended lines -- the diff "
            "removes or modifies at least one line. This tool only recovers a "
            "pure append; nothing was classified and nothing was written")
    lines = _split_lines(work[len(head):])
    return dict(snap, register=register, work=work, ref=ref,
                work_hash=hashlib.sha256(work).hexdigest(),
                head_lines=head.count(b"\n"), ref_lines=snap["ref_blob"].count(b"\n"),
                lines=lines, classes=classify_uncommitted(lines, snap["ref_blob"]))


def _show(line: bytes) -> str:
    return line.rstrip(b"\n").decode("utf-8", "replace")[:120]


def _sync_report(m: dict) -> dict:
    """Print BOTH input sizes beside the result, and each row's class."""
    print(f"register-sync: register  {m['register']}")
    print(f"register-sync: HEAD      {m['head_sha']}  ({m['head_lines']} lines committed)")
    print(f"register-sync: ref       {m['ref']} = {m['ref_sha']}  "
          f"({m['ref_lines']} lines; NOT fetched by this tool)")
    print(f"register-sync: INPUT     {len(m['lines'])} uncommitted line(s) "
          "appended after HEAD")
    counts = {c: sum(1 for k, _ in m["classes"] if k == c)
              for c in (ON_MAIN, RE_FILED, KEEP)}
    if not m["lines"]:
        print("register-sync: nothing to sync -- the INPUT is empty (the working "
              "register equals HEAD); that is not an empty result.")
        return counts
    for cls, line in m["classes"]:
        print(f"  {cls:<8} {_show(line)}")
    print(f"register-sync: RESULT    {counts[ON_MAIN]} ON-MAIN, "
          f"{counts[RE_FILED]} RE-FILED, {counts[KEEP]} KEEP "
          f"(of {len(m['lines'])} input)")
    return counts


def _sidecar_dir(repo: Path) -> Path:
    """The sidecar directory, only once git confirms it can never be committed."""
    probe = f"{SYNC_SIDECAR_REL}/probe.keep.md"
    proc = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", probe],
                          capture_output=True)
    if proc.returncode != 0:
        raise SyncRefused(
            f"{SYNC_SIDECAR_REL}/ is not gitignored in {repo}, so a sidecar "
            "written there could be committed. Nothing was written")
    d = repo / SYNC_SIDECAR_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_exclusive(path: Path, data: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise SyncRefused(f"sidecar {path} already exists; nothing on the "
                          "register was written. Re-run the sync") from exc
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _append_bytes(register: Path, data: bytes) -> None:
    """The O_APPEND primitive, on BYTES, so nothing is re-encoded on the way out."""
    fd = os.open(register, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def sync_register(repo: Path, ref: str, apply: bool, hold: bool) -> int:
    m = _sync_measure(repo, ref)
    _sync_report(m)
    if not m["lines"]:
        return EXIT_OK
    keep = b"".join(line for cls, line in m["classes"] if cls == KEEP)
    dropped = b"".join(line for cls, line in m["classes"] if cls != KEEP)
    n_keep, n_drop = len(_split_lines(keep)), len(_split_lines(dropped))
    if not apply:
        print(f"register-sync: DRY RUN - would restore the register to HEAD, drop "
              f"{n_drop} line(s), and {'HOLD' if hold else 're-append'} {n_keep} "
              "KEEP line(s). Nothing written. Re-run with APPLY=1 (or --apply).")
        return EXIT_OK

    side = _sidecar_dir(repo)
    register = m["register"]
    with register_lock(register):
        # A CONCURRENT WRITER -- to the register, HEAD or the ref -- between
        # classification and now voids the classification. Re-read all three
        # under the lock and refuse rather than drop a row nobody classified.
        if hashlib.sha256(register.read_bytes()).hexdigest() != m["work_hash"]:
            raise SyncRefused(
                "the register changed after it was classified (a concurrent "
                "writer). Nothing was written. Re-run the sync")
        again = _snapshot(repo, ref)
        if (again["head_sha"], again["ref_sha"]) != (m["head_sha"], m["ref_sha"]):
            raise SyncRefused(
                "HEAD or the ref moved after classification. Nothing was "
                "written. Re-run the sync")

        # SIDECARS FIRST: KEEP, the dropped lines, and a FULL PRE-IMAGE of the
        # register, plus a manifest that pins the KEEP file's hash for reapply.
        # Nothing on the register moves until all four are on disk.
        stamp = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                 + f"-{os.getpid()}")
        keep_path = side / f"{stamp}.keep.md"
        pre_path = side / f"{stamp}.preimage.md"
        _write_exclusive(pre_path, m["work"])
        _write_exclusive(side / f"{stamp}.dropped.md", dropped)
        _write_exclusive(keep_path, keep)
        _write_exclusive(side / f"{stamp}.manifest.json", json.dumps({
            "keep": keep_path.name, "keep_sha256": hashlib.sha256(keep).hexdigest(),
            "preimage_sha256": m["work_hash"], "head": m["head_sha"],
            "ref": ref, "ref_sha": m["ref_sha"], "mode": "hold" if hold else "apply",
            "held_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, indent=2).encode("utf-8"))
        print(f"register-sync: KEEP rows saved to    {keep_path}")
        print(f"register-sync: full pre-image saved  {pre_path}")

        # FTRUNCATE TO HEAD'S LENGTH, never rewrite HEAD: the prefix is already
        # verified byte-equal to HEAD, so cutting the tail cannot tear it. Same
        # inode, so a waiter on register_lock still locks the file it will write.
        expected = m["head"] + (b"" if hold else keep)
        try:
            fd = os.open(register, os.O_WRONLY)
            try:
                os.ftruncate(fd, len(m["head"]))
            finally:
                os.close(fd)
            if keep and not hold:
                _append_bytes(register, keep)
            after = register.read_bytes()      # verified UNDER the lock
        except Exception as exc:  # noqa: BLE001 -- the message must stay true
            raise SyncRefused(
                f"PARTIAL APPLY - the register WAS modified and then failed "
                f"({type(exc).__name__}: {exc}). HEAD's bytes are intact (the "
                f"register was only truncated to HEAD's length); the full "
                f"original is in {pre_path} and KEEP is in {keep_path}. Recover "
                f"with `make -C pmoves register-sync REAPPLY={keep_path} APPLY=1` "
                "once the register is back at HEAD") from exc
        if after != expected:
            raise SyncRefused(
                "PARTIAL APPLY - post-write check failed: the register is not "
                f"HEAD{'' if hold else ' + KEEP'} byte-for-byte. The full original "
                f"is in {pre_path}; KEEP is in {keep_path}")
    print(f"register-sync: APPLIED - the working diff vs HEAD now adds "
          f"{0 if hold else n_keep} line(s) and removes 0; {n_drop} dropped"
          f"{f', {n_keep} KEEP held in the sidecar' if hold else ''}.")
    if hold:
        print("register-sync: next: git pull --ff-only --no-recurse-submodules, "
              f"then make -C pmoves register-sync REAPPLY={keep_path} APPLY=1")
    return EXIT_OK


REAPPLY_KINDS = ("CLAIM", "RELEASE", "NOTE")      # what the append roads emit
REAPPLY_MAX_AGE = timedelta(days=30)
REAPPLY_CLOCK_SKEW = timedelta(minutes=5)
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _verified_sidecar(repo: Path, sidecar: Path) -> tuple[bytes, dict, bytes]:
    """(KEEP bytes, manifest, pre-image bytes) of an INTACT sidecar set -- or a refusal.

    INTEGRITY, NOT AUTHORSHIP. This proves the `.keep.md`, its manifest and its
    pre-image are mutually consistent and live under the gitignored sidecar
    directory. It does NOT prove this tool wrote them: anyone who can write that
    directory can write a consistent set. Authorship-shaped guarantees come from
    the row checks in `reapply_sidecar` (renderer round-trip, kinds, timestamp
    window, collision gate), and `make -C pmoves register-postdate-check` remains
    the backstop for timestamps.
    """
    root = os.path.realpath(repo / SYNC_SIDECAR_REL)
    real = os.path.realpath(sidecar)
    if os.path.dirname(real) != root or not real.endswith(".keep.md"):
        raise SyncRefused(
            f"{sidecar} is not a `.keep.md` sidecar in {SYNC_SIDECAR_REL}/. "
            "REAPPLY only accepts sidecar sets under that directory")
    if not os.path.isfile(real):
        raise SyncRefused(f"no sidecar at {sidecar}")
    stem = real[: -len(".keep.md")]
    try:
        meta = json.loads(Path(stem + ".manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncRefused(f"no readable manifest beside {sidecar} ({exc}); "
                          "refusing an unpinned sidecar") from exc
    data = Path(real).read_bytes()
    if meta.get("keep") != os.path.basename(real) or \
            meta.get("keep_sha256") != hashlib.sha256(data).hexdigest():
        raise SyncRefused(
            f"{sidecar} does not match its manifest (edited since it was "
            "written?). Refusing to append rows nobody classified")
    try:
        pre = Path(stem + ".preimage.md").read_bytes()
    except OSError as exc:
        raise SyncRefused(f"no pre-image beside {sidecar} ({exc})") from exc
    if meta.get("preimage_sha256") != hashlib.sha256(pre).hexdigest():
        raise SyncRefused(f"the pre-image beside {sidecar} does not match its manifest")
    return data, meta, pre


def _parse_rendered(text: str):
    """Split a row back into build_row's arguments, or None. Fail-closed: any
    field this does not recognise returns None, and the caller refuses."""
    head_m = re.match(r"^- `([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z)` ([A-Z]+) `([^`]+)`",
                      text)
    if not head_m or _SCOPE_SEP not in text:
        return None
    header, scope = text.split(_SCOPE_SEP, 1)
    rest = header[head_m.end():]
    out = {"ts": head_m.group(1), "kind": head_m.group(2), "owner": head_m.group(3),
           "branch": "", "ttl": "", "co_owners": [], "scope": scope.lstrip(" "),
           "baton_from": "", "baton_to": "", "ruling": "", "handoff": ""}
    if not rest:
        return out
    if not rest.startswith(" "):
        return None
    for field in rest[1:].split(" · "):
        m = re.fullmatch(r"branch: `([^`]+)`", field)
        if m:
            out["branch"] = m.group(1)
            continue
        m = re.fullmatch(r"\*\*TTL (\S+) \(expires `[^`]+`\)\*\*", field)
        if m:
            out["ttl"] = m.group(1)
            continue
        if field.startswith("co-owners: "):
            for ident, note in re.findall(r"`([^`]+)`(?: \(([^()]*)\))?",
                                          field[len("co-owners: "):]):
                out["co_owners"].append(f"{ident}:{note}" if note else ident)
            continue
        m = re.fullmatch(r"(baton-from|baton-to|ruling|handoff): `([^`]+)`", field)
        if m:
            out[m.group(1).replace("-", "_")] = m.group(2)
            continue
        return None
    return out


def _assert_round_trips(line: bytes) -> dict:
    """The row must be exactly what the claim/release/note roads would render.

    Parsed, re-rendered with `build_row` at the row's own timestamp, and compared
    byte-for-byte; the scope also faces `assert_prose_clean`, the expansion-
    residue check every append road applies. This is what stops a sidecar from
    carrying arbitrary kinds or hand-built text past the renderer.
    """
    try:
        text = line.rstrip(b"\n").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyncRefused(f"a reapplied row is not UTF-8 ({exc}); the append "
                          "roads never emit that") from exc
    parsed = _parse_rendered(text)
    if parsed is None:
        raise SyncRefused(f"not a row the append roads render: {text[:120]!r}")
    if parsed["kind"] not in REAPPLY_KINDS:
        raise SyncRefused(f"kind `{parsed['kind']}` is not reapplied (only "
                          f"{', '.join(REAPPLY_KINDS)}): {text[:120]!r}")
    try:
        assert_prose_clean(parsed["scope"])
        rendered = build_row(
            kind=parsed["kind"], owner=parsed["owner"], branch=parsed["branch"],
            scope=parsed["scope"], ttl=parsed["ttl"], co_owners=parsed["co_owners"],
            now=datetime.strptime(parsed["ts"], _TS_FMT).replace(tzinfo=timezone.utc),
            baton_from=parsed["baton_from"], ruling=parsed["ruling"],
            handoff=parsed["handoff"], baton_to=parsed["baton_to"])
    except ValueError as exc:
        raise SyncRefused(f"row refused by the renderer ({exc}): {text[:120]!r}") from exc
    if rendered.rstrip("\n") != text:
        raise SyncRefused(f"row does not round-trip through the renderer "
                          f"(hand-built or edited?): {text[:120]!r}")
    return parsed


def reapply_sidecar(repo: Path, sidecar: Path, ref: str, apply: bool,
                    coordinated: bool = False) -> int:
    """Append a HOLD sidecar's rows to the tail -- through the same checks as a CLAIM."""
    register = repo / REGISTER_REL
    if not register.is_file():
        raise SyncRefused(f"no register at {register}")
    data, meta, pre = _verified_sidecar(repo, sidecar)
    lines = [ln for ln in _split_lines(data) if ln.strip()]
    print(f"register-sync: INPUT     {len(_split_lines(data))} line(s) in {sidecar} "
          f"({len(lines)} non-blank)")
    bad = [ln for ln in lines if _row_key(_as_text(ln)) is None]
    if bad:
        raise SyncRefused(
            f"{len(bad)} non-blank line(s) are not ledger rows (first: "
            f"{_show(bad[0])!r}). REAPPLY appends rows only")

    # THE TIMESTAMP WINDOW. A row cannot be later than the moment it was held
    # (and that moment cannot be in the future), nor older than
    # REAPPLY_MAX_AGE before it -- an uncommitted row older than that is stale
    # and belongs back on register-claim, which reads the clock itself. The
    # held time comes from the manifest, so this bounds an honest sidecar and
    # a careless forger, not a determined one; register-postdate-check is the
    # backstop. Every row must also be a line of the recorded pre-image.
    try:
        held_at = datetime.strptime(meta.get("held_at", ""), _TS_FMT).replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise SyncRefused("the manifest records no valid `held_at`") from exc
    if held_at > datetime.now(timezone.utc) + REAPPLY_CLOCK_SKEW:
        raise SyncRefused(f"the manifest's held_at {meta['held_at']} is in the future")
    pre_lines = set(_split_lines(pre))
    for ln in lines:
        parsed = _assert_round_trips(ln)
        ts = datetime.strptime(parsed["ts"], _TS_FMT).replace(tzinfo=timezone.utc)
        if ts > held_at or ts < held_at - REAPPLY_MAX_AGE:
            raise SyncRefused(
                f"row timestamp {parsed['ts']} is outside the window "
                f"[{(held_at - REAPPLY_MAX_AGE).strftime(_TS_FMT)}, "
                f"{meta['held_at']}] (held time minus {REAPPLY_MAX_AGE.days}d, "
                "held time)")
        if (ln if ln.endswith(b"\n") else ln + b"\n") not in pre_lines:
            raise SyncRefused(f"row is not in the recorded pre-image: {_show(ln)!r}")
        if parsed["kind"] == "RELEASE" and not parsed["branch"]:
            raise SyncRefused(
                f"a bare RELEASE names no lane and would close EVERY lane its "
                f"owner holds: {_show(ln)!r}. File it with "
                "`make -C pmoves register-release` if that is intended")

    try:
        gate = _load_gate()
    except Exception as exc:  # noqa: BLE001 -- report, never guess
        raise SyncRefused(f"the collision gate could not be loaded ({exc})") from exc
    for ln in lines:
        parsed = _parse_rendered(_as_text(ln))
        if parsed and parsed["baton_from"]:
            problem = baton_refusal(gate, parsed["owner"], parsed["baton_from"])
            if problem:
                raise SyncRefused(f"a reapplied baton RELEASE is refused: {problem}")

    with register_lock(register):
        current = register.read_bytes()
        snap = _snapshot(repo, ref)
        classes = classify_uncommitted(lines, current, snap["ref_blob"])
        todo = [ln if ln.endswith(b"\n") else ln + b"\n"
                for cls, ln in classes if cls == KEEP]
        for cls, ln in classes:
            print(f"  {('APPEND' if cls == KEEP else 'SKIP ' + cls):<16} {_show(ln)}")
        # SEQUENTIAL, exactly as the ledger reads: each CLAIM is judged against
        # the lanes open in the current register PLUS the payload rows before
        # it, so a lane-scoped RELEASE earlier in the payload frees that lane
        # (and only that lane) for a later CLAIM -- a handoff held across a
        # pull reapplies instead of stranding every KEEP row.
        ledger = current.decode("utf-8", "replace")
        if ledger and not ledger.endswith("\n"):
            ledger += "\n"
        for ln in todo:
            row = ln.decode("utf-8")
            if _row_key(row.rstrip("\n"))[1] == "CLAIM":
                try:
                    verdict = gate.evaluate_claims(row, gate.open_claims_in(ledger))
                except Exception as exc:  # noqa: BLE001
                    raise SyncRefused(f"the collision gate raised {type(exc).__name__}: "
                                      f"{exc}; nothing was appended") from exc
                if verdict.collisions:
                    held = "; ".join(f"`{lane}` held by `{other}` (line {n})"
                                     for lane, other, n in verdict.collisions)
                    raise SyncLaneHeld(f"a reapplied CLAIM names a lane another "
                                       f"owner holds: {held}. Nothing was appended")
                for lane, other, n in verdict.shared:
                    print(f"register-sync: SHARED LANE - `{lane}` is held by `{other}` "
                          f"(line {n}), whose row declares this claimant. Allowing.",
                          file=sys.stderr)
                if verdict.one_sided and not coordinated:
                    raise SyncLaneHeld(
                        "a reapplied CLAIM shares a lane only by its OWN co-owner "
                        "declaration; the incumbent has not named it back. Re-run "
                        "with ARGS=--i-have-coordinated if you have coordinated. "
                        "Nothing was appended")
                if verdict.unreadable_co_owners or verdict.unkeyed:
                    raise SyncRefused("a reapplied CLAIM has unreadable co-owners or "
                                      "names no lane. Nothing was appended")
            ledger += row
        payload = b"".join(todo)
        print(f"register-sync: RESULT    {len(todo)} to append, "
              f"{len(lines) - len(todo)} skipped (now on the ref or the register)")
        if not apply:
            print("register-sync: DRY RUN - nothing written. Re-run with APPLY=1.")
            return EXIT_OK
        if payload:
            _append_bytes(register, payload)
    print(f"register-sync: APPLIED - appended {len(todo)} row(s).")
    return EXIT_OK


def _warn_if_invisible(register: Path) -> None:
    """A row appended on `main` (or a detached HEAD) is a row nobody else sees.

    WARN, DON'T REFUSE: the append is still the right first step. But the fleet
    reads the register from main, so a row never committed on a branch that
    merges is invisible to every other node -- and, left uncommitted on a `main`
    checkout, it later blocks that checkout's own pull (the 2026-09-28 stuck
    root checkout: 8 such rows).

    NEVER RAISES. It runs AFTER a successful append; an exception here (git
    missing) would turn a written row into exit 3, and a retry would file it
    twice.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(register.parent), "symbolic-ref", "-q", "--short", "HEAD"],
            capture_output=True, text=True)
        if proc.returncode != 0:
            in_repo = subprocess.run(
                ["git", "-C", str(register.parent), "rev-parse", "--git-dir"],
                capture_output=True).returncode == 0
            if not in_repo:
                return      # not a checkout at all: nothing to be invisible from
    except OSError as exc:
        print(f"register-append: note - the row WAS appended, but git could not be "
              f"run ({exc}) to check whether this checkout is on main.",
              file=sys.stderr)
        return
    branch = proc.stdout.strip() if proc.returncode == 0 else None
    if branch is None or branch == "main":
        where = "a DETACHED HEAD" if branch is None else "`main`"
        print("register-append: WARNING - this checkout is on " + where + ". "
              "The row is UNCOMMITTED and INVISIBLE fleet-wide until it is "
              "committed on a branch that merges to main; left here it will also "
              "block this checkout's next `git pull`. Recovery road: "
              "`make -C pmoves register-sync`.", file=sys.stderr)


def _print_lane_delta(before: dict, after: dict) -> None:
    """Name what moved. A refusal that does not say what it saw is a wall."""
    for owner in sorted(set(before) | set(after), key=str):
        was = len(before.get(owner, []))
        now = len(after.get(owner, []))
        if was != now:
            print(f"  - `{owner}`: {was} open lane(s) before, {now} after",
                  file=sys.stderr)


def _dispatch(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("kind",
                        choices=["claim", "release", "note", "docs", "amend",
                                 "sync"],
                        help="CLAIM opens a lane, RELEASE closes it, "
                             "NOTE records a fact and transitions nothing, "
                             "docs inserts prose without touching rows, "
                             "amend adds co-owners to YOUR OWN open row, "
                             "sync drops uncommitted rows main already has "
                             "(dry run unless --apply)")
    # sync mode. Environment doors for the make target, same as every field.
    parser.add_argument("--repo", default=os.environ.get("REGISTER_SYNC_REPO", ""),
                        help="sync: checkout whose register to sync "
                             "(default: this tool's own repository)")
    parser.add_argument("--ref",
                        default=os.environ.get("REGISTER_SYNC_REF", "") or "origin/main",
                        help="sync: ref to classify against (default origin/main; "
                             "NOT fetched by this tool)")
    parser.add_argument("--apply", action="store_true",
                        default=os.environ.get("REGISTER_SYNC_APPLY", "") in ("1", "true", "yes"),
                        help="sync: write. Without it every sync mode is a dry run")
    parser.add_argument("--hold", action="store_true",
                        default=os.environ.get("REGISTER_SYNC_HOLD", "") in ("1", "true", "yes"),
                        help="sync: restore to HEAD and HOLD the KEEP rows in the "
                             "sidecar (then pull, then --reapply)")
    parser.add_argument("--reapply", default=os.environ.get("REGISTER_SYNC_REAPPLY", ""),
                        metavar="SIDECAR",
                        help="sync: append a --hold sidecar's rows to the tail")
    parser.add_argument("--anchor",
                        default=os.environ.get("REGISTER_ANCHOR", ""),
                        help="docs mode: unique line to insert BEFORE "
                             "(or set REGISTER_ANCHOR)")
    parser.add_argument("--text-file",
                        default=os.environ.get("REGISTER_TEXT_FILE", ""),
                        help="docs mode: file holding the prose to insert "
                             "(or set REGISTER_TEXT_FILE)")
    # EVERY FIELD HAS AN ENVIRONMENT DOOR, and that is a security property, not
    # a convenience. A caller that builds a shell command out of these values
    # hands their content to a shell first. Measured through `make` at
    # 776b429b9: SCOPE already travelled by environment, so the ROW came out
    # correct -- and the guard line `[ -z "$(SCOPE)" ]` still expanded it, so
    #     SCOPE='document `touch /tmp/PROOF` behavior'
    # created that file. The row was clean and the command still ran. OWNER,
    # BRANCH, TTL, ANCHOR and TEXT_FILE were interpolated outright. Passing by
    # environment is the only arrangement where the value is never part of a
    # command string at any point.
    parser.add_argument("--owner", default=os.environ.get("REGISTER_OWNER", ""),
                        help="owner ID exactly as the register spells it, "
                             "e.g. 'B850-CLAUDE (Knuckles)' "
                             "(or set REGISTER_OWNER)")
    parser.add_argument("--branch",
                        default=os.environ.get("REGISTER_BRANCH", ""),
                        help="the lane (or set REGISTER_BRANCH). A claim naming "
                             "no branch cannot be checked by the collision "
                             "gate, so this is REQUIRED for a claim.")
    parser.add_argument("--scope", default=os.environ.get("REGISTER_SCOPE", ""),
                        help="what this lane covers (or set REGISTER_SCOPE). "
                             "PREFER THE ENVIRONMENT for prose: a register row "
                             "is full of backticks, and any layer that hands "
                             "the text to a shell will command-substitute "
                             "them. Discovered by filing a real RELEASE "
                             "through `make`, which re-parses its own "
                             "variables -- the row came back with its code "
                             "spans executed and deleted.")
    parser.add_argument("--ttl", default=os.environ.get("REGISTER_TTL", ""),
                        help="e.g. 72h, 7d, or n/a (or set REGISTER_TTL)")
    parser.add_argument("--co-owner", action="append",
                        default=[c for c in
                                 os.environ.get("REGISTER_CO_OWNERS", "").split("\n")
                                 if c.strip()],
                        metavar="ID[:note]",
                        help="another body that worked this lane; repeatable")
    parser.add_argument("--scope-file",
                        default=os.environ.get("REGISTER_SCOPE_FILE", ""),
                        help="read the scope prose from a FILE. The most "
                             "robust option and the one to reach for with long "
                             "rows: prose never becomes part of a command "
                             "string, so nothing downstream can expand, "
                             "substitute or pattern-match against it. "
                             "(A register row quoting an ordinary path fragment "
                             "was refused by the damage-control hook, which "
                             "matches literal strings anywhere in a command -- "
                             "including inside prose.)")
    parser.add_argument(
        "--i-have-coordinated", action="store_true",
        help="proceed with a UNILATERAL co-owner declaration -- a lane whose "
             "incumbent has NOT named you back. The hook asks a human at this "
             "point; a CLI has nobody to ask, so it refuses unless you say so "
             "here. Without this flag the sanctioned path would be the one "
             "route that skips the question, which is how a gate becomes "
             "theatre.")
    parser.add_argument(
        "--literal-assignments", action="store_true",
        help="proceed when the prose QUOTES empty assignments as evidence "
             "(e.g. 'env.tier-ui had empty SUPABASE_ANON_KEY= entries') -- "
             "the one legitimate use of the swallowed-expansion signature. "
             "Does NOT waive the compose-chain or long-token symptoms.")
    parser.add_argument(
        "--all-lanes", action="store_true",
        help="RELEASE mode: close EVERY lane this owner holds. The register's "
             "convention for a full handoff -- 142 rows already use it -- and "
             "from now on it must be asked for. It used to be what you got by "
             "leaving --branch off.")
    parser.add_argument("--baton-from",
                        default=os.environ.get("REGISTER_BATON_FROM", ""),
                        metavar="HOLDER",
                        help="RELEASE mode: pass or close lanes HELD BY THIS "
                             "PEER (a registered identity), not your own. "
                             "Needs --branch and one of --ruling/--handoff. "
                             "(or set REGISTER_BATON_FROM)")
    parser.add_argument("--baton-to",
                        default=os.environ.get("REGISTER_BATON_TO", ""),
                        metavar="RECEIVER",
                        help="NOTE mode: make this note a baton GRANT to this "
                             "registered identity. Needs --branch; an operator "
                             "grant also needs --baton-from <holder>. "
                             "(or set REGISTER_BATON_TO)")
    parser.add_argument("--ruling", default=os.environ.get("REGISTER_RULING", ""),
                        help="baton authority: the TIMESTAMP of a committed "
                             "grant NOTE signed by an operator identity "
                             "(or set REGISTER_RULING)")
    parser.add_argument("--handoff", default=os.environ.get("REGISTER_HANDOFF", ""),
                        help="baton authority: the TIMESTAMP of a committed "
                             "grant NOTE signed by the holder "
                             "(or set REGISTER_HANDOFF)")
    parser.add_argument("--dry-run", action="store_true",
                        help="render and check the row, write nothing")
    args = parser.parse_args(argv)

    if args.kind == "sync":
        repo = Path(args.repo).resolve() if args.repo else REPO_ROOT
        try:
            if args.reapply:
                if args.hold:
                    raise SyncRefused("--hold and --reapply are opposite halves "
                                      "of the sequence; name one")
                return reapply_sidecar(repo, Path(args.reapply), args.ref, args.apply,
                                       coordinated=args.i_have_coordinated)
            return sync_register(repo, args.ref, args.apply, args.hold)
        except SyncLaneHeld as exc:
            print(f"register-sync: refusing - {exc}.", file=sys.stderr)
            return EXIT_REFUSED
        except SyncRefused as exc:
            print(f"register-sync: NOT MEASURED - {exc}.", file=sys.stderr)
            return EXIT_UNMEASURED

    if args.kind == "docs":
        if not args.anchor or not args.text_file:
            print("register-append: docs mode needs --anchor and --text-file",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        block = Path(args.text_file).read_text(encoding="utf-8")
        try:
            assert_prose_clean(block,
                               literal_assignments=args.literal_assignments)
        except ValueError as exc:
            print(f"register-append: refusing - {exc}", file=sys.stderr)
            return EXIT_REFUSED
        return insert_docs(args.anchor, block)

    if args.kind == "amend":
        if not args.branch or not args.co_owner:
            print("register-append: amend needs --branch and at least one "
                  "--co-owner (or CO_OWNER= via make).", file=sys.stderr)
            return EXIT_UNMEASURED
        if not args.owner:
            print("register-append: amend needs --owner or REGISTER_OWNER: it "
                  "only ever edits a row filed by that identity.",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        if not REGISTER.is_file():
            print(f"register-append: NOT MEASURED - no register at {REGISTER}",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        try:
            gate = _load_gate()
        except Exception as exc:  # noqa: BLE001 -- report, never guess
            print("register-append: NOT MEASURED - the collision gate could not "
                  f"be loaded ({exc}); the row could not be located.",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        return amend_co_owners(args.owner, args.branch, args.co_owner, gate=gate)

    if args.scope_file:
        args.scope = Path(args.scope_file).read_text(encoding="utf-8").strip()

    if not args.owner:
        print("register-append: no --owner and no REGISTER_OWNER. The row must "
              "say who filed it.", file=sys.stderr)
        return EXIT_UNMEASURED
    if not args.scope.strip():
        print("register-append: --scope is required. A row that records no "
              "scope records nothing.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "claim" and not args.branch:
        print("register-append: a CLAIM must name --branch. Without a lane the "
              "collision gate has nothing to compare, and the claim is "
              "unenforceable -- 78 rows in this register are already in that "
              "state.", file=sys.stderr)
        return EXIT_UNMEASURED
    # AN UNTARGETED DESTRUCTIVE ACTION REFUSES; IT DOES NOT BROADEN.
    #
    # `open_claims_in()` closes EVERY lane an owner holds when a RELEASE names
    # none, and that reading must stay -- 142 rows in the live register are
    # filed that way and reinterpreting them would reopen years of closed work.
    # What changes is the WRITE path: omission is no longer how you ask for it.
    #
    # This is the second half of the trap the `note` kind opens the door out of.
    # With no way to record a fact, a correction had to be filed as a release;
    # a release with no lane closes everything; so a footnote could empty a
    # node's whole workload while reading like a comment. Observed live, and
    # harmless only because that owner had nothing open at the time.
    #
    # EXIT 3, NOT 1, and the choice is deliberate. In this tool exit 1 means
    # "another owner holds your lane" -- a fact about the register. Nothing was
    # measured here: the invocation is under-specified, exactly like a CLAIM
    # naming no branch, which has always been 3.
    if args.kind == "release" and not args.branch and not args.all_lanes:
        print("register-append: refusing - a RELEASE naming no lane closes "
              "EVERY lane `" + args.owner + "` holds, and nothing in this "
              "command says that was the intention.\n"
              "  To close one lane:      --branch <lane>   (usually what you "
              "want)\n"
              "  To close ALL your lanes: --all-lanes       (a full handoff, "
              "stated on purpose)\n"
              "  To record a FACT without closing anything: file a `note` "
              "instead -- `make -C pmoves register-note`.\n"
              "Nothing was written.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "release" and args.branch and args.all_lanes:
        print("register-append: NOT MEASURED - --branch names one lane and "
              "--all-lanes closes every lane. Both cannot be the instruction, "
              "and guessing which you meant is how a release closes work "
              "nobody asked it to. Nothing was written.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "release" and args.baton_from and args.all_lanes:
        print("register-append: refusing - --all-lanes closes everything the "
              "SIGNER holds, and --baton-from passes a PEER's named lanes. A "
              "baton is never bare: name each lane with --branch. Nothing was "
              "written.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "note" and args.all_lanes:
        print("register-append: NOT MEASURED - --all-lanes is a RELEASE flag. "
              "A NOTE closes nothing by construction.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "note" and args.ttl:
        print("register-append: a NOTE takes no --ttl. A TTL is a promise to "
              "release a lane by a deadline, and a note holds no lane; an "
              "expiring footnote would be read as an overdue claim.",
              file=sys.stderr)
        return EXIT_UNMEASURED

    # CONTENT REFUSAL, before any lane comparison. A scope that absorbed a
    # shell or Make expansion is uncorrectable once appended, so it is refused
    # on its own text regardless of how it arrived (--scope, the environment,
    # or --scope-file all resolve to this one string). Exit 1: this is a
    # finding, not a measurement failure -- and never exit 3, which would let
    # a filer read "could not measure" as "nothing was found".
    try:
        assert_prose_clean(args.scope,
                           literal_assignments=args.literal_assignments)
    except ValueError as exc:
        print(f"register-append: refusing - {exc}", file=sys.stderr)
        return EXIT_REFUSED

    try:
        row = build_row(
            kind=args.kind.upper(),
            owner=args.owner,
            branch=args.branch,
            scope=args.scope.strip(),
            ttl=args.ttl,
            co_owners=args.co_owner,
            baton_from=args.baton_from,
            ruling=args.ruling,
            handoff=args.handoff,
            baton_to=args.baton_to,
        )
    except ValueError as exc:
        print(f"register-append: refusing - {exc}", file=sys.stderr)
        return EXIT_UNMEASURED

    if not REGISTER.is_file():
        print(f"register-append: NOT MEASURED - no register at {REGISTER}",
              file=sys.stderr)
        return EXIT_UNMEASURED

    try:
        gate = _load_gate()
    except Exception as exc:  # noqa: BLE001 -- report, never guess
        print("register-append: NOT MEASURED - the collision gate could not be "
              f"loaded ({exc}), so this row was NOT checked against the open "
              "lanes. Refusing rather than appending unchecked.", file=sys.stderr)
        return EXIT_UNMEASURED

    if args.kind == "note" and (args.baton_to or args.baton_from):
        problem = grant_refusal(gate, args.owner, args.baton_from, args.baton_to)
        if problem:
            print(f"register-append: refusing - {problem}. Nothing was written.",
                  file=sys.stderr)
            return EXIT_UNMEASURED

    if args.kind == "note":
        if args.dry_run:
            sys.stdout.write(row)
            print("register-append: dry run - rendered, not written.",
                  file=sys.stderr)
            return EXIT_OK
        rc = append_note(row, gate, REGISTER)
        if rc == EXIT_OK:
            _warn_if_invisible(REGISTER)
        return rc

    # THE WHOLE TRANSACTION, UNDER ONE LOCK. Reading the register, deciding,
    # and appending are one operation or they are a race: two filers can both
    # read a free lane and both append to it, which is two owners on one lane
    # produced by the tool written to prevent exactly that.
    with register_lock(REGISTER):
        existing = REGISTER.read_text(encoding="utf-8", errors="replace")
        # WRAPPED, and the wrapping is the fix for a defect this tool shipped.
        # `evaluate_claims` used to be called bare. When the gate's return type
        # widened from 2 categories to a verdict object, this line raised
        # `ValueError: too many values to unpack` -- an UNCAUGHT traceback, exit 1.
        # Exit 1 in this tool's own doctrine means "refused: the lane is held by
        # another owner", so a crash was indistinguishable from a legitimate refusal
        # by exit code alone, in the one tool the fleet has when the Bash path
        # denies and there is no Write tool. A crash must never be able to wear a
        # refusal's exit code; could-not-measure (3) is what it is.
        try:
            verdict = gate.evaluate_claims(row, gate.open_claims_in(existing))
        except Exception as exc:  # noqa: BLE001 -- report, never guess
            print("register-append: NOT MEASURED - the collision gate raised "
                  f"{type(exc).__name__}: {exc}. The row was NOT checked against "
                  "the open lanes and was NOT written. This is a crash, not a "
                  "refusal -- exit 3, never 1.", file=sys.stderr)
            return EXIT_UNMEASURED

        if verdict.collisions:
            print("register-append: refusing to add a CLAIM for a lane another "
                  "owner holds.", file=sys.stderr)
            for lane, other, lineno in verdict.collisions:
                print(f"  - lane `{lane}` is already claimed by `{other}` "
                      f"(open CLAIM at line {lineno})", file=sys.stderr)
            print("Either coordinate a handoff, wait for their RELEASE, or pick a "
                  "different branch (see Village Rule in AGNOTE4482PHI.t1.md).",
                  file=sys.stderr)
            return EXIT_REFUSED

        # A CONSENTED SHARE IS ALLOWED AND ANNOUNCED. An allow that prints nothing
        # cannot be told apart from a gate that did not run.
        for lane, other, lineno in verdict.shared:
            print(f"register-append: SHARED LANE - `{lane}` is held by `{other}` "
                  f"(open CLAIM at line {lineno}), whose own row declares this "
                  "claimant as a co-owner. Allowing: the incumbent declared it.",
                  file=sys.stderr)

        # UNILATERAL. The hook emits `permissionDecision: "ask"` here and a human
        # answers. This tool has nobody to ask, so it refuses and names the flag
        # that answers the question -- rather than being the one path on which the
        # question is never put.
        if verdict.one_sided and not args.i_have_coordinated:
            print("register-append: refusing - this row does not collide only "
                  "because of something IT declares. Nobody on the other side has "
                  "said so:", file=sys.stderr)
            for owner, lane, other, lineno, witnesses in verdict.one_sided:
                print(f"  - `{owner}` claims lane `{lane}`, held by `{other}` "
                      f"(open CLAIM at line {lineno}); `{other}`'s open row does "
                      f"not declare `{owner}` back, so the sharing is UNILATERAL "
                      f"(shared participants: {', '.join(witnesses)}).",
                      file=sys.stderr)
            print("If you have coordinated -- or the incumbent is offline and you "
                  "are picking the lane up -- re-run with --i-have-coordinated. "
                  "The incumbent's own reciprocation is "
                  "`make -C pmoves register-amend`.", file=sys.stderr)
            return EXIT_REFUSED

        if verdict.unreadable_co_owners:
            print("register-append: NOT MEASURED - this row declares `co-owners:` "
                  "and names none the parser can read, so the shared-lane check ran "
                  "WITHOUT them. Write each ID in backticks.", file=sys.stderr)
            return EXIT_UNMEASURED

        if verdict.unkeyed:
            for owner in verdict.unkeyed:
                print(f"register-append: NOT MEASURED - CLAIM by `{owner}` names no "
                      "branch the gate can read, so no lane was compared.",
                      file=sys.stderr)
            return EXIT_UNMEASURED

        if args.kind == "release":
            rc = _check_release_reading(row, existing, args, gate)
            if rc is not None:
                return rc

        if args.dry_run:
            sys.stdout.write(row)
            print("register-append: dry run - checked, not written.", file=sys.stderr)
            return EXIT_OK

        append_row(row, REGISTER)
        print(row.rstrip("\n"))
        try:
            where = REGISTER.relative_to(REPO_ROOT)
        except ValueError:
            where = REGISTER
        print(f"register-append: appended to {where}", file=sys.stderr)
        _warn_if_invisible(REGISTER)
        return EXIT_OK


def _check_release_reading(row: str, existing: str, args, gate):
    """Make the gate's READING of a RELEASE match what the filer asked for.

    Returns an exit code to stop with, or None to proceed. Checked by parsing
    the rendered row with the same pairing every reader uses, not by trusting
    the flags -- the row is what the fleet will read, not the command line.
    """
    declared = gate.baton_declared(row)
    if not args.baton_from:
        if declared:
            print("register-append: refusing - this RELEASE's scope DECLARES a "
                  "`baton-from:` field, so every reader would treat it as a "
                  "baton. Quote the grammar inside a code span, or pass "
                  "--baton-from with its authority. Nothing was written.",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        return None
    problem = baton_refusal(gate, args.owner, args.baton_from)
    if problem:
        print(f"register-append: refusing - {problem}. Nothing was written.",
              file=sys.stderr)
        return EXIT_UNMEASURED
    ledger = existing if not existing or existing.endswith("\n") else existing + "\n"
    events = gate.baton_events_in(ledger + row)
    event = events[-1] if events else None
    if event is None or event.problem:
        print("register-append: NOT MEASURED - the rendered row does not read "
              "back as a valid baton ("
              + (event.problem if event else "no baton event") + "). "
              "Nothing was written.", file=sys.stderr)
        return EXIT_UNMEASURED
    # COMMITTED. The reader resolved the grant in the working register; the
    # write road additionally requires that exact row to be on origin/main,
    # i.e. merged after review. A grant in a working tree is a claim of
    # authority, not authority.
    grant_row = ledger.split("\n")[event.grant_line - 1]
    committed = _committed_register_text()
    if committed is None:
        print("register-append: NOT MEASURED - git could not show the register "
              "on origin/main, so the grant could not be confirmed as "
              "committed. Nothing was written.", file=sys.stderr)
        return EXIT_UNMEASURED
    if grant_row not in committed.split("\n"):
        print(f"register-append: refusing - the grant `{event.authority[1]}` "
              f"(line {event.grant_line}) is not on origin/main. Merge the grant "
              "NOTE first (and `git fetch origin main`), then file the baton. "
              "Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    # The reader closes every lane-shaped token on a RELEASE row, scope prose
    # included -- that is the register's long-standing convention and the
    # reader keeps it. The WRITE road is narrower: a baton closes the lane in
    # --branch and nothing a sentence in the scope happens to mention.
    extra = event.closed - {args.branch}
    if extra:
        print("register-append: refusing - the scope names "
              + ", ".join(f"`{x}`" for x in sorted(extra))
              + f", which `{event.holder}` also holds, so every reader would "
              "close it too. One baton row, one lane: drop it from the scope "
              "and pass each lane as its own row. "
              "Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    if not event.closed:
        print(f"register-append: WARNING - {event.warning}", file=sys.stderr)
        print("register-append: refusing - a baton that closes nothing "
              "records nothing. `make -C pmoves register-status` lists the "
              "lanes that peer actually holds. Nothing was written.",
              file=sys.stderr)
        return EXIT_REFUSED
    print("register-append: BATON - `" + args.owner + "` closes "
          + ", ".join(f"`{x}`" for x in sorted(event.closed))
          + f" held by `{event.holder}` ({event.authority[0]}: "
          f"{event.authority[1]})", file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    """Dispatch, translating a lock timeout into could-not-measure.

    `LockUnavailable` means the transaction never ran: nothing was read against
    the open lanes and nothing was written. That is exit 3. It must never
    become exit 1, which in this tool means "another owner holds your lane" --
    a filer who backs off on that reading has been told a fact about the
    register that was never established.
    """
    try:
        return _dispatch(argv)
    except LockUnavailable as exc:
        print(f"register-append: NOT MEASURED - {exc}.", file=sys.stderr)
        return EXIT_UNMEASURED


def _guarded(argv=None) -> int:
    """Run main(), and never let an unexpected exception exit 1.

    The exit codes are a CONTRACT here -- 0 appended / 1 the lane is held / 3
    could not measure -- and python's default for an uncaught exception is 1.
    That collapses "this tool crashed" into "another owner holds your lane",
    which is the fleet's signature defect appearing inside the tool built to
    prevent it. A traceback is could-not-measure, and it is printed in full.
    """
    try:
        return main(argv)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 -- the whole point is to not exit 1
        import traceback
        traceback.print_exc()
        print("register-append: NOT MEASURED - this tool crashed (traceback "
              "above). Nothing was written. Exit 3, NOT 1: a crash must not be "
              "indistinguishable from 'refused, the lane is held'.",
              file=sys.stderr)
        return EXIT_UNMEASURED


if __name__ == "__main__":
    sys.exit(_guarded())
