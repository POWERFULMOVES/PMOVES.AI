"""Prosodic text parser for natural speech chunking.

This module provides the main parse_prosodic() function that converts
text into ProsodicChunk sequences ready for TTS synthesis.

Key features:
1. Ultra-low TTFS: First chunk is minimal (2 words by default)
2. Natural breaks: Chunks at punctuation and phrase boundaries
3. Breath planning: Forces breath points every ~10 syllables
4. Position tracking: Each chunk knows its position in the utterance
"""

from __future__ import annotations

from .types import BoundaryType, ProsodicChunk
from .syllable_counter import estimate_syllables
from .boundary_detector import detect_boundary


def parse_prosodic(
    text: str,
    first_chunk_words: int = 2,
    max_syllables_before_breath: int = 10,
    min_words_per_chunk: int = 2,
) -> list[ProsodicChunk]:
    """Parse text into prosodically-aware chunks for TTS synthesis.

    Strategy:
    1. First chunk: Minimal (first_chunk_words) for ultra-low TTFS
    2. Break at natural boundaries: punctuation, phrase-starters
    3. Force breath points: Every ~10 syllables if no natural break
    4. Track position: For intonation modeling (position_ratio)

    Args:
        text: Input text to parse.
        first_chunk_words: Number of words in first chunk (default 2).
            Smaller = faster TTFS but potentially less natural.
        max_syllables_before_breath: Force breath break after this many
            syllables without a natural boundary (default 10).
        min_words_per_chunk: Minimum words before allowing a break
            at non-sentence boundaries (default 2).

    Returns:
        List of ProsodicChunk objects ready for TTS synthesis.

    Example:
        >>> chunks = parse_prosodic("Hello! This is a test.")
        >>> [c.text for c in chunks]
        ['Hello! This', 'is a test.']
        >>> chunks[0].is_first
        True
        >>> chunks[-1].is_final
        True
    """
    words = text.strip().split()
    if not words:
        return []

    chunks: list[ProsodicChunk] = []
    total_words = len(words)

    # === FIRST CHUNK: Minimal for ultra-low TTFS ===
    n_first = min(first_chunk_words, len(words))
    first_text = " ".join(words[:n_first])

    # Detect boundary after first chunk
    first_boundary = detect_boundary(
        words[n_first - 1],
        words[n_first] if n_first < len(words) else None,
    )

    # Calculate syllables for first chunk
    first_syllables = sum(estimate_syllables(w) for w in words[:n_first])

    chunks.append(
        ProsodicChunk(
            text=first_text,
            boundary_before=BoundaryType.SENTENCE,  # Start of utterance
            boundary_after=first_boundary,
            is_first=True,
            is_final=(n_first == len(words)),
            position_ratio=n_first / total_words,
            estimated_syllables=first_syllables,
        )
    )

    # If first chunk consumed all words, we're done
    if n_first >= len(words):
        return chunks

    # === REMAINING CHUNKS: Prosodic boundaries ===
    current_words: list[str] = []
    syllables_since_break = 0

    for i in range(n_first, len(words)):
        word = words[i]
        next_word = words[i + 1] if i + 1 < len(words) else None

        current_words.append(word)
        syllables_since_break += estimate_syllables(word)

        boundary = detect_boundary(word, next_word)

        # Decision: should we break here?
        should_break = False

        if boundary == BoundaryType.SENTENCE:
            # Always break at sentence endings
            should_break = True
        elif boundary == BoundaryType.CLAUSE and len(current_words) >= min_words_per_chunk:
            # Break at clause boundaries if we have enough words
            should_break = True
        elif boundary == BoundaryType.PHRASE and len(current_words) >= min_words_per_chunk:
            # Break at phrase boundaries if we have enough words
            should_break = True
        elif (
            syllables_since_break >= max_syllables_before_breath
            and len(current_words) >= 3
        ):
            # Force breath point if no natural break for too long
            # Preserve natural boundaries if present, only force BREATH for NONE
            if boundary == BoundaryType.NONE:
                boundary = BoundaryType.BREATH
            should_break = True

        if should_break:
            words_processed = i + 1
            chunks.append(
                ProsodicChunk(
                    text=" ".join(current_words),
                    boundary_before=chunks[-1].boundary_after,
                    boundary_after=boundary,
                    is_first=False,
                    is_final=(i == len(words) - 1),
                    position_ratio=words_processed / total_words,
                    estimated_syllables=syllables_since_break,
                )
            )
            current_words = []
            syllables_since_break = 0

    # Handle any remaining words (shouldn't happen often, but safety first)
    if current_words:
        chunks.append(
            ProsodicChunk(
                text=" ".join(current_words),
                boundary_before=chunks[-1].boundary_after if chunks else BoundaryType.SENTENCE,
                boundary_after=BoundaryType.SENTENCE,  # End of utterance
                is_first=False,
                is_final=True,
                position_ratio=1.0,
                estimated_syllables=syllables_since_break,
            )
        )

    return chunks


def format_prosodic_analysis(text: str, first_chunk_words: int = 2) -> str:
    """Format prosodic analysis for human-readable output.

    Useful for debugging and understanding chunking decisions.

    Args:
        text: Input text to analyze.
        first_chunk_words: Words in first chunk.

    Returns:
        Formatted string showing chunks with boundary info.

    Example:
        >>> print(format_prosodic_analysis("Hello, world! How are you?"))
        Prosodic Analysis (3 chunks):
          [1] "Hello, world!" → SENTENCE (350ms)
          [2] "How are" → NONE (0ms)
          [3] "you?" → SENTENCE (350ms)
    """
    chunks = parse_prosodic(text, first_chunk_words=first_chunk_words)

    lines = [f"Prosodic Analysis ({len(chunks)} chunks):"]
    for i, chunk in enumerate(chunks, 1):
        pause = chunk.pause_after
        symbol = "→" if pause > 0 else "—"
        lines.append(
            f'  [{i}] "{chunk.text}" {symbol} {chunk.boundary_after.name} ({pause:.0f}ms)'
        )

    return "\n".join(lines)
