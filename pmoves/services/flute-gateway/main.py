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
    VoiceCloningProvider,
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
# VibeVoice is a host-run realtime TTS demo (Pinokio or manual run).
# Default to the host-gateway URL so the Flute stack is voice-ready by default.
VIBEVOICE_URL = (os.getenv("VIBEVOICE_URL") or "http://host.docker.internal:3000").strip()
WHISPER_URL = os.getenv("WHISPER_URL", "http://ffmpeg-whisper:8078")
ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://ultimate-tts-studio:7860")
PRESIGN_URL = os.getenv("PRESIGN_URL", "http://presign:8088")
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
PROSODIC_TTFS = Histogram(
    "flute_prosodic_ttfs_seconds",
    "Time-to-first-speech for prosodic synthesis",
    ["provider"],
    buckets=(0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)
)
PROSODIC_CHUNKS = Histogram(
    "flute_prosodic_chunks",
    "Number of prosodic chunks per synthesis",
    buckets=(1, 2, 3, 4, 5, 7, 10, 15)
)
PROSODIC_CHUNKS_FAILED = Counter(
    "flute_prosodic_chunks_failed_total",
    "Number of prosodic chunks that failed to synthesize",
    ["provider", "reason"]
)

# Provider instances (initialized on startup)
vibevoice_provider: Optional[VibeVoiceProvider] = None
whisper_provider: Optional[WhisperProvider] = None
ultimate_tts_provider: Optional[UltimateTTSProvider] = None
cloning_provider: Optional[VoiceCloningProvider] = None
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
        logger.warning(
            "chit_voice_event_failed",
            extra={"error": str(exc), "exc_type": type(exc).__name__},
            exc_info=True
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


class ProsodicAnalyzeRequest(BaseModel):
    """Request for prosodic text analysis."""
    text: str = Field(..., description="Text to analyze", max_length=5000)
    first_chunk_words: int = Field(2, ge=1, le=10, description="Words in first chunk (for TTFS)")
    max_syllables_before_breath: int = Field(10, ge=5, le=20, description="Syllables before forced breath")


class ProsodicChunkResponse(BaseModel):
    """A single prosodic chunk in the analysis."""
    text: str
    boundary_after: str
    pause_ms: float
    is_first: bool
    is_final: bool
    estimated_syllables: int


class ProsodicAnalyzeResponse(BaseModel):
    """Response for prosodic text analysis."""
    chunks: List[ProsodicChunkResponse]
    total_chunks: int
    estimated_ttfs_benefit: str


class ProsodicSynthesizeRequest(BaseModel):
    """Request for prosodic TTS synthesis (low-latency with natural pauses)."""
    text: str = Field(..., description="Text to synthesize", max_length=5000)
    provider: Optional[str] = Field(None, description="Provider override (vibevoice, ultimate_tts)")
    voice: Optional[str] = Field(None, description="Voice preset for provider")
    engine: Optional[str] = Field(None, description="TTS engine for ultimate_tts")
    first_chunk_words: int = Field(2, ge=1, le=10, description="Words in first chunk (for TTFS)")
    output_format: str = Field("wav", description="Output format: wav, pcm")


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


# Voice cloning request/response models
class VoiceCloneRegisterResponse(BaseModel):
    """Response for voice sample registration."""
    persona_id: str
    status: str
    sample_uri: str
    message: str


class VoiceCloneTrainRequest(BaseModel):
    """Request to start voice cloning training."""
    persona_id: str = Field(..., description="Voice persona UUID")


class VoiceCloneStatusResponse(BaseModel):
    """Response for voice cloning status."""
    persona_id: str
    voice_cloning_status: Optional[str] = None
    training_progress: Optional[int] = None
    training_message: Optional[str] = None
    rvc_model_uri: Optional[str] = None
    rvc_index_uri: Optional[str] = None
    training_started_at: Optional[str] = None
    training_completed_at: Optional[str] = None


class VoiceCloneSynthesizeRequest(BaseModel):
    """Request to synthesize with cloned voice."""
    text: str = Field(..., description="Text to synthesize", max_length=5000)
    persona_id: str = Field(..., description="Voice persona UUID with trained model")
    output_format: str = Field("wav", description="Output format: wav, pcm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global vibevoice_provider, whisper_provider, ultimate_tts_provider, cloning_provider, nats_client

    logger.info("Starting Flute Gateway...")

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

    # Initialize NATS (optional) - must be before cloning_provider
    try:
        import nats
        nats_client = await nats.connect(NATS_URL)
        logger.info("Connected to NATS at %s", NATS_URL)
    except Exception as e:
        logger.warning("NATS connection failed: %s (continuing without NATS)", e)
        nats_client = None

    # Initialize Voice Cloning provider (after NATS for nats_client)
    cloning_provider = VoiceCloningProvider(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        ultimate_tts_url=ULTIMATE_TTS_URL,
        presign_url=PRESIGN_URL,
        nats_client=nats_client,
    )
    logger.info("Voice Cloning provider enabled")

    logger.info("Flute Gateway started successfully")
    yield

    # Shutdown
    logger.info("Shutting down Flute Gateway...")
    if nats_client:
        await nats_client.close()
    if cloning_provider:
        await cloning_provider.close()


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
            "stt_stream": PIPECAT_CONFIG.enabled and PIPECAT_AVAILABLE,
            "duplex_voice": PIPECAT_CONFIG.enabled and PIPECAT_AVAILABLE,
            "voice_cloning": True,
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
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize", status="500").inc()
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail="TTS synthesis failed") from None


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
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/audio", status="500").inc()
        logger.exception("TTS synthesis (audio) failed")
        raise HTTPException(status_code=500, detail="TTS synthesis failed") from None


# Prosodic analysis endpoint
@app.post("/v1/voice/analyze/prosodic", response_model=ProsodicAnalyzeResponse, dependencies=[Depends(verify_api_key)])
async def analyze_prosodic(request: ProsodicAnalyzeRequest):
    """
    Analyze text for prosodic chunking without synthesizing.

    Returns the chunking structure that would be used for prosodic TTS,
    useful for debugging and understanding how text will be split.
    """
    chunks = parse_prosodic(
        request.text,
        first_chunk_words=request.first_chunk_words,
        max_syllables_before_breath=request.max_syllables_before_breath,
    )

    if not chunks:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/analyze/prosodic", status="400").inc()
        raise HTTPException(status_code=400, detail="No text to analyze (empty or whitespace-only input)")

    chunk_responses = [
        ProsodicChunkResponse(
            text=chunk.text,
            boundary_after=chunk.boundary_after.name,
            pause_ms=chunk.pause_after,
            is_first=chunk.is_first,
            is_final=chunk.is_final,
            estimated_syllables=chunk.estimated_syllables,
        )
        for chunk in chunks
    ]

    # Estimate TTFS benefit: compare first chunk vs full text word count
    total_words = len(request.text.strip().split())
    first_chunk_words = len(chunks[0].text.split())
    ratio = first_chunk_words / total_words if total_words > 0 else 1.0
    benefit = f"~{int((1 - ratio) * 100)}% faster TTFS (first {first_chunk_words}/{total_words} words)"

    REQUESTS_TOTAL.labels(endpoint="/v1/voice/analyze/prosodic", status="200").inc()

    return ProsodicAnalyzeResponse(
        chunks=chunk_responses,
        total_chunks=len(chunks),
        estimated_ttfs_benefit=benefit,
    )


# Prosodic TTS synthesis endpoint
@app.post("/v1/voice/synthesize/prosodic", dependencies=[Depends(verify_api_key)])
async def synthesize_prosodic(request: ProsodicSynthesizeRequest):
    """
    Synthesize speech with prosodic chunking for ultra-low TTFS.

    Uses the prosodic sidecar approach:
    1. Parse text into natural prosodic chunks
    2. Synthesize first chunk immediately (tiny, for fast TTFS)
    3. Synthesize remaining chunks in parallel
    4. Stitch with natural pauses and optional breath sounds

    Returns audio with ~160ms TTFS vs ~750ms for baseline synthesis.
    """
    import time
    import numpy as np
    start_time = time.time()

    provider_name = request.provider or DEFAULT_PROVIDER
    output_format = (request.output_format or "wav").lower().strip()

    if output_format not in {"wav", "pcm"}:
        raise HTTPException(status_code=400, detail=f"output_format '{output_format}' not supported")

    # Parse into prosodic chunks
    chunks = parse_prosodic(request.text, first_chunk_words=request.first_chunk_words)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text to synthesize")

    PROSODIC_CHUNKS.observe(len(chunks))

    try:
        if provider_name == "vibevoice" and vibevoice_provider:
            sample_rate = 24000

            # Synthesize first chunk for TTFS measurement
            first_pcm = await vibevoice_provider.synthesize(
                text=chunks[0].text,
                voice=request.voice,
            )
            ttfs = time.time() - start_time
            PROSODIC_TTFS.labels(provider="vibevoice").observe(ttfs)

            if not first_pcm:
                raise HTTPException(status_code=502, detail="VibeVoice returned empty audio")

            # Convert to float32 for processing
            first_audio = np.frombuffer(first_pcm, dtype=np.int16).astype(np.float32) / 32768.0

            # Synthesize remaining chunks (could be parallelized in future)
            audio_chunks = [first_audio]
            boundaries = []

            for chunk_idx, chunk in enumerate(chunks[1:], start=1):
                pcm = await vibevoice_provider.synthesize(
                    text=chunk.text,
                    voice=request.voice,
                )
                if not pcm:
                    logger.error(
                        "VibeVoice returned empty audio for chunk %d/%d: %r",
                        chunk_idx + 1, len(chunks), chunk.text[:50]
                    )
                    PROSODIC_CHUNKS_FAILED.labels(provider="vibevoice", reason="empty_audio").inc()
                    raise HTTPException(
                        status_code=502,
                        detail=f"VibeVoice failed to synthesize chunk {chunk_idx + 1}/{len(chunks)}"
                    )
                audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
                audio_chunks.append(audio)
                boundaries.append(chunks[chunk_idx - 1].boundary_after)

            # Stitch with prosodic transitions
            if len(audio_chunks) > 1:
                final_audio = stitch_chunks(audio_chunks, boundaries, sample_rate=sample_rate)
            else:
                final_audio = audio_chunks[0]

            # Convert back to PCM16
            final_pcm = (final_audio * 32767).astype(np.int16).tobytes()

            duration = time.time() - start_time
            TTS_DURATION.labels(provider="vibevoice_prosodic").observe(duration)
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="200").inc()

            # Publish CHIT voice attribution event
            audio_duration = len(final_pcm) / 48000  # 24kHz * 2 bytes
            await _publish_chit_voice_event(
                provider="vibevoice_prosodic",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            if output_format == "pcm":
                return Response(content=final_pcm, media_type="application/octet-stream")

            wav_bytes = _pcm16_to_wav_bytes(final_pcm, sample_rate=sample_rate)
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": 'attachment; filename="prosodic_tts.wav"',
                    "X-Prosodic-TTFS-Ms": str(int(ttfs * 1000)),
                    "X-Prosodic-Chunks": str(len(chunks)),
                },
            )

        elif provider_name == "ultimate_tts" and ultimate_tts_provider:
            sample_rate = 24000

            # Synthesize first chunk
            first_wav = await ultimate_tts_provider.synthesize(
                text=chunks[0].text,
                voice=request.voice,
                engine=request.engine or "kitten_tts",
            )
            ttfs = time.time() - start_time
            PROSODIC_TTFS.labels(provider="ultimate_tts").observe(ttfs)

            if not first_wav:
                raise HTTPException(status_code=502, detail="Ultimate-TTS returned empty audio")

            # Extract PCM from WAV and convert to float32
            try:
                with io.BytesIO(first_wav) as buf:
                    with wave.open(buf, "rb") as wf:
                        sample_rate = wf.getframerate()
                        first_pcm = wf.readframes(wf.getnframes())
            except wave.Error as wav_err:
                logger.error("WAV parsing failed for first chunk (%d bytes): %s", len(first_wav), wav_err)
                PROSODIC_CHUNKS_FAILED.labels(provider="ultimate_tts", reason="wav_parse_error").inc()
                raise HTTPException(
                    status_code=502,
                    detail="WAV parsing failed for first chunk"
                ) from wav_err
            first_audio = np.frombuffer(first_pcm, dtype=np.int16).astype(np.float32) / 32768.0

            audio_chunks = [first_audio]
            boundaries = []

            for chunk_idx, chunk in enumerate(chunks[1:], start=1):
                wav_data = await ultimate_tts_provider.synthesize(
                    text=chunk.text,
                    voice=request.voice,
                    engine=request.engine or "kitten_tts",
                )
                if not wav_data:
                    logger.error(
                        "Ultimate-TTS returned empty audio for chunk %d/%d: %r",
                        chunk_idx + 1, len(chunks), chunk.text[:50]
                    )
                    PROSODIC_CHUNKS_FAILED.labels(provider="ultimate_tts", reason="empty_audio").inc()
                    raise HTTPException(
                        status_code=502,
                        detail=f"Ultimate-TTS failed to synthesize chunk {chunk_idx + 1}/{len(chunks)}"
                    )
                try:
                    with io.BytesIO(wav_data) as buf:
                        with wave.open(buf, "rb") as wf:
                            pcm_data = wf.readframes(wf.getnframes())
                except wave.Error as wav_err:
                    logger.error(
                        "WAV parsing failed for chunk %d/%d (%d bytes): %s",
                        chunk_idx + 1, len(chunks), len(wav_data), wav_err
                    )
                    PROSODIC_CHUNKS_FAILED.labels(provider="ultimate_tts", reason="wav_parse_error").inc()
                    raise HTTPException(
                        status_code=502,
                        detail=f"WAV parsing failed for chunk {chunk_idx + 1}/{len(chunks)}"
                    ) from wav_err
                audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
                audio_chunks.append(audio)
                boundaries.append(chunks[chunk_idx - 1].boundary_after)

            # Stitch with prosodic transitions
            if len(audio_chunks) > 1:
                final_audio = stitch_chunks(audio_chunks, boundaries, sample_rate=sample_rate)
            else:
                final_audio = audio_chunks[0]

            final_pcm = (final_audio * 32767).astype(np.int16).tobytes()

            duration = time.time() - start_time
            TTS_DURATION.labels(provider="ultimate_tts_prosodic").observe(duration)
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="200").inc()

            audio_duration = len(final_pcm) / (sample_rate * 2)
            await _publish_chit_voice_event(
                provider="ultimate_tts_prosodic",
                text_length=len(request.text),
                audio_duration=audio_duration,
                voice=request.voice,
            )

            if output_format == "pcm":
                return Response(content=final_pcm, media_type="application/octet-stream")

            wav_bytes = _pcm16_to_wav_bytes(final_pcm, sample_rate=sample_rate)
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": 'attachment; filename="prosodic_tts.wav"',
                    "X-Prosodic-TTFS-Ms": str(int(ttfs * 1000)),
                    "X-Prosodic-Chunks": str(len(chunks)),
                },
            )

        if provider_name == "vibevoice" and not vibevoice_provider:
            raise HTTPException(status_code=503, detail="VibeVoice provider not configured")
        if provider_name == "ultimate_tts" and not ultimate_tts_provider:
            raise HTTPException(status_code=503, detail="Ultimate-TTS provider not configured")
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available for prosodic synthesis")

    except (VibeVoiceBusyError, VibeVoiceNoAudioError, UltimateTTSError) as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="502").inc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status=str(exc.status_code)).inc()
        raise
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/synthesize/prosodic", status="500").inc()
        logger.exception("Prosodic TTS synthesis failed")
        raise HTTPException(status_code=500, detail="Prosodic TTS synthesis failed") from None


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
        raise HTTPException(status_code=500, detail="STT recognition failed") from None


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
                logger.error(
                    "Supabase persona query failed: status=%s body=%s",
                    resp.status_code, resp.text[:200] if resp.text else "empty"
                )
                REQUESTS_TOTAL.labels(endpoint="/v1/voice/personas", status=str(resp.status_code)).inc()
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch personas from database (status {resp.status_code})"
                )
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


