"""Multi-strategy, length-capped text chunker shared by the PMOVES ingest path.

Why this exists
---------------
Layer map #3406 measured 12717 of 52620 inputs to ``qwen3-embedding:4b``
(~24%) arriving at the 8191/8192-token context limit and being clipped. The
chain was notebook-sync -> langextract ``/extract/text`` -> ``RuleProvider``
-> extract-worker ``/ingest`` -> TensorZero -> Ollama, and nothing on it capped
chunk length: ``RuleProvider`` split on blank lines only, so a long paragraph
(or a document with no blank lines at all) went to the embedder whole and its
tail was silently discarded from the vector.

Strategy ladder (first rung that fits wins)
-------------------------------------------
1. **paragraph** - blank-line paragraphs, kept whole when ``<= max_chars``.
2. **sentence** - an over-cap paragraph is re-packed greedily by sentences
   (precedent: CHIT ``units_mode=sentences``,
   ``pmoves/docs/PMOVESCHIT/doc2structure.py:make_chunks``). Sentence packs do
   not overlap: the boundary is a natural one.
3. **hard** - a single sentence longer than the cap is hard-split into windows
   of ``max_chars`` with ``overlap_chars`` of shared text, preferring to cut at
   whitespace (precedent: ``pmoves/tools/repo_crawl.py:_chunk_text``,
   2000/200).

Every span carries ``start``/``end`` offsets into the source string, and
``source[start:end] == text`` always holds, so a chunk can be mapped back onto
the document (CGP point ``char`` offsets) without storing a second copy.

Why the cap is in characters (chars -> tokens reasoning)
--------------------------------------------------------
Token counts are model-specific and the tokenizer is not available in every
image on this path, so the cap is measured in characters as a conservative
proxy:

* qwen3-embedding (8192-token context) uses a byte-level BPE, which emits at
  most one token per UTF-8 byte, and a character is at most 4 UTF-8 bytes. So
  2000 characters is at most 8000 tokens even for adversarial text (emoji,
  rare CJK) - a hard bound under 8192, not an average.
* For ordinary prose a token is ~3.5-4.5 characters, so 2000 characters is
  ~450-570 tokens: well under the 2048-token context of the smaller
  embedders (embeddinggemma, nomic-embed-text) that share named vectors with
  qwen3 (PR #3355). For those models the bound is typical-case, not
  worst-case: dense non-Latin text could still exceed 2048 tokens at 2000
  characters. Lower ``LANGEXTRACT_MAX_CHARS`` if such a corpus is routed to a
  2048-token model.

Configuration
-------------
``LANGEXTRACT_MAX_CHARS`` (default 2000) and ``LANGEXTRACT_OVERLAP_CHARS``
(default 200), read at call time. Invalid values fall back to the defaults;
overlap is clamped to half the cap so a split always makes progress.

This module is stdlib-only on purpose: ``services/extract-worker`` is built
from its own directory and cannot import ``libs/``, so it carries a
byte-identical copy (``langextract_chunking.py``) that a test keeps in parity.
Edit this file, then copy it over the vendored one.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_MAX_CHARS = 2000
DEFAULT_OVERLAP_CHARS = 200
MIN_MAX_CHARS = 100

# Blank-line paragraph separator. Same expression RuleProvider always used.
_PARA_SEP = re.compile(r"\n\s*\n+")
# Sentence boundary: terminal punctuation (+ closing quotes/brackets) followed
# by whitespace, or a hard line break inside a paragraph (log lines, lists,
# code), which is the only boundary such text has.
_SENT_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*(?=\s)|\n")


@dataclass(frozen=True)
class Span:
    """A slice of the source text: ``source[start:end] == text``."""

    text: str
    start: int
    end: int
    strategy: str  # "paragraph" | "sentence" | "hard"


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def max_chars_from_env() -> int:
    return _env_int("LANGEXTRACT_MAX_CHARS", DEFAULT_MAX_CHARS, MIN_MAX_CHARS)


def overlap_chars_from_env() -> int:
    return _env_int("LANGEXTRACT_OVERLAP_CHARS", DEFAULT_OVERLAP_CHARS, 0)


def _resolve(max_chars: Optional[int], overlap_chars: Optional[int]) -> Tuple[int, int]:
    mc = max_chars_from_env() if max_chars is None else max(1, int(max_chars))
    ov = overlap_chars_from_env() if overlap_chars is None else max(0, int(overlap_chars))
    return mc, min(ov, mc // 2)


def _strip_bounds(text: str, start: int, end: int) -> Tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def iter_paragraphs(text: str) -> List[Tuple[int, int]]:
    """Return ``(start, end)`` of each non-empty, whitespace-trimmed paragraph."""
    text = text or ""
    out: List[Tuple[int, int]] = []
    pos = 0
    for m in _PARA_SEP.finditer(text):
        s, e = _strip_bounds(text, pos, m.start())
        if s < e:
            out.append((s, e))
        pos = m.end()
    s, e = _strip_bounds(text, pos, len(text))
    if s < e:
        out.append((s, e))
    return out


def _sentences(text: str, start: int, end: int) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    pos = start
    for m in _SENT_BOUNDARY.finditer(text, start, end):
        s, e = _strip_bounds(text, pos, m.end())
        if s < e:
            out.append((s, e))
        pos = m.end()
    s, e = _strip_bounds(text, pos, end)
    if s < e:
        out.append((s, e))
    return out


def _hard_split(text: str, start: int, end: int, max_chars: int, overlap: int) -> List[Span]:
    spans: List[Span] = []
    pos = start
    while pos < end:
        limit = min(pos + max_chars, end)
        cut = limit
        if limit < end:
            # Prefer the last whitespace in the back half of the window so a
            # word is not cut in two; fall back to a hard cut (no whitespace,
            # e.g. CJK or base64).
            ws = max(text.rfind(" ", pos, limit), text.rfind("\n", pos, limit), text.rfind("\t", pos, limit))
            if ws > pos + max_chars // 2:
                cut = ws
        s, e = _strip_bounds(text, pos, cut)
        if s < e:
            spans.append(Span(text[s:e], s, e, "hard"))
        if cut >= end:
            break
        nxt = max(cut - overlap, pos + 1)
        # Do not start the next window mid-word when a nearby space exists.
        if overlap and nxt > pos + 1:
            sp = text.find(" ", nxt, cut)
            if sp != -1 and sp + 1 < cut:
                nxt = sp + 1
        pos = nxt
    return spans


def split_span(
    text: str,
    start: int = 0,
    end: Optional[int] = None,
    *,
    max_chars: Optional[int] = None,
    overlap_chars: Optional[int] = None,
) -> List[Span]:
    """Split ``text[start:end]`` (one paragraph) into spans of ``<= max_chars``.

    Offsets in the returned spans are absolute into ``text``.
    """
    mc, ov = _resolve(max_chars, overlap_chars)
    end = len(text) if end is None else end
    start, end = _strip_bounds(text, start, end)
    if start >= end:
        return []
    if end - start <= mc:
        return [Span(text[start:end], start, end, "paragraph")]

    out: List[Span] = []
    buf_s: Optional[int] = None
    buf_e = 0

    def flush() -> None:
        nonlocal buf_s
        if buf_s is not None:
            out.append(Span(text[buf_s:buf_e], buf_s, buf_e, "sentence"))
            buf_s = None

    for s, e in _sentences(text, start, end):
        if e - s > mc:
            flush()
            out.extend(_hard_split(text, s, e, mc, ov))
            continue
        if buf_s is None:
            buf_s, buf_e = s, e
        elif e - buf_s <= mc:
            buf_e = e
        else:
            flush()
            buf_s, buf_e = s, e
    flush()
    return out


def chunk_text(
    text: str,
    *,
    max_chars: Optional[int] = None,
    overlap_chars: Optional[int] = None,
) -> List[List[Span]]:
    """Paragraph-first chunking: one inner list of capped spans per paragraph."""
    text = text or ""
    return [
        split_span(text, s, e, max_chars=max_chars, overlap_chars=overlap_chars)
        for s, e in iter_paragraphs(text)
    ]


def resplit_oversized(
    chunks: Sequence[Dict[str, Any]],
    *,
    threshold: int,
    max_chars: Optional[int] = None,
    overlap_chars: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Defence-in-depth guard for embedding endpoints.

    Any chunk whose ``text`` is longer than ``threshold`` characters is
    replaced by child chunks of ``<= max_chars`` (paragraph/sentence/hard
    ladder above). Children copy every key of the parent, get
    ``chunk_id = f"{parent}-r{k}"`` (``id`` too when the parent used it),
    ``parent_chunk_id``, and ``char_start``/``char_end`` (absolute when the
    parent carried ``char_start``, else relative to the parent text).

    Returns ``(chunks, n_oversized)``. Input dicts are never mutated.
    """
    out: List[Dict[str, Any]] = []
    n_over = 0
    for chunk in chunks:
        text = chunk.get("text") or ""
        if len(text) <= threshold:
            out.append(chunk)
            continue
        n_over += 1
        parent_id = chunk.get("chunk_id") or chunk.get("id")
        base_id = parent_id or "anon-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        base_off = chunk.get("char_start") if isinstance(chunk.get("char_start"), int) else 0
        pieces = [s for para in chunk_text(text, max_chars=max_chars, overlap_chars=overlap_chars) for s in para]
        for k, span in enumerate(pieces, start=1):
            child = dict(chunk)
            child_id = f"{base_id}-r{k}"
            child["chunk_id"] = child_id
            if "id" in chunk:
                child["id"] = child_id
            child["parent_chunk_id"] = parent_id
            child["text"] = span.text
            child["char_start"] = base_off + span.start
            child["char_end"] = base_off + span.end
            child["chunk_strategy"] = span.strategy
            child["resplit"] = True
            out.append(child)
    return out, n_over


__all__ = [
    "DEFAULT_MAX_CHARS",
    "DEFAULT_OVERLAP_CHARS",
    "Span",
    "chunk_text",
    "iter_paragraphs",
    "max_chars_from_env",
    "overlap_chars_from_env",
    "resplit_oversized",
    "split_span",
]
