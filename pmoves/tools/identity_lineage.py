#!/usr/bin/env python3
"""Resolve claim-register author strings, and the lineage edges the register lacks.

The register records who did what, in free text. 331 entries, 49 distinct author
strings, ~13 identities. Three things it cannot express have each been worked
around by editing history in place:

    attribution correction   the recorded author was wrong        (6 entries)
    key drift                one identity, several spellings       (1 annotated)
    succession               identity A became identity B          (0 -- encoded
                             as an ARROW inside the author field, 8 entries)

This module gives each an addressable form, reading
`pmoves/config/identity_vocabulary.yaml`. It never rewrites the register: a
correction preserves `recorded_as`, which the in-place edits destroyed.

CLI:
    python pmoves/tools/identity_lineage.py --census      # spellings per identity
    python pmoves/tools/identity_lineage.py --verify      # the gate
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCABULARY_PATH = REPO_ROOT / "pmoves" / "config" / "identity_vocabulary.yaml"
REGISTER_PATH = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
SIGNATURES_PATH = REPO_ROOT / "pmoves" / "config" / "agent_signatures.yaml"

# `- `<ts>` <KIND> `<author>`` -- the register's entry grammar.
#
# THE AUDIT SURFACE MUST NOT BE NARROWER THAN THE ENFORCEMENT SURFACE. This
# used to require a bare `[0-9TZ:\-]+` timestamp at column 0, while the
# collision hook's CLAIM_RE/RELEASE_RE match anywhere on any line. Measured on
# the live register, 10 rows the GATE treats as claims were invisible here: 6
# carry fractional seconds or a UTC offset (`...:35.7340973-05:00`) and 2 are
# indented. That gap was a reporting nicety until `co-owners:` existed; now a
# field on such a row can GRANT PARTICIPATION and suppress a collision while
# being unreachable by `--verify`, `--co-owners` and `unmeasured_rows()` -- an
# unaudited participant grant. So: allow leading whitespace, and `.`/`+` in the
# timestamp. Measured effect: 404 -> 415 entries, 11 newly visible, all real.
ENTRY = re.compile(r"^[ \t]*- `([0-9TZ:.+\-]+)` ([A-Z+]+) `([^`]+)`", re.M)
CORRECTION = re.compile(r"\[CORRECTION ([^\]]*)\]")

# An identity written as `BASE (parenthetical)`. The parenthetical carries a
# model, a lane/alter, or a node -- three fields in one free-text slot.
SPLIT = re.compile(r"^([^(]+?)\s*\((.*)\)\s*$")

NON_IDENTITY_KINDS = frozenset({"unresolved"})

# ---------------------------------------------------------------------------
# CO-OWNERS -- every body that worked a lane, not only the one that signed it.
#
# The row grammar above captures exactly ONE backticked author, so a lane worked
# by several bodies could only ever be attributed to one of them. The register
# has been working around that in prose for months, and the workarounds are the
# evidence the field is needed:
#
#   * `Three-body: delivery=..., control=..., memory=...` -- 198 rows. Already
#     key=value, already names three agents, and parses as nothing.
#   * `Cross-node review team (4090 + SPARK + DARKXSIDE) acknowledged` (L797)
#     and `Cross-node team formed for review: 4090-CLAUDE + SPARK` (L772).
#   * `(assisting CRUSH-GLM52 claim at L1256)` (L1415) -- an assisting agent
#     cross-referencing its primary by LINE NUMBER, in an APPEND-ONLY file where
#     line numbers shift under every later entry.
#
# So this is not a new ceremony. It is the existing practice, given a grammar.
#
# THE FIELD RIDES THE HEADER SEGMENT THE REGISTER ALREADY GREW: nine rows carry
# ``branch: `x` * **TTL ...** * scope: ...`` before their prose. `co-owners:`
# sits in the same place and reads the same way. It may also appear inside the
# scope prose -- the parser is position-independent, because requiring a
# position would invalidate rows people will write either way.
#
# BACKWARD COMPATIBILITY IS STRUCTURAL, NOT PROMISED: a row with no marker never
# enters this code path and yields an empty list, which is byte-for-byte what
# every row does today. Nothing needs rewriting and no existing row changes
# meaning.
#
# THE BACKTICKS DELIMIT THE ID; THE PARENTHETICAL AFTER THEM IS THE
# CONTRIBUTION. This matters because identities ALREADY carry parentheticals --
# `B850-CLAUDE (Knuckles)` is one identity string, not an ID plus a note. Put
# the ID inside backticks and that ambiguity cannot arise:
#
#   co-owners: `B850-CLAUDE (Knuckles)` (posted the cross-node correction)
#              ^--------- identity ---^  ^------- contribution -------^
# ---------------------------------------------------------------------------

# Shaped after BRANCH_MARKER_RE in claim-collision-pre.py
# (`\bbranch\b[:=]?\s*`) with ONE deliberate difference: the `:` or `=` is
# REQUIRED here, where `branch` makes it optional.
#
# The reason is measured, not stylistic. `branch` could afford optional
# punctuation because ``Branch `x`` was already in the wild before the marker
# existed and the regex had to accept history. `co-owners` is a new field, so it
# gets to set its own terms -- and it needs to, because the WORD occurs in
# ordinary prose in a way `branch` does not. This lane's own CLAIM row contains
# "keys on PARTICIPANTS (owner U co-owners) intersected with the LANE", which an
# optional-punctuation marker read as a field declaration and then reported as
# an unreadable one. Found by running the gate, on its second live run, against
# the row that introduced the field.
#
# So: `co-owners:` and `co_owners =` declare the field; the bare noun never
# does. Spelling variants are folded because the register's own history is a
# catalogue of one thing written several ways.
CO_OWNER_MARKER = re.compile(r"\bco[-_ ]?owners?\b\s*[:=]\s*", re.IGNORECASE)

# One item: a backticked ID, optionally followed by a parenthetical note. The
# note admits ONE level of nested parens, because a real contribution note reads
# "cross-node correction (false positive)" often enough to matter.
_CO_OWNER_ITEM = re.compile(
    r"`([^`]+)`(?:\s*\(((?:[^()]|\([^()]*\))*)\))?"
)

# Items are separated by commas and whitespace ONLY. Deliberately NOT the `*`
# field separator: consuming it would let the parser walk out of its own field
# and into the next one, and a scope that happens to open with a backticked
# token would then be read as a co-owner. The field must end where it ends.
_CO_OWNER_SEP = re.compile(r"[,\s]*")


def _code_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every Markdown code span, matched by BACKTICK RUN LENGTH.

    This replaced a parity test -- "an odd number of backticks before `pos`
    means `pos` is inside a span" -- which was documented as failing toward a
    loud false "could not measure". Measured, it failed the other way, in both
    directions, and silently:

      * a ``...`` example is EVEN, so a marker inside one read as real usage. A
        row that merely DOCUMENTS the grammar (``co-owners: `X` (note)``)
        parsed as a successful declaration and could suppress a real collision.
        A silent grant produced by documentation, in a file whose whole subject
        is its own governance.
      * an unbalanced backtick earlier in a row flipped parity for everything
        after it, so a GENUINE field read as being inside a span and was
        dropped -- and dropped is not reported as unmeasured, so the
        attribution vanished from --co-owners and --verify with no signal. That
        is "satisfies a human reader, empty to every machine", which is the
        defect the field exists to remove.

    Run-length matching is the CommonMark rule and it fixes both: a run of N
    backticks opens a span that only a later run of exactly N closes, and a run
    that is never closed is not a span at all. It is ~20 lines and no more a
    Markdown parser than the parity test was -- the earlier note calling the
    alternative "a Markdown inline parser in a governance gate" overestimated
    the cost of the correct rule and underestimated the failure.
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "`":
            i += 1
            continue
        j = i
        while j < n and text[j] == "`":
            j += 1
        run = j - i
        k = j
        while k < n:
            if text[k] != "`":
                k += 1
                continue
            e = k
            while e < n and text[e] == "`":
                e += 1
            if e - k == run:
                spans.append((i, e))
                i = e
                break
            k = e
        else:
            # Unterminated run: not a span. Everything after it stays outside,
            # instead of the rest of the row flipping polarity.
            i = j
    return spans


def _in_code_span(text: str, pos: int) -> bool:
    """True when `pos` falls inside a Markdown backtick span.

    FOUND BY THE GATE, ON ITS FIRST LIVE RUN, AGAINST THIS LANE'S OWN CLAIM ROW.
    That row DESCRIBES the field -- it contains the phrase "a `co-owners:` field
    carrying backticked IDs" -- and the marker matched the mention, so a row
    that declares no co-owners at all was reported as an unreadable attribution.

    A row that TALKS ABOUT the field is not a row that USES it, and the register
    is a document about its own governance: rows describing the grammar are
    normal here, not exotic. Without this the very first row to explain the
    field would have been the first row to fail the gate.
    """
    return any(start <= pos < end for start, end in _code_spans(text))


def _co_owner_markers(text: str) -> list[int]:
    """End offsets of every `co-owners` marker that is NOT a code-span mention."""
    spans = _code_spans(text)
    return [
        m.end() for m in CO_OWNER_MARKER.finditer(text)
        if not any(start <= m.start() < end for start, end in spans)
    ]


def co_owners_in(text: str) -> list[tuple[str, str]]:
    """[(id_as_written, contribution)] declared by a `co-owners:` field.

    Empty when the row declares no co-owners -- which is every row written
    before this field existed, and is why adding it changes nothing for them.

    Parsing stops at the first token that is not a backticked ID, so the field
    terminates naturally at ` * `, at `scope:`, or at end of line without
    needing a closing delimiter nobody would remember to write.
    """
    # EVERY marker is tried, not just the first. A row may describe the field
    # and then use it -- this lane's own RELEASE does exactly that -- and
    # stopping at the first marker would read the description and miss the data.
    for start in _co_owner_markers(text):
        pos = start
        found: list[tuple[str, str]] = []
        while True:
            pos = _CO_OWNER_SEP.match(text, pos).end()
            item = _CO_OWNER_ITEM.match(text, pos)
            if not item:
                break
            identity = item.group(1).strip()
            if identity:
                found.append((identity, (item.group(2) or "").strip()))
            pos = item.end()
        if found:
            return found
    return []


def co_owner_field_is_unparseable(text: str) -> bool:
    """True when a row ANNOUNCES co-owners and names none the parser can read.

    This is the "could not measure" case and it must be loud. A row like
    `co-owners: 4090 and SPARK` (no backticks) looks attributed to a human and
    is empty to a machine -- exactly the failure this whole field exists to
    remove, reintroduced one layer down. Reporting it as `[]` would be
    indistinguishable from a row that simply has no co-owners, so the two are
    kept apart here rather than silently merged.
    """
    return bool(_co_owner_markers(text)) and not co_owners_in(text)


@dataclass(frozen=True)
class Identity:
    canonical: str
    kind: str
    node: str | None
    aliases: tuple[str, ...]

    @property
    def is_resolvable(self) -> bool:
        return self.kind not in NON_IDENTITY_KINDS


@dataclass
class Vocabulary:
    index: dict[str, Identity] = field(default_factory=dict)
    corrections: list[dict] = field(default_factory=list)
    successions: list[dict] = field(default_factory=list)


def _norm(raw: Any) -> str:
    """Fold an author string for lookup. Arrow forms are normalised so the
    unicode `→` and the ascii `->` are one key, not two."""
    text = str(raw).strip().replace("→", "->")
    return " ".join(text.split()).casefold()


def split_author(author: str) -> tuple[str, str]:
    """`BASE (paren)` -> (base, paren). Returns ('', ...) never; paren may be ''."""
    match = SPLIT.match(author.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return author.strip(), ""


def _vocabulary_path() -> Path:
    return Path(os.environ.get("PMOVES_IDENTITY_VOCABULARY") or VOCABULARY_PATH)


def load_vocabulary(path: Path | None = None) -> Vocabulary:
    # PMOVES_IDENTITY_VOCABULARY lets a caller point at a different file --
    # used by the claim-collision hook's fail-safe test to simulate the
    # vocabulary being absent. Without a real override the test could only
    # assert the fallback by mocking, which would test the mock.
    path = path or Path(os.environ.get("PMOVES_IDENTITY_VOCABULARY")
                        or VOCABULARY_PATH)
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    vocab = Vocabulary(
        corrections=list(doc.get("corrections") or []),
        successions=list(doc.get("successions") or []),
    )
    for entry in doc.get("identities") or []:
        canonical = str(entry["canonical"])
        identity = Identity(
            canonical=canonical,
            kind=entry.get("kind", "identity"),
            node=entry.get("node"),
            aliases=tuple(str(a) for a in (entry.get("aliases") or [canonical])),
        )
        for alias in (*identity.aliases, canonical):
            key = _norm(alias)
            existing = vocab.index.get(key)
            if existing is not None and existing.canonical != canonical:
                raise ValueError(
                    f"alias {alias!r} is claimed by both {existing.canonical!r} "
                    f"and {canonical!r} -- an alias must name exactly one identity"
                )
            vocab.index[key] = identity
    return vocab


def canonical_identity(author: str, vocab: Vocabulary | None = None) -> str | None:
    """Canonical identity for any author string, or None if undeclared.

    Matches the whole string first, then the base with the parenthetical
    stripped -- so a new model or lane in the parenthetical does NOT create an
    unknown identity, which is the drift that broke the collision hook.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    for candidate in (author, split_author(author)[0]):
        found = vocab.index.get(_norm(candidate))
        if found:
            return found.canonical
    return None


