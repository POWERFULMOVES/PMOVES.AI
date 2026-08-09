"""
Flute Gateway - PMOVES Multimodal Voice Communication Layer

FastAPI service providing Text-to-Speech (TTS) and Speech-to-Text (STT)
capabilities across the PMOVES.AI agent hierarchy.

Ports:
    8055: HTTP REST API
    8056: WebSocket streaming (future)

Providers:
    - VibeVoice: Real-time TTS (WebSocket, 24kHz PCM16)
    - Whisper: STT via ffmpeg-whisper service
    - ElevenLabs: External TTS (optional)
"""

import asyncio
import io
import json
import logging
import os
import socket
import wave
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
import numpy as np
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services.common.env import get_secret
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Geometry-bus bridge (#1397): wraps voice events into signed CGP v0.2 packets
# for the canonical geometry.cgp.v1 subject. Legacy subject stays unchanged.
from geometry_bridge import GeometryBridge, cgp_subject, is_dual_publish_enabled

# Provider imports
from providers import (
    VibeVoiceBusyError,
    VibeVoiceNoAudioError,
    VibeVoiceProvider,
    VoiceboxBusyError,
    VoiceboxError,
    VoiceboxNoProfileError,
    VoiceboxProvider,
    OmniVoiceBusyError,
    OmniVoiceError,
    OmniVoiceProvider,
    WhisperProvider,
    UltimateTTSError,
    UltimateTTSProvider,
)

# Prosodic sidecar imports
from prosodic import (
    ProsodicChunk,
    parse_prosodic,
    stitch_chunks,
)

# Voice "S1" profile registry (pmoves_core.voice_profiles, v5_16). No import cycle:
# voice_registry never imports main.
from voice_registry import (
    ENGINE_VALUES,
    REGISTRY_UPDATE_SUBJECT,
    VoiceProfile,
    VoiceRegistry,
    grounding_contract,
    select_provider_and_params,
    validate_capability,
    validate_grounding,
)

# Pipecat integration (optional - enable with PIPECAT_ENABLED=true)
# NOTE: the local package is `flute_pipecat`, NOT `pipecat`. Naming it `pipecat`
# would shadow the installed `pipecat-ai` dependency (same top-level name), so the
# external `pipecat.pipeline.*` runtime imports (see the voice-agent route) would
# resolve to this local package and raise ModuleNotFoundError.
from flute_pipecat.config import get_pipecat_config
PIPECAT_CONFIG = get_pipecat_config()

# NATS service announcement integration
try:
    from services.common.nats_service_listener import announce_service, ServiceTier
    NATS_ANNOUNCE_AVAILABLE = True
except ImportError:
    NATS_ANNOUNCE_AVAILABLE = False

try:
    from flute_pipecat.transports import FluteFastAPIWebsocketTransport, FluteFastAPIWebsocketParams
    from flute_pipecat.pipelines import VoiceAgentConfig, build_voice_agent_pipeline
    from flute_pipecat.processors import TensorZeroLLMProcessor
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("flute-gateway")

# Environment configuration


def _build_nats_url() -> str:
    explicit = get_secret("NATS_URL", "") or os.getenv("NATS_URL", "")
    if explicit:
        return explicit

    host = get_secret("NATS_HOST", os.getenv("NATS_HOST", "nats")) or "nats"
    port = str(get_secret("NATS_PORT", os.getenv("NATS_PORT", "4222")) or "4222")
    user = get_secret("NATS_USER", os.getenv("NATS_USER", "")) or ""
    password = get_secret("NATS_PASSWORD", os.getenv("NATS_PASSWORD", "")) or ""

    if user and password:
        return f"nats://{user}:{password}@{host}:{port}"
    if user:
        return f"nats://{user}@{host}:{port}"
    logger.warning("NATS connection without credentials — set NATS_URL or NATS_USER/NATS_PASSWORD")
    return f"nats://{host}:{port}"


def _redact_url_password(url: str) -> str:
    try:
        split = urlsplit(url)
    except Exception:
        return url
    if not split.netloc:
        return url
    host = split.hostname or ""
    port = f":{split.port}" if split.port else ""
    user = split.username
    if user:
        netloc = f"{user}:<redacted>@{host}{port}"
    else:
        netloc = f"{host}{port}"
    return urlunsplit((split.scheme, netloc, split.path, split.query, split.fragment))


NATS_URL = _build_nats_url()
NATS_URL_REDACTED = _redact_url_password(NATS_URL)
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:3010")
SUPABASE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY", "")
# Ultimate-TTS-Studio: native Pinokio at 7860, Docker at 7861.
# Default to host-gateway (native) — override with ULTIMATE_TTS_URL for Docker.
VIBEVOICE_URL = (os.getenv("VIBEVOICE_URL") or "http://host.docker.internal:7860").strip()
WHISPER_URL = os.getenv("WHISPER_URL", "http://ffmpeg-whisper:8078")
ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://host.docker.internal:7860")
# Voicebox is a Pinokio-managed voice production service (default port 17493).
# Set VOICEBOX_URL="" to disable. Auto-normalized for Docker contexts below.
VOICEBOX_URL = os.getenv("VOICEBOX_URL", "http://host.docker.internal:17493")
# OmniVoice is the production voice server (creator-operator/omnivoice_server.py).
# Presence of OMNIVOICE_URL enables the provider; default points at its loopback bind.
OMNIVOICE_URL = os.getenv("OMNIVOICE_URL", "http://127.0.0.1:8002")
DEFAULT_PROVIDER = os.getenv("DEFAULT_VOICE_PROVIDER", "vibevoice")
FLUTE_API_KEY = get_secret("FLUTE_API_KEY", "")

# CHIT integration configuration
CHIT_VOICE_ATTRIBUTION = os.getenv("CHIT_VOICE_ATTRIBUTION", "false").lower() == "true"
CHIT_NAMESPACE = os.getenv("CHIT_NAMESPACE", "pmoves.voice")
CHIT_GEOMETRY_SUBJECT = os.getenv("CHIT_GEOMETRY_SUBJECT", "tokenism.geometry.event.v1")
# Geometry-bus bridge (#1397): canonical CGP subject + dual-publish kill-switch.
# FLUTE_CGP_SUBJECT and FLUTE_GEOMETRY_DUAL_PUBLISH are resolved lazily via
# geometry_bridge.cgp_subject() / is_dual_publish_enabled() so test monkeypatch
# of env works without re-importing this module.


def _pcm16_to_wav_bytes(pcm16: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)
    return buf.getvalue()


def _running_in_docker() -> bool:
    return os.path.exists("/.dockerenv")


def _normalize_vibevoice_url(url: str) -> str:
    """Normalize a user-provided VibeVoice URL for Docker contexts.

    A common misconfiguration is setting `VIBEVOICE_URL=http://localhost:<port>` in `env.shared`,
    which works on the host but fails inside containers (localhost points at the container).
    """
    if not url:
        return url
    if not _running_in_docker():
        return url
    if url.startswith("http://localhost"):
        return url.replace("http://localhost", "http://host.docker.internal", 1)
    if url.startswith("http://127.0.0.1"):
        return url.replace("http://127.0.0.1", "http://host.docker.internal", 1)
    if url.startswith("https://localhost"):
        return url.replace("https://localhost", "https://host.docker.internal", 1)
    if url.startswith("https://127.0.0.1"):
        return url.replace("https://127.0.0.1", "https://host.docker.internal", 1)
    return url


VIBEVOICE_URL = _normalize_vibevoice_url(VIBEVOICE_URL)
# Voicebox runs on the host via Pinokio — same Docker-context normalization applies.
VOICEBOX_URL = _normalize_vibevoice_url(VOICEBOX_URL)
# OmniVoice runs on the host (loopback) — same Docker-context normalization applies.
OMNIVOICE_URL = _normalize_vibevoice_url(OMNIVOICE_URL)

# API Key authentication dependency
async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key for service authentication."""
    # Skip auth if no key configured (development mode)
    if not FLUTE_API_KEY:
        return None
    if not x_api_key or x_api_key != FLUTE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key

# Prometheus metrics
REQUESTS_TOTAL = Counter(
    "flute_requests_total",
    "Total requests by endpoint and status",
    ["endpoint", "status"]
)
TTS_DURATION = Histogram(
    "flute_tts_duration_seconds",
    "TTS synthesis duration in seconds",
    ["provider"]
)
STT_DURATION = Histogram(
    "flute_stt_duration_seconds",
    "STT recognition duration in seconds",
    ["provider"]
)
CHIT_EVENTS_FAILED = Counter(
    "flute_chit_events_failed_total",
    "Total CHIT event publish failures",
    ["reason"]
)
CHIT_CGP_PUBLISHED = Counter(
    "flute_chit_cgp_published_total",
    "Total CGP v0.2 packets published to the canonical geometry-bus subject (#1397)",
    ["subject"]
)

# Provider instances (initialized on startup)
vibevoice_provider: Optional[VibeVoiceProvider] = None
whisper_provider: Optional[WhisperProvider] = None
ultimate_tts_provider: Optional[UltimateTTSProvider] = None
voicebox_provider: Optional[VoiceboxProvider] = None
omnivoice_provider: Optional[OmniVoiceProvider] = None
nats_client = None
# Geometry-bus bridge (#1397): module-level singleton, instantiated on first use.
geometry_bridge: Optional[GeometryBridge] = None
# Voice "S1" registry (preloaded in lifespan; None until startup runs).
voice_registry: Optional[VoiceRegistry] = None
voice_registry_task: Optional[asyncio.Task] = None


def _resolve_voice_profile(request: "SynthesizeRequest") -> bool:
    """Spec §4 cascade step 1: explicit ``voice`` slug -> registry.

    Mutates the REQUEST object in place (provider/engine/voice) so the value is
    read by the downstream ``provider_name = request.provider or DEFAULT_PROVIDER``
    assignment and the if/elif dispatch. Returns True when a profile matched, so
    the caller can skip the persona/intent branch (voice slug wins the cascade).

    No-op (returns False) when the registry is absent/unhealthy, ``voice`` is
    unset, ``engine`` is already pinned, or the slug is unknown — preserving the
    existing DEFAULT_PROVIDER behaviour (graceful degradation).
    """
    if voice_registry is None or not voice_registry.healthy or not request.voice or request.engine:
        return False
    profile = voice_registry.get(request.voice)
    if profile is None:
        return False
    provider_name, params = select_provider_and_params(profile, DEFAULT_PROVIDER)
    request.provider = provider_name
    if params.get("engine"):
        request.engine = params["engine"]
    # The registry slug is NOT a provider-native voice. Replace it with the
    # resolved provider voice, or CLEAR it (None) so the provider falls back to
    # its own default — never leak the slug as a preset/ref_audio.
    request.voice = params.get("voice")
    return True


async def _publish_chit_voice_event(
    provider: str,
    text_length: int,
    audio_duration: float,
    voice: Optional[str] = None,
    voice_provenance_meta: Optional[dict] = None,
) -> None:
    """Publish voice synthesis event to CHIT geometry bus (best-effort).

    Dual-publish (#1397): always publishes the legacy flat event to
    `CHIT_GEOMETRY_SUBJECT` (default `tokenism.geometry.event.v1`) so existing
    tokenism consumers keep working unchanged; additionally publishes a
    HMAC-signed CGP v0.2 packet to `FLUTE_CGP_SUBJECT` (default `geometry.cgp.v1`)
    when `FLUTE_GEOMETRY_DUAL_PUBLISH` is true (default), so canonical
    consumers (graphiti, matrix monitor, cymatic visualizer) get a
    schema-valid packet.

    When voice_provenance_meta is supplied (from provenance_gate.build_cgp_meta),
    it is injected into the CGP v0.2 `meta` field per §8 provenance attribution.

    Both publishes are gated by `CHIT_VOICE_ATTRIBUTION`. Errors on either
    publish are logged but do not fail the request.
    """
    global geometry_bridge

    if not CHIT_VOICE_ATTRIBUTION or not nats_client:
        return

    payload = {
        "namespace": CHIT_NAMESPACE,
        "modality": "voice_synthesis",
        "provider": provider,
        "text_length": text_length,
        "audio_duration_seconds": audio_duration,
        "voice": voice,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Legacy publish — flat event on tokenism.geometry.event.v1 (unchanged)
    try:
        await nats_client.publish(
            CHIT_GEOMETRY_SUBJECT,
            json.dumps(payload).encode("utf-8"),
        )
        logger.debug("chit_voice_event_published", extra={"subject": CHIT_GEOMETRY_SUBJECT})
    except Exception as exc:
        CHIT_EVENTS_FAILED.labels(reason="legacy_publish_failed").inc()
        if CHIT_VOICE_ATTRIBUTION:
            logger.error(
                "chit_voice_event_failed",
                extra={
                    "error": str(exc),
                    "exc_type": type(exc).__name__,
                    "provider": provider,
                    "subject": CHIT_GEOMETRY_SUBJECT,
                },
                exc_info=True,
            )
        else:
            logger.debug(
                "chit_voice_event_failed",
                extra={"error": str(exc), "exc_type": type(exc).__name__},
            )

    # 2. Canonical publish — signed CGP v0.2 on geometry.cgp.v1 (#1397)
    if not is_dual_publish_enabled():
        return
    if geometry_bridge is None:
        geometry_bridge = GeometryBridge()
    canonical_subject = cgp_subject()
    try:
        cgp_packet = geometry_bridge.encode_packet(payload, meta=voice_provenance_meta)
        await nats_client.publish(
            canonical_subject,
            json.dumps(cgp_packet).encode("utf-8"),
        )
        CHIT_CGP_PUBLISHED.labels(subject=canonical_subject).inc()
        logger.debug(
            "chit_cgp_packet_published",
            extra={"subject": canonical_subject, "signed": "sig" in cgp_packet},
        )
    except Exception as exc:
        CHIT_EVENTS_FAILED.labels(reason="cgp_publish_failed").inc()
        logger.error(
            "chit_cgp_publish_failed",
            extra={
                "error": str(exc),
                "exc_type": type(exc).__name__,
                "subject": canonical_subject,
            },
            exc_info=True,
        )


# Pydantic models
class SynthesizeRequest(BaseModel):
    """Request for TTS synthesis."""
    text: str = Field(..., description="Text to synthesize", max_length=5000)
    persona_id: Optional[str] = Field(None, description="Voice persona ID or slug")
    provider: Optional[str] = Field(None, description="Provider override (vibevoice, ultimate_tts, elevenlabs)")
    voice: Optional[str] = Field(None, description="Voice preset for provider")
    engine: Optional[str] = Field(None, description="TTS engine for ultimate_tts (kitten_tts, f5_tts, kokoro)")
    intent: Optional[str] = Field(None, description="Expression intent (narrate, emote, dramatic, clone, multilingual, podcast, persona, agent, bpm_sync)")
    output_format: str = Field("wav", description="Output format: wav, mp3, pcm")


class SynthesizeResponse(BaseModel):
    """Response for TTS synthesis."""
    audio_uri: Optional[str] = Field(None, description="MinIO URI if stored")
    duration_seconds: float = Field(..., description="Audio duration")
    sample_rate: int = Field(24000, description="Sample rate in Hz")
    format: str = Field("pcm16", description="Audio format")
    node: Optional[str] = Field(
        None,
        description="Fleet node the cast was routed to via host-affinity, or None "
        "when routing is disabled / the configured URL was used.",
    )


class RecognizeResponse(BaseModel):
    """Response for STT recognition."""
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., description="Confidence score 0-1")
    language: str = Field(..., description="Detected/specified language")


class VoicePersona(BaseModel):
    """Voice persona configuration."""
    id: UUID
    slug: str
    name: str
    voice_provider: str
    voice_config: Dict[str, Any]
    personality_traits: List[str]
    language: str
    is_active: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    providers: Dict[str, bool]
    nats: str
    supabase: str
    timestamp: str


class ConfigResponse(BaseModel):
    """Service configuration response."""
    providers: List[str]
    default_provider: str
    sample_rate: int
    format: str
    features: Dict[str, bool]


class VoiceProfileIn(BaseModel):
    """Create/register payload for a voice profile (pmoves_core.voice_profiles)."""
    name: str = Field(
        ...,
        # pydantic v2 uses `pattern=` (v1's `regex=`); enforce the v5_16 slug
        # CHECK at input time so /v1/voice/profiles can't persist a bad slug.
        pattern=r"^[a-zA-Z0-9_-]{3,64}$",
        description="Slug selector (^[a-zA-Z0-9_-]{3,64}$)",
    )
    engine: str = Field(..., description="omnivoice|vibevoice|voicebox|ultimate_tts")
    engine_specific: Dict[str, Any] = Field(default_factory=dict)
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    grounding: Dict[str, Any] = Field(default_factory=dict)
    ref_audio_path: Optional[str] = None
    sample_rate_hz: int = 24000
    rights_basis: Optional[str] = None


class ValidateRequest(BaseModel):
    """Validate a prospective engine/engine_specific/grounding combination."""
    engine: str
    engine_specific: Dict[str, Any] = Field(default_factory=dict)
    grounding: Dict[str, Any] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    """Result of /v1/voice/validate."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown with NATS service announcement."""
    global vibevoice_provider, whisper_provider, ultimate_tts_provider, voicebox_provider, omnivoice_provider, nats_client
    global voice_registry, voice_registry_task

    logger.info("Starting Flute Gateway...")

    # Get service configuration for announcement
    port = int(os.getenv("FLUTE_HTTP_PORT", "8055"))
    hostname = os.getenv("HOSTNAME", socket.gethostname())
    slug = os.getenv("SERVICE_SLUG", "flute-gateway")
    name = os.getenv("SERVICE_NAME", "PMOVES Flute Gateway")
    url = os.getenv("SERVICE_URL") or f"http://{hostname}:{port}"
    health_check = f"{url}/healthz"

    # Validate critical environment variables
    if not SUPABASE_KEY:
        logger.error("SUPABASE_SERVICE_ROLE_KEY is not set")
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")

    # Initialize providers (VibeVoice is optional; Whisper is required for STT)
    if VIBEVOICE_URL:
        vibevoice_provider = VibeVoiceProvider(VIBEVOICE_URL)
    else:
        vibevoice_provider = None
        logger.info("VibeVoice disabled (set VIBEVOICE_URL to enable realtime TTS).")
    whisper_provider = WhisperProvider(WHISPER_URL)

    # Initialize Ultimate-TTS provider (optional)
    if ULTIMATE_TTS_URL:
        ultimate_tts_provider = UltimateTTSProvider(ULTIMATE_TTS_URL)
        logger.info("Ultimate-TTS provider enabled at %s", ULTIMATE_TTS_URL)
    else:
        ultimate_tts_provider = None
        logger.info("Ultimate-TTS disabled (set ULTIMATE_TTS_URL to enable).")

    # Initialize Voicebox provider (optional)
    if VOICEBOX_URL:
        voicebox_provider = VoiceboxProvider(VOICEBOX_URL)
        logger.info("Voicebox provider enabled at %s (synthesis requires a profile)", VOICEBOX_URL)
    else:
        voicebox_provider = None
        logger.info("Voicebox disabled (set VOICEBOX_URL to enable).")

    # Initialize OmniVoice provider (optional)
    if OMNIVOICE_URL:
        omnivoice_provider = OmniVoiceProvider(OMNIVOICE_URL)
        logger.info("OmniVoice provider enabled at %s", OMNIVOICE_URL)
    else:
        omnivoice_provider = None
        logger.info("OmniVoice disabled (set OMNIVOICE_URL to enable).")

    # Initialize NATS (optional)
    try:
        import nats
        nats_client = await nats.connect(NATS_URL)
        logger.info("Connected to NATS at %s", NATS_URL_REDACTED)

        # Announce service on NATS after connection is established
        if NATS_ANNOUNCE_AVAILABLE:
            try:
                await announce_service(
                    nats_url=NATS_URL,
                    slug=slug,
                    name=name,
                    url=url,
                    health_check=health_check,
                    tier=ServiceTier.MEDIA,
                    port=port,
                    metadata={"version": "0.1.0", "publishes": ["tokenism.geometry.event.v1"]},
                    retry=True,
                )
                logger.info("NATS service announcement published: %s at %s", slug, url)
            except Exception as e:
                logger.warning("Failed to publish NATS service announcement: %s", e)
    except Exception as e:
        logger.warning("NATS connection failed: %s (continuing without NATS)", e)
        nats_client = None

    # Start CGP geometry consumer as a companion background task.
    # Opt-out: set CGP_CONSUMER_ENABLED=false to disable.
    _cgp_task: Optional[asyncio.Task] = None
    _cgp_enabled = os.environ.get("CGP_CONSUMER_ENABLED", "true").strip().lower() not in {"false", "0", "no", "off"}
    if nats_client and _cgp_enabled:
        from cgp_consumer import main as _cgp_consumer_main
        _cgp_task = asyncio.create_task(_cgp_consumer_main())
        logger.info("CGP consumer started on subject %s", cgp_subject())

    # Preload the voice "S1" registry. load() never raises — an unhealthy/empty
    # registry simply leaves the existing DEFAULT_PROVIDER cascade unchanged.
    voice_registry = VoiceRegistry(SUPABASE_URL, SUPABASE_KEY)
    _vr_loaded = await voice_registry.load()
    logger.info("voice_registry: healthy=%s count=%d", _vr_loaded, voice_registry.count)
    voice_registry_task = asyncio.create_task(voice_registry.run_ttl_loop())
    if nats_client is not None:
        await voice_registry.subscribe(nats_client)  # voice.registry.update.v1

    logger.info("Flute Gateway started successfully")
    yield

    # Shutdown
    logger.info("Shutting down Flute Gateway...")
    if _cgp_task and not _cgp_task.done():
        _cgp_task.cancel()
        try:
            await _cgp_task
        except asyncio.CancelledError:
            pass
    if voice_registry_task and not voice_registry_task.done():
        voice_registry_task.cancel()
        try:
            await voice_registry_task
        except asyncio.CancelledError:
            pass
    if nats_client:
        await nats_client.close()


# Create FastAPI app
app = FastAPI(
    title="PMOVES-Flute-Gateway",
    description="Multimodal Voice Communication Layer",
    version="0.1.0",
    lifespan=lifespan
)

# MCP bridge (mcp_bridge.py) — the curated 6-tool surface over all 14 engines
# (tts_list_engines/intents/synthesize/engine_status/load/unload). Written for
# the vei.contract.mcp-bridge TAC contract (:8055/sse) but never mounted until
# now. Callables defer to the module globals set during lifespan startup.
from mcp_bridge import create_mcp_router  # noqa: E402

app.include_router(
    create_mcp_router(
        get_provider=lambda: ultimate_tts_provider,
        get_nats_client=lambda: nats_client,
    ),
    dependencies=[Depends(verify_api_key)],
)


# Health check endpoint
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Check service health and provider availability."""
    providers = {}

    # Check VibeVoice
    if vibevoice_provider:
        providers["vibevoice"] = await vibevoice_provider.health_check()
    else:
        providers["vibevoice"] = False

    # Check Whisper
    if whisper_provider:
        providers["whisper"] = await whisper_provider.health_check()
    else:
        providers["whisper"] = False

    # Check Ultimate-TTS
    if ultimate_tts_provider:
        providers["ultimate_tts"] = await ultimate_tts_provider.health_check()
    else:
        providers["ultimate_tts"] = False

    # Check Voicebox
    if voicebox_provider:
        providers["voicebox"] = await voicebox_provider.health_check()
    else:
        providers["voicebox"] = False

    # Check OmniVoice
    if omnivoice_provider:
        providers["omnivoice"] = await omnivoice_provider.health_check()
    else:
        providers["omnivoice"] = False

    # Check NATS
    nats_status = "connected" if nats_client and nats_client.is_connected else "disconnected"

    # Check Supabase
    supabase_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SUPABASE_URL}/rest/v1/")
            supabase_status = "connected" if resp.status_code in [200, 401] else "error"
    except Exception as exc:
        logger.warning("Supabase health check failed: %s", exc)
        supabase_status = "disconnected"

    REQUESTS_TOTAL.labels(endpoint="/healthz", status="200").inc()

    return HealthResponse(
        status="healthy",
        providers=providers,
        nats=nats_status,
        supabase=supabase_status,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


# Configuration endpoint
@app.get("/v1/voice/config", response_model=ConfigResponse)
async def get_config():
    """Get service configuration and available features."""
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/config", status="200").inc()

    providers: List[str] = ["whisper", "elevenlabs"]
    if vibevoice_provider:
        providers.insert(0, "vibevoice")
    if ultimate_tts_provider:
        providers.append("ultimate_tts")
    if voicebox_provider:
        providers.append("voicebox")
    if omnivoice_provider:
        providers.append("omnivoice")

    return ConfigResponse(
        providers=providers,
        default_provider=DEFAULT_PROVIDER,
        sample_rate=24000,
        format="pcm16",
        features={
            "tts_batch": True,
            "tts_stream": True,
            "stt_batch": True,
            "stt_stream": False,  # TODO: Implement
            "voice_cloning": False,  # TODO: Implement
            "personas": True,
            "voice_profiles": bool(voice_registry and voice_registry.healthy),
        }
    )


# TTS synthesis endpoint
class VoiceBindingResponse(BaseModel):
    """Resolved agent→voice binding (see AGENT_VOICE_BINDING_CONTRACT.md).

    Read-only metadata — which engine/voice/provider an agent uses, its FlOO$
    prosody, and the host-affinity node + target URL. Consumed by the CLI
    (persona-bind) and OpenRoom helper agents so both resolve identically.
    """
    agent_id: str
    alter: Optional[str] = None
    engine: str
    voice_id: Optional[str] = None
    provider: str
    prosody: Optional[Dict[str, float]] = None
    node: Optional[str] = None
    target_url: Optional[str] = None
    floos_suit: Optional[str] = None
    source: str


def _configured_url_for_provider(provider: str) -> Optional[str]:
    """Configured base URL for a provider, used to host-swap under host-affinity."""
    return {
        "ultimate_tts": ULTIMATE_TTS_URL,
        "omnivoice": OMNIVOICE_URL,
        "vibevoice": VIBEVOICE_URL,
        "voicebox": VOICEBOX_URL,
    }.get(provider) or None


@app.get("/v1/voice/binding", response_model=VoiceBindingResponse, dependencies=[Depends(verify_api_key)])
async def voice_binding(agent_id: str, alter: Optional[str] = None, intent: Optional[str] = None):
    """Resolve an agent identity to its VoiceBinding — the HTTP consumption seam
    for the CLI (persona-bind) and OpenRoom helper agents.

    Read-only. When ``VOICE_HOST_AFFINITY`` is enabled the ``target_url`` is
    host-swapped to the selected fleet node (``pmoves-<node>``); otherwise it is
    the provider's configured URL. Fail-open: unresolved layers fall through to
    the provider default, so this never errors on an unknown agent.
    """
    from persona_selector import resolve_agent_voice, resolve_engine_target

    binding = await resolve_agent_voice(agent_id, alter=alter, intent=intent)
    configured = _configured_url_for_provider(binding.get("provider", ""))
    if configured:
        target_url, node = resolve_engine_target(binding["engine"], configured)
        binding["target_url"] = target_url
        binding["node"] = node
        if node and "affinity" not in binding["source"]:
            binding["source"] = f"{binding['source']}+affinity"
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/binding", status="200").inc()
    return VoiceBindingResponse(**binding)


def _route_engine_provider(singleton, provider_cls, engine: str, configured_url: str):
    """Host-affinity seam: pick the provider instance for this cast.

    When ``VOICE_HOST_AFFINITY`` selects a node whose URL differs from the
    configured one, return a transient provider bound to that node's URL;
    otherwise return the startup singleton. Fail-open: any construction error
    falls back to the singleton (routing never blocks a cast).

    Returns ``(provider, selected_node)`` — ``selected_node`` is surfaced in the
    response so callers can see where the cast ran.
    """
    from persona_selector import resolve_engine_target

    target_url, node = resolve_engine_target(engine, configured_url)
    if node and target_url != configured_url:
        try:
            return provider_cls(target_url), node
        except Exception as exc:  # noqa: BLE001 - fail-open to the configured host
            logger.warning(
                "host-affinity: could not build %s for node=%s (%s); using configured URL",
                provider_cls.__name__, node, exc,
            )
            return singleton, None
    return singleton, node


@app.post("/v1/voice/synthesize", response_model=SynthesizeResponse, dependencies=[Depends(verify_api_key)])
async def synthesize_speech(request: SynthesizeRequest):
    """
    Synthesize speech from text.

    Uses VibeVoice by default for real-time TTS.
    Returns audio data or MinIO URI.
    """
    import time
    start_time = time.time()

    # Spec §4 cascade: explicit voice slug -> registry (mutates request in place),
    # else fall through to persona/intent resolution if no profile matched.
    if not _resolve_voice_profile(request) and (request.persona_id or request.intent) and not request.engine:
        from persona_selector import resolve_persona_engine
        resolved_engine, extra_kwargs = await resolve_persona_engine(
            request.persona_id, request.intent,
        )
        request.engine = resolved_engine
        if not request.provider:
            # A persona/intent that resolves to engine "omnivoice" routes to the
            # OmniVoice provider; everything else defaults to ultimate_tts.
            request.provider = "omnivoice" if resolved_engine == "omnivoice" else "ultimate_tts"
        if not request.voice and "voice" in extra_kwargs:
            request.voice = extra_kwargs.pop("voice")

    provider_name = request.provider or DEFAULT_PROVIDER

    try:
        if provider_name == "vibevoice" and vibevoice_provider:
            audio_data = await vibevoice_provider.synthesize(
                text=request.text,
                voice=request.voice,
            )
            if not audio_data:
                raise HTTPException(status_code=502, detail="VibeVoice returned empty audio (try again later).")
            duration = time.time() - start_time
            TTS_DURATION.labels(provider="vibevoice").observe(duration)

            # Estimate audio duration (24kHz, 16-bit = 48000 bytes/sec)
            audio_duration = len(audio_data) / 48000

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="200").inc()

            # Publish CHIT voice attribution event (best-effort)
            await _publish_chit_voice_event(
                provider="vibevoice",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            return SynthesizeResponse(
                duration_seconds=audio_duration,
                sample_rate=24000,
                format="pcm16"
            )
        elif provider_name == "ultimate_tts" and ultimate_tts_provider:
            ut_engine = request.engine or "kitten_tts"
            ut_provider, ut_node = _route_engine_provider(
                ultimate_tts_provider, UltimateTTSProvider, ut_engine, ULTIMATE_TTS_URL,
            )
            audio_data = await ut_provider.synthesize(
                text=request.text,
                voice=request.voice,
                engine=ut_engine,
            )
            if not audio_data:
                raise HTTPException(status_code=502, detail="Ultimate-TTS returned empty audio.")
            duration = time.time() - start_time
            TTS_DURATION.labels(provider="ultimate_tts").observe(duration)

            # Estimate audio duration from WAV (24kHz assumed)
            audio_duration = len(audio_data) / 48000

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="200").inc()

            # Publish CHIT voice attribution event (best-effort)
            await _publish_chit_voice_event(
                provider="ultimate_tts",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            return SynthesizeResponse(
                duration_seconds=audio_duration,
                sample_rate=24000,
                format="wav",
                node=ut_node,
            )
        elif provider_name == "voicebox" and voicebox_provider:
            audio_data = await voicebox_provider.synthesize(
                text=request.text,
                voice=request.voice,
                engine=request.engine,
            )
            if not audio_data:
                raise HTTPException(status_code=502, detail="Voicebox returned empty audio.")
            duration = time.time() - start_time
            TTS_DURATION.labels(provider="voicebox").observe(duration)

            # Parse WAV header to derive actual sample rate and duration
            try:
                with io.BytesIO(audio_data) as buf:
                    with wave.open(buf, "rb") as wf:
                        sample_rate = wf.getframerate()
                        frame_count = wf.getnframes()
                audio_duration = frame_count / sample_rate
            except wave.Error:
                audio_duration = len(audio_data) / 48000  # fallback
                sample_rate = 24000

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="200").inc()

            # Publish CHIT voice attribution event (best-effort)
            await _publish_chit_voice_event(
                provider="voicebox",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            return SynthesizeResponse(
                duration_seconds=audio_duration,
                sample_rate=sample_rate,
                format="wav"
            )
        elif provider_name == "omnivoice" and omnivoice_provider:
            ov_provider, ov_node = _route_engine_provider(
                omnivoice_provider, OmniVoiceProvider, "omnivoice", OMNIVOICE_URL,
            )
            audio_data = await ov_provider.synthesize(
                text=request.text,
                voice=request.voice,
                instruct=request.engine if request.engine and request.engine != "omnivoice" else None,
            )
            if not audio_data:
                raise HTTPException(status_code=502, detail="OmniVoice returned empty audio.")
            duration = time.time() - start_time
            TTS_DURATION.labels(provider="omnivoice").observe(duration)

            # Parse WAV header to derive actual sample rate and duration
            try:
                with io.BytesIO(audio_data) as buf:
                    with wave.open(buf, "rb") as wf:
                        sample_rate = wf.getframerate()
                        frame_count = wf.getnframes()
                audio_duration = frame_count / sample_rate
            except wave.Error:
                audio_duration = len(audio_data) / 48000  # fallback
                sample_rate = 24000

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="200").inc()

            # Publish CHIT voice attribution event (best-effort)
            await _publish_chit_voice_event(
                provider="omnivoice",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            return SynthesizeResponse(
                duration_seconds=audio_duration,
                sample_rate=sample_rate,
                format="wav",
                node=ov_node,
            )
        else:
            if provider_name == "vibevoice" and not vibevoice_provider:
                raise HTTPException(
                    status_code=503,
                    detail="VibeVoice provider not configured (set VIBEVOICE_URL to the running server URL).",
                )
            if provider_name == "ultimate_tts" and not ultimate_tts_provider:
                raise HTTPException(
                    status_code=503,
                    detail="Ultimate-TTS provider not configured (set ULTIMATE_TTS_URL to the running studio URL).",
                )
            if provider_name == "voicebox" and not voicebox_provider:
                raise HTTPException(
                    status_code=503,
                    detail="Voicebox provider not configured (set VOICEBOX_URL to the running Voicebox server URL).",
                )
            if provider_name == "omnivoice" and not omnivoice_provider:
                raise HTTPException(
                    status_code=503,
                    detail="OmniVoice provider not configured (set OMNIVOICE_URL to the running OmniVoice server URL).",
                )
            raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available")

    except OmniVoiceBusyError as exc:
        # OmniVoice model still loading into VRAM — surface as 503 so callers retry.
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="503").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VoiceboxNoProfileError as exc:
        # Voicebox first-run not complete — distinct status so operators can act
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="503").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (VibeVoiceBusyError, VibeVoiceNoAudioError, UltimateTTSError, VoiceboxBusyError, VoiceboxError, OmniVoiceError) as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="502").inc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status=str(exc.status_code)).inc()
        raise
    except NotImplementedError as e:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="400").inc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="500").inc()
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail="TTS synthesis failed")


@app.post("/v1/voice/synthesize/audio", dependencies=[Depends(verify_api_key)])
async def synthesize_speech_audio(request: SynthesizeRequest):
    """
    Synthesize speech and return the audio bytes.

    - `output_format=wav` returns `audio/wav` (PCM16 mono, 24kHz)
    - `output_format=pcm` returns raw PCM16 bytes (`application/octet-stream`)
    """
    # Spec §4 cascade: explicit voice slug -> registry (mutates request in place),
    # else fall through to persona/intent resolution if no profile matched.
    if not _resolve_voice_profile(request) and (request.persona_id or request.intent) and not request.engine:
        from persona_selector import resolve_persona_engine
        resolved_engine, extra_kwargs = await resolve_persona_engine(
            request.persona_id, request.intent,
        )
        request.engine = resolved_engine
        if not request.provider:
            # A persona/intent that resolves to engine "omnivoice" routes to the
            # OmniVoice provider; everything else defaults to ultimate_tts.
            request.provider = "omnivoice" if resolved_engine == "omnivoice" else "ultimate_tts"
        if not request.voice and "voice" in extra_kwargs:
            request.voice = extra_kwargs.pop("voice")

    provider_name = request.provider or DEFAULT_PROVIDER
    output_format = (request.output_format or "wav").lower().strip()

    if output_format not in {"wav", "pcm"}:
        raise HTTPException(status_code=400, detail=f"output_format '{output_format}' not supported (use wav or pcm)")

    try:
        if provider_name == "vibevoice" and vibevoice_provider:
            pcm16 = await vibevoice_provider.synthesize(
                text=request.text,
                voice=request.voice,
            )
            if not pcm16:
                raise HTTPException(status_code=502, detail="VibeVoice returned empty audio (try again later).")
            if len(pcm16) % 2 != 0:
                raise HTTPException(status_code=502, detail="VibeVoice returned malformed PCM16 (odd byte length).")
            if output_format == "pcm":
                REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                return Response(content=pcm16, media_type="application/octet-stream")

            wav_bytes = _pcm16_to_wav_bytes(pcm16, sample_rate=24000)
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="flute_tts.wav"'},
            )

        elif provider_name == "ultimate_tts" and ultimate_tts_provider:
            # Ultimate-TTS returns WAV directly
            wav_bytes = await ultimate_tts_provider.synthesize(
                text=request.text,
                voice=request.voice,
                engine=request.engine or "kitten_tts",
            )
            if not wav_bytes:
                raise HTTPException(status_code=502, detail="Ultimate-TTS returned empty audio.")

            if output_format == "pcm":
                # Extract PCM from WAV
                try:
                    with io.BytesIO(wav_bytes) as buf:
                        with wave.open(buf, "rb") as wf:
                            pcm_data = wf.readframes(wf.getnframes())
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=pcm_data, media_type="application/octet-stream")
                except wave.Error:
                    # If not a valid WAV, return as-is
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=wav_bytes, media_type="application/octet-stream")

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="ultimate_tts.wav"'},
            )

        elif provider_name == "voicebox" and voicebox_provider:
            wav_bytes = await voicebox_provider.synthesize(
                text=request.text,
                voice=request.voice,
                engine=request.engine,
            )
            if not wav_bytes:
                raise HTTPException(status_code=502, detail="Voicebox returned empty audio.")

            if output_format == "pcm":
                # Extract PCM from WAV
                try:
                    with io.BytesIO(wav_bytes) as buf:
                        with wave.open(buf, "rb") as wf:
                            pcm_data = wf.readframes(wf.getnframes())
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=pcm_data, media_type="application/octet-stream")
                except wave.Error:
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=wav_bytes, media_type="application/octet-stream")

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="voicebox.wav"'},
            )

        elif provider_name == "omnivoice" and omnivoice_provider:
            wav_bytes = await omnivoice_provider.synthesize(
                text=request.text,
                voice=request.voice,
                instruct=request.engine if request.engine and request.engine != "omnivoice" else None,
            )
            if not wav_bytes:
                raise HTTPException(status_code=502, detail="OmniVoice returned empty audio.")

            if output_format == "pcm":
                # Extract PCM from WAV
                try:
                    with io.BytesIO(wav_bytes) as buf:
                        with wave.open(buf, "rb") as wf:
                            pcm_data = wf.readframes(wf.getnframes())
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=pcm_data, media_type="application/octet-stream")
                except wave.Error:
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
                    return Response(content=wav_bytes, media_type="application/octet-stream")

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="200").inc()
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="omnivoice.wav"'},
            )

        if provider_name == "vibevoice" and not vibevoice_provider:
            raise HTTPException(
                status_code=503,
                detail="VibeVoice provider not configured (set VIBEVOICE_URL to the running server URL).",
            )
        if provider_name == "ultimate_tts" and not ultimate_tts_provider:
            raise HTTPException(
                status_code=503,
                detail="Ultimate-TTS provider not configured (set ULTIMATE_TTS_URL to the running studio URL).",
            )
        if provider_name == "voicebox" and not voicebox_provider:
            raise HTTPException(
                status_code=503,
                detail="Voicebox provider not configured (set VOICEBOX_URL to the running Voicebox server URL).",
            )
        if provider_name == "omnivoice" and not omnivoice_provider:
            raise HTTPException(
                status_code=503,
                detail="OmniVoice provider not configured (set OMNIVOICE_URL to the running server URL).",
            )
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available")
    except VoiceboxNoProfileError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="503").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OmniVoiceBusyError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="503").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (VibeVoiceBusyError, VibeVoiceNoAudioError, UltimateTTSError, VoiceboxBusyError, VoiceboxError, OmniVoiceError) as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="502").inc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status=str(exc.status_code)).inc()
        raise
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="500").inc()
        logger.exception("TTS synthesis (audio) failed")
        raise HTTPException(status_code=500, detail="TTS synthesis failed")


# Prosodic synthesis endpoint — boundary-aware chunked TTS
@app.post("/v1/voice/synthesize/prosodic", dependencies=[Depends(verify_api_key)])
async def synthesize_prosodic_speech(request: SynthesizeRequest):
    """
    Synthesize speech with prosodic awareness.

    Parses text into boundary-aware chunks (sentence, clause, phrase, breath),
    synthesizes each chunk independently, then stitches with natural pauses
    and crossfades. Returns WAV audio + prosodic timeline metadata.

    The prosodic timeline includes BPM encoding compatible with CHIT CGP events.
    """
    # Spec §4 cascade: explicit voice slug -> registry (mutates request in place),
    # else fall through to persona/intent resolution if no profile matched.
    if not _resolve_voice_profile(request) and (request.persona_id or request.intent) and not request.engine:
        from persona_selector import resolve_persona_engine
        resolved_engine, extra_kwargs = await resolve_persona_engine(
            request.persona_id, request.intent,
        )
        request.engine = resolved_engine
        if not request.provider:
            # Prosodic synthesis is ultimate_tts-only (BPM chunking is an
            # ultimate_tts-specific feature), so always route there regardless of
            # the resolved engine — an omnivoice persona falls back to ultimate_tts.
            request.provider = "ultimate_tts"
        if not request.voice and "voice" in extra_kwargs:
            request.voice = extra_kwargs.pop("voice")

    provider_name = request.provider or DEFAULT_PROVIDER
    engine = request.engine or "kokoro"

    if provider_name != "ultimate_tts" or not ultimate_tts_provider:
        raise HTTPException(
            status_code=400,
            detail="Prosodic synthesis requires ultimate_tts provider",
        )

    try:
        # 1. Parse text into prosodic chunks
        chunks = parse_prosodic(request.text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No parseable text")

        # 2. Synthesize each chunk, tracking successful ones
        chunk_audio: list[bytes] = []
        successful_chunks: list[ProsodicChunk] = []
        for chunk in chunks:
            try:
                wav_bytes = await ultimate_tts_provider.synthesize(
                    text=chunk.text,
                    voice=request.voice,
                    engine=engine,
                )
            except Exception as chunk_exc:
                logger.warning("Chunk synthesis failed for %r: %s", chunk.text[:40], chunk_exc)
                continue
            if wav_bytes:
                chunk_audio.append(wav_bytes)
                successful_chunks.append(chunk)

        if not chunk_audio:
            raise HTTPException(status_code=502, detail="All chunks failed synthesis")

        # 3. Convert WAV bytes to numpy arrays for stitching
        audio_arrays = []
        for wav_data in chunk_audio:
            with io.BytesIO(wav_data) as buf:
                with wave.open(buf, "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    audio_arrays.append(
                        np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    )

        # Extract boundaries between chunks (stitch_chunks expects len == len(arrays) - 1)
        boundaries = [c.boundary_after for c in successful_chunks[:-1]]

        # 4. Stitch with prosodic pauses
        stitched = stitch_chunks(audio_arrays, boundaries)

        # 5. Convert stitched float32 numpy array to WAV bytes
        int16_data = (stitched * 32767).clip(-32768, 32767).astype(np.int16)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(int16_data.tobytes())
        wav_bytes_out = wav_buf.getvalue()

        # 6. Build prosodic timeline for response
        timeline = []
        position = 0.0
        for chunk in successful_chunks:
            entry = {
                "text": chunk.text,
                "boundary_before": chunk.boundary_before.name,
                "boundary_after": chunk.boundary_after.name,
                "pause_after_ms": chunk.pause_after,
                "position_ratio": round(chunk.position_ratio, 3),
                "estimated_syllables": chunk.estimated_syllables,
                "offset_sec": round(position, 3),
            }
            timeline.append(entry)
            # Rough duration estimate: 150ms per syllable + pause
            position += (chunk.estimated_syllables * 0.15) + (chunk.pause_after / 1000.0)

        # 7. Build BPM metadata from boundaries (uses prosodic.bpm_encoder constants)
        from prosodic.bpm_encoder import BPM_MAP
        avg_bpm = sum(
            BPM_MAP.get(c.boundary_after, 120) for c in successful_chunks
        ) / max(len(successful_chunks), 1)

        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="200").inc()

        # Publish CHIT voice attribution event with prosodic metadata
        # (best-effort — only fires when CHIT_VOICE_ATTRIBUTION is enabled).
        # The stitched audio is at 22050 Hz mono 16-bit, so duration is
        # len(stitched_samples) / 22050. This lets downstream geometry-bus
        # consumers correlate voice synthesis with BPM-encoded prosodic
        # structure for CGP events.
        prosodic_audio_duration = len(stitched) / 22050.0
        await _publish_chit_voice_event(
            provider=f"ultimate_tts:{request.engine or 'kokoro'}:prosodic",
            text_length=len(request.text),
            audio_duration=prosodic_audio_duration,
            voice=request.voice,
        )

        # Return WAV bytes with compact metadata in headers.
        # Full timeline available via X-Prosodic-Timeline-URL (future) or
        # by POST-ing to /v1/voice/synthesize/prosodic with Accept: application/json.
        timeline_compact = json.dumps(
            [{"t": e["text"][:30], "b": e["boundary_after"][0], "o": e["offset_sec"]} for e in timeline]
        )
        return Response(
            content=wav_bytes_out,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'attachment; filename="prosodic_tts.wav"',
                "X-Prosodic-Chunks": str(len(successful_chunks)),
                "X-Prosodic-BPM": str(round(avg_bpm, 1)),
                "X-Prosodic-Timeline": timeline_compact,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="500").inc()
        logger.exception("Prosodic synthesis failed")
        raise HTTPException(status_code=500, detail="Prosodic synthesis failed") from exc


# STT recognition endpoint
@app.post("/v1/voice/recognize", response_model=RecognizeResponse, dependencies=[Depends(verify_api_key)])
async def recognize_speech(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """
    Recognize speech from audio file.

    Uses Whisper for transcription.
    Supports WAV, MP3, and other common audio formats.
    """
    import time
    start_time = time.time()

    try:
        audio_data = await audio.read()

        if whisper_provider:
            result = await whisper_provider.recognize(
                audio_data=audio_data,
                language=language
            )
            duration = time.time() - start_time
            STT_DURATION.labels(provider="whisper").observe(duration)

            REQUESTS_TOTAL.labels(endpoint="/v1/voice/recognize", status="200").inc()

            return RecognizeResponse(
                text=result["text"],
                confidence=result["confidence"],
                language=result["language"]
            )
        else:
            raise HTTPException(
                status_code=503,
                detail="Whisper provider not available"
            )

    except NotImplementedError as e:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/recognize", status="400").inc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/recognize", status="500").inc()
        logger.exception("STT recognition failed")
        raise HTTPException(status_code=500, detail="STT recognition failed")


# Voice personas endpoints
@app.get("/v1/voice/personas", dependencies=[Depends(verify_api_key)])
async def list_personas() -> List[Dict[str, Any]]:
    """List all voice personas from Supabase."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/voice_persona",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                },
                params={"is_active": "eq.true", "select": "*"}
            )
            if resp.status_code == 200:
                REQUESTS_TOTAL.labels(endpoint="/v1/voice/personas", status="200").inc()
                return resp.json()
            else:
                logger.warning(
                    "Supabase persona query failed: status=%s body=%s",
                    resp.status_code, resp.text[:200] if resp.text else "empty"
                )
                REQUESTS_TOTAL.labels(endpoint="/v1/voice/personas", status=str(resp.status_code)).inc()
                return []
    except Exception:
        logger.exception("Failed to fetch personas")
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/personas", status="500").inc()
        raise HTTPException(status_code=500, detail="Failed to fetch personas")


