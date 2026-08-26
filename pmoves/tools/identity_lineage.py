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
ENTRY = re.compile(r"^- `([0-9TZ:\-]+)` ([A-Z+]+) `([^`]+)`", re.M)
CORRECTION = re.compile(r"\[CORRECTION ([^\]]*)\]")

# An identity written as `BASE (parenthetical)`. The parenthetical carries a
# model, a lane/alter, or a node -- three fields in one free-text slot.
SPLIT = re.compile(r"^([^(]+?)\s*\((.*)\)\s*$")

NON_IDENTITY_KINDS = frozenset({"unresolved"})


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
        if author is not None:
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


def annotated_corrections(text: str | None = None) -> list[tuple[str, str, str]]:
    """Register entries carrying a prose `[CORRECTION ...]` annotation."""
    text = text if text is not None else read_register()
    out = []
    for line in text.splitlines():
        if "[CORRECTION" not in line:
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

    known = {i.canonical for i in vocab.index.values()}
    for record in vocab.corrections:
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

    findings = verify(vocab)
    if findings:
        print(f"{len(findings)} finding(s):")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("identity lineage: clean")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