def read_register(path: Path | None = None) -> str:
    """The register contains a NUL byte and other control characters, so it must
    be read with errors='replace'. `grep` classifies it as binary and stops
    printing after its first match -- do not audit this file with grep."""
    path = path or REGISTER_PATH
    return path.read_text(encoding="utf-8", errors="replace")


def register_entries(text: str | None = None) -> list[tuple[str, str, str]]:
    """(timestamp, kind, author) for every CLAIM/RELEASE/UPDATE line."""
    return ENTRY.findall(text if text is not None else read_register())


def entry_lines(text: str | None = None) -> list[tuple[int, str]]:
    """(1-based line number, line) for every row matching the entry grammar.

    `split("\n")`, NOT `splitlines()`, for the same reason the collision hook
    spells it that way: the register carries vertical-tab and form-feed
    characters that `splitlines()` breaks on and grep, sed and every editor do
    not, so the two disagree by a growing offset that lands hardest on the
    NEWEST entries -- the ones any message points at.
    """
    text = text if text is not None else read_register()
    return [
        (lineno, line)
        for lineno, line in enumerate(text.split("\n"), start=1)
        if ENTRY.match(line)
    ]


def co_owner_attribution(
    text: str | None = None,
) -> list[tuple[int, str, str, list[tuple[str, str]]]]:
    """(lineno, kind, owner, [(co-owner, contribution)]) for rows declaring one.

    This is the query the register could not answer before: "which bodies worked
    this lane", as data rather than as prose a person has to read.
    """
    text = text if text is not None else read_register()
    out = []
    for lineno, line in entry_lines(text):
        co = co_owners_in(line)
        if not co:
            continue
        _, kind, owner = ENTRY.match(line).groups()
        out.append((lineno, kind, owner, co))
    return out


