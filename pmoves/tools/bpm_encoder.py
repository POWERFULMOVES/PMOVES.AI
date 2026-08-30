#!/usr/bin/env python3
"""
bpm_encoder.py -- Prosodic BPM Encoder (Python port of musicMapping.ts)

Converts BPM / MIDI / frequency / prosodic boundaries into timing profiles
and CGP v0.2 packets for the Beats-to-Voice pipeline.

Source spec: pmoves/docs/AGENTS/AGNOTE4482.BEATS.md lines 136-327

Functions:
    midi_to_freq      -- 440 * 2^((midi-69)/12)
    freq_to_midi      -- round(69 + 12*log2(freq/440))
    midi_to_note_name -- C4, D#5, etc.
    note_name_to_midi -- parse note name to MIDI number
    boundary_to_bpm   -- SENTENCE=60, CLAUSE=90, PHRASE=120, BREATH=80, NONE=150
    encode_prosodic_profile -- generate prosodic chunks with timing
    build_cgp_packet  -- CGP v0.2 packet

CLI:
    python bpm_encoder.py encode --bpm 120 --pattern "kick snare kick snare"
    python bpm_encoder.py note --midi 60
    python bpm_encoder.py timeline --bpm 120 --duration 6
"""

from __future__ import annotations

import argparse
import hashlib
import asyncio
import json
import math
import re
import sys
import time
from typing import Any
try:
    from pmoves.services.common.chakra import CHAKRA_BANDS, chakra_to_band, freq_to_chakra
except ImportError:
    import pathlib as _pl
    sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
    from pmoves.services.common.chakra import freq_to_chakra
# ---------------------------------------------------------------------------
# Constants (mirrored from musicMapping.ts)
# ---------------------------------------------------------------------------

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

SCALES: dict[str, list[int]] = {
    "chromatic":       list(range(12)),
    "major":           [0, 2, 4, 5, 7, 9, 11],
    "minor":           [0, 2, 3, 5, 7, 8, 10],
    "pentatonicMajor": [0, 2, 4, 7, 9],
    "pentatonicMinor": [0, 3, 5, 7, 10],
}

# BPM <-> Prosodic Boundary mapping (from AGNOTE4482 spec)
BOUNDARY_BPM: dict[str, int] = {
    "SENTENCE": 60,
    "CLAUSE":   90,
    "PHRASE":   120,
    "BREATH":   80,
    "NONE":     150,
}

# Pause durations in milliseconds per boundary type
BOUNDARY_PAUSE_MS: dict[str, int] = {
    "SENTENCE": 350,
    "CLAUSE":   180,
    "PHRASE":   100,
    "BREATH":   130,
    "NONE":     0,
}


# Tempo labels (Italian musical terms)
TEMPO_LABELS: list[tuple[int, str]] = [
    (66,  "Largo"),
    (88,  "Andante"),
    (112, "Moderato"),
    (140, "Allegro"),
    (999, "Presto"),
]

# Base letter -> semitone offset from C
_BASE_INDEX: dict[str, int] = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}


# ---------------------------------------------------------------------------
# Core conversion functions
# ---------------------------------------------------------------------------

def midi_to_freq(midi: int, a4: float = 440.0) -> float:
    """Convert MIDI note number to frequency in Hz.

    >>> midi_to_freq(69)
    440.0
    >>> round(midi_to_freq(60), 2)
    261.63
    """
    return a4 * (2.0 ** ((midi - 69) / 12.0))


def freq_to_midi(freq: float, a4: float = 440.0) -> int:
    """Convert frequency in Hz to nearest MIDI note number.

    >>> freq_to_midi(440.0)
    69
    >>> freq_to_midi(261.63)
    60
    """
    if freq <= 0:
        raise ValueError(f"Frequency must be positive, got {freq}")
    return round(69 + 12 * math.log2(freq / a4))


