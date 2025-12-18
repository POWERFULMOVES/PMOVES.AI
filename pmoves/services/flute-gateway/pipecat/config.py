"""Pipecat configuration for flute-gateway.

Environment variables:
    PIPECAT_ENABLED: Enable pipecat voice agent endpoints (default: false)
    PIPECAT_VAD_THRESHOLD: Silero VAD threshold 0-1 (default: 0.5)
    PIPECAT_DEFAULT_TRANSPORT: Default transport type (default: websocket)
    PIPECAT_SAMPLE_RATE: Audio sample rate in Hz (default: 24000)
    PIPECAT_CHANNELS: Audio channels (default: 1)
    WEBRTC_STUN_SERVER: STUN server for WebRTC (default: stun:stun.l.google.com:19302)
    WEBRTC_TURN_SERVER: Optional TURN server for NAT traversal
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipecatConfig:
    """Configuration for pipecat voice agent pipelines."""

    # Feature flag
    enabled: bool = False

    # Audio settings
    sample_rate: int = 24000
    channels: int = 1
    bit_depth: int = 16

    # VAD settings
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 300

    # Transport settings
    default_transport: str = "websocket"
    session_timeout_seconds: int = 300

    # WebRTC settings
    webrtc_stun_server: str = "stun:stun.l.google.com:19302"
    webrtc_turn_server: Optional[str] = None
    webrtc_turn_username: Optional[str] = None
    webrtc_turn_password: Optional[str] = None

    # TensorZero LLM settings
    tensorzero_url: str = "http://localhost:3030"
    default_llm_model: str = "claude-sonnet-4-5"

    # Provider preferences
    default_tts_provider: str = "vibevoice"
    default_stt_provider: str = "whisper"

    # NATS integration
    nats_publish_events: bool = True
    nats_voice_subject_prefix: str = "voice.agent"


def get_pipecat_config() -> PipecatConfig:
    """Load pipecat configuration from environment variables."""
    return PipecatConfig(
        enabled=os.getenv("PIPECAT_ENABLED", "false").lower() == "true",
        sample_rate=int(os.getenv("PIPECAT_SAMPLE_RATE", "24000")),
        channels=int(os.getenv("PIPECAT_CHANNELS", "1")),
        vad_threshold=float(os.getenv("PIPECAT_VAD_THRESHOLD", "0.5")),
        default_transport=os.getenv("PIPECAT_DEFAULT_TRANSPORT", "websocket"),
        session_timeout_seconds=int(os.getenv("PIPECAT_SESSION_TIMEOUT", "300")),
        webrtc_stun_server=os.getenv(
            "WEBRTC_STUN_SERVER", "stun:stun.l.google.com:19302"
        ),
        webrtc_turn_server=os.getenv("WEBRTC_TURN_SERVER"),
        webrtc_turn_username=os.getenv("WEBRTC_TURN_USERNAME"),
        webrtc_turn_password=os.getenv("WEBRTC_TURN_PASSWORD"),
        tensorzero_url=os.getenv("TENSORZERO_URL", "http://localhost:3030"),
        default_llm_model=os.getenv("PIPECAT_DEFAULT_LLM_MODEL", "claude-sonnet-4-5"),
        default_tts_provider=os.getenv("PIPECAT_DEFAULT_TTS", "vibevoice"),
        default_stt_provider=os.getenv("PIPECAT_DEFAULT_STT", "whisper"),
        nats_publish_events=os.getenv("PIPECAT_NATS_EVENTS", "true").lower() == "true",
        nats_voice_subject_prefix=os.getenv(
            "PIPECAT_NATS_PREFIX", "voice.agent"
        ),
    )