def unmeasured_rows(text: str | None = None) -> list[tuple[int, str]]:
    """Rows that ANNOUNCE co-owners and name none a machine can read.

    Kept separate from findings on purpose. A finding is "I looked and this is
    wrong"; this is "I could not look". Collapsing the two lets a row that
    defeated the parser be reported as clean, which is the failure mode this
    whole lane exists to remove -- an attribution that satisfies a human reader
    and is empty to every machine.
    """
    text = text if text is not None else read_register()
    return [
        (lineno, ENTRY.match(line).group(3))
        for lineno, line in entry_lines(text)
        if co_owner_field_is_unparseable(line)
    ]


def undeclared_authors(
    entries: list[tuple[str, str, str]] | None = None,
    vocab: Vocabulary | None = None,
) -> dict[str, int]:
    """Author strings that resolve to no declared identity, with their counts."""
    vocab = vocab if vocab is not None else load_vocabulary()
    entries = entries if entries is not None else register_entries()
    missing: dict[str, int] = {}
    for _, _, author in entries:
        if canonical_identity(author, vocab) is None:
            missing[author] = missing.get(author, 0) + 1
    return missing


def correction_for(
    timestamp: str, kind: str, author: str | None = None,
    vocab: Vocabulary | None = None,
) -> dict | None:
    """The correction for one entry, or None.

    (timestamp, kind) is NOT unique in the register -- two different authors
    share `2026-03-04T20:50:26-05:00 CLAIM`. Without `author` this returned
    one entry's correction for the other's row. When `author` is given it
    must canonicalise to the correction's `actual`, since the register line
    already carries the corrected name.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    for record in vocab.corrections:
        entry = record.get("entry") or {}
        if entry.get("timestamp") != timestamp or entry.get("kind") != kind:
            continue
        if author is not None and record.get("corrects", "authorship") == "authorship":
            # Only an authorship correction carries `actual`. A correction of a
            # measurement or a count has no identity to compare against, so
            # matching on one would reject every non-authorship record.
            if canonical_identity(author, vocab) != record.get("actual"):
                continue
        return record
    return None


def resolve_author(
    timestamp: str, kind: str, author: str, vocab: Vocabulary | None = None
) -> tuple[str | None, str]:
    """(canonical_identity, provenance) for one register entry.

    A corrected entry resolves to its corrected author AND says so, naming what
    the register originally recorded. That is the whole point: the repair is
    visible rather than laundered into the line.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    record = correction_for(timestamp, kind, author, vocab)
    if record is not None:
        return record["actual"], (
            f"corrected {record.get('asserted_on', '?')}: register recorded "
            f"{record['recorded_as']!r}; {record.get('reason', 'no reason given')} "
            f"[{record.get('evidence', 'no evidence cited')}]"
        )
    canonical = canonical_identity(author, vocab)
    if canonical is None:
        return None, f"author {author!r} resolves to no declared identity"
    identity = vocab.index[_norm(canonical)]
    if not identity.is_resolvable:
        # Declared, and deliberately NOT collapsed to a real identity. Saying
        # "this is ambiguous and here is why" is the honest answer; picking an
        # endpoint would launder an open question into a fact.
        return canonical, (
            f"{author!r} is declared AMBIGUOUS (kind={identity.kind}) -- it "
            f"resolves to a marker, not to an identity, and needs an operator "
            f"decision before it can be attributed"
        )
    return canonical, f"as recorded ({author!r})"


