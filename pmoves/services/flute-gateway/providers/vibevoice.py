"""VibeVoice realtime TTS provider integration."""

import logging
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import quote

import httpx
import websockets

from .base import VoiceProvider

logger = logging.getLogger(__name__)


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
        chunks = []
        async for chunk in self.synthesize_stream(text, voice, **kwargs):
            chunks.append(chunk)
        return b"".join(chunks)

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
        voice_preset = voice or "default"
        cfg = kwargs.get("cfg", 1.5)
        steps = kwargs.get("steps", 8)

        # URL encode the text
        encoded_text = quote(text)
        ws_endpoint = f"{self.ws_url}?text={encoded_text}&cfg={cfg}&steps={steps}&voice={voice_preset}"

        try:
            async with websockets.connect(ws_endpoint) as ws:
                async for message in ws:
                    if isinstance(message, bytes):
                        yield message
                    else:
                        # Log text messages (status updates from server)
                        logger.debug("VibeVoice log: %s", message)
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning("VibeVoice connection closed: %s", e)
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
            logger.warning("VibeVoice health check failed: %s", exc)
            return False
