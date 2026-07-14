#!/usr/bin/env python3
"""
voice_persona_bridge.py -- CHIT-sign -> Flute-Gateway persona/intent bridge.

Phase 0 of the CHIT-driven EXPRESSIVE voice pipeline (see
``pmoves/tools/VOICE_CAST_ON_SIGN.md``). Resolves a signed
``agent.graphiti.signed.v1`` trail payload's ``selected_alter`` (else
``voice``) field to an expressive Flute-Gateway synthesis intent + persona,
using the FlOO$ suit mapping documented by the ``persona-bind`` skill
(``.claude/skills/persona-bind/SKILL.md``).

Only ``intent`` and ``persona_id`` are consumed today by Flute-Gateway's
``/v1/voice/synthesize*`` endpoints (see ``persona_selector.resolve_persona_engine``
in ``pmoves/services/flute-gateway/persona_selector.py``, which maps intent ->
primary engine via ``pmoves/configs/tts-engine-expressions.yaml``). The
``exaggeration``/``temperature`` pair is carried through as advisory metadata
for future direct engine-param wiring (e.g. ``chatterbox_exaggeration`` /
``chatterbox_temperature``) once the gateway grows a param pass-through on
these endpoints -- callers should not assume the gateway honors them yet.

Consumed by ``pmoves/tools/voice_cast_on_sign.py``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# Lookup key (alter name OR agent_signatures.yaml `voice` descriptor) ->
# (intent, persona_id, exaggeration, temperature).
#
# Intents come from pmoves/configs/tts-engine-expressions.yaml:
#   dramatic -> chatterbox (theatrical delivery, exaggeration/temperature knobs)
#   narrate  -> kokoro (clear narration with pace control)
BRIDGE: Dict[str, Tuple[str, str, float, float]] = {
    # Mr. Clean -- command / crisp delivery
    "mr-clean": ("dramatic", "mr-clean", 0.6, 0.9),
    "command": ("dramatic", "mr-clean", 0.6, 0.9),
    # Dr. Bean -- analytical / measured narration
    "dr-bean": ("narrate", "dr-bean", 0.3, 0.7),
    "analytical": ("narrate", "dr-bean", 0.3, 0.7),
    # Powerpuff Buttercup -- action / drive
    "powerpuff-buttercup": ("dramatic", "powerpuff-buttercup", 0.9, 1.0),
    "action": ("dramatic", "powerpuff-buttercup", 0.9, 1.0),
    # Powerpuff Blossom -- joy / warmth
    "powerpuff-blossom": ("dramatic", "powerpuff-blossom", 0.8, 1.0),
    "joy": ("dramatic", "powerpuff-blossom", 0.8, 1.0),
    # Powerpuff Bubbles -- coordination / friendly
    "powerpuff-bubbles": ("narrate", "powerpuff-bubbles", 0.5, 0.8),
    "coordination": ("narrate", "powerpuff-bubbles", 0.5, 0.8),
}

# Fallback when the payload carries no recognizable alter/voice key.
DEFAULT: Tuple[str, Optional[str], float, float] = ("dramatic", None, 0.5, 0.8)


def resolve(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve a signed CHIT trail payload to Flute-Gateway synthesis params.

    Lookup key precedence: ``payload["selected_alter"]`` (explicit persona
    pick via ``sign_trail.py --alter``) else ``payload["voice"]`` (the
    agent's default voice descriptor from ``agent_signatures.yaml``).

    Args:
        payload: A ``signature.v1`` trail payload dict (or ``None``/empty).

    Returns:
        dict with keys ``intent``, ``persona_id``, ``exaggeration``,
        ``temperature``. Falls back to :data:`DEFAULT` when the payload is
        empty/None or the resolved key is unrecognized -- never raises.
    """
    key: Optional[str] = None
    if payload:
        key = payload.get("selected_alter") or payload.get("voice")

    resolved = BRIDGE.get(key, DEFAULT) if key else DEFAULT
    intent, persona_id, exaggeration, temperature = resolved

    return {
        "intent": intent,
        "persona_id": persona_id,
        "exaggeration": exaggeration,
        "temperature": temperature,
    }
