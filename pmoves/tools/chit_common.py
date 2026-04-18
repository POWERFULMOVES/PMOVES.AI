"""Shared CHIT utilities used across multiple modules."""
from __future__ import annotations
import json
from typing import Any, Dict


def canon(obj: Dict[str, Any]) -> bytes:
    """Create canonical JSON representation for signing.

    Uses deterministic JSON with sorted keys and minimal whitespace
    to ensure consistent hashing across platforms.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