def successors(identity: str, vocab: Vocabulary | None = None) -> list[dict]:
    vocab = vocab if vocab is not None else load_vocabulary()
    return [s for s in vocab.successions if s.get("from") == identity]


def predecessors(identity: str, vocab: Vocabulary | None = None) -> list[dict]:
    vocab = vocab if vocab is not None else load_vocabulary()
    return [s for s in vocab.successions if s.get("to") == identity]


# An inline code span. A register entry that DESCRIBES the correction
# convention writes it in backticks -- as this module's own docstring does one
# line down -- and a substring test cannot tell that apart from an entry that
# USES it. B850's 2026-08-25T15:00:00Z entry surveys "six hand-edited
# `[CORRECTION ...]` annotations" and was counted as a seventh, which failed
# both the count assertion and the register-clean gate. Stripping code spans
# first is the discriminator: an actual annotation is written bare, in bold.
CODE_SPAN = re.compile(r"`[^`]*`")


def annotated_corrections(text: str | None = None) -> list[tuple[str, str, str]]:
    """Register entries carrying a prose `[CORRECTION ...]` annotation.

    Mentions inside inline code spans do not count -- writing about the
    convention is not using it.
    """
    text = text if text is not None else read_register()
    out = []
    for line in text.splitlines():
        if "[CORRECTION" not in CODE_SPAN.sub("", line):
            continue
        match = ENTRY.match(line)
        if match:
            out.append(match.groups())
    return out


