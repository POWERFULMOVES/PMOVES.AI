"""Whisper STT provider integration via ffmpeg-whisper service."""

import logging
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class WhisperProvider(VoiceProvider):
    """Whisper speech-to-text provider (via ffmpeg-whisper service).

    Connects to the existing ffmpeg-whisper service for transcription.
    Supports multiple audio formats via ffmpeg preprocessing.
    """

    def __init__(self, base_url: str = "http://ffmpeg-whisper:8078"):
        """
        Initialize Whisper provider.

        Args:
            base_url: ffmpeg-whisper service URL (default: http://ffmpeg-whisper:8078)
        """
        super().__init__(base_url)
        self.transcribe_endpoint = f"{base_url}/transcribe"
        self.health_endpoint = f"{base_url}/healthz"

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Whisper is STT-only, does not support TTS."""
        raise NotImplementedError("Whisper does not support speech synthesis")

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Whisper is STT-only, does not support TTS."""
        raise NotImplementedError("Whisper does not support speech synthesis")
        # Make this an async generator to satisfy type checker
        if False:
            yield b""

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Recognize speech from audio data using Whisper.

        Args:
            audio_data: Audio file bytes (WAV, MP3, etc.)
            language: Language code for transcription (optional, auto-detect if None)
            **kwargs: model, task parameters

        Returns:
            Dictionary with 'text', 'confidence', 'language'
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"audio": ("audio.wav", audio_data, "audio/wav")}
                data = {}
                if language:
                    data["language"] = language
                if "model" in kwargs:
                    data["model"] = kwargs["model"]

                response = await client.post(
                    self.transcribe_endpoint,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()

                # Extract transcription from ffmpeg-whisper response format
                return {
                    "text": result.get("text", "").strip(),
                    "confidence": result.get("confidence", 0.95),
                    "language": result.get("language", language or "en"),
                    "segments": result.get("segments", []),
                }

        except httpx.TimeoutException:
            logger.error("Whisper recognition timed out")
            raise
        except Exception as exc:
            logger.error("Whisper recognition failed: %s", exc)
            raise

    async def health_check(self) -> bool:
        """Check if Whisper service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_endpoint)
                return response.status_code == 200
        except Exception as exc:
            logger.warning("Whisper health check failed: %s", exc)
            return False
