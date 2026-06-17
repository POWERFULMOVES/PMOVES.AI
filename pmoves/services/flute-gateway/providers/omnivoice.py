"""OmniVoice TTS provider integration.

OmniVoice is the production voice server (``omnivoice_server.py`` in
``creator-operator``) that holds k2-fsa/OmniVoice in VRAM and serves
``model.generate()`` directly over a small FastAPI surface. It is the
load-once, steady-state counterpart to the gradio try-it demo.

Endpoints used by this provider:
    POST /synthesize   — synchronous WAV synthesis (audio/wav FileResponse)
    GET  /healthz       — service + model status

Server contract (``omnivoice_server.py``):
    POST /synthesize JSON body:
        {text, instruct?, ref_audio?, ref_text?, duration?, speed?}
    When ``OMNIVOICE_TOKEN`` is set server-side, the request must carry an
    ``X-OmniVoice-Token`` header with the matching secret; otherwise the
    server returns 401. The response is a complete WAV (24 kHz).

Mapping notes:
    - ``voice`` (VoiceProvider ABC) maps to the server's ``ref_audio`` — an
      opaque catalog id resolved under ``OMNIVOICE_REFERENCE_VOICE_DIR`` on
      the server (never a raw path). If omitted, the model uses its default
      voice.
    - The gateway's voice-design attributes map to the server's ``instruct``
      kwarg. Accepted via either ``instruct`` or ``voice_design`` kwarg.
    - ``ref_text``, ``duration``, ``speed`` pass through when provided.

Configuration:
    OMNIVOICE_URL     base URL (default http://127.0.0.1:8002)
    OMNIVOICE_TOKEN   if set, sent as the X-OmniVoice-Token header
    OMNIVOICE_TIMEOUT_SEC  synthesis timeout (default 120)
"""

import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class OmniVoiceError(RuntimeError):
    """Base exception for OmniVoice provider failures."""


class OmniVoiceBusyError(OmniVoiceError):
    """Raised when OmniVoice reports it cannot synthesize right now.

    The production server returns 503 while the model is still loading into
    VRAM. Distinct from a hard failure so callers can retry.
    """


class OmniVoiceProvider(VoiceProvider):
    """OmniVoice synthesis provider.

    Talks to an OmniVoice production server (default 127.0.0.1:8002). Uses the
    synchronous /synthesize endpoint which returns a complete WAV. Sends the
    X-OmniVoice-Token header when OMNIVOICE_TOKEN is set in the environment.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8002"):
        """Initialize OmniVoice provider.

        Args:
            base_url: OmniVoice server base URL. Defaults to 127.0.0.1:8002,
                the production server's loopback bind.
        """
        super().__init__(base_url.rstrip("/"))
        self.synthesize_endpoint = f"{self.base_url}/synthesize"
        self.health_endpoint = f"{self.base_url}/healthz"
        self._timeout = float(os.getenv("OMNIVOICE_TIMEOUT_SEC", "120"))
        self._token = os.getenv("OMNIVOICE_TOKEN") or None

    def _auth_headers(self) -> Dict[str, str]:
        """Build the auth header set, including the shared-secret token when set."""
        headers: Dict[str, str] = {}
        if self._token:
            headers["X-OmniVoice-Token"] = self._token
        return headers

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """Synthesize speech from text via /synthesize (batch mode).

        Args:
            text: Text to synthesize.
            voice: OmniVoice ref_audio catalog id (voice clone). If None, the
                model uses its default voice.
            **kwargs: instruct / voice_design (voice-design attributes mapped to
                the server's ``instruct``), ref_text, duration, speed.

        Returns:
            Complete WAV audio as bytes.

        Raises:
            OmniVoiceBusyError: If the server reports the model is not loaded (503).
            OmniVoiceError: On any other non-2xx response or transport failure.
        """
        # Map the gateway voice-design attribute onto the server's `instruct`.
        instruct = kwargs.get("instruct")
        if instruct is None:
            instruct = kwargs.get("voice_design")

        payload: Dict[str, Any] = {
            "text": text,
            "instruct": instruct,
            "ref_audio": voice,
            "ref_text": kwargs.get("ref_text"),
            "duration": kwargs.get("duration"),
            "speed": kwargs.get("speed"),
        }
        # Drop None values so the server applies its documented defaults.
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self.synthesize_endpoint,
                    json=payload,
                    headers=self._auth_headers(),
                )
                if response.status_code == 503:
                    raise OmniVoiceBusyError(
                        f"OmniVoice busy / model not loaded: {response.status_code}"
                    )
                if response.status_code >= 400:
                    body = response.content
                    raise OmniVoiceError(
                        f"OmniVoice /synthesize failed: {response.status_code} {body[:200]!r}"
                    )
                audio = response.content
        except OmniVoiceError:
            raise
        except httpx.TimeoutException as exc:
            logger.error("OmniVoice synthesis timed out after %ss", self._timeout)
            raise OmniVoiceError(f"OmniVoice synthesis timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("OmniVoice synthesis HTTP error: %s", exc)
            raise OmniVoiceError(f"OmniVoice HTTP error: {exc}") from exc

        if not audio:
            raise OmniVoiceError("OmniVoice produced no audio bytes")
        return audio

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Yield the full WAV as a single chunk.

        The OmniVoice server synthesizes the whole utterance and returns it as
        one WAV FileResponse (no chunked transfer), so this wraps ``synthesize``
        to satisfy the VoiceProvider ABC.
        """
        audio = await self.synthesize(text, voice, **kwargs)
        yield audio

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """OmniVoice is a TTS-only server — STT is not supported."""
        raise NotImplementedError("OmniVoice provider does not support speech recognition")

    async def health_check(self) -> bool:
        """Check if the OmniVoice service is reachable.

        Returns True if /healthz responds with 200, regardless of whether the
        model has finished loading (the server reports ``status: loading``
        until VRAM load completes).
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_endpoint)
                return response.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("OmniVoice health check failed: %s", exc)
            return False
