"""Shared CHIT utilities — single source of truth for canonical serialization.

DO NOT duplicate this function. All CHIT modules MUST import from here.
"""
from __future__ import annotations
import json
from typing import Any, Dict


def canon(obj: Dict[str, Any]) -> bytes:
    """Canonical JSON serialization for HMAC signing.

    Produces deterministic byte representation: sorted keys, no whitespace.
    This is the ONE canonical implementation — never copy this elsewhere.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
