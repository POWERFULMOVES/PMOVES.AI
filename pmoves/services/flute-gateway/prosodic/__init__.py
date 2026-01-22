"""Prosodic TTS Sidecar - Natural speech chunking for low-latency synthesis.

This module provides prosodically-aware text chunking for TTS synthesis,
enabling sub-100ms Time-To-First-Speech (TTFS) while maintaining natural
human-like prosody.

Key Components:
    BoundaryType: Enum for prosodic boundary strengths (SENTENCE > CLAUSE > PHRASE)
    ProsodicChunk: Dataclass representing a text chunk with prosodic metadata
    parse_prosodic: Main parsing function that converts text to chunk sequences
    prosodic_stitch: Audio stitching with boundary-appropriate pauses and breaths

Example:
    >>> from prosodic import parse_prosodic, BoundaryType
    >>> chunks = parse_prosodic("Hello, world! How are you?")
    >>> for chunk in chunks:
    ...     print(f"{chunk.text} -> {chunk.boundary_after.name}")
    Hello, world! -> SENTENCE
    How are you? -> SENTENCE

Performance Targets:
    - TTFS: ~160ms (vs ~750ms baseline, ~300ms naive chunking)
    - Quality: Natural pauses at sentence/clause boundaries
    - Breath sounds: Inserted at ~10 syllable intervals with 90% probability

Theory:
    Human speech patterns follow prosodic hierarchies where pauses correlate
    with linguistic boundary strength. This module mimics that by:
    1. Analyzing punctuation and phrase-starter words
    2. Tracking syllable counts for breath point planning
    3. Applying appropriate pause durations (350ms for sentences, 180ms for clauses)
    4. Optionally inserting subtle breath sounds at natural pause points
"""

from .types import (
    BoundaryType,
    ProsodicChunk,
    PauseConfig,
    get_pause_config,
    PAUSE_CONFIGS,
    PHRASE_STARTERS,
    SENTENCE_ENDINGS,
    CLAUSE_ENDINGS,
)

from .syllable_counter import (
    estimate_syllables,
    count_syllables_in_text,
    syllables_per_word,
)

from .boundary_detector import (
    detect_boundary,
    detect_boundaries_in_text,
    find_chunk_points,
)

from .prosodic_parser import (
    parse_prosodic,
    format_prosodic_analysis,
)

from .audio_processor import (
    silence,
    breath_sound,
    smooth_transition,
    crossfade,
    prosodic_stitch,
    stitch_chunks,
)

__all__ = [
    # Types
    "BoundaryType",
    "ProsodicChunk",
    "PauseConfig",
    "get_pause_config",
    "PAUSE_CONFIGS",
    "PHRASE_STARTERS",
    "SENTENCE_ENDINGS",
    "CLAUSE_ENDINGS",
    # Syllable counting
    "estimate_syllables",
    "count_syllables_in_text",
    "syllables_per_word",
    # Boundary detection
    "detect_boundary",
    "detect_boundaries_in_text",
    "find_chunk_points",
    # Prosodic parsing
    "parse_prosodic",
    "format_prosodic_analysis",
    # Audio processing
    "silence",
    "breath_sound",
    "smooth_transition",
    "crossfade",
    "prosodic_stitch",
    "stitch_chunks",
]

__version__ = "0.1.0"