def midi_to_note_name(midi: int) -> str:
    """Convert MIDI note number to note name with octave.

    >>> midi_to_note_name(60)
    'C4'
    >>> midi_to_note_name(69)
    'A4'
    >>> midi_to_note_name(63)
    'D#4'
    """
    m = round(midi)
    name = NOTE_NAMES[((m % 12) + 12) % 12]
    octave = (m // 12) - 1
    return f"{name}{octave}"


def note_name_to_midi(name: str) -> int:
    """Parse note name (e.g. C4, F#3, Bb2) to MIDI note number.

    Supports # (sharp) and b (flat) accidentals.

    >>> note_name_to_midi('C4')
    60
    >>> note_name_to_midi('A4')
    69
    >>> note_name_to_midi('F#3')
    54
    >>> note_name_to_midi('Bb2')
    46
    """
    m = re.match(r"^([A-Ga-g])([#b]?)(-?\d+)$", name.strip())
    if not m:
        raise ValueError(f'Invalid note name: "{name}"')
    letter = m.group(1).upper()
    accidental = m.group(2)
    octave = int(m.group(3))

    idx = _BASE_INDEX[letter]
    if accidental == "#":
        idx += 1
    elif accidental == "b":
        idx -= 1

    return (octave + 1) * 12 + ((idx % 12) + 12) % 12


# ---------------------------------------------------------------------------
# Visual mapping helpers (from musicMapping.ts freqToY / yToFreq)
# ---------------------------------------------------------------------------

def freq_to_y(freq: float, height_px: int,
              f_min: float = 27.5, f_max: float = 4186.01) -> float:
    """Map frequency to Y pixel coordinate (log scale).

    Top = high freq, bottom = low freq.
    """
    l_min = math.log2(f_min)
    l_max = math.log2(f_max)
    u = (math.log2(max(freq, f_min)) - l_min) / (l_max - l_min)
    clamped = min(1.0, max(0.0, u))
    return (1.0 - clamped) * height_px


# ---------------------------------------------------------------------------
# Boundary / BPM helpers
# ---------------------------------------------------------------------------

def boundary_to_bpm(boundary: str) -> int:
    """Map prosodic boundary type to BPM.

    >>> boundary_to_bpm('SENTENCE')
    60
    >>> boundary_to_bpm('phrase')
    120
    >>> boundary_to_bpm('NONE')
    150
    """
    key = boundary.upper().strip()
    if key not in BOUNDARY_BPM:
        raise ValueError(
            f"Unknown boundary '{boundary}'. "
            f"Expected one of: {', '.join(BOUNDARY_BPM)}"
        )
    return BOUNDARY_BPM[key]


def bpm_to_tempo_label(bpm: int) -> str:
    """Return Italian tempo marking for a BPM value.

    >>> bpm_to_tempo_label(60)
    'Largo'
    >>> bpm_to_tempo_label(120)
    'Allegro'
    """
    for threshold, label in TEMPO_LABELS:
        if bpm < threshold:
            return label
    return "Presto"


# ---------------------------------------------------------------------------
# Scale / degree helpers (from musicMapping.ts degreeToMidi)
# ---------------------------------------------------------------------------

def degree_to_midi(root_midi: int, degree: int, scale: str = "chromatic") -> int:
    """Convert a scale degree to a MIDI note relative to root."""
    if scale == "chromatic":
        return root_midi + degree
    pattern = SCALES.get(scale)
    if pattern is None:
        raise ValueError(f"Unknown scale '{scale}'. Known: {list(SCALES)}")
    steps_per_octave = len(pattern)
    octave = degree // steps_per_octave
    step = degree % steps_per_octave
    return root_midi + octave * 12 + pattern[step]

# ---------------------------------------------------------------------------
# Timeline builder (from musicMapping.ts buildTimeline)
# ---------------------------------------------------------------------------

def build_timeline(
    duration_sec: float,
    slices: int,
    bpm: float,
    root_midi: int = 60,
    scale: str = "chromatic",
    notes_per_beat: int = 1,
    mode: str = "step",
    a4: float = 440.0,
    plot_height_px: int | None = None,
    f_min: float = 27.5,
    f_max: float = 4186.01,
) -> list[dict[str, Any]]:
    """Build a beat timeline mapping time slices to notes/frequencies.

    Returns a list of TimelinePoint dicts with keys:
        t_sec, beats, beat_index, midi, freq, note, y_px (optional)
    """
    points: list[dict[str, Any]] = []
    dt = duration_sec / slices
    beats_per_sec = bpm / 60.0

    for i in range(slices + 1):
        t_sec = i * dt
        beats = t_sec * beats_per_sec
        note_pos = beats * notes_per_beat

        idx0 = int(math.floor(note_pos))
        frac = note_pos - idx0

        midi0 = degree_to_midi(root_midi, idx0, scale)
        midi = midi0

        if mode == "glide" and frac > 0:
            midi1 = degree_to_midi(root_midi, idx0 + 1, scale)
            f0 = midi_to_freq(midi0, a4)
            f1 = midi_to_freq(midi1, a4)
            # Perceptually smooth log-frequency interpolation
            f = 2.0 ** (math.log2(f0) + (math.log2(f1) - math.log2(f0)) * frac)
            midi = freq_to_midi(f, a4)

        freq = midi_to_freq(midi, a4)
        note = midi_to_note_name(midi)
        beat_index = int(math.floor(beats))

        point: dict[str, Any] = {
            "t_sec":      round(t_sec, 4),
            "beats":      round(beats, 4),
            "beat_index": beat_index,
            "midi":       midi,
            "freq":       round(freq, 2),
            "note":       note,
        }
        if plot_height_px is not None:
            point["y_px"] = round(freq_to_y(freq, plot_height_px, f_min, f_max), 2)
        points.append(point)

    return points


# ---------------------------------------------------------------------------
# Prosodic profile encoder
# ---------------------------------------------------------------------------

def _classify_boundary(token: str) -> str:
    """Heuristic boundary classification from punctuation."""
    stripped = token.rstrip()
    if stripped.endswith((".","!","?")):
        return "SENTENCE"
    if stripped.endswith((",",";")):
        return "CLAUSE"
    if stripped.endswith((":","-","--")):
        return "PHRASE"
    return "NONE"


def encode_prosodic_profile(text: str, bpm: int = 120) -> dict[str, Any]:
    """Generate a prosodic profile with timing for each chunk.

    Splits text on whitespace, classifies boundaries from punctuation,
    and assigns BPM-derived timing to each chunk.

    Returns:
        {
            "text": original text,
            "bpm": base BPM,
            "tempo_label": "Allegro",
            "chunks": [
                {
                    "text": "Hello",
                    "boundary": "NONE",
                    "bpm": 150,
                    "pause_ms": 0,
                    "start_sec": 0.0,
                    "duration_sec": 0.4,
                    "midi": 60,
                    "freq": 261.63,
                    "note": "C4",
                    "position_ratio": 0.0
                },
                ...
            ],
            "total_duration_sec": ...,
        }
    """
    tokens = text.split()
    if not tokens:
        return {
            "text": text, "bpm": bpm, "tempo_label": bpm_to_tempo_label(bpm),
            "chunks": [], "total_duration_sec": 0.0,
        }

    # Base beat duration from the overall BPM
    beat_sec = 60.0 / bpm
    # Each token gets one beat of speaking time
    # plus a pause determined by boundary type
    chunks: list[dict[str, Any]] = []
    cursor_sec = 0.0

    for i, token in enumerate(tokens):
        boundary = _classify_boundary(token)
        chunk_bpm = boundary_to_bpm(boundary) if boundary != "NONE" else bpm
        pause_ms = BOUNDARY_PAUSE_MS[boundary]
        pause_sec = pause_ms / 1000.0

        # Duration: proportional to token length relative to a "standard" 5-char word
        char_factor = max(0.5, len(token) / 5.0)
        duration_sec = round(beat_sec * char_factor, 4)

        # Map position ratio (0.0 -> 1.0) to MIDI 60-72 (C4-C5)
        position_ratio = i / max(1, len(tokens) - 1)
        midi = 60 + round(position_ratio * 12)
        freq = midi_to_freq(midi)

        chunks.append({
            "text":           token,
            "boundary":       boundary,
            "bpm":            chunk_bpm,
            "pause_ms":       pause_ms,
            "start_sec":      round(cursor_sec, 4),
            "duration_sec":   duration_sec,
            "midi":           midi,
            "freq":           round(freq, 2),
            "note":           midi_to_note_name(midi),
            "position_ratio": round(position_ratio, 4),
        })

        cursor_sec += duration_sec + pause_sec

    return {
        "text":               text,
        "bpm":                bpm,
        "tempo_label":        bpm_to_tempo_label(bpm),
        "chunks":             chunks,
        "total_duration_sec": round(cursor_sec, 4),
    }


# ---------------------------------------------------------------------------
# CGP v0.2 packet builder
# ---------------------------------------------------------------------------

def _stable_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()[:12]


def build_cgp_packet(profile: dict[str, Any], agent_id: str = "4090-claude") -> dict[str, Any]:
    """Wrap a prosodic profile as a CGP v0.2 packet for NATS.

    Subject: tokenism.prosodic.bpm.v1

    Returns a dict suitable for JSON serialization and NATS publish.
    """
    chunks = profile.get("chunks", [])
    bpm = profile.get("bpm", 120)

    # Build points from chunks (one per prosodic chunk)
    points: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        pos = chunk.get("position_ratio", 0.0)
        points.append({
            "id":       _stable_id(f"chunk_{i}_{chunk.get('text', '')}"),
            "label":    chunk.get("text", ""),
            "modality": "prosodic",
            "proj":     [pos, chunk.get("bpm", bpm) / 180.0, chunk.get("freq", 262) / 523.0],
            "conf":     1.0 - (chunk.get("pause_ms", 0) / 350.0),  # longer pause = lower conf
            "sv": {
                "delta":  round((chunk.get("bpm", bpm) - 60) / 120.0, 4),
                "kappa":  round(-(chunk.get("pause_ms", 0) / 350.0), 4),
                "Hz":     round(chunk.get("freq", 262) / 523.0, 4),
                "A":      round(1.0 - pos, 4),
                "F":      0.5,
            },
        })

    # Compute aggregate state vector
    avg_bpm = sum(c.get("bpm", bpm) for c in chunks) / max(len(chunks), 1)
    avg_freq = sum(c.get("freq", 262) for c in chunks) / max(len(chunks), 1)
    avg_pause = sum(c.get("pause_ms", 0) for c in chunks) / max(len(chunks), 1)

    state_vector = {
        "delta": round((avg_bpm - 60) / 120.0, 4),
        "kappa": round(-(avg_pause / 350.0), 4),
        "Hz":    round(avg_freq / 523.0, 4),
        "A":     0.75,
        "F":     0.5,
    }

    packet_id = _stable_id(f"prosodic_{profile.get('text', '')[:40]}_{bpm}")

    return {
        "spec":    "chit.cgp.v0.2",
        "type":    "tokenism.prosodic.bpm.v1",
        "id":      packet_id,
        "label":   f"Prosodic @ {bpm} BPM",
        "source":  agent_id,
        "ts":      time.time(),
        "super_nodes": [{
            "id":          _stable_id(f"sn_prosodic_{bpm}"),
            "label":       f"Prosodic Profile ({profile.get('tempo_label', '')})",
            "type":        "prosodic_constellation",
            "x":           state_vector["delta"],
            "y":           state_vector["Hz"],
            "r":           10.0,
            "state_vector": state_vector,
            "constellations": [{
                "id":      _stable_id(f"c_prosodic_{bpm}"),
                "label":   f"Chunks @ {bpm} BPM",
                "anchor":  [state_vector["delta"], state_vector["Hz"], 0.5],
                "spectrum": [state_vector["Hz"], state_vector["delta"], 1.0],
                "points":  points,
            }],
        }],
        "control_plane": {
            "state_vector":  state_vector,
            "param_surface": {
                "temperature":   0.3 + state_vector["delta"] * 0.4,
                "top_k":         max(5, round(state_vector["Hz"] * 20)),
                "speaking_rate": round(bpm / 120.0, 2),
            },
            "chakra": freq_to_chakra(avg_freq) if chunks else None,
        },
        "prosodic_profile": {
            "text":               profile.get("text", ""),
            "bpm":                bpm,
            "tempo_label":        profile.get("tempo_label", ""),
            "total_duration_sec": profile.get("total_duration_sec", 0.0),
            "chunk_count":        len(chunks),
        },
    }


# ---------------------------------------------------------------------------
# CLI (argparse)
# ---------------------------------------------------------------------------

def _cmd_encode(args: argparse.Namespace) -> None:
    """Encode a prosodic profile from text + BPM."""
    text = args.pattern if args.pattern else "kick snare kick snare"
    profile = encode_prosodic_profile(text, bpm=args.bpm)

    if args.cgp:
        packet = build_cgp_packet(profile, agent_id=args.agent_id)
        print(json.dumps(packet, indent=2))

        if args.publish:
            subject = args.subject or "tokenism.prosodic.bpm.v1"
            import os as _os
            from pmoves.services.common.nats_client import publish_cgp as _pub
            published = asyncio.run(_pub(packet, subject=subject, nats_url=_os.getenv("NATS_URL", "")))
            print(json.dumps({"nats_published": published, "subject": subject}))
    else:
        print(json.dumps(profile, indent=2))


def _cmd_note(args: argparse.Namespace) -> None:
    """Print note name and frequency for a MIDI number."""
    midi = args.midi
    freq = midi_to_freq(midi)
    name = midi_to_note_name(midi)
    y = freq_to_y(freq, args.height) if args.height else None

    result = {
        "midi": midi,
        "note": name,
        "freq_hz": round(freq, 4),
    }
    if y is not None:
        result["y_px"] = round(y, 2)
        result["height_px"] = args.height

    print(json.dumps(result, indent=2))


def _cmd_timeline(args: argparse.Namespace) -> None:
    """Print a beat timeline."""
    slices = args.slices if args.slices else int(args.duration * 2)
    points = build_timeline(
        duration_sec=args.duration,
        slices=slices,
        bpm=args.bpm,
        root_midi=args.root,
        scale=args.scale,
        notes_per_beat=args.notes_per_beat,
        mode=args.mode,
        plot_height_px=args.height if args.height else None,
    )
    print(json.dumps(points, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bpm_encoder",
        description="Prosodic BPM Encoder -- Python port of musicMapping.ts",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- encode --
    p_enc = sub.add_parser("encode", help="Encode prosodic profile from text + BPM")
    p_enc.add_argument("--bpm", type=int, default=120, help="Beats per minute (default: 120)")
    p_enc.add_argument("--pattern", type=str, default="", help="Text pattern to encode")
    p_enc.add_argument("--cgp", action="store_true", help="Output as CGP v0.2 packet")
    p_enc.add_argument("--agent-id", type=str, default="4090-claude", help="Agent ID for CGP packet")
    p_enc.add_argument("--publish", action="store_true", help="Publish CGP packet to NATS")
    p_enc.add_argument("--subject", type=str, default="", help="NATS subject (default: tokenism.prosodic.bpm.v1)")
    p_enc.set_defaults(func=_cmd_encode)

    # -- note --
    p_note = sub.add_parser("note", help="Print note name + frequency for a MIDI number")
    p_note.add_argument("--midi", type=int, required=True, help="MIDI note number")
    p_note.add_argument("--height", type=int, default=0, help="Plot height in pixels (0 = skip y_px)")
    p_note.set_defaults(func=_cmd_note)

    # -- timeline --
    p_tl = sub.add_parser("timeline", help="Print beat timeline")
    p_tl.add_argument("--bpm", type=float, default=120, help="Beats per minute")
    p_tl.add_argument("--duration", type=float, default=6, help="Duration in seconds")
    p_tl.add_argument("--slices", type=int, default=0, help="Number of time slices (0 = auto)")
    p_tl.add_argument("--root", type=int, default=60, help="Root MIDI note (default: 60 = C4)")
    p_tl.add_argument("--scale", type=str, default="chromatic",
                       choices=list(SCALES.keys()), help="Musical scale")
    p_tl.add_argument("--notes-per-beat", type=int, default=1, help="Notes per beat")
    p_tl.add_argument("--mode", type=str, default="step", choices=["step", "glide"],
                       help="Note transition mode")
    p_tl.add_argument("--height", type=int, default=0, help="Plot height for y_px (0 = skip)")
    p_tl.set_defaults(func=_cmd_timeline)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