def verify(vocab: Vocabulary | None = None) -> list[str]:
    """The gate. Returns findings; empty means clean."""
    vocab = vocab if vocab is not None else load_vocabulary()
    text = read_register()
    entries = register_entries(text)
    findings: list[str] = []

    missing = undeclared_authors(entries, vocab)
    for author, count in sorted(missing.items(), key=lambda kv: -kv[1]):
        findings.append(
            f"undeclared author {author!r} ({count} entries) -- add it as an "
            f"alias in {VOCABULARY_PATH.name}"
        )

    # Every prose correction must be backed by a structured record, or the
    # workaround silently spreads again.
    #
    # A record does NOT have to be an authorship correction. The schema began
    # as `recorded_as -> actual`, an identity pair, and the finding below still
    # explains itself in those terms -- but a register entry can also correct a
    # measurement, a count, or a factual claim, and those have no author to
    # recover. Demanding `actual` for them made a legitimate repair
    # unexpressible, so the gate rejected corrections it should have accepted.
    # `corrects:` names the kind; only `authorship` needs `actual`.
    for timestamp, kind, author in annotated_corrections(text):
        if correction_for(timestamp, kind, author, vocab) is None:
            findings.append(
                f"[CORRECTION] annotation on {timestamp} {kind} has no record "
                f"in {VOCABULARY_PATH.name}: the repair is prose only, so the "
                f"original author is recoverable from git alone"
            )

    # Every parenthetical token must classify. 331 entries parse with zero
    # unclassified today; an unrecognised token means a new KIND of fact is
    # being smuggled into the free-text slot, which is how it became
    # unparseable the first time.
    stray: dict[str, int] = {}
    for _, _, author in entries:
        for token in wearing(author, vocab).unclassified:
            stray[token] = stray.get(token, 0) + 1
    for token, count in sorted(stray.items(), key=lambda kv: -kv[1]):
        findings.append(
            f"unclassified token {token!r} in {count} author string(s) -- "
            f"declare it as a model, lane, harness, node relation or "
            f"provisioning token in {VOCABULARY_PATH.name}"
        )

    # A co-owner is an author. It goes through the SAME vocabulary as the
    # signing owner -- otherwise the field would let an identity in through a
    # side door under any spelling at all, and the register would grow a second
    # uncontrolled name space right next to the one this file was written to
    # control.
    co_missing: dict[str, int] = {}
    for _, _, _, co_owners in co_owner_attribution(text):
        for identity, _contribution in co_owners:
            if canonical_identity(identity, vocab) is None:
                co_missing[identity] = co_missing.get(identity, 0) + 1
    for identity, count in sorted(co_missing.items(), key=lambda kv: -kv[1]):
        findings.append(
            f"undeclared co-owner {identity!r} ({count} row(s)) -- add it as an "
            f"alias in {VOCABULARY_PATH.name}, same as a signing author"
        )

    known = {i.canonical for i in vocab.index.values()}
    for record in vocab.corrections:
        if record.get("corrects", "authorship") != "authorship":
            continue  # nothing to name: the correction is not about an author
        if record.get("actual") not in known:
            findings.append(f"correction names unknown identity {record.get('actual')!r}")
    for record in vocab.successions:
        for side in ("from", "to"):
            if record.get(side) not in known:
                findings.append(
                    f"succession {side}={record.get(side)!r} is not a declared identity"
                )
        if not record.get("evidence"):
            findings.append(
                f"succession {record.get('from')} -> {record.get('to')} cites no "
                f"evidence; an unevidenced lineage edge is a guess with a schema"
            )
    return findings


