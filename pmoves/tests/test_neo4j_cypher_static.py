"""Every Cypher file a make road applies must run statement by statement.

cypher-shell does not carry variables across ';' (tools/chit_mindmap_seed.cypher
says so at its relationship section), and on file input it stops at the first
failing statement, with every earlier statement already committed. Two ways that
went wrong here before 2026-10:

- `WITH phil` opening a statement on a variable from the PREVIOUS statement
  (data/consciousness/neo4j-consciousness-schema.cypher had 15) is a semantic
  error: the load aborted at :66 after committing the root and one category.
- `MERGE (a)-[:FORMS]->(c);` with `a` and `c` bound only earlier
  (neo4j/cypher/003 and 010:19) is NOT an error: MERGE creates two unlabeled
  nodes and the edge between them, so FORMS never reached the real Anchor.

A file-exists check catches neither, so this parses every road file. The road
set is derived, not listed: the bootstrap glob plus every `.cypher` path the
Makefile hands to `neo4j_apply_cypher`, so a new road is covered when it lands.
Nothing here talks to Neo4j.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]

CLAUSE = re.compile(r"\b(OPTIONAL MATCH|MATCH|MERGE|CREATE|WITH|UNWIND|RETURN|SET|WHERE|DELETE|DETACH|FOREACH|CALL|REMOVE)\b")
# (var) / (var:Label ...) / (var {..}); not a function call such as count(t)
NODE = re.compile(r"(?<![\w.])\(\s*([A-Za-z_]\w*)\s*(:\s*[A-Za-z_`][\w:`]*)?\s*(?=[){])")
REL_VAR = re.compile(r"\[\s*([A-Za-z_]\w*)\s*[:\]{*]")
ALIAS = re.compile(r"\bAS\s+([A-Za-z_]\w*)")
# x.prop, but not a namespaced function such as apoc.util.validate(
PROP = re.compile(r"(?<![\w.$])([A-Za-z_]\w*)\.(?=[A-Za-z_])(?![\w.]*\s*\()")


def strip_strings_and_comments(text: str) -> str:
    """Blank string bodies and drop // comments, so neither can look like Cypher."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            out.append(ch + ch)
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def statements(text: str) -> list[str]:
    return [s.strip() for s in strip_strings_and_comments(text).split(";") if s.strip()]


def unbound_uses(stmt: str) -> list[str]:
    """Variables a statement uses before (or without) binding them itself."""
    bound: set[str] = set()
    problems: list[str] = []
    clause = None
    events = []
    for rx, kind in ((CLAUSE, "clause"), (NODE, "node"), (REL_VAR, "rel"), (ALIAS, "alias"), (PROP, "prop")):
        events += [(m.start(), kind, m) for m in rx.finditer(stmt)]
    for _, kind, m in sorted(events, key=lambda e: e[0]):
        if kind == "clause":
            clause = m.group(1)
            if clause == "WITH":
                tail = stmt[m.end():]
                nxt = CLAUSE.search(tail)
                for item in tail[: nxt.start() if nxt else None].split(","):
                    item = item.strip()
                    if re.fullmatch(r"[A-Za-z_]\w*", item) and item not in bound:
                        problems.append(f"WITH {item}: not bound in this statement")
        elif kind == "node":
            var, label = m.group(1), m.group(2)
            if var in bound:
                continue
            if label or clause in ("MATCH", "OPTIONAL MATCH"):
                bound.add(var)
            elif clause in ("MERGE", "CREATE"):
                problems.append(f"{clause} ({var}): unlabeled and unbound, creates a blank node")
                bound.add(var)
            else:
                problems.append(f"({var}) in {clause}: not bound in this statement")
        elif kind in ("rel", "alias"):
            bound.add(m.group(1))
        elif kind == "prop" and m.group(1) not in bound:
            problems.append(f"{m.group(1)}.<prop>: not bound in this statement")
    return problems


def idempotency_problems(stmt: str) -> list[str]:
    problems = []
    if re.match(r"CREATE\s+(CONSTRAINT|INDEX)\b", stmt) and "IF NOT EXISTS" not in stmt:
        problems.append("CREATE CONSTRAINT/INDEX without IF NOT EXISTS")
    if re.search(r"\bCREATE\s*\(", stmt):
        problems.append("bare CREATE of a node or edge (use MERGE)")
    for pattern in re.findall(r"\bMERGE\s+(\([^;]*?\))(?=\s*(?:\n|ON|SET|WITH|MERGE|RETURN|$))", stmt):
        if re.search(r"\b(datetime|timestamp|randomUUID|rand)\s*\(", pattern):
            problems.append(f"non-deterministic value inside a MERGE pattern: {pattern[:80]}")
    return problems


