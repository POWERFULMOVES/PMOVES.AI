"""VibeVoice realtime TTS provider integration."""

import asyncio
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import quote

import httpx
import websockets

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class VibeVoiceNoAudioError(RuntimeError):
    """Raised when VibeVoice closes without producing any audio bytes."""


class VibeVoiceBusyError(VibeVoiceNoAudioError):
    """Raised when VibeVoice reports it's busy before yielding audio."""


class VibeVoiceProvider(VoiceProvider):
    """VibeVoice Realtime TTS provider (Microsoft VibeVoice-Realtime-0.5B).

    Connects to VibeVoice WebSocket server for streaming TTS.
    Audio format: PCM16, 24kHz sample rate.
    """

    def __init__(self, base_url: str = "http://localhost:3000"):
        """
        Initialize VibeVoice provider.

        Args:
            base_url: Base URL (e.g., 'http://localhost:3000' from Pinokio)
        """
        super().__init__(base_url)
        # Convert http:// to ws:// for WebSocket
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/stream"
        self.config_url = f"{base_url}/config"
        self._health_last_log_ts: float = 0.0
        self._health_log_interval_sec: float = float(os.getenv("VIBEVOICE_HEALTH_LOG_INTERVAL_SEC", "60"))

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Synthesize speech from text (batch mode).

        Args:
            text: Text to synthesize
            voice: Voice preset (default: 'default')
            **kwargs: cfg, steps parameters

        Returns:
            Complete audio as PCM16 bytes (24kHz)
        """
        max_attempts = int(os.getenv("VIBEVOICE_SYNTH_MAX_ATTEMPTS", "20"))
        retry_delay_sec = float(os.getenv("VIBEVOICE_SYNTH_RETRY_DELAY_SEC", "0.5"))
        busy_max_wait_sec = float(os.getenv("VIBEVOICE_SYNTH_BUSY_MAX_WAIT_SEC", "30"))

        last_exc: Optional[Exception] = None
        waited_sec = 0.0
        for attempt in range(1, max_attempts + 1):
            try:
                chunks: list[bytes] = []
                async for chunk in self.synthesize_stream(text, voice, **kwargs):
                    chunks.append(chunk)
                audio = b"".join(chunks)
                if not audio:
                    raise VibeVoiceNoAudioError("VibeVoice produced no audio bytes")
                return audio
            except (VibeVoiceBusyError, VibeVoiceNoAudioError) as exc:
                last_exc = exc
                if attempt < max_attempts and isinstance(exc, VibeVoiceBusyError):
                    sleep_for = min(retry_delay_sec * attempt, 2.0)
                    if waited_sec + sleep_for > busy_max_wait_sec:
                        break
                    waited_sec += sleep_for
                    await asyncio.sleep(sleep_for)
                    continue
                raise
        raise last_exc or VibeVoiceNoAudioError("VibeVoice produced no audio bytes")

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech chunks via WebSocket.

        Args:
            text: Text to synthesize
            voice: Voice preset (default: 'default')
            **kwargs: cfg=1.5, steps=8

        Yields:
            Audio chunks (PCM16, 24kHz)
        """
        cfg = kwargs.get("cfg", 1.5)
        steps = kwargs.get("steps", 8)

        # URL encode the text
        encoded_text = quote(text)
        ws_endpoint = f"{self.ws_url}?text={encoded_text}&cfg={cfg}&steps={steps}"
        # `voice` is optional. If omitted, the server should use its default_voice from /config.
        if voice:
            ws_endpoint += f"&voice={quote(voice)}"

        yielded_any = False
        try:
            async with websockets.connect(ws_endpoint) as ws:
                async for message in ws:
                    if isinstance(message, bytes):
                        yielded_any = True
                        yield message
                    else:
                        # Log text messages (status updates from server)
                        logger.debug("VibeVoice log: %s", message)
        except websockets.exceptions.ConnectionClosed as e:
            if not yielded_any:
                # Common transient for overloaded hosts: 1013 "try again later" / "Service busy".
                msg = str(e).lower()
                if getattr(e, "code", None) == 1013 or "service busy" in msg or "try again later" in msg:
                    raise VibeVoiceBusyError(f"VibeVoice busy: {e}") from e
                raise VibeVoiceNoAudioError(f"VibeVoice closed before yielding audio: {e}") from e
            logger.warning("VibeVoice connection closed after audio: %s", e)
        except Exception as exc:
            logger.error("VibeVoice stream failed: %s", exc)
            raise

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """VibeVoice is TTS-only, does not support STT."""
        raise NotImplementedError("VibeVoice does not support speech recognition")

    async def get_config(self) -> Dict[str, Any]:
        """Get VibeVoice server configuration including available voices."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.config_url)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error("Failed to get VibeVoice config: %s", exc)
            return {}

    async def health_check(self) -> bool:
        """Check if VibeVoice service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.config_url)
                return response.status_code == 200
        except Exception as exc:
            now = time.monotonic()
            if now - self._health_last_log_ts >= self._health_log_interval_sec:
                self._health_last_log_ts = now
                logger.warning(
                    "VibeVoice health check failed (%s). Is the realtime server running? "
                    "Expected GET %s (Pinokio/host-run VibeVoice).",
                    exc,
                    self.config_url,
                )
            else:
                logger.debug("VibeVoice health check failed: %s", exc)
            return False