# ============================================================================
# Voice Cloning Endpoints
# ============================================================================

@app.post("/v1/voice/clone/register", response_model=VoiceCloneRegisterResponse, dependencies=[Depends(verify_api_key)])
async def register_voice_sample(
    persona_slug: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Register a voice sample for cloning.

    Uploads a voice sample and queues it for RVC training.
    The sample should be 10-30 seconds of clear speech.

    Args:
        persona_slug: Voice persona slug to attach the sample to
        audio: Audio file (WAV or MP3 format, 10-30 seconds recommended)

    Returns:
        Registration confirmation with persona_id and status
    """
    import time
    start_time = time.time()

    try:
        # Read audio data
        audio_data = await audio.read()
        audio_format = audio.filename.split(".")[-1].lower() if audio.filename else "wav"

        if audio_format not in {"wav", "mp3"}:
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/register", status="400").inc()
            raise HTTPException(status_code=400, detail="Audio format must be WAV or MP3")

        # Validate audio size (max 10MB)
        if len(audio_data) > 10 * 1024 * 1024:
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/register", status="400").inc()
            raise HTTPException(status_code=400, detail="Audio file too large (max 10MB)")

        # Register sample
        result = await cloning_provider.register_voice_sample(
            persona_slug=persona_slug,
            sample_audio_data=audio_data,
            sample_format=audio_format,
        )

        duration = time.time() - start_time
        logger.info("Voice sample registered for %s in %.2fs", persona_slug, duration)
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/register", status="200").inc()

        return VoiceCloneRegisterResponse(**result)

    except ValueError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/register", status="400").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/register", status="500").inc()
        logger.exception("Voice sample registration failed")
        raise HTTPException(status_code=500, detail="Failed to register voice sample") from None


@app.post("/v1/voice/clone/train", dependencies=[Depends(verify_api_key)])
async def start_voice_training(request: VoiceCloneTrainRequest):
    """
    Start RVC training for a registered voice sample.

    Triggers the GPU training job for the registered voice sample.
    Training typically takes 10-30 minutes depending on GPU availability.

    Args:
        request: Training request with persona_id

    Returns:
        Training job confirmation
    """
    try:
        result = await cloning_provider.start_training(request.persona_id)
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/train", status="200").inc()
        return result

    except ValueError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/train", status="400").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/train", status="500").inc()
        logger.exception("Voice training start failed")
        raise HTTPException(status_code=500, detail="Failed to start voice training") from None


@app.get("/v1/voice/clone/status/{persona_id}", response_model=VoiceCloneStatusResponse, dependencies=[Depends(verify_api_key)])
async def get_voice_training_status(persona_id: str):
    """
    Get training status for a voice clone.

    Returns the current training status, progress, and model URIs.

    Args:
        persona_id: Voice persona UUID

    Returns:
        Training status with progress and model URIs (if completed)
    """
    try:
        result = await cloning_provider.get_training_status(persona_id)
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/status", status="200").inc()
        return VoiceCloneStatusResponse(**result)

    except ValueError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/status", status="404").inc()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/status", status="500").inc()
        logger.exception("Failed to get training status")
        raise HTTPException(status_code=500, detail="Failed to get training status")


@app.get("/v1/voice/clone/jobs", dependencies=[Depends(verify_api_key)])
async def list_voice_training_jobs(status: Optional[str] = None):
    """
    List all voice cloning training jobs.

    Args:
        status: Optional filter by status (pending, training, completed, failed)

    Returns:
        List of training job summaries
    """
    try:
        if status and status not in {"pending", "training", "completed", "failed"}:
            REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/jobs", status="400").inc()
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be one of: pending, training, completed, failed"
            )

        jobs = await cloning_provider.list_training_jobs(status=status)
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/jobs", status="200").inc()
        return {"jobs": jobs, "count": len(jobs)}

    except HTTPException:
        raise
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/jobs", status="500").inc()
        logger.exception("Failed to list training jobs")
        raise HTTPException(status_code=500, detail="Failed to list training jobs") from None


@app.post("/v1/voice/clone/synthesize", dependencies=[Depends(verify_api_key)])
async def synthesize_cloned_voice(request: VoiceCloneSynthesizeRequest):
    """
    Synthesize speech using a trained cloned voice.

    Requires the voice training to be completed before synthesis.

    Args:
        request: Synthesis request with text and persona_id

    Returns:
        Audio file (WAV or PCM format)
    """
    import time
    start_time = time.time()

    try:
        audio_data = await cloning_provider.synthesize_cloned(
            text=request.text,
            persona_id=request.persona_id,
        )

        duration = time.time() - start_time
        logger.info("Cloned voice synthesis completed in %.2fs", duration)
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/synthesize", status="200").inc()

        output_format = request.output_format.lower()
        if output_format == "pcm":
            return Response(content=audio_data, media_type="application/octet-stream")
        else:
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="cloned_voice.wav"'},
            )

    except ValueError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/synthesize", status="400").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/synthesize", status="501").inc()
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception:
        REQUESTS_TOTAL.labels(endpoint="/v1/voice/clone/synthesize", status="500").inc()
        logger.exception("Cloned voice synthesis failed")
        raise HTTPException(status_code=500, detail="Cloned voice synthesis failed")


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
    finally:
        await websocket.close()


# Full duplex voice agent WebSocket endpoint (pipecat)
@app.websocket("/v1/voice/stream/duplex")
async def websocket_duplex(websocket: WebSocket, persona: Optional[str] = None):
    """
    Full duplex voice conversation WebSocket endpoint.

    Uses pipecat pipeline: VAD → STT → LLM → TTS

    Protocol:
        Client → Server:
            - Binary: Audio frames (PCM16, 24kHz, mono)
            - JSON: {"type": "start", "voice": "default", "persona": "assistant"}
            - JSON: {"type": "text", "text": "direct input"} (skip STT)
            - JSON: {"type": "interrupt"} (cancel current generation)
            - JSON: {"type": "stop"} (end conversation)

        Server → Client:
            - Binary: TTS audio frames (PCM16, 24kHz, mono)
            - JSON: {"type": "transcription", "text": "user speech"}
            - JSON: {"type": "llm_text", "text": "assistant response"}
            - JSON: {"type": "response_start"}
            - JSON: {"type": "response_end"}
            - JSON: {"type": "error", "message": "..."}

    Query Parameters:
        persona: Optional persona name (determines system prompt and voice)

    Requires:
        - PIPECAT_ENABLED=true in environment
        - pipecat-ai[silero] installed
    """
    if not PIPECAT_CONFIG.enabled:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "Pipecat not enabled. Set PIPECAT_ENABLED=true in environment."
        })
        await websocket.close()
        return

    if not PIPECAT_AVAILABLE:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "Pipecat not installed. Install with: pip install pipecat-ai[silero]"
        })
        await websocket.close()
        return

    await websocket.accept()

    try:
        # Configure transport
        transport_params = FluteFastAPIWebsocketParams(
            sample_rate=PIPECAT_CONFIG.sample_rate,
            vad_enabled=True,
            vad_start_threshold=PIPECAT_CONFIG.vad_threshold,
        )
        transport = FluteFastAPIWebsocketTransport(websocket, transport_params)

        # Configure voice agent
        voice_config = VoiceAgentConfig(
            persona=persona or "assistant",
            voice=PIPECAT_CONFIG.default_voice,
            llm_model=PIPECAT_CONFIG.default_llm_model,
            max_tokens=PIPECAT_CONFIG.default_max_tokens,
            temperature=0.7,
            vad_threshold=PIPECAT_CONFIG.vad_threshold,
            enable_interruption=True,
        )

        # Build pipeline
        pipeline = await build_voice_agent_pipeline(
            transport=transport,
            config=voice_config,
            vibevoice_provider=vibevoice_provider,
            whisper_provider=whisper_provider,
            tensorzero_url=PIPECAT_CONFIG.tensorzero_url,
        )

        # Send ready status
        await websocket.send_json({
            "type": "status",
            "status": "ready",
            "config": {
                "persona": voice_config.persona,
                "voice": voice_config.voice,
                "model": voice_config.llm_model,
                "sample_rate": transport_params.sample_rate,
            }
        })

        # Run pipeline (this blocks until client disconnects or sends stop)
        try:
            from pipecat.pipeline.runner import PipelineRunner
            runner = PipelineRunner()
            await runner.run(pipeline)
        except ImportError:
            # Fallback: simple frame loop if PipelineRunner not available
            await transport.start()
            async for frame in transport.input():
                # Process frames through pipeline stages
                pass
            await transport.stop()

    except Exception as e:
        logger.exception("Duplex WebSocket error: %s", e)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Pipeline error: {str(e)}"
            })
        except Exception as close_err:
            logger.error("Failed to send error to WebSocket: %s", close_err)
    finally:
        try:
            await websocket.close()
        except Exception as close_err:
            logger.warning("Failed to close WebSocket: %s", close_err)


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