def road_files() -> list[Path]:
    files = set((PMOVES / "neo4j" / "cypher").glob("*.cypher"))
    makefile = (PMOVES / "Makefile").read_text()
    for rel in re.findall(r"neo4j_apply_cypher,\$\(CURDIR\)/([^)\s]+\.cypher)\)", makefile):
        files.add(PMOVES / rel)
    return sorted(files)


def test_road_set_includes_the_known_roads():
    rel = {str(p.relative_to(PMOVES)) for p in road_files()}
    assert "data/consciousness/neo4j-consciousness-schema.cypher" in rel, rel
    assert "tools/chit_mindmap_seed.cypher" in rel, rel
    assert "neo4j/cypher/001_init.cypher" in rel, rel


@pytest.mark.parametrize("path", road_files(), ids=lambda p: str(p.relative_to(PMOVES)))
def test_every_statement_is_self_contained(path):
    bad = [(i, s.splitlines()[0][:80], p) for i, s in enumerate(statements(path.read_text()), 1)
           for p in unbound_uses(s)]
    assert not bad, "\n".join(f"stmt {i} `{head}`: {p}" for i, head, p in bad)


@pytest.mark.parametrize("path", road_files(), ids=lambda p: str(p.relative_to(PMOVES)))
def test_every_statement_is_idempotent(path):
    bad = [(i, p) for i, s in enumerate(statements(path.read_text()), 1) for p in idempotency_problems(s)]
    assert not bad, bad


# --- the checker itself: it must flag the shapes that broke, and pass the fixes ---

@pytest.mark.parametrize("cypher", [
    "MERGE (a:Anchor {id:'x'}) SET a.k=1;\nMERGE (a)-[:FORMS]->(c);",
    "MERGE (phil:S {id:'x'});\nWITH phil\nUNWIND [1] AS x MERGE (t:T {n:x}) MERGE (phil)-[:C]->(t);",
    "MERGE (hp)-[:MOTIVATES]->(pp);",
    "MATCH (a:A) RETURN a;\nSET a.x = 1;",
], ids=["merge-blank-pair", "with-from-previous-statement", "standalone-merge", "set-on-previous-var"])
def test_checker_flags_cross_statement_variables(cypher):
    assert any(unbound_uses(s) for s in statements(cypher)), cypher


@pytest.mark.parametrize("cypher", [
    "MATCH (a:Anchor {id:'x'}), (c:Constellation {id:'y'})\nMERGE (a)-[:FORMS]->(c);",
    "MATCH (phil:S {id:'x'})\nUNWIND [{n:'a', ps:['p']}] AS theory\nMERGE (t:T {name: theory.n})\n"
    "MERGE (phil)-[:C]->(t)\nWITH t, theory\nUNWIND theory.ps AS pn\nMERGE (p:P {name: pn})\nMERGE (t)-[:BY]->(p);",
    "MATCH (c:C)-[:HAS]->(:P)-[:LOCATES]->(m:M)\nRETURN size(collect(DISTINCT m.modality)) >= 2 AS ok, count(c) AS n;",
    "CREATE CONSTRAINT x IF NOT EXISTS FOR (a:Anchor) REQUIRE a.id IS UNIQUE;",
    "MERGE (n:N {k:'a // not a comment; nor a split'}) SET n.v = 'it''s (x) here';",
], ids=["match-then-merge", "unwind-chain", "aggregates", "constraint", "strings-are-opaque"])
def test_checker_passes_self_contained_statements(cypher):
    assert [p for s in statements(cypher) for p in unbound_uses(s)] == [], cypher


@pytest.mark.parametrize("cypher", [
    "CREATE CONSTRAINT x FOR (a:A) REQUIRE a.id IS UNIQUE;",
    "CREATE (a:A {id:'x'});",
    "MATCH (a:A {id:'x'}), (l:L {n:'y'})\nMERGE (a)-[:AT {since: datetime()}]->(l);",
], ids=["constraint-without-if-not-exists", "bare-create", "datetime-in-merge"])
def test_checker_flags_non_idempotent_statements(cypher):
    assert any(idempotency_problems(s) for s in statements(cypher)), cypher
