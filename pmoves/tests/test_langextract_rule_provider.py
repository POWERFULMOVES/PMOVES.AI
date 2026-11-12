"""RuleProvider chunk cap + stable hierarchical ids (libs/langextract/providers/rule.py).

Before this change RuleProvider emitted one chunk per blank-line paragraph with
no length cap, and ids were positional (``{doc_id}-{section}-{len(chunks)+1}``),
so a question added to paragraph 1 renumbered every later chunk.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

PMOVES_DIR = Path(__file__).resolve().parents[1]
if str(PMOVES_DIR) not in sys.path:
    sys.path.insert(0, str(PMOVES_DIR))

rule = importlib.import_module("libs.langextract.providers.rule")
RuleProvider = rule.RuleProvider

CAP = 2000


@pytest.fixture(autouse=True)
def _default_caps(monkeypatch):
    monkeypatch.delenv("LANGEXTRACT_MAX_CHARS", raising=False)
    monkeypatch.delenv("LANGEXTRACT_OVERLAP_CHARS", raising=False)


def _long_paragraph(n: int = 420) -> str:
    return " ".join(f"Sentence number {i} talks about retrieval and embeddings." for i in range(n))


def _extract(doc: str, doc_id: str = "doc1"):
    return RuleProvider().extract_text(doc, "pmoves", doc_id)["chunks"]


def test_long_paragraph_chunks_are_capped():
    doc = "Short intro.\n\n" + _long_paragraph() + "\n\nOutro."
    assert len(doc) > 20_000
    chunks = _extract(doc)
    assert chunks
    assert max(len(c["text"]) for c in chunks) <= CAP
    sec2 = [c for c in chunks if c["section_id"] == "sec2"]
    assert len(sec2) > 1


def test_env_cap_is_honoured(monkeypatch):
    monkeypatch.setenv("LANGEXTRACT_MAX_CHARS", "400")
    chunks = _extract(_long_paragraph(50))
    assert max(len(c["text"]) for c in chunks) <= 400


def test_existing_keys_kept_and_new_fields_present():
    chunks = _extract("Alpha paragraph. Is it?\n\nBeta paragraph.")
    for c in chunks:
        for key in ("doc_id", "section_id", "chunk_id", "namespace", "text", "kind"):
            assert key in c, key
        assert c["doc_id"] == "doc1"
        assert c["namespace"] == "pmoves"
        assert c["parent_section"] == c["section_id"]
        assert isinstance(c["char_start"], int) and isinstance(c["char_end"], int)
    kinds = [c["kind"] for c in chunks]
    assert kinds.count("paragraph") == 2
    assert kinds.count("question") == 1


def test_hierarchical_ids():
    doc = "Alpha. Why alpha?\n\n" + _long_paragraph(100) + "\n\nGamma?"
    chunks = _extract(doc)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    for c in chunks:
        if c["kind"] == "paragraph":
            assert re.fullmatch(r"doc1-sec\d+-p\d+", c["chunk_id"]), c["chunk_id"]
        else:
            assert re.fullmatch(r"doc1-sec\d+-q\d+", c["chunk_id"]), c["chunk_id"]
        assert c["chunk_id"].startswith(f"doc1-{c['section_id']}-")
    assert "doc1-sec1-p1" in ids
    assert "doc1-sec1-q1" in ids
    sec2_ids = [c["chunk_id"] for c in chunks if c["section_id"] == "sec2"]
    assert sec2_ids == [f"doc1-sec2-p{k}" for k in range(1, len(sec2_ids) + 1)]


def test_ids_stable_when_a_later_paragraph_changes():
    p1 = "First paragraph. Does it have a question? Yes it does."
    p2 = _long_paragraph(120)
    before = _extract(f"{p1}\n\n{p2}\n\nThird paragraph.")
    after = _extract(
        f"{p1}\n\n{p2}\n\nThird paragraph rewritten. Now with questions? And more? "
        + _long_paragraph(80)
    )

    def early(chunks):
        return [(c["chunk_id"], c["text"]) for c in chunks if c["section_id"] in ("sec1", "sec2")]

    assert early(before) == early(after)
    assert early(before)


def test_offsets_reconstruct_text():
    doc = "  Lead para. Really?  \n\n\n" + _long_paragraph() + "\n \n" + ("z" * 7000) + "\n\nEnd?"
    chunks = _extract(doc)
    for c in chunks:
        assert doc[c["char_start"]:c["char_end"]] == c["text"], c["chunk_id"]


def test_question_chunks_are_capped():
    preamble = " ".join(f"word{i}" for i in range(2500))  # >> cap, no terminal punctuation
    doc = preamble + " so what is the answer?"
    chunks = _extract(doc)
    questions = [c for c in chunks if c["kind"] == "question"]
    assert questions
    assert all(len(q["text"]) <= CAP for q in questions)
    assert questions[-1]["text"].endswith("what is the answer?")


def test_short_document_output_unchanged_apart_from_ids():
    chunks = _extract("Hello world.\n\nHow are you?")
    assert [(c["section_id"], c["text"], c["kind"]) for c in chunks] == [
        ("sec1", "Hello world.", "paragraph"),
        ("sec2", "How are you?", "paragraph"),
        ("sec2", "How are you?", "question"),
    ]


def test_extract_text_works_without_lxml(monkeypatch):
    """extract_text needs no lxml; only extract_xml does (lazy import)."""
    monkeypatch.setitem(sys.modules, "lxml", None)
    monkeypatch.setitem(sys.modules, "lxml.etree", None)
    reloaded = importlib.reload(rule)
    try:
        out = reloaded.RuleProvider().extract_text("One.\n\nTwo?", "ns", "d")
        assert len(out["chunks"]) == 3
    finally:
        monkeypatch.undo()
        importlib.reload(rule)


def test_extract_xml_chunks_are_capped_and_ids_unique():
    pytest.importorskip("lxml")
    long_p = _long_paragraph()
    long_q = " ".join(f"word{i}" for i in range(2500)) + " right?"
    xml = (
        "<doc><title>Heading</title>"
        f"<p>Short para. Is this short?</p><p>{long_p}</p>"
        f"<q>{long_q}</q>"
        "<h2>Second</h2>"
        f"<section>{'blob ' * 3000}</section>"
        "</doc>"
    )
    out = RuleProvider().extract_xml(xml, "pmoves", "x1")
    chunks = out["chunks"]
    assert chunks
    assert max(len(c["text"]) for c in chunks) <= CAP
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        assert c["chunk_id"].startswith(f"x1-{c['section_id']}-")
        assert c["parent_section"] == c["section_id"]
    assert any(c["kind"] == "title" and c["text"] == "Heading" for c in chunks)
    qs = [c for c in chunks if c["kind"] == "question"]
    assert any(q["text"] == "Short para. Is this short?" or q["text"] == "Is this short?" for q in qs)
    assert all(len(q["text"]) <= CAP and q["text"].endswith("?") for q in qs)


def test_extract_xml_ids_stable_when_a_later_element_changes():
    pytest.importorskip("lxml")
    head = "<doc><title>T</title><p>Para one. Why?</p><p>Para two.</p>"
    a = RuleProvider().extract_xml(head + "<p>Three.</p></doc>", "ns", "x")["chunks"]
    b = RuleProvider().extract_xml(head + "<p>Three changed? Yes?</p><p>Four.</p></doc>", "ns", "x")["chunks"]
    first = lambda cs: [(c["chunk_id"], c["text"]) for c in cs][:4]  # noqa: E731
    assert first(a) == first(b)
