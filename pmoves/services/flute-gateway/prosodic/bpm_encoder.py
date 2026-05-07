"""BPM encoder for prosodic chunks — bridges Flute prosodic parser with CHIT Geometry Bus.

Converts ProsodicChunk[] into BPM-encoded CGP v0.2 packets for voice attribution,
then optionally publishes to NATS subject ``tokenism.prosodic.bpm.v1``.

BPM mapping follows musical tempo markings:
    SENTENCE = 60 BPM (Largo)   — full stop, slow breath
    BREATH   = 80 BPM (Adagio)  — natural breath point
    CLAUSE   = 90 BPM (Andante) — comma pause, walking pace
    PHRASE   = 120 BPM (Allegro) — conjunction, quick transition
    NONE     = 150 BPM (Presto) — continuous speech, no pause
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .types import BoundaryType, ProsodicChunk

# ---------------------------------------------------------------------------
# BPM and MIDI constants (from .claude/commands/chit/bpm.md spec)
# ---------------------------------------------------------------------------

BPM_MAP: dict[BoundaryType, int] = {
    BoundaryType.SENTENCE: 60,
    BoundaryType.CLAUSE: 90,
    BoundaryType.PHRASE: 120,
    BoundaryType.BREATH: 80,
    BoundaryType.NONE: 150,
}

MIDI_OFFSET: dict[BoundaryType, int] = {
    BoundaryType.SENTENCE: 0,   # C4
    BoundaryType.CLAUSE: 4,     # E4
    BoundaryType.PHRASE: 7,     # G4
    BoundaryType.BREATH: 2,     # D4
    BoundaryType.NONE: 12,      # C5
}

# Milliseconds per syllable estimate (150ms average spoken English)
_MS_PER_SYLLABLE = 150

# 7-chakra axis — mirrors pmoves/tools/bpm_encoder.py CHAKRA_BANDS (AGNOTE4482FLUTE.md Movement I)
CHAKRA_BANDS: list[dict[str, Any]] = [
    {"name": "muladhara",    "label": "Root",      "element": "Earth",
     "bpm_min": 40,  "bpm_max": 55,  "hz": 65.41,  "note": "C2", "boundary": "SENTENCE",
     "breath_in_sec": 6, "breath_out_sec": 6},
    {"name": "svadhisthana", "label": "Sacral",    "element": "Water",
     "bpm_min": 55,  "bpm_max": 70,  "hz": 146.83, "note": "D3", "boundary": "BREATH",
     "breath_in_sec": 5, "breath_out_sec": 5},
    {"name": "manipura",     "label": "Solar",     "element": "Fire",
     "bpm_min": 70,  "bpm_max": 90,  "hz": 164.81, "note": "E3", "boundary": "CLAUSE",
     "breath_in_sec": 4, "breath_out_sec": 4},
    {"name": "anahata",      "label": "Heart",     "element": "Air",
     "bpm_min": 80,  "bpm_max": 100, "hz": 349.23, "note": "F4", "boundary": "PHRASE",
     "breath_in_sec": 4, "breath_out_sec": 6},
    {"name": "vishuddha",    "label": "Throat",    "element": "Ether",
     "bpm_min": 90,  "bpm_max": 110, "hz": 392.00, "note": "G4", "boundary": "PHRASE",
     "breath_in_sec": 3, "breath_out_sec": 5},
    {"name": "ajna",         "label": "Third Eye", "element": "Light",
     "bpm_min": 100, "bpm_max": 130, "hz": 440.00, "note": "A4", "boundary": "NONE",
     "breath_in_sec": 2, "breath_out_sec": 4},
    {"name": "sahasrara",    "label": "Crown",     "element": "Consciousness",
     "bpm_min": 130, "bpm_max": 180, "hz": 523.25, "note": "C5", "boundary": "NONE",
     "breath_in_sec": 0, "breath_out_sec": 0},
]


def chakra_to_band(bpm: float) -> dict[str, Any]:
    """Return nearest chakra band for a BPM value (by band midpoint)."""
    return min(CHAKRA_BANDS, key=lambda b: abs(bpm - (b["bpm_min"] + b["bpm_max"]) / 2.0))


def encode_bpm_timeline(
    chunks: list[ProsodicChunk],
    utterance_id: str,
    voice_persona_id: str = "",
    scale: str = "pentatonicMajor",
) -> dict[str, Any]:
    """Encode prosodic chunks as a BPM timeline in CGP v0.2 format.

    Args:
        chunks: Prosodic chunks from ``parse_prosodic()``.
        utterance_id: Unique identifier for this utterance.
        voice_persona_id: Optional persona slug for attribution.
        scale: Musical scale name (default ``pentatonicMajor``).

    Returns:
        CGP v0.2 packet dict ready for JSON serialization or NATS publishing.
    """
    if not chunks:
        return _empty_packet(utterance_id, voice_persona_id, scale)

    bpm_timeline: list[int] = []
    boundary_sequence: list[str] = []
    points: list[dict[str, Any]] = []
    total_syllables = 0
    position_ms = 0.0

    # Energy profile counters
    sentence_count = 0
    clause_count = 0
    phrase_count = 0
    breath_count = 0
    presto_count = 0

    for i, chunk in enumerate(chunks):
        boundary = chunk.boundary_after
        bpm = BPM_MAP.get(boundary, 120)
        midi = MIDI_OFFSET.get(boundary, 7)

        bpm_timeline.append(bpm)
        boundary_sequence.append(boundary.name)
        total_syllables += chunk.estimated_syllables

        # Count boundaries for energy profile
        if boundary == BoundaryType.SENTENCE:
            sentence_count += 1
        elif boundary == BoundaryType.CLAUSE:
            clause_count += 1
        elif boundary == BoundaryType.PHRASE:
            phrase_count += 1
        elif boundary == BoundaryType.BREATH:
            breath_count += 1
        elif boundary == BoundaryType.NONE:
            presto_count += 1

        # Build CGP point
        proj = round(i / max(len(chunks) - 1, 1), 3) if len(chunks) > 1 else 1.0
        summary_text = chunk.text[:60] if len(chunk.text) > 60 else chunk.text
        points.append({
            "id": f"chunk:{i}",
            "modality": "voice",
            "proj": proj,
            "conf": 0.92,
            "summary": f"{boundary.name} boundary @ {bpm} BPM — {summary_text}",
            "meta": {
                "bpm": bpm,
                "midi_offset": midi,
                "syllables": chunk.estimated_syllables,
                "offset_ms": round(position_ms),
            },
        })

        # Advance position estimate
        position_ms += (chunk.estimated_syllables * _MS_PER_SYLLABLE) + chunk.pause_after

    avg_bpm = round(sum(bpm_timeline) / len(bpm_timeline), 1)
    duration_estimate_ms = round(position_ms)

    return {
        "spec": "chit.cgp.v0.2",
        "summary": f"Prosodic BPM timeline for voice attribution",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": [{
            "id": f"flute:prosodic:{utterance_id}",
            "label": "voice_prosodic",
            "constellations": [{
                "id": f"prosodic.bpm.{utterance_id}",
                "summary": "BPM-encoded prosodic timeline",
                "spectrum": [0.8, 0.6, 0.4],
                "points": points,
                "meta": {
                    "namespace": "pmoves.voice.prosodic",
                    "bpm_timeline": bpm_timeline,
                    "boundary_sequence": boundary_sequence,
                    "total_syllables": total_syllables,
                    "total_chunks": len(chunks),
                    "duration_estimate_ms": duration_estimate_ms,
                    "avg_bpm": avg_bpm,
                    "chakra_band": chakra_to_band(avg_bpm),
                    "energy_profile": {
                        "sentence_count": sentence_count,
                        "clause_count": clause_count,
                        "phrase_count": phrase_count,
                        "breath_count": breath_count,
                        "presto_count": presto_count,
                    },
                    "scale": scale,
                    "root_note": "C4",
                },
            }],
        }],
        "meta": {
            "source": "tokenism.prosodic.bpm.v1",
            "voice_persona_id": voice_persona_id,
            "tags": ["prosodic", "bpm", "voice-attribution"],
        },
    }


def _empty_packet(
    utterance_id: str, voice_persona_id: str, scale: str,
) -> dict[str, Any]:
    """Return a valid but empty CGP packet for zero-chunk input."""
    return {
        "spec": "chit.cgp.v0.2",
        "summary": "Empty prosodic BPM timeline (no chunks)",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": [{
            "id": f"flute:prosodic:{utterance_id}",
            "label": "voice_prosodic",
            "constellations": [{
                "id": f"prosodic.bpm.{utterance_id}",
                "summary": "BPM-encoded prosodic timeline",
                "spectrum": [0.0, 0.0, 0.0],
                "points": [],
                "meta": {
                    "namespace": "pmoves.voice.prosodic",
                    "bpm_timeline": [],
                    "boundary_sequence": [],
                    "total_syllables": 0,
                    "total_chunks": 0,
                    "duration_estimate_ms": 0,
                    "avg_bpm": 0,
                    "chakra_band": chakra_to_band(0),
                    "energy_profile": {
                        "sentence_count": 0, "clause_count": 0,
                        "phrase_count": 0, "breath_count": 0, "presto_count": 0,
                    },
                    "scale": scale,
                    "root_note": "C4",
                },
            }],
        }],
        "meta": {
            "source": "tokenism.prosodic.bpm.v1",
            "voice_persona_id": voice_persona_id,
            "tags": ["prosodic", "bpm", "voice-attribution"],
        },
    }


async def publish_bpm_event(
    cgp_packet: dict[str, Any],
    nats_url: str = "",
) -> bool:
    """Publish a BPM CGP packet to NATS (best-effort).

    Gated by ``PROSODIC_BPM_PUBLISH`` env var (default ``false``).

    Args:
        cgp_packet: The CGP v0.2 packet from ``encode_bpm_timeline()``.
        nats_url: NATS server URL. Falls back to env var ``NATS_URL``.

    Returns:
        True if published, False if skipped or failed.
    """
    if os.getenv("PROSODIC_BPM_PUBLISH", "false").lower() != "true":
        return False

    if not nats_url:
        nats_url = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")

    try:
        import nats as nats_client
        nc = nats_client.NATS()
        await nc.connect(nats_url)
        await nc.publish(
            "tokenism.prosodic.bpm.v1",
            json.dumps(cgp_packet).encode("utf-8"),
        )
        await nc.drain()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    from .prosodic_parser import parse_prosodic

    parser = argparse.ArgumentParser(description="Encode text as BPM timeline (CGP v0.2)")
    parser.add_argument("text", nargs="?", help="Text to encode (or pipe via stdin)")
    parser.add_argument("--scale", default="pentatonicMajor", help="Musical scale")
    parser.add_argument("--publish", action="store_true", help="Publish to NATS")
    parser.add_argument("--persona", default="", help="Voice persona ID")
    args = parser.parse_args()

    text = args.text or sys.stdin.read().strip()
    if not text:
        print("No text provided", file=sys.stderr)
        sys.exit(1)

    chunks = parse_prosodic(text)
    utterance_id = str(uuid.uuid4())[:8]
    packet = encode_bpm_timeline(chunks, utterance_id, args.persona, args.scale)

    print(json.dumps(packet, indent=2))

    if args.publish:
        published = asyncio.run(publish_bpm_event(packet))
        status = "published" if published else "skipped (PROSODIC_BPM_PUBLISH not set)"
        print(f"\nNATS: {status}", file=sys.stderr)
