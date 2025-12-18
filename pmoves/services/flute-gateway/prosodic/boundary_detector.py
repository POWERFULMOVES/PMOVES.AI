"""Prosodic boundary detection for natural speech chunking.

This module detects prosodic boundaries between words based on:
1. Punctuation (periods, commas, semicolons, etc.)
2. Phrase-starting words (conjunctions, transitions)

The detection order matters - phrase boundaries before major connectors
take precedence over clause boundaries from trailing commas for more
natural prosody.
"""

from __future__ import annotations

import re
from typing import Optional

from .types import BoundaryType, PHRASE_STARTERS


def detect_boundary(word: str, next_word: Optional[str] = None) -> BoundaryType:
    """Detect the prosodic boundary type after a word.

    Analyzes the current word's punctuation and the next word to determine
    the appropriate prosodic boundary. Detection priority:
    1. Sentence endings (. ! ?)
    2. Phrase boundaries (before conjunctions/transitions)
    3. Clause boundaries (, ; : - —)
    4. No boundary (continuous speech)

    Args:
        word: The current word (may include trailing punctuation).
        next_word: The following word, if any. Used for phrase detection.

    Returns:
        BoundaryType indicating the boundary strength after this word.

    Example:
        >>> detect_boundary("Hello!", None)
        <BoundaryType.SENTENCE: 4>
        >>> detect_boundary("Well,", "however")
        <BoundaryType.PHRASE: 2>
        >>> detect_boundary("first,", "we")
        <BoundaryType.CLAUSE: 3>
        >>> detect_boundary("the", "dog")
        <BoundaryType.NONE: 0>
    """
    word = word.strip()
    if not word:
        return BoundaryType.NONE

    # Check for sentence endings (highest priority)
    # Note: This also handles ellipsis (...) since it ends with '.'
    if re.search(r"[.!?]$", word):
        return BoundaryType.SENTENCE

    # Check for phrase boundary BEFORE checking clause punctuation
    # This gives "Well, however" -> PHRASE instead of CLAUSE
    if next_word:
        next_lower = next_word.lower().strip(".,!?;:\"'-")
        if next_lower in PHRASE_STARTERS:
            return BoundaryType.PHRASE

    # Check for clause boundaries (commas, semicolons, colons, dashes)
    if re.search(r"[,;:\-—]$", word):
        return BoundaryType.CLAUSE

    return BoundaryType.NONE


def detect_boundaries_in_text(text: str) -> list[tuple[str, BoundaryType]]:
    """Detect boundaries for all words in a text.

    Useful for debugging and visualization of prosodic structure.

    Args:
        text: Input text to analyze.

    Returns:
        List of (word, boundary_after) tuples.

    Example:
        >>> result = detect_boundaries_in_text("Hello, world!")
        >>> [(w, b.name) for w, b in result]
        [('Hello,', 'CLAUSE'), ('world!', 'SENTENCE')]
    """
    words = text.strip().split()
    if not words:
        return []

    result = []
    for i, word in enumerate(words):
        next_word = words[i + 1] if i + 1 < len(words) else None
        boundary = detect_boundary(word, next_word)
        result.append((word, boundary))

    return result


def find_chunk_points(text: str, min_words: int = 2) -> list[int]:
    """Find word indices where chunks should break.

    Returns indices (0-based) where the text should be split.
    Does not include 0 (start) or len(words) (end).

    Args:
        text: Input text to analyze.
        min_words: Minimum words per chunk (prevents tiny fragments).

    Returns:
        List of word indices where breaks should occur (exclusive).

    Example:
        >>> text = "Hello, world! How are you?"
        >>> find_chunk_points(text, min_words=1)
        [2, 5]  # Break after "world!" and after "you?"
    """
    words = text.strip().split()
    if len(words) <= min_words:
        return []

    points = []
    words_since_break = 0

    for i, word in enumerate(words[:-1]):  # Exclude last word
        next_word = words[i + 1]
        boundary = detect_boundary(word, next_word)
        words_since_break += 1

        # Only break at significant boundaries with enough words
        if boundary != BoundaryType.NONE and words_since_break >= min_words:
            points.append(i + 1)  # Break after this word
            words_since_break = 0

    return points
