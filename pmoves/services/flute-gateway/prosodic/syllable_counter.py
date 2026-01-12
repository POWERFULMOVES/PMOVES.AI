"""Syllable estimation for prosodic breath planning.

This module provides fast, approximate syllable counting for English text.
Used to determine when to insert breath points (typically every ~10 syllables).

The algorithm uses vowel-run counting with adjustments for common patterns
like silent-e. While not 100% accurate, it's fast enough for real-time
processing and sufficiently accurate for breath planning purposes.
"""

from __future__ import annotations

import re

# Vowel characters for syllable detection
VOWELS: frozenset[str] = frozenset("aeiouy")


def estimate_syllables(word: str) -> int:
    """Estimate syllable count for a single word.

    Uses vowel-run counting with adjustment for common English patterns:
    1. Count consecutive vowel groups as one syllable
    2. Subtract one for silent final -e (when word has multiple syllables)

    Args:
        word: A single word to analyze.

    Returns:
        Estimated syllable count (minimum 1 for non-empty words).

    Example:
        >>> estimate_syllables("hello")
        2
        >>> estimate_syllables("world")
        1
        >>> estimate_syllables("beautiful")
        4
        >>> estimate_syllables("breathe")
        1
        >>> estimate_syllables("")
        0
    """
    # Strip punctuation and convert to lowercase
    word = re.sub(r"[.,!?;:\"'\-]", "", word.lower())
    if not word:
        return 0

    count = 0
    prev_was_vowel = False

    for char in word:
        is_vowel = char in VOWELS
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel

    # Adjust for silent final -e (common English pattern)
    # "breathe" -> 1 syllable, not 2
    # "love" -> 1 syllable, not 2
    if word.endswith("e") and count > 1:
        # Check if it's likely a silent-e word
        # Don't subtract for words ending in -le, -re, -ne where e is pronounced
        if len(word) >= 2 and word[-2] not in "lrn":
            count -= 1

    return max(1, count)


def count_syllables_in_text(text: str) -> int:
    """Count total estimated syllables in a text string.

    Args:
        text: Input text (can be multiple words).

    Returns:
        Total estimated syllable count.

    Example:
        >>> count_syllables_in_text("Hello, world!")
        3
        >>> count_syllables_in_text("The quick brown fox")
        4
    """
    words = text.strip().split()
    return sum(estimate_syllables(word) for word in words)


def syllables_per_word(text: str) -> list[tuple[str, int]]:
    """Get syllable count for each word in text.

    Useful for debugging and understanding breath point placement.

    Args:
        text: Input text string.

    Returns:
        List of (word, syllable_count) tuples.

    Example:
        >>> syllables_per_word("beautiful butterfly")
        [('beautiful', 4), ('butterfly', 3)]
    """
    words = text.strip().split()
    return [(word, estimate_syllables(word)) for word in words]
