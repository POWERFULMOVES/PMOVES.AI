"""Prosodic boundary types and data structures for human-like TTS chunking.

This module defines the core type system for prosodic analysis:
- BoundaryType: Enum for prosodic boundary strengths
- ProsodicChunk: Dataclass for text chunks with prosodic metadata
- PauseConfig: Configuration for pause duration and breath probability

Based on cognitive linguistics research on human speech patterns, these types
enable sub-100ms Time-To-First-Speech (TTFS) while maintaining natural prosody.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING  # NamedTuple replaced with dataclass


class BoundaryType(Enum):
    """Prosodic boundary strength determining pause and breath behavior.

    Higher values indicate stronger boundaries with longer pauses.
    The numeric values enable mathematical comparison (SENTENCE > CLAUSE > PHRASE).

    Attributes:
        SENTENCE: Period, exclamation, question mark. 300-400ms pause.
        CLAUSE: Comma, semicolon, colon, dash. 150-200ms pause.
        PHRASE: Before conjunctions (and, but, however). 80-120ms pause.
        BREATH: Forced breath point after ~10 syllables. 100-150ms pause.
        NONE: Continuous speech, crossfade only. 0ms pause.

    Example:
        >>> BoundaryType.SENTENCE.value > BoundaryType.CLAUSE.value
        True
        >>> BoundaryType.SENTENCE.name
        'SENTENCE'
    """

    SENTENCE = 4
    CLAUSE = 3
    PHRASE = 2
    BREATH = 1
    NONE = 0


@dataclass(frozen=True)
class PauseConfig:
    """Configuration for prosodic pause behavior.

    Attributes:
        pause_ms: Duration of pause in milliseconds.
        can_breath: Whether breath sounds are allowed at this boundary.
        breath_probability: Probability [0,1] of inserting breath sound.
    """

    pause_ms: float
    can_breath: bool
    breath_probability: float

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.pause_ms < 0:
            raise ValueError(f"PauseConfig.pause_ms must be non-negative, got {self.pause_ms}")
        if not 0.0 <= self.breath_probability <= 1.0:
            raise ValueError(
                f"PauseConfig.breath_probability must be in [0.0, 1.0], got {self.breath_probability}"
            )


# Pause configuration lookup table for each boundary type
PAUSE_CONFIGS: dict[BoundaryType, PauseConfig] = {
    BoundaryType.SENTENCE: PauseConfig(pause_ms=350.0, can_breath=True, breath_probability=0.35),
    BoundaryType.CLAUSE: PauseConfig(pause_ms=180.0, can_breath=True, breath_probability=0.15),
    BoundaryType.PHRASE: PauseConfig(pause_ms=100.0, can_breath=False, breath_probability=0.0),
    BoundaryType.BREATH: PauseConfig(pause_ms=130.0, can_breath=True, breath_probability=0.90),
    BoundaryType.NONE: PauseConfig(pause_ms=0.0, can_breath=False, breath_probability=0.0),
}


def get_pause_config(boundary: BoundaryType) -> PauseConfig:
    """Get pause configuration for a boundary type.

    Args:
        boundary: The prosodic boundary type.

    Returns:
        PauseConfig with pause_ms, can_breath, and breath_probability.

    Example:
        >>> config = get_pause_config(BoundaryType.SENTENCE)
        >>> config.pause_ms
        350.0
        >>> config.breath_probability
        0.35
    """
    return PAUSE_CONFIGS.get(boundary, PauseConfig(0.0, False, 0.0))


@dataclass
class ProsodicChunk:
    """A text chunk with prosodic metadata for TTS synthesis.

    Prosodic chunks represent segments of text that should be synthesized
    together, with metadata about their boundaries and position in the
    overall utterance.

    Attributes:
        text: The text content to synthesize.
        boundary_before: Prosodic boundary type preceding this chunk.
        boundary_after: Prosodic boundary type following this chunk.
        is_first: Whether this is the first chunk (ultra-low TTFS target).
        is_final: Whether this is the last chunk in the utterance.
        position_ratio: Position in utterance [0.0=start, 1.0=end].
        estimated_syllables: Estimated syllable count for breath planning.

    Example:
        >>> chunk = ProsodicChunk(
        ...     text="Hello, world!",
        ...     boundary_before=BoundaryType.SENTENCE,
        ...     boundary_after=BoundaryType.SENTENCE,
        ...     is_first=True,
        ...     estimated_syllables=4
        ... )
        >>> chunk.pause_after
        350.0
    """

    text: str
    boundary_before: BoundaryType
    boundary_after: BoundaryType
    is_first: bool = False
    is_final: bool = False
    position_ratio: float = 0.0
    estimated_syllables: int = 0

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if not self.text or not self.text.strip():
            raise ValueError("ProsodicChunk.text cannot be empty")
        if not 0.0 <= self.position_ratio <= 1.0:
            raise ValueError(
                f"ProsodicChunk.position_ratio must be in [0.0, 1.0], got {self.position_ratio}"
            )
        if self.estimated_syllables < 0:
            raise ValueError(
                f"ProsodicChunk.estimated_syllables must be non-negative, got {self.estimated_syllables}"
            )

    @property
    def pause_after(self) -> float:
        """Get pause duration in milliseconds after this chunk."""
        return get_pause_config(self.boundary_after).pause_ms

    @property
    def can_breath_after(self) -> bool:
        """Whether breath sounds are allowed after this chunk."""
        return get_pause_config(self.boundary_after).can_breath

    @property
    def breath_probability_after(self) -> float:
        """Probability of inserting breath sound after this chunk."""
        return get_pause_config(self.boundary_after).breath_probability

    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return (
            f"ProsodicChunk({self.text!r}, "
            f"after={self.boundary_after.name}, "
            f"pause={self.pause_after:.0f}ms)"
        )


# Phrase-starting words that trigger PHRASE boundaries
PHRASE_STARTERS: frozenset[str] = frozenset({
    # Conjunctions
    "and", "but", "or", "so", "yet", "nor",
    # Subordinating conjunctions
    "because", "although", "though", "while", "when",
    "if", "then", "unless", "until", "whereas",
    # Connectors and transitions
    "however", "therefore", "thus", "hence", "consequently",
    "first", "second", "third", "finally", "next", "lastly",
    "meanwhile", "furthermore", "moreover", "instead", "otherwise",
    # Question words (when mid-sentence)
    "what", "where", "why", "how",
})


# Sentence-ending punctuation
SENTENCE_ENDINGS: frozenset[str] = frozenset({".", "!", "?"})


# Clause-ending punctuation
CLAUSE_ENDINGS: frozenset[str] = frozenset({",", ";", ":", "-", "—", "..."})