# ---------------------------------------------------------------------------
# WEARING -- the (identity, model, lane, node) join, parsed out of the ledger.
#
# Operator doctrine, 2026-08-25: an identity is WORN, not owned. "The signature
# is not the model, as models hold many; the identity a model puts on will
# align with the model and be tuned with the harness."
#
# That resolves what looked like an unanswerable question. `CLAUDE-OPUS-5` and
# `4090-CLAUDE-OPUS-5` were marked ambiguous because folding into `claude-opus`
# erases which machine did the work and folding into `4090-claude` ratifies
# node-bound identity. Under the doctrine neither fold is right: the string
# carries an identity AND a model, and the answer is to PARSE it.
# ---------------------------------------------------------------------------

SESSION_ID = re.compile(r"^mvs_[0-9a-f]{32}$")


@dataclass(frozen=True)
class Wearing:
    """One wearing event, recovered from a register author string."""
    as_written: str
    identity: str | None
    model: str | None = None
    lane: str | None = None
    node: str | None = None
    harness: str | None = None
    mirrored_from: str | None = None
    provisioning: tuple[str, ...] = ()
    session: str | None = None
    unclassified: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        """No token went unrecognised. NOT the same as 'fully specified' --
        most entries name no model at all, and that is a real absence rather
        than a parse failure."""
        return not self.unclassified


