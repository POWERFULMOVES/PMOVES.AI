"""Persona-to-engine selector for Flute-Gateway TTS synthesis.

Resolves a voice persona and/or expression intent to an engine ID and
synthesis kwargs. Priority: persona.tts_settings > intent.params > defaults.

Consumed by ``synthesize_speech()`` and ``synthesize_prosodic_speech()``
endpoints in ``main.py`` when ``persona_id`` or ``intent`` is provided.
"""

from __future__ import annotations

import logging
import os
from services.common.env import get_secret
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

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
_HOST_AFFINITY: dict[str, dict[str, Any]] = {}


def _load_configs() -> None:
    """Load expression, capability, and host-affinity YAML configs."""
    global _EXPRESSION_MAP, _CAPABILITY_MAP, _HOST_AFFINITY

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
        # host_affinity: engine -> {requires, min_vram_mb?, nodes, preferred}
        affinity = data.get("host_affinity", {})
        _HOST_AFFINITY = affinity if isinstance(affinity, dict) else {}
        logger.info(
            "Loaded %d engine capabilities + %d host-affinity rows from %s",
            len(_CAPABILITY_MAP), len(_HOST_AFFINITY), cap_path,
        )


# Load on import
try:
    _load_configs()
except Exception as e:
    logger.warning("Failed to load persona selector configs: %s", e)

# Supabase connection for persona lookups
_SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("SUPA_REST_URL", ""))
_SUPABASE_KEY = get_secret("SUPABASE_KEY", get_secret("ANON_KEY", ""))

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


# ---------------------------------------------------------------------------
# Host affinity — resolve which fleet node should run a given engine
# ---------------------------------------------------------------------------

def resolve_engine_host(
    engine: str,
    available_nodes: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Resolve which fleet node should run ``engine`` (persona → engine → NODE).

    Reads the ``host_affinity`` table from ``tts-engine-capabilities.yaml``.
    Node affinity is a property of the engine's hardware needs (CPU-viable vs
    GPU/VRAM), not of any single voice — so this is keyed by engine, and a
    future ``voice_profiles.host_affinity`` DB column would override per-voice.

    Args:
        engine: Engine id (e.g. ``kokoro``, ``f5_tts``).
        available_nodes: Optional list of nodes currently up. When given, the
            selected node is the preferred node if it's available, else the
            first eligible node that is available; ``None`` if none are up.
            When omitted, ``selected`` is simply the configured ``preferred``.

    Returns:
        ``{requires, min_vram_mb?, nodes, preferred, selected}`` for the engine,
        or ``None`` if the engine has no host-affinity entry (caller decides a
        fallback rather than this module inventing one).
    """
    affinity = _HOST_AFFINITY.get(engine)
    if not isinstance(affinity, dict):
        logger.debug("No host_affinity entry for engine=%s", engine)
        return None

    eligible = list(affinity.get("nodes") or [])
    preferred = affinity.get("preferred")

    if available_nodes is None:
        selected = preferred
    else:
        # Node ids are strings (kvm4-2, spark, z890), but bare numeric slugs
        # like 5090/4090 parse as ints in YAML — normalize both sides to str
        # so membership never silently fails on a numeric node.
        up = {str(n) for n in available_nodes}
        if preferred is not None and str(preferred) in up:
            selected = preferred
        else:
            selected = next((n for n in eligible if str(n) in up), None)

    result = dict(affinity)
    result["selected"] = selected
    return result


def host_affinity_enabled() -> bool:
    """True when host-affinity routing is opted in via ``VOICE_HOST_AFFINITY``.

    Default OFF — casts target the single configured provider URL unless the
    operator explicitly enables cross-node routing.
    """
    return os.getenv("VOICE_HOST_AFFINITY", "").strip().lower() in ("1", "true", "yes", "on")


def fleet_nodes_from_env() -> Optional[list[str]]:
    """Parse ``VOICE_FLEET_NODES`` (comma-separated up-node ids) → list or None.

    None (unset) means "assume the preferred node is up" — the optimistic
    default. A set value restricts routing to nodes currently reported up.
    """
    raw = os.getenv("VOICE_FLEET_NODES", "").strip()
    if not raw:
        return None
    return [n.strip() for n in raw.split(",") if n.strip()]


def node_to_host(node: str) -> str:
    """Map a fleet node id to its Tailscale hostname (``pmoves-<node>``).

    Node ids in host_affinity are bare slugs (``kvm4-2``, ``spark``, ``5090``);
    the fleet reaches them over the tailnet by hostname. Never emits raw IPs.
    Already-prefixed ids pass through unchanged.
    """
    node = str(node)
    return node if node.startswith("pmoves-") else f"pmoves-{node}"


def resolve_engine_target(
    engine: str,
    configured_url: str,
    *,
    available_nodes: Optional[list[str]] = None,
    enabled: Optional[bool] = None,
) -> tuple[str, Optional[str]]:
    """Resolve the target URL for an ``engine`` cast under host-affinity routing.

    This is the seam that wires ``resolve_engine_host()`` into the Flute-Gateway
    synthesis path. When routing is enabled and a node is selected, the
    ``configured_url`` host is swapped for the selected node's Tailscale
    hostname (``pmoves-<node>``), preserving scheme / port / path / userinfo.

    Returns ``(target_url, selected_node)``. Falls back to
    ``(configured_url, None)`` — i.e. the single-configured-URL behaviour —
    when routing is disabled, the engine has no host_affinity entry, no eligible
    node is up, or the configured URL has no host to swap. Fail-open by design:
    routing never blocks a cast.

    Args:
        engine: Engine id used for the host_affinity lookup.
        configured_url: The provider's configured base URL (e.g. ULTIMATE_TTS_URL).
        available_nodes: Up-node filter; defaults to ``VOICE_FLEET_NODES``.
        enabled: Override the ``VOICE_HOST_AFFINITY`` opt-in (mainly for tests).
    """
    if enabled is None:
        enabled = host_affinity_enabled()
    if not enabled or not configured_url:
        return configured_url, None

    if available_nodes is None:
        available_nodes = fleet_nodes_from_env()

    affinity = resolve_engine_host(engine, available_nodes)
    if not affinity:
        return configured_url, None
    selected = affinity.get("selected")
    if not selected:
        return configured_url, None

    parts = urlsplit(configured_url)
    if not parts.hostname:
        return configured_url, None

    # hostport is credential-free and safe to log; the full netloc may carry
    # userinfo (user:password@host) which must never be logged in clear text.
    hostport = node_to_host(selected)
    if parts.port:
        hostport = f"{hostport}:{parts.port}"
    netloc = hostport
    if parts.username:
        auth = parts.username + (f":{parts.password}" if parts.password else "")
        netloc = f"{auth}@{hostport}"

    target = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    logger.info("host-affinity: engine=%s routed to node=%s (%s)", engine, selected, hostport)
    return target, str(selected)


def get_host_affinity_map() -> dict[str, dict[str, Any]]:
    """Return the full engine → host-affinity routing table (read-only copy)."""
    return {engine: dict(rows) for engine, rows in _HOST_AFFINITY.items()}
