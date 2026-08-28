"""Single source of truth for the 7-chakra axis band table and lookup helpers.

Consumed by:
    - pmoves/services/flute-gateway/prosodic/bpm_encoder.py  (BPM-only)
    - pmoves/tools/bpm_encoder.py                            (BPM + frequency)

Spec: AGNOTE4482FLUTE.md Movement I
"""

from __future__ import annotations

from typing import Any

# 7-chakra axis bands — additive over the 5-band BOUNDARY table (AGNOTE4482FLUTE.md Movement I)
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
    """Return the nearest chakra band for a BPM value (by band midpoint).

    Ranges overlap by design; nearest-midpoint wins.

    >>> chakra_to_band(47)["name"]
    'muladhara'
    >>> chakra_to_band(62)["name"]
    'svadhisthana'
    >>> chakra_to_band(120)["name"]
    'ajna'
    >>> chakra_to_band(999)["name"]
    'sahasrara'
    """
    return min(CHAKRA_BANDS, key=lambda b: abs(bpm - (b["bpm_min"] + b["bpm_max"]) / 2.0))


def freq_to_chakra(hz: float) -> dict[str, Any]:
    """Return the nearest chakra band for a frequency in Hz.

    >>> freq_to_chakra(65.0)["name"]
    'muladhara'
    >>> freq_to_chakra(440.0)["name"]
    'ajna'
    >>> freq_to_chakra(523.0)["name"]
    'sahasrara'
    """
    return min(CHAKRA_BANDS, key=lambda b: abs(hz - b["hz"]))
