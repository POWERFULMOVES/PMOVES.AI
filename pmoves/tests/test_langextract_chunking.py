"""Unit tests for the shared multi-strategy chunker (libs/langextract/chunking.py).

Measured problem (layer map #3406): 12717 of 52620 embedding inputs to
qwen3-embedding:4b were clipped at the 8192-token context because
RuleProvider split on blank lines with no length cap. These tests pin the cap
and the fallback ladder: paragraph -> sentence pack -> hard split w/ overlap.

The extract-worker image is built from ``services/extract-worker`` alone and
cannot see ``libs/``, so it carries a byte-identical copy of the helper. Every
behavioural test runs against BOTH files, and a parity test fails the moment
they drift.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

PMOVES_DIR = Path(__file__).resolve().parents[1]
SHARED = PMOVES_DIR / "libs" / "langextract" / "chunking.py"
VENDORED = PMOVES_DIR / "services" / "extract-worker" / "langextract_chunking.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[SHARED, VENDORED], ids=["shared", "extract-worker-vendored"])
def chunking(request):
    return _load(request.param, f"_chunking_under_test_{request.param.parent.name.replace('-', '_')}")


def _long_sentence_paragraph(n: int = 420) -> str:
    # ~57 chars per sentence -> ~24k chars, one paragraph, no blank lines.
    return " ".join(
        f"Sentence number {i} talks about retrieval and embeddings." for i in range(n)
    )


def _long_unpunctuated_run(n_chars: int = 25_000) -> str:
    words = []
    i = 0
    while sum(len(w) + 1 for w in words) < n_chars:
        words.append(f"token{i}")
        i += 1
    return " ".join(words)


def test_vendored_copy_is_byte_identical_to_shared_helper():
    assert VENDORED.read_bytes() == SHARED.read_bytes(), (
        "services/extract-worker/langextract_chunking.py drifted from "
        "libs/langextract/chunking.py; copy the shared file over it"
    )


def test_defaults_are_2000_and_200(chunking, monkeypatch):
    monkeypatch.delenv("LANGEXTRACT_MAX_CHARS", raising=False)
    monkeypatch.delenv("LANGEXTRACT_OVERLAP_CHARS", raising=False)
    assert chunking.max_chars_from_env() == 2000
    assert chunking.overlap_chars_from_env() == 200


def test_env_overrides_and_invalid_values(chunking, monkeypatch):
    monkeypatch.setenv("LANGEXTRACT_MAX_CHARS", "500")
    monkeypatch.setenv("LANGEXTRACT_OVERLAP_CHARS", "50")
    assert chunking.max_chars_from_env() == 500
    assert chunking.overlap_chars_from_env() == 50
    monkeypatch.setenv("LANGEXTRACT_MAX_CHARS", "not-a-number")
    monkeypatch.setenv("LANGEXTRACT_OVERLAP_CHARS", "-7")
    assert chunking.max_chars_from_env() == 2000
    assert chunking.overlap_chars_from_env() == 200


def test_short_paragraphs_pass_through_whole(chunking):
    doc = "  First paragraph here.  \n\n\n Second one?\n  \n"
    paras = chunking.chunk_text(doc, max_chars=2000, overlap_chars=200)
    assert [[s.text for s in pieces] for pieces in paras] == [
        ["First paragraph here."],
        ["Second one?"],
    ]
    for pieces in paras:
        assert pieces[0].strategy == "paragraph"
        for s in pieces:
            assert doc[s.start:s.end] == s.text


def test_long_paragraph_is_sentence_packed_under_cap(chunking):
    doc = _long_sentence_paragraph()
    assert len(doc) > 20_000
    paras = chunking.chunk_text(doc, max_chars=2000, overlap_chars=200)
    assert len(paras) == 1
    pieces = paras[0]
    assert len(pieces) > 1
    assert all(len(p.text) <= 2000 for p in pieces)
    # sentence boundaries preferred: every piece ends a sentence
    assert all(p.strategy == "sentence" for p in pieces)
    assert all(p.text.endswith(".") for p in pieces)
    # each piece starts a sentence too
    assert all(p.text.startswith("Sentence number") for p in pieces)


def test_offsets_reconstruct_text_and_cover_all_content(chunking):
    doc = "Intro para.\n\n" + _long_sentence_paragraph() + "\n\n" + _long_unpunctuated_run()
    paras = chunking.chunk_text(doc, max_chars=2000, overlap_chars=200)
    covered = [False] * len(doc)
    for pieces in paras:
        for s in pieces:
            assert doc[s.start:s.end] == s.text
            for i in range(s.start, s.end):
                covered[i] = True
    lost = [i for i, ch in enumerate(doc) if not ch.isspace() and not covered[i]]
    assert lost == [], "content characters dropped by the chunker"


def test_single_oversized_sentence_is_hard_split_with_overlap(chunking):
    doc = _long_unpunctuated_run()
    assert len(doc) > 20_000
    pieces = chunking.split_span(doc, 0, max_chars=2000, overlap_chars=200)
    assert len(pieces) > 1
    assert all(len(p.text) <= 2000 for p in pieces)
    assert all(p.strategy == "hard" for p in pieces)
    for prev, nxt in zip(pieces, pieces[1:]):
        overlap = prev.end - nxt.start
        assert overlap > 0, "hard splits must overlap"
        assert overlap <= 200 + 1
        # overlapping text is literally shared
        assert doc[nxt.start:prev.end] == prev.text[len(prev.text) - overlap:]
    assert pieces[0].start == 0
    assert pieces[-1].end == len(doc)


def test_hard_split_prefers_whitespace_boundaries(chunking):
    doc = _long_unpunctuated_run()
    pieces = chunking.split_span(doc, 0, max_chars=2000, overlap_chars=200)
    # every piece but the last should end on a whole token (no mid-word cut)
    for p in pieces[:-1]:
        assert re.search(r"token\d+$", p.text), p.text[-20:]


def test_sentence_over_cap_inside_normal_paragraph(chunking):
    giant = _long_unpunctuated_run(6000) + "."
    doc = "Short opener. " + giant + " Short closer."
    pieces = chunking.split_span(doc, 0, max_chars=2000, overlap_chars=200)
    assert all(len(p.text) <= 2000 for p in pieces)
    assert pieces[0].text == "Short opener."
    assert pieces[-1].text.endswith("Short closer.")
    assert {"sentence", "hard"} <= {p.strategy for p in pieces}


def test_overlap_is_clamped_so_split_terminates(chunking):
    doc = "x" * 5000
    pieces = chunking.split_span(doc, 0, max_chars=300, overlap_chars=10_000)
    assert all(len(p.text) <= 300 for p in pieces)
    assert pieces[-1].end == 5000
    assert len(pieces) < 5000  # made progress


def test_unicode_wide_text_is_capped_in_characters(chunking):
    doc = "检索增强生成" * 3000  # 18k CJK chars, no ASCII punctuation
    pieces = chunking.split_span(doc, 0, max_chars=2000, overlap_chars=200)
    assert all(len(p.text) <= 2000 for p in pieces)
    assert pieces[-1].end == len(doc)


def test_resplit_oversized_rewrites_only_items_over_threshold(chunking):
    big = _long_sentence_paragraph(200)  # ~11.5k chars
    chunks = [
        {"doc_id": "d", "section_id": "s1", "chunk_id": "d-s1-1", "namespace": "ns",
         "text": "small", "kind": "paragraph"},
        {"doc_id": "d", "section_id": "s2", "chunk_id": "d-s2-1", "namespace": "ns",
         "text": big, "kind": "paragraph", "char_start": 100, "char_end": 100 + len(big)},
    ]
    out, n_over = chunking.resplit_oversized(chunks, threshold=8000, max_chars=2000, overlap_chars=200)
    assert n_over == 1
    assert out[0] == chunks[0]
    children = out[1:]
    assert len(children) > 1
    assert all(len(c["text"]) <= 2000 for c in children)
    assert [c["chunk_id"] for c in children] == [f"d-s2-1-r{k}" for k in range(1, len(children) + 1)]
    for c in children:
        assert c["parent_chunk_id"] == "d-s2-1"
        assert c["doc_id"] == "d" and c["section_id"] == "s2" and c["namespace"] == "ns"
        assert c["kind"] == "paragraph"
        # offsets are absolute when the parent carried them
        rel_start = c["char_start"] - 100
        assert big[rel_start:rel_start + len(c["text"])] == c["text"]
    # input not mutated
    assert chunks[1]["text"] == big and "parent_chunk_id" not in chunks[1]


def test_resplit_oversized_handles_id_key_and_missing_ids(chunking):
    big = "y " * 6000
    out, n_over = chunking.resplit_oversized(
        [{"id": "abc", "text": big}, {"text": big}], threshold=8000, max_chars=2000, overlap_chars=200
    )
    assert n_over == 2
    assert all(len(c["text"]) <= 2000 for c in out)
    with_id = [c for c in out if c.get("parent_chunk_id") == "abc"]
    assert with_id and all(c["id"] == c["chunk_id"] for c in with_id)
    assert all(c["chunk_id"] for c in out)