def _fold_table(doc_key: str, vocab_doc: dict) -> dict[str, str]:
    table: dict[str, str] = {}
    for entry in vocab_doc.get(doc_key) or []:
        canonical = str(entry["canonical"])
        for alias in (*(entry.get("aliases") or []), canonical):
            table[_norm(alias)] = canonical
    return table


_TABLES: dict[str, dict[str, str]] | None = None


def _tables(path: Path | None = None) -> dict[str, dict[str, str]]:
    global _TABLES
    if _TABLES is None:
        with open(path or _vocabulary_path(), encoding="utf-8") as handle:
            doc = yaml.safe_load(handle) or {}
        _TABLES = {
            key: _fold_table(key, doc)
            for key in ("models", "lanes", "provisioning", "harnesses")
        }
        # Node names come from the node vocabulary, which already exists and is
        # already gated -- duplicating them here would be a second source of
        # truth for the same fact.
        _TABLES["relations"] = {
            _norm(r["token"]): (r.get("node"), r.get("mirrored_from"))
            for r in (doc.get("node_relations") or [])
        }
        _TABLES["nodes"] = {}
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "node_identity", REPO_ROOT / "pmoves" / "tools" / "node_identity.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["node_identity"] = module
            spec.loader.exec_module(module)
            for alias, node in module.load_vocabulary().items():
                _TABLES["nodes"][alias] = node.canonical
        except Exception:  # noqa: BLE001 -- node vocab is optional here
            pass
    return _TABLES


def wearing(author: str, vocab: Vocabulary | None = None) -> Wearing:
    """Parse a register author string into the wearing event it records.

    Unrecognised tokens land in `unclassified` and are REPORTED. Guessing what
    an unknown token means is how the parenthetical became unparseable in the
    first place.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    base, paren = split_author(author)
    tables = _tables()

    identity = canonical_identity(author, vocab)
    model = lane = node = session = harness = mirrored_from = None
    provisioning: list[str] = []
    unclassified: list[str] = []

    for token in (t.strip() for t in paren.split(",")):
        if not token:
            continue
        key = _norm(token)
        if SESSION_ID.match(token):
            session = token
        elif key in tables["models"]:
            model = tables["models"][key]
        elif key in tables["lanes"]:
            lane = tables["lanes"][key]
        elif key in tables["harnesses"]:
            harness = tables["harnesses"][key]
        elif key in tables["relations"]:
            node, mirrored_from = tables["relations"][key]
        elif key in tables["provisioning"]:
            provisioning.append(tables["provisioning"][key])
        elif key in tables["nodes"]:
            node = tables["nodes"][key]
        else:
            unclassified.append(token)

    # `4090-CLAUDE-OPUS-5` carries the model in the BASE, not the parenthetical.
    if model is None:
        for candidate, canonical in tables["models"].items():
            if candidate and candidate in _norm(base):
                model = canonical
                break

    return Wearing(
        as_written=author, identity=identity, model=model, lane=lane, node=node,
        harness=harness, mirrored_from=mirrored_from,
        provisioning=tuple(provisioning), session=session,
        unclassified=tuple(unclassified),
    )


def describe_self(identity: str, vocab: Vocabulary | None = None) -> dict:
    """What a wearer can observe about the identity it is wearing.

    The doctrine's active half: "the model will be able to observe the shape of
    what it wears and choose, adjust accordingly." This is the read side of
    that -- the mechanism Archon needs at mint time, and the reason an identity
    has to be data rather than prose in a signature file.

    Reports what is KNOWN and what is ABSENT, because an identity with no
    grounding is the normal case today and must not read as a complete one.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    entry = vocab.index.get(_norm(identity))
    if entry is None:
        return {"identity": identity, "known": False,
                "why": "not a declared identity"}

    spellings = sorted(
        {a for _, _, a in register_entries()
         if canonical_identity(a, vocab) == entry.canonical}
    )
    worn = [wearing(s, vocab) for s in spellings]
    return {
        "identity": entry.canonical,
        "known": True,
        "node": entry.node,
        "spellings": spellings,
        "models_worn": sorted({w.model for w in worn if w.model}),
        "harnesses_worn": sorted({w.harness for w in worn if w.harness}),
        "lanes_worn": sorted({w.lane for w in worn if w.lane}),
        "entries": sum(1 for _, _, a in register_entries()
                       if canonical_identity(a, vocab) == entry.canonical),
        "succeeds": [s["from"] for s in predecessors(entry.canonical, vocab)],
        "succeeded_by": [s["to"] for s in successors(entry.canonical, vocab)],
        "alters": _alters_of(entry.canonical),
        # Absences, stated. An identity co-created with the founder and one
        # derived from a grounded persona are different things, and nothing in
        # the repo currently distinguishes them -- see CATALOG_325.
        "grounded": False,
        "grounding_note": (
            "No identity in this repo is prose-grounded. The lensing engine "
            "(pmoves/tools/catalog_lensing_engine.py, 2070 lines) has produced "
            "exactly one artifact -- 8 test items, not the 325 -- so there is "
            "no grounded persona to compare a co-created identity against."
        ),
    }


