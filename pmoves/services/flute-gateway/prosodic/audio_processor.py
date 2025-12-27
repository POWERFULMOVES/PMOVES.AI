"""Audio processing utilities for prosodic TTS stitching.

This module provides audio manipulation functions for:
1. Silence generation with configurable duration
2. Breath sound synthesis using filtered noise
3. Smooth transitions to prevent clicks
4. Prosodic stitching with boundary-aware pauses

All functions operate on float32 audio arrays normalized to [-1, 1].
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Optional
import random

from .types import BoundaryType, get_pause_config

logger = logging.getLogger(__name__)

# Optional scipy for better breath sound filtering
try:
    import scipy.signal as signal
    HAS_SCIPY = True
    logger.info("scipy.signal available - using Butterworth filter for breath sounds")
except ImportError:
    HAS_SCIPY = False
    logger.info("scipy.signal not available - using moving average fallback for breath sounds")


def silence(duration_ms: float, sample_rate: int = 22050) -> np.ndarray:
    """Generate silence of specified duration.

    Args:
        duration_ms: Silence duration in milliseconds.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Float32 array of zeros.

    Example:
        >>> sil = silence(100, sample_rate=22050)
        >>> len(sil)
        2205
    """
    samples = int(sample_rate * duration_ms / 1000)
    return np.zeros(samples, dtype=np.float32)


def breath_sound(
    duration_ms: float = 80,
    intensity: float = 0.015,
    sample_rate: int = 22050,
) -> np.ndarray:
    """Generate a subtle breath/inhalation sound.

    Uses filtered white noise with an attack-decay envelope to
    simulate human breath intake. The result is subliminal but
    adds naturalness to pauses.

    Args:
        duration_ms: Breath sound duration in milliseconds.
        intensity: Maximum amplitude [0, 1]. Default 0.015 is subtle.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Float32 audio array with breath sound.

    Example:
        >>> breath = breath_sound(80, intensity=0.015)
        >>> np.max(np.abs(breath)) <= 0.015
        True
    """
    samples = int(sample_rate * duration_ms / 1000)
    if samples <= 0:
        return np.array([], dtype=np.float32)

    # Generate white noise
    noise = np.random.randn(samples).astype(np.float32)

    # Low-pass filter for "breathy" quality
    if HAS_SCIPY:
        # 600Hz cutoff for breath-like spectrum
        nyquist = sample_rate / 2
        cutoff = min(600 / nyquist, 0.99)  # Ensure valid cutoff
        b, a = signal.butter(2, cutoff, btype="low")
        breath = signal.filtfilt(b, a, noise).astype(np.float32)
    else:
        # Fallback: simple moving average smoothing
        kernel_size = max(30, samples // 20)
        kernel = np.ones(kernel_size) / kernel_size
        breath = np.convolve(noise, kernel, mode="same").astype(np.float32)

    # Attack-decay envelope: quick attack (20%), gradual decay (80%)
    attack_samples = samples // 5
    decay_samples = samples - attack_samples

    envelope = np.concatenate([
        np.linspace(0, 1, attack_samples, dtype=np.float32),
        np.linspace(1, 0.3, decay_samples, dtype=np.float32),
    ])

    return breath * envelope * intensity


def smooth_transition(
    audio: np.ndarray,
    fade_in: bool = True,
    fade_out: bool = True,
    fade_ms: float = 12,
    sample_rate: int = 22050,
) -> np.ndarray:
    """Apply smooth energy transitions to audio edges.

    Prevents clicks and pops at chunk boundaries by applying
    subtle fade-in and fade-out envelopes.

    Args:
        audio: Input audio array.
        fade_in: Whether to apply fade-in at start.
        fade_out: Whether to apply fade-out at end.
        fade_ms: Fade duration in milliseconds.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Audio with smooth transitions applied.
    """
    if len(audio) == 0:
        return audio

    fade_samples = int(sample_rate * fade_ms / 1000)
    if len(audio) < fade_samples * 2:
        # Audio too short for fades, return as-is
        return audio

    out = audio.copy()

    if fade_in and fade_samples > 0:
        # Gentle ramp from 85% to 100%
        out[:fade_samples] *= np.linspace(0.85, 1.0, fade_samples, dtype=np.float32)

    if fade_out and fade_samples > 0:
        # Gentle ramp from 100% to 90%
        out[-fade_samples:] *= np.linspace(1.0, 0.9, fade_samples, dtype=np.float32)

    return out


def crossfade(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    crossfade_ms: float = 10,
    sample_rate: int = 22050,
) -> np.ndarray:
    """Crossfade between two audio segments.

    Creates a smooth transition by overlapping the end of audio_a
    with the beginning of audio_b using linear crossfade.

    Args:
        audio_a: First audio segment.
        audio_b: Second audio segment.
        crossfade_ms: Crossfade duration in milliseconds.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Concatenated audio with crossfade transition.
    """
    if len(audio_a) == 0:
        return audio_b
    if len(audio_b) == 0:
        return audio_a

    fade_samples = int(sample_rate * crossfade_ms / 1000)
    if fade_samples <= 0 or len(audio_a) < fade_samples or len(audio_b) < fade_samples:
        # Can't crossfade, just concatenate
        return np.concatenate([audio_a, audio_b])

    # Linear crossfade weights
    weights = np.linspace(0, 1, fade_samples, dtype=np.float32)

    return np.concatenate([
        audio_a[:-fade_samples],
        audio_a[-fade_samples:] * (1 - weights) + audio_b[:fade_samples] * weights,
        audio_b[fade_samples:],
    ])


def prosodic_stitch(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    boundary: BoundaryType,
    sample_rate: int = 22050,
    rng: Optional[random.Random] = None,
) -> np.ndarray:
    """Stitch audio segments with prosodically-appropriate transitions.

    This is the main stitching function that combines:
    1. Boundary-appropriate pause duration
    2. Optional breath sound insertion
    3. Smooth energy transitions

    Args:
        audio_a: First audio segment.
        audio_b: Second audio segment.
        boundary: Prosodic boundary type between segments.
        sample_rate: Audio sample rate in Hz.
        rng: Optional random number generator for reproducibility.

    Returns:
        Stitched audio with appropriate prosodic transition.

    Example:
        >>> a = np.ones(1000, dtype=np.float32)
        >>> b = np.ones(1000, dtype=np.float32) * 0.5
        >>> stitched = prosodic_stitch(a, b, BoundaryType.SENTENCE)
        >>> len(stitched) > len(a) + len(b)  # Due to pause insertion
        True
    """
    if len(audio_a) == 0:
        return audio_b
    if len(audio_b) == 0:
        return audio_a

    if rng is None:
        rng = random.Random()

    pause_config = get_pause_config(boundary)
    pause_ms = pause_config.pause_ms
    can_breath = pause_config.can_breath
    breath_prob = pause_config.breath_probability

    if pause_ms > 0:
        # Build transition with pause and optional breath
        parts = []

        # Smooth end of first segment
        parts.append(smooth_transition(audio_a, fade_in=False, fade_out=True, sample_rate=sample_rate))

        # Insert breath sound with configured probability
        if can_breath and rng.random() < breath_prob:
            breath_duration = min(pause_ms * 0.6, 90)  # Max 90ms breath
            parts.append(breath_sound(breath_duration, sample_rate=sample_rate))
            parts.append(silence(pause_ms - breath_duration, sample_rate=sample_rate))
        else:
            parts.append(silence(pause_ms, sample_rate=sample_rate))

        # Smooth start of second segment
        parts.append(smooth_transition(audio_b, fade_in=True, fade_out=False, sample_rate=sample_rate))

        return np.concatenate(parts)

    # No pause needed: quick crossfade
    return crossfade(audio_a, audio_b, crossfade_ms=10, sample_rate=sample_rate)


def stitch_chunks(
    audio_chunks: list[np.ndarray],
    boundaries: list[BoundaryType],
    sample_rate: int = 22050,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Stitch multiple audio chunks with prosodic transitions.

    Args:
        audio_chunks: List of audio arrays to stitch.
        boundaries: List of boundary types between chunks.
            Length should be len(audio_chunks) - 1.
        sample_rate: Audio sample rate in Hz.
        seed: Random seed for reproducible breath insertion.

    Returns:
        Single audio array with all chunks stitched.

    Raises:
        ValueError: If boundaries list has wrong length.
    """
    if not audio_chunks:
        return np.array([], dtype=np.float32)

    if len(audio_chunks) == 1:
        return audio_chunks[0]

    if len(boundaries) != len(audio_chunks) - 1:
        raise ValueError(
            f"Expected {len(audio_chunks) - 1} boundaries, got {len(boundaries)}"
        )

    rng = random.Random(seed) if seed is not None else None

    result = audio_chunks[0]
    for chunk, boundary in zip(audio_chunks[1:], boundaries, strict=True):
        result = prosodic_stitch(result, chunk, boundary, sample_rate=sample_rate, rng=rng)

    return result
