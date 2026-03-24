"""Persona-to-engine selector for Flute-Gateway TTS synthesis.

Resolves a voice persona and/or expression intent to an engine ID and
synthesis kwargs. Priority: persona.tts_settings > intent.params > defaults.

Consumed by ``synthesize_speech()`` and ``synthesize_prosodic_speech()``
endpoints in ``main.py`` when ``persona_id`` or ``intent`` is provided.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loading (once at import time)
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs"
# Fallback: look relative to flute-gateway location
if not _CONFIG_DIR.exists():
    _CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs"

_EXPRESSION_MAP: dict[str, dict[str, Any]] = {}
_CAPABILITY_MAP: dict[str, dict[str, Any]] = {}


def _load_configs() -> None:
    """Load expression and capability YAML configs."""
    global _EXPRESSION_MAP, _CAPABILITY_MAP

    expr_path = _CONFIG_DIR / "tts-engine-expressions.yaml"
    if expr_path.exists():
        with open(expr_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _EXPRESSION_MAP = data.get("intents", {})
        logger.info("Loaded %d expression intents from %s", len(_EXPRESSION_MAP), expr_path)

    cap_path = _CONFIG_DIR / "tts-engine-capabilities.yaml"
    if cap_path.exists():
        with open(cap_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        engines = data.get("engines", {})
        _CAPABILITY_MAP = engines if isinstance(engines, dict) else {}
        logger.info("Loaded %d engine capabilities from %s", len(_CAPABILITY_MAP), cap_path)


# Load on import
try:
    _load_configs()
except Exception as e:
    logger.warning("Failed to load persona selector configs: %s", e)

# Supabase connection for persona lookups
_SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("SUPA_REST_URL", ""))
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", os.getenv("ANON_KEY", ""))

# Default engine when nothing else matches
_DEFAULT_ENGINE = "kitten_tts"
_DEFAULT_KWARGS: dict[str, Any] = {"kitten_voice": "expr-voice-2-f"}


async def resolve_persona_engine(
    persona_id: Optional[str] = None,
    intent: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve persona + intent to (engine_id, synth_kwargs).

    Priority chain:
        1. persona_id → Supabase voice_persona table → tts_settings
        2. intent → tts-engine-expressions.yaml → primary engine + params
        3. Fallback → kitten_tts with defaults

    Args:
        persona_id: Voice persona ID or slug (e.g., ``agent-zero-default``).
        intent: Expression intent (e.g., ``narrate``, ``emote``, ``dramatic``).

    Returns:
        Tuple of (engine_id, synth_kwargs) where kwargs are ready for the
        Ultimate-TTS provider.
    """
    engine = _DEFAULT_ENGINE
    kwargs: dict[str, Any] = dict(_DEFAULT_KWARGS)

    # Layer 1: Intent defaults (base layer)
    if intent and intent in _EXPRESSION_MAP:
        intent_config = _EXPRESSION_MAP[intent]
        engine = intent_config.get("primary", engine)
        intent_params = intent_config.get("params", {})
        kwargs = dict(intent_params)
        logger.debug("Intent '%s' resolved to engine=%s", intent, engine)

    # Layer 2: Persona overrides (higher priority)
    if persona_id:
        persona = await _fetch_persona(persona_id)
        if persona:
            # Persona's engine takes precedence
            p_engine = persona.get("tts_provider") or persona.get("engine")
            if p_engine:
                engine = p_engine

            # Merge persona tts_settings over intent params
            tts_settings = persona.get("tts_settings") or {}
            if isinstance(tts_settings, dict):
                kwargs.update(tts_settings)

            # Voice override
            p_voice = persona.get("tts_voice_id")
            if p_voice:
                kwargs["voice"] = p_voice

            logger.debug("Persona '%s' resolved to engine=%s", persona_id, engine)

    return engine, kwargs


async def _fetch_persona(persona_id: str) -> Optional[dict[str, Any]]:
    """Fetch a voice persona from Supabase by ID or slug.

    Returns None if Supabase is not configured or persona not found.
    """
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        logger.debug("Supabase not configured, skipping persona lookup")
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_SUPABASE_URL}/rest/v1/voice_persona",
                headers={
                    "apikey": _SUPABASE_KEY,
                    "Authorization": f"Bearer {_SUPABASE_KEY}",
                },
                params={
                    "or": f"(id.eq.{persona_id},slug.eq.{persona_id})",
                    "limit": "1",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
    except Exception as e:
        logger.warning("Persona lookup failed for '%s': %s", persona_id, e)

    return None


def get_available_intents() -> list[str]:
    """Return list of available expression intent names."""
    return list(_EXPRESSION_MAP.keys())


def get_intent_config(intent: str) -> Optional[dict[str, Any]]:
    """Return the full config for an intent, or None if not found."""
    return _EXPRESSION_MAP.get(intent)