def _alters_of(identity: str) -> list[dict]:
    """Alter lineage: how an alter came to be, not just that it exists."""
    with open(_vocabulary_path(), encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return [a for a in (doc.get("alter_lineage") or [])
            if a.get("identity") == identity]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--census", action="store_true",
                        help="spellings per canonical identity")
    parser.add_argument("--verify", action="store_true", help="run the gate")
    parser.add_argument("--co-owners", action="store_true",
                        help="every lane that names more than one body")
    args = parser.parse_args(argv)

    vocab = load_vocabulary()

    if args.census:
        entries = register_entries()
        by_identity: dict[str, dict[str, int]] = {}
        for _, _, author in entries:
            canonical = canonical_identity(author, vocab) or "UNDECLARED"
            by_identity.setdefault(canonical, {})
            by_identity[canonical][author] = by_identity[canonical].get(author, 0) + 1
        print(f"{len(entries)} entries, "
              f"{len({a for _, _, a in entries})} distinct author strings, "
              f"{len(by_identity)} identities")
        for canonical, spellings in sorted(
            by_identity.items(), key=lambda kv: -sum(kv[1].values())
        ):
            total = sum(spellings.values())
            print(f"\n{canonical}  ({total} entries, {len(spellings)} spellings)")
            for author, count in sorted(spellings.items(), key=lambda kv: -kv[1]):
                print(f"  {count:4}  {author}")
        return 0

    if args.co_owners:
        text = read_register()
        rows = co_owner_attribution(text)
        print(f"{len(rows)} row(s) name a co-owner")
        for lineno, kind, owner, co_owners in rows:
            print(f"\nL{lineno}  {kind}  {owner}")
            for identity, contribution in co_owners:
                canonical = canonical_identity(identity, vocab) or "UNDECLARED"
                note = f" -- {contribution}" if contribution else ""
                print(f"    + {identity}  [{canonical}]{note}")
        unmeasured = unmeasured_rows(text)
        for lineno, owner in unmeasured:
            print(f"\nL{lineno}  {owner}: co-owners field present, NOT PARSEABLE")
        return 3 if unmeasured else 0

    findings = verify(vocab)

    # EXIT-CODE DOCTRINE: 0 clean, 1 findings, 3 could not measure.
    #
    # 3 is not a worse 1. A finding means the gate looked and something was
    # wrong; 3 means part of the register defeated the parser, so "no findings
    # there" is not a result -- it is an absence of one. Folding 3 into 0 would
    # report an unreadable attribution as a clean one, which is precisely the
    # thing being fixed, one layer down. It therefore takes precedence over
    # findings: you cannot call a run measured when part of it was not.
    unmeasured = unmeasured_rows()
    if unmeasured:
        print(f"COULD NOT MEASURE: {len(unmeasured)} row(s) announce co-owners "
              f"the parser cannot read:")
        for lineno, owner in unmeasured:
            print(f"  - L{lineno} `{owner}`: `co-owners` marker present, zero "
                  f"backticked IDs parsed. Write each ID in backticks, e.g. "
                  f"co-owners: `4090-CLAUDE` (what they did)")
    if findings:
        print(f"{len(findings)} finding(s):")
        for finding in findings:
            print(f"  - {finding}")
    if unmeasured:
        return 3
    if findings:
        return 1
    print("identity lineage: clean")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
