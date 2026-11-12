"""Surface-depth quote verification: a Python port of Mike's verifyCitations.ts.

Ported from PMOVES-Mike @ 563c8319:
  backend/src/modules/chat/engine/verifyCitations.ts  (locateQuote,
      locateQuoteFrom, locateSegmentsInOrder, locateNormalized,
      verifyQuoteAgainstSource)
  backend/src/modules/chat/engine/tools/documentOps.ts (normalizeWithMap,
      isPunctuation)

Faithful to Mike's three-tier search (exact, then whitespace+case, then
punctuation-tolerant) and its ellipsis / [[PAGE_BREAK]] handling. One
addition: every result says WHICH tier matched (``match_tier``), so a
tolerant match is never reported as if it were verbatim.

Known deliberate differences from the TypeScript:
  * Offsets are Unicode code-point offsets (Mike's are UTF-16 code units).
    They differ only for astral-plane characters.
  * When lowercasing turns one character into several (e.g. U+0130), each
    output character maps back to the same source index. In Mike the
    expansion lands in one array slot and shifts later offsets. The match
    outcome is the same; the Python offsets are the correct ones.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

PAGE_BREAK_SENTINEL = "[[PAGE_BREAK]]"
ELLIPSIS_PATTERN = re.compile(r"\.{3}|…")
MAX_PAGE_BREAK_SPAN_CHARS = 5_000
MAX_LOCATE_ATTEMPTS = 64
UNREADABLE_SOURCES = frozenset({"Document could not be read.", "Document not found."})

TIER_EXACT = "exact"
TIER_WS_CASE = "whitespace_case"
TIER_PUNCT = "punctuation_tolerant"
_TIER_RANK = {TIER_EXACT: 0, TIER_WS_CASE: 1, TIER_PUNCT: 2}


def _is_letter_or_number(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("L", "N")


def _is_punctuation(ch: str) -> bool:
    # documentOps.isPunctuation: not a letter, number or whitespace.
    return not (_is_letter_or_number(ch) or ch.isspace())


def _has_letter_or_number(text: str) -> bool:
    return any(_is_letter_or_number(c) for c in text)


def normalize_with_map(text: str, strip_punctuation: bool = False) -> tuple[str, list[int]]:
    """documentOps.normalizeWithMap: collapse whitespace runs to one space,
    lowercase, optionally drop punctuation; map each normalized char to its
    source index."""
    norm: list[str] = []
    orig_idx: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_space:
                norm.append(" ")
                orig_idx.append(i)
                prev_space = True
        elif strip_punctuation and _is_punctuation(ch):
            continue
        else:
            for low in ch.lower():
                norm.append(low)
                orig_idx.append(i)
            prev_space = False
    return "".join(norm), orig_idx


@dataclass(frozen=True)
class QuoteLocation:
    start: int
    end: int
    excerpt: str
    tier: str


def _locate_normalized(source: str, quote: str, strip_punctuation: bool) -> QuoteLocation | None:
    norm, orig_idx = normalize_with_map(source, strip_punctuation)
    needle = normalize_with_map(quote, strip_punctuation)[0].strip()
    if not needle:
        return None
    pos = norm.find(needle)
    if pos < 0:
        return None
    end_norm = pos + len(needle)
    start = orig_idx[pos] if pos < len(orig_idx) else 0
    end = orig_idx[end_norm - 1] + 1 if end_norm - 1 < len(orig_idx) else len(source)
    return QuoteLocation(start, end, source[start:end], TIER_PUNCT if strip_punctuation else TIER_WS_CASE)


def locate_quote(source: str, quote: str) -> QuoteLocation | None:
    """verifyCitations.locateQuote: first hit of exact, ws+case, punctuation-tolerant."""
    if not source or not quote:
        return None
    idx = source.find(quote)
    if idx >= 0:
        return QuoteLocation(idx, idx + len(quote), quote, TIER_EXACT)
    return _locate_normalized(source, quote, False) or _locate_normalized(source, quote, True)


def _locate_quote_from(source: str, quote: str, from_: int) -> QuoteLocation | None:
    if from_ >= len(source):
        return None
    offset = max(0, from_)
    suffix = source[offset:]
    candidates: list[QuoteLocation] = []
    idx = suffix.find(quote)
    if idx >= 0:
        candidates.append(QuoteLocation(idx, idx + len(quote), quote, TIER_EXACT))
    for strip in (False, True):
        loc = _locate_normalized(suffix, quote, strip)
        if loc:
            candidates.append(loc)
    if not candidates:
        return None
    best = candidates[0]
    for c in candidates[1:]:
        if c.start < best.start:  # strict <, as in the TS reduce
            best = c
    return QuoteLocation(best.start + offset, best.end + offset, best.excerpt, best.tier)


def _locate_segments_in_order(source: str, segments: list[str], max_gap: int) -> list[QuoteLocation] | None:
    attempts = 0

    def search(index: int, from_: int, previous_end: int | None) -> list[QuoteLocation] | None:
        nonlocal attempts
        if index == len(segments):
            return []
        cursor = from_
        while attempts < MAX_LOCATE_ATTEMPTS:
            attempts += 1
            loc = _locate_quote_from(source, segments[index], cursor)
            if loc is None:
                return None
            if previous_end is not None and loc.start - previous_end > max_gap:
                return None
            rest = search(index + 1, loc.end, loc.end)
            if rest is not None:
                return [loc, *rest]
            cursor = loc.start + 1
        return None

    return search(0, 0, None)


@dataclass
class QuoteVerification:
    verified: bool
    needs_correction: bool = False
    match_tier: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    source_excerpt: str | None = None
    segments: int = 1
    notes: list[str] = field(default_factory=list)


def _worst_tier(tiers: list[str | None]) -> str | None:
    real = [t for t in tiers if t]
    return max(real, key=_TIER_RANK.__getitem__) if real else None


def verify_quote_against_source(source: str, quote: str) -> QuoteVerification:
    """verifyCitations.verifyQuoteAgainstSource, plus match_tier."""
    if not source or source in UNREADABLE_SOURCES:
        return QuoteVerification(False, notes=["source unreadable or empty"])

    if PAGE_BREAK_SENTINEL in quote:
        segments = [s.strip() for s in quote.split(PAGE_BREAK_SENTINEL) if s.strip()]
        if not segments:
            return QuoteVerification(False)
        results = [verify_quote_against_source(source, s) for s in segments]
        if any(not r.verified for r in results):
            return QuoteVerification(False, segments=len(segments))
        anchors: list[str] = []
        for seg in segments:
            frags = [f.strip() for f in ELLIPSIS_PATTERN.split(seg)]
            frags = [f for f in frags if _has_letter_or_number(f)]
            anchors.extend(frags or [seg])
        if _locate_segments_in_order(source, anchors, MAX_PAGE_BREAK_SPAN_CHARS) is None:
            return QuoteVerification(False, segments=len(segments), notes=["page segments out of order or too far apart"])
        return QuoteVerification(
            True,
            needs_correction=any(r.needs_correction for r in results),
            match_tier=_worst_tier([r.match_tier for r in results]),
            source_excerpt=f" {PAGE_BREAK_SENTINEL} ".join(
                r.source_excerpt or segments[i] for i, r in enumerate(results)
            ),
            segments=len(segments),
        )

    if ELLIPSIS_PATTERN.search(quote):
        segments = [s.strip() for s in ELLIPSIS_PATTERN.split(quote)]
        segments = [s for s in segments if _has_letter_or_number(s)]
        if not segments:
            return QuoteVerification(False)
        located = [(s, locate_quote(source, s)) for s in segments]
        if any(loc is None for _, loc in located):
            return QuoteVerification(False, segments=len(segments))
        return QuoteVerification(
            True,
            needs_correction=any(loc.excerpt != s for s, loc in located),  # type: ignore[union-attr]
            match_tier=_worst_tier([loc.tier for _, loc in located]),  # type: ignore[union-attr]
            source_excerpt=" ... ".join(loc.excerpt for _, loc in located),  # type: ignore[union-attr]
            segments=len(segments),
        )

    loc = locate_quote(source, quote)
    if loc is None:
        return QuoteVerification(False)
    return QuoteVerification(
        True,
        needs_correction=loc.excerpt != quote,
        match_tier=loc.tier,
        start_char=loc.start,
        end_char=loc.end,
        source_excerpt=loc.excerpt,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