@app.get("/v1/voice/personas/{persona_id}", dependencies=[Depends(verify_api_key)])
async def get_persona(persona_id: str) -> Dict[str, Any]:
    """Get a specific voice persona by ID or slug."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try by ID first, then by slug
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/voice_persona",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                },
                params={"or": f"(id.eq.{persona_id},slug.eq.{persona_id})", "limit": "1"}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    REQUESTS_TOTAL.labels(endpoint="/v1/voice/personas/{id}", status="200").inc()
                    return data[0]
            raise HTTPException(status_code=404, detail="Persona not found")
    except HTTPException:
        raise
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.exception("Failed to fetch persona")
        raise HTTPException(status_code=500, detail="Failed to fetch persona") from exc


# Voice profile registry endpoints (S1: pmoves_core.voice_profiles)
@app.get("/v1/voice/profiles", dependencies=[Depends(verify_api_key)])
async def list_voice_profiles(
    engine: Optional[str] = None,
    tag: Optional[str] = None,
    rights: Optional[str] = None,
) -> Dict[str, Any]:
    """List voice profiles from the in-memory registry, optionally filtered.

    Returns ``{"profiles": [], "healthy": False}`` (HTTP 200) when the registry
    is absent/unhealthy (graceful degradation — table not migrated, Supabase
    unreachable, etc.).
    """
    if voice_registry is None or not voice_registry.healthy:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles", status="200").inc()
        return {"profiles": [], "healthy": False, "count": 0}
    rows = voice_registry.list(engine=engine, tag=tag, rights=rights)
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles", status="200").inc()
    return {"profiles": [p.raw for p in rows], "healthy": True, "count": len(rows)}


@app.get("/v1/voice/profiles/{name}", dependencies=[Depends(verify_api_key)])
async def get_voice_profile(name: str) -> Dict[str, Any]:
    """Resolve a single voice profile by slug."""
    profile = voice_registry.get(name) if voice_registry else None
    if profile is None:
        raise HTTPException(status_code=404, detail="voice profile not found")
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles/{name}", status="200").inc()
    return profile.raw


@app.post("/v1/voice/profiles", status_code=201, dependencies=[Depends(verify_api_key)])
async def create_voice_profile(body: VoiceProfileIn) -> Dict[str, Any]:
    """Create/register a voice profile (service-gated via verify_api_key).

    Validates the engine + capability matrix + grounding contract before any
    Supabase write. Writes to pmoves_core via PostgREST (Content-Profile header),
    then warms the in-memory cache so the new slug resolves immediately.
    """
    if body.engine not in ENGINE_VALUES:
        raise HTTPException(status_code=422, detail=f"engine must be one of {ENGINE_VALUES}")
    cap_errors = validate_capability(body.engine, body.engine_specific)
    g_errors, g_warnings = await validate_grounding(
        body.grounding, supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY,
    )
    if cap_errors or g_errors:
        raise HTTPException(
            status_code=422,
            detail={"capability": cap_errors, "grounding": g_errors, "warnings": g_warnings},
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/voice_profiles",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    # pmoves_core schema is not the default PostgREST profile.
                    "Content-Profile": "pmoves_core",
                    "Accept-Profile": "pmoves_core",
                    "Prefer": "return=representation",
                },
                json=body.model_dump(exclude_none=True),
            )
    except httpx.HTTPError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles", status="502").inc()
        raise HTTPException(status_code=502, detail=f"voice_profiles write failed: {exc}") from exc

    if resp.status_code not in (200, 201):
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles", status=str(resp.status_code)).inc()
        raise HTTPException(status_code=resp.status_code, detail=(resp.text or "")[:300])

    payload = resp.json()
    row = payload[0] if isinstance(payload, list) and payload else payload
    if voice_registry is not None and isinstance(row, dict):
        try:
            voice_registry.upsert_local(VoiceProfile.from_row(row))
        except (KeyError, TypeError):
            logger.warning("voice_registry: created row missing fields, cache not warmed")
    # Notify peer gateway instances to refresh so they don't serve stale data
    # until their TTL elapses. Fire-and-forget on the shared invalidation subject
    # (this instance is subscribed too, which reconciles its warm cache from DB).
    if nats_client is not None and isinstance(row, dict):
        try:
            await nats_client.publish(
                REGISTRY_UPDATE_SUBJECT,
                json.dumps({
                    "op": "upsert",
                    "name": row.get("name"),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }).encode("utf-8"),
            )
        except Exception as exc:  # best-effort; the TTL loop is the safety net
            logger.warning("voice_registry: failed to publish %s (%s)", REGISTRY_UPDATE_SUBJECT, exc)
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/profiles", status="201").inc()
    return row


@app.get("/v1/voice/validate")
async def voice_validate_contract() -> Dict[str, Any]:
    """Introspection: engines + the grounding contract (keys -> substrate PKs)."""
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/validate", status="200").inc()
    return grounding_contract()


@app.post("/v1/voice/validate", dependencies=[Depends(verify_api_key)], response_model=ValidateResponse)
async def voice_validate(body: ValidateRequest) -> ValidateResponse:
    """Validate engine capability + grounding contract (grounding keys -> real PKs)."""
    errors = validate_capability(body.engine, body.engine_specific)
    g_errors, g_warnings = await validate_grounding(
        body.grounding, supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY,
    )
    errors = list(errors) + list(g_errors)
    REQUESTS_TOTAL.labels(endpoint="/v1/voice/validate", status="200").inc()
    return ValidateResponse(valid=not errors, errors=errors, warnings=g_warnings)


# WebSocket TTS streaming endpoint
@app.websocket("/v1/voice/stream/tts")
async def websocket_tts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time TTS streaming.

    Client sends: {"text": "Hello world", "voice": "default"}
    Server sends: Binary audio chunks (PCM16, 24kHz)
    Server sends: {"type": "done", "duration": 1.5}
    """
    await websocket.accept()

    try:
        while True:
            # Receive text request
            data = await websocket.receive_json()
            text = data.get("text", "")
            voice = data.get("voice", "default")

            if not text:
                await websocket.send_json({"type": "error", "message": "No text provided"})
                continue

            # Validate text length (same limit as REST endpoint)
            if len(text) > 5000:
                await websocket.send_json({"type": "error", "message": "Text exceeds 5000 character limit"})
                continue

            # Stream audio chunks
            if vibevoice_provider:
                try:
                    chunk_count = 0
                    async for chunk in vibevoice_provider.synthesize_stream(text, voice):
                        await websocket.send_bytes(chunk)
                        chunk_count += 1
                    if chunk_count == 0:
                        await websocket.send_json({"type": "error", "message": "VibeVoice produced no audio (try again later)."})
                        continue
                    await websocket.send_json({"type": "done", "chunks": chunk_count})
                except (VibeVoiceBusyError, VibeVoiceNoAudioError) as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "VibeVoice provider not available"
                })

    except Exception:
        logger.exception("WebSocket TTS error")
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass  # WebSocket already closed
    finally:
        await websocket.close()


