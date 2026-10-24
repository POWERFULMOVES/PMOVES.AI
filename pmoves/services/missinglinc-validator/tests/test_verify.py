"""Behavioural parity with Mike's verifyCitations.ts (PMOVES-Mike @ 563c8319)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from missinglinc_validator.verify import (  # noqa: E402
    TIER_EXACT,
    TIER_PUNCT,
    TIER_WS_CASE,
    locate_quote,
    normalize_with_map,
    sha256_text,
    verify_quote_against_source,
)

SRC = "The Court held that the U.S. statute applies.\n\nIn  addition,   the plaintiff's claim fails."


def test_exact_match_has_offsets_and_no_correction():
    r = verify_quote_against_source(SRC, "the U.S. statute applies")
    assert r.verified and r.match_tier == TIER_EXACT and not r.needs_correction
    assert SRC[r.start_char:r.end_char] == "the U.S. statute applies"


def test_whitespace_and_case_tier_returns_original_excerpt():
    r = verify_quote_against_source(SRC, "in addition, the PLAINTIFF'S claim")
    assert r.verified and r.match_tier == TIER_WS_CASE and r.needs_correction
    assert r.source_excerpt == "In  addition,   the plaintiff's claim"


def test_punctuation_tolerant_tier_is_labelled():
    r = verify_quote_against_source(SRC, "the US statute applies")
    assert r.verified and r.match_tier == TIER_PUNCT and r.needs_correction


def test_fabricated_quote_is_not_found():
    r = verify_quote_against_source(SRC, "the statute is unconstitutional")
    assert not r.verified and r.match_tier is None


def test_unreadable_source_never_verifies():
    assert not verify_quote_against_source("Document not found.", "Document not found").verified
    assert not verify_quote_against_source("", "anything").verified


def test_ellipsis_segments_verified_independently():
    r = verify_quote_against_source(SRC, "The Court held … the plaintiff's claim fails")
    assert r.verified and r.segments == 2 and r.match_tier == TIER_EXACT
    assert not verify_quote_against_source(SRC, "The Court held ... a missing tail").verified


def test_page_break_requires_order_and_proximity():
    ok = verify_quote_against_source(SRC, "The Court held [[PAGE_BREAK]] the plaintiff's claim")
    assert ok.verified and ok.segments == 2
    reversed_ = verify_quote_against_source(SRC, "the plaintiff's claim [[PAGE_BREAK]] The Court held")
    assert not reversed_.verified
    far = "alpha beta" + (" x" * 6000) + " gamma delta"
    assert not verify_quote_against_source(far, "alpha beta [[PAGE_BREAK]] gamma delta").verified


def test_normalize_with_map_matches_mike():
    norm, idx = normalize_with_map("A  B,c", strip_punctuation=True)
    assert norm == "a bc" and idx == [0, 1, 3, 5]


def test_locate_quote_none_on_empty():
    assert locate_quote(SRC, "") is None and locate_quote("", "x") is None


def test_sha256_text_is_stable():
    assert sha256_text("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
