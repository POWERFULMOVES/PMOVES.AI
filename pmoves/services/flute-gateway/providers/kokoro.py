"""Kokoro CPU TTS provider.

Talks to the standalone `kokoro-tts` HTTP service (services/kokoro-tts, port 8004)
— the CPU-only deploy unit that lets a GPU-less node (a KVM VPS) serve voice.
TTS-only (no STT); `recognize()` raises NotImplementedError.

Endpoint used:
    POST /synthesize  {text, voice?, speed?, lang?} -> audio/wav
    GET  /healthz

`voice` maps to a Kokoro voice preset (e.g. af_heart, am_adam); None -> default.
Auth: if KOKORO_TOKEN is set, it is sent as the X-Kokoro-Token header.
"""

import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class KokoroError(RuntimeError):
    """Kokoro provider failure."""


class KokoroProvider(VoiceProvider):
    """Kokoro CPU TTS synthesis provider (no STT)."""

    DEFAULT_VOICE = "af_heart"

    def __init__(self, base_url: str = "http://host.docker.internal:8004"):
        """Initialize.

        Args:
            base_url: kokoro-tts service base URL. Defaults to host.docker.internal:8004
                so an in-container flute-gateway reaches a host- or sibling-hosted service.
        """
        super().__init__(base_url.rstrip("/"))
        self.synthesize_endpoint = f"{self.base_url}/synthesize"
        self.health_endpoint = f"{self.base_url}/healthz"
        self._timeout = float(os.getenv("KOKORO_TIMEOUT_SEC", "60"))
        self._token = os.getenv("KOKORO_TOKEN", "")

    def _headers(self) -> Dict[str, str]:
        return {"X-Kokoro-Token": self._token} if self._token else {}

    async def synthesize(self, text: str, voice: Optional[str] = None, **kwargs) -> bytes:
        """Synthesize speech from text; returns a complete WAV (PCM16, 24kHz).

        kwargs: speed (float, default 1.0), lang (e.g. 'en-us').
        """
        payload: Dict[str, Any] = {
            "text": text,
            "voice": voice or self.DEFAULT_VOICE,
            "speed": kwargs.get("speed", 1.0),
        }
        if kwargs.get("lang"):
            payload["lang"] = kwargs["lang"]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self.synthesize_endpoint, json=payload, headers=self._headers()
                )
                if resp.status_code == 503:
                    raise KokoroError(f"Kokoro model not ready: {resp.text[:200]!r}")
                if resp.status_code >= 400:
                    raise KokoroError(
                        f"Kokoro /synthesize failed: {resp.status_code} {resp.text[:200]!r}"
                    )
                audio = resp.content
        except httpx.TimeoutException as exc:
            raise KokoroError(f"Kokoro synthesis timed out after {self._timeout}s") from exc
        except httpx.HTTPError as exc:
            raise KokoroError(f"Kokoro HTTP error: {exc}") from exc

        if not audio:
            raise KokoroError("Kokoro produced no audio bytes")
        return audio

    async def synthesize_stream(
        self, text: str, voice: Optional[str] = None, **kwargs
    ) -> AsyncIterator[bytes]:
        """Kokoro is fast and non-streaming — emit the full WAV as one chunk."""
        yield await self.synthesize(text, voice, **kwargs)

    async def recognize(
        self, audio_data: bytes, language: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Kokoro is TTS-only; STT is not supported."""
        raise NotImplementedError(
            "Kokoro is a TTS-only engine; use a Whisper/Voicebox provider for STT."
        )

    async def health_check(self) -> bool:
        """True if the kokoro-tts service /healthz responds 200."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.health_endpoint)
                return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Kokoro health check failed: %s", exc)
            return False