@app.websocket("/v1/voice/agent")
async def websocket_voice_agent(websocket: WebSocket):
    """Full-duplex realtime voice agent.

    Pipeline: mic PCM16 in → VAD → STT (Whisper) → LLM (TensorZero) →
    TTS (VibeVoice) → PCM16 out. This is the entry point that connects a
    microphone client to the pre-built pipecat pipeline.

    Gated behind ``PIPECAT_ENABLED=true`` *and* pipecat-ai being installed.
    When disabled/unavailable the socket is accepted then closed with a clear
    reason, so clients fail fast instead of hanging. Off by default — wiring
    this route changes no existing behaviour until the operator opts in.

    Client streams binary PCM16 frames (``PIPECAT_SAMPLE_RATE``, default 24 kHz,
    mono). Server streams binary PCM16 audio + JSON status frames.
    """
    await websocket.accept()

    if not PIPECAT_CONFIG.enabled:
        await websocket.send_json({"type": "error", "message": "Realtime voice agent disabled. Set PIPECAT_ENABLED=true to enable."})
        await websocket.close()
        return
    if not PIPECAT_AVAILABLE:
        await websocket.send_json({"type": "error", "message": "pipecat-ai not installed; realtime voice agent unavailable."})
        await websocket.close()
        return
    if whisper_provider is None or vibevoice_provider is None:
        await websocket.send_json({"type": "error", "message": "STT/TTS providers not ready (Whisper + VibeVoice required)."})
        await websocket.close()
        return

    try:
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineTask

        params = FluteFastAPIWebsocketParams(
            sample_rate=PIPECAT_CONFIG.sample_rate,
            vad_enabled=True,
            vad_start_threshold=PIPECAT_CONFIG.vad_threshold,
        )
        transport = FluteFastAPIWebsocketTransport(websocket, params)
        pipeline = await build_voice_agent_pipeline(
            transport,
            VoiceAgentConfig(),
            vibevoice_provider=vibevoice_provider,
            whisper_provider=whisper_provider,
            tensorzero_url=PIPECAT_CONFIG.tensorzero_url,
        )
        await websocket.send_json({
            "type": "ready",
            "stt": "whisper",
            "tts": "vibevoice",
            "llm": PIPECAT_CONFIG.default_llm_model,
        })
        await PipelineRunner().run(PipelineTask(pipeline))
    except Exception:
        logger.exception("Voice agent pipeline error")
        try:
            await websocket.send_json({"type": "error", "message": "Voice agent pipeline error"})
        except Exception:
            pass  # WebSocket already closed
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# NATS event publishing helper
async def publish_voice_event(subject: str, data: Dict[str, Any]):
    """Publish a voice event to NATS."""
    if nats_client and nats_client.is_connected:
        try:
            await nats_client.publish(
                subject,
                json.dumps(data).encode()
            )
            logger.debug("Published to %s: %s", subject, data)
        except Exception:
            logger.exception("Failed to publish to NATS")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("FLUTE_HTTP_PORT", "8055"))
    uvicorn.run(app, host="0.0.0.0", port=port)
