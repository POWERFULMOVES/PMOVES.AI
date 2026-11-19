"""Deterministic engine selection + route planning (scaffold policy).

Selection is pure and replayable: no RNG, no network, no model state.
Wiring the actual transports is the 5090 voice-layer lane's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENGINES = ("omnivoice", "flute", "utts")

# Deterministic hints, ordered by priority. Realtime/low-latency -> Flute relay,
# studio cloning/UTTS pipeline -> utts, long-form narration -> OmniVoice.
_HINTS = (
    ("flute", ("realtime", "stream", "low-latency")),
    ("utts", ("clone", "studio", "ultimate-tts", "voice-clone")),
    ("omnivoice", ("narration", "audiobook", "longform", "long-form")),
)


@dataclass(frozen=True)
class RoutePlan:
    engine: str
    reason: str
    wired: bool  # False in scaffold phase - transports deferred to 5090 lane


def select_engine(
    text: str,
    hints: tuple[str, ...] = (),
    default: str = "omnivoice",
) -> tuple[str, str]:
    """Return (engine, reason). Explicit hints beat text keywords beat default."""
    lower = text.lower()
    for hint in hints:
        h = hint.strip().lower()
        if h in ENGINES:
            return h, "explicit engine hint: " + h
        for eng, kws in _HINTS:
            if h in kws:
                return eng, "explicit hint matched keyword '" + h + "' -> " + eng
    for eng, kws in _HINTS:
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                return eng, "text keyword '" + kw + "' -> " + eng
    if default not in ENGINES:
        raise ValueError("unknown engine: " + default)
    return default, "default"


def build_route(
    text: str,
    hints: tuple[str, ...] = (),
    default: str = "omnivoice",
) -> RoutePlan:
    """Plan a route deterministically (scaffold phase - no transport)."""
    engine, reason = select_engine(text, hints, default)
    return RoutePlan(engine=engine, reason=reason, wired=False)