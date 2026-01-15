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
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Provider imports
from providers import (
    VibeVoiceBusyError,
    VibeVoiceNoAudioError,
    VibeVoiceProvider,
    WhisperProvider,
    UltimateTTSError,
    UltimateTTSProvider,
)

# Prosodic sidecar imports
from prosodic import (
    BoundaryType,
    ProsodicChunk,
    parse_prosodic,
    format_prosodic_analysis,
    prosodic_stitch,
    stitch_chunks,
)

# Pipecat integration (optional - enable with PIPECAT_ENABLED=true)
from pipecat.config import get_pipecat_config
PIPECAT_CONFIG = get_pipecat_config()

# NATS service announcement integration
try:
    from services.common.nats_service_listener import announce_service, ServiceTier
    NATS_ANNOUNCE_AVAILABLE = True
except ImportError:
    NATS_ANNOUNCE_AVAILABLE = False

try:
    from pipecat.transports import FluteFastAPIWebsocketTransport, FluteFastAPIWebsocketParams
    from pipecat.pipelines import VoiceAgentConfig, build_voice_agent_pipeline
    from pipecat.processors import TensorZeroLLMProcessor
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
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:3010")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
# VibeVoice is now served by Ultimate-TTS-Studio (port 7861)
# Default to the host-gateway URL so the Flute stack is voice-ready by default.
VIBEVOICE_URL = (os.getenv("VIBEVOICE_URL") or "http://host.docker.internal:7861").strip()
WHISPER_URL = os.getenv("WHISPER_URL", "http://ffmpeg-whisper:8078")
ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://ultimate-tts-studio:7860")
DEFAULT_PROVIDER = os.getenv("DEFAULT_VOICE_PROVIDER", "vibevoice")
FLUTE_API_KEY = os.getenv("FLUTE_API_KEY", "")

# CHIT integration configuration
CHIT_VOICE_ATTRIBUTION = os.getenv("CHIT_VOICE_ATTRIBUTION", "false").lower() == "true"
CHIT_NAMESPACE = os.getenv("CHIT_NAMESPACE", "pmoves.voice")
CHIT_GEOMETRY_SUBJECT = os.getenv("CHIT_GEOMETRY_SUBJECT", "tokenism.geometry.event.v1")


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

# Provider instances (initialized on startup)
vibevoice_provider: Optional[VibeVoiceProvider] = None
whisper_provider: Optional[WhisperProvider] = None
ultimate_tts_provider: Optional[UltimateTTSProvider] = None
nats_client = None


async def _publish_chit_voice_event(
    provider: str,
    text_length: int,
    audio_duration: float,
    voice: Optional[str] = None,
) -> None:
    """Publish voice synthesis event to CHIT geometry bus (best-effort).

    Only publishes if CHIT_VOICE_ATTRIBUTION is enabled.
    Non-blocking: errors are logged but don't fail the request.
    """
    if not CHIT_VOICE_ATTRIBUTION or not nats_client:
        return
    try:
        payload = {
            "namespace": CHIT_NAMESPACE,
            "modality": "voice_synthesis",
            "provider": provider,
            "text_length": text_length,
            "audio_duration_seconds": audio_duration,
            "voice": voice,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await nats_client.publish(
            CHIT_GEOMETRY_SUBJECT,
            json.dumps(payload).encode("utf-8"),
        )
        logger.debug("chit_voice_event_published", extra={"subject": CHIT_GEOMETRY_SUBJECT})
    except Exception as exc:
        # Track failures in Prometheus for observability
        reason = "nats_unavailable" if not nats_client else "publish_failed"
        CHIT_EVENTS_FAILED.labels(reason=reason).inc()
        # If user explicitly enabled CHIT, they should know it's failing
        if CHIT_VOICE_ATTRIBUTION:
            logger.error(
                "chit_voice_event_failed",
                extra={
                    "error": str(exc),
                    "exc_type": type(exc).__name__,
                    "provider": provider,
                },
                exc_info=True
            )
        else:
            logger.debug(
                "chit_voice_event_failed",
                extra={
                    "error": str(exc),
                    "exc_type": type(exc).__name__,
                },
            )


# Pydantic models
class SynthesizeRequest(BaseModel):
    """Request for TTS synthesis."""
    text: str = Field(..., description="Text to synthesize", max_length=5000)
    persona_id: Optional[str] = Field(None, description="Voice persona ID or slug")
    provider: Optional[str] = Field(None, description="Provider override (vibevoice, ultimate_tts, elevenlabs)")
    voice: Optional[str] = Field(None, description="Voice preset for provider")
    engine: Optional[str] = Field(None, description="TTS engine for ultimate_tts (kitten_tts, f5_tts, kokoro)")
    output_format: str = Field("wav", description="Output format: wav, mp3, pcm")


class SynthesizeResponse(BaseModel):
    """Response for TTS synthesis."""
    audio_uri: Optional[str] = Field(None, description="MinIO URI if stored")
    duration_seconds: float = Field(..., description="Audio duration")
    sample_rate: int = Field(24000, description="Sample rate in Hz")
    format: str = Field("pcm16", description="Audio format")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown with NATS service announcement."""
    global vibevoice_provider, whisper_provider, ultimate_tts_provider, cloning_provider, nats_client

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

    # Initialize NATS (optional)
    try:
        import nats
        nats_client = await nats.connect(NATS_URL)
        logger.info("Connected to NATS at %s", NATS_URL)

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

    logger.info("Flute Gateway started successfully")
    yield

    # Shutdown
    logger.info("Shutting down Flute Gateway...")
    if nats_client:
        await nats_client.close()


# Create FastAPI app
app = FastAPI(
    title="PMOVES-Flute-Gateway",
    description="Multimodal Voice Communication Layer",
    version="0.1.0",
    lifespan=lifespan
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
        }
    )


# TTS synthesis endpoint
@app.post("/v1/voice/synthesize", response_model=SynthesizeResponse, dependencies=[Depends(verify_api_key)])
async def synthesize_speech(request: SynthesizeRequest):
    """
    Synthesize speech from text.

    Uses VibeVoice by default for real-time TTS.
    Returns audio data or MinIO URI.
    """
    import time
    start_time = time.time()

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
            audio_data = await ultimate_tts_provider.synthesize(
                text=request.text,
                voice=request.voice,
                engine=request.engine or "kitten_tts",
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
                format="wav"
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
            raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available")

    except (VibeVoiceBusyError, VibeVoiceNoAudioError, UltimateTTSError) as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="502").inc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status=str(exc.status_code)).inc()
        raise
    except NotImplementedError as e:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="400").inc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available")
    except (VibeVoiceBusyError, VibeVoiceNoAudioError, UltimateTTSError) as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="502").inc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status=str(exc.status_code)).inc()
        raise
    except Exception as e:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="500").inc()
        logger.exception("TTS synthesis (audio) failed")
        raise HTTPException(status_code=500, detail="TTS synthesis failed")


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
    except Exception as e:
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

    except Exception as exc:
        logger.exception("WebSocket TTS error")
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass  # WebSocket already closed
    finally:
        await websocket.close()


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
