"""Voicebox TTS/STT provider integration.

Voicebox is a self-hosted voice production service (jamiepine/voicebox) that
runs as a Pinokio app on the host. It exposes a profile-based synthesis API
where each "profile" wraps a voice persona with optional cloning samples,
default engine, and effects chain.

Endpoints used by this provider:
    POST /generate/stream   — synchronous WAV streaming (audio/wav response)
    POST /transcribe        — multipart STT (returns text + duration)
    GET  /profiles          — list voice profiles
    GET  /health            — service + model status

Mapping notes:
    - `voice` parameter on the VoiceProvider ABC is interpreted as a Voicebox
      `profile_id` (UUID string). If omitted, the provider auto-selects the
      first profile from /profiles and caches the choice.
    - `engine` kwarg defaults to "qwen" (matches Voicebox default) but can be
      overridden per call.
    - `model_size` kwarg defaults to "1.7B" (Qwen3-TTS-12Hz-1.7B-Base).

First-run setup:
    Voicebox ships with 0 profiles. Until at least one profile exists,
    `/generate/stream` returns 404 "Profile not found" and this provider
    raises `VoiceboxNoProfileError`. `health_check()` returns True in this
    state because the service itself is up — the no-profile condition only
    surfaces on synthesis attempts.

    Profile creation is fully API-driven (no UI required). The simplest
    path is a **preset profile** using a built-in voice from Kokoro,
    Chatterbox, Qwen, etc. — no audio sample upload needed:

        POST /profiles
        {
          "name": "PMOVES Default",
          "voice_type": "preset",
          "language": "en",
          "preset_engine": "kokoro",
          "preset_voice_id": "af_alloy",       # discover via GET /profiles/presets/kokoro
          "default_engine": "kokoro"
        }

    PMOVES exposes this as a Make target that auto-discovers preset voices:

        make -C pmoves voicebox-profile-create
        # Override engine/name with env vars:
        VOICEBOX_PROFILE_ENGINE=qwen_custom_voice make -C pmoves voicebox-profile-create

    For voice cloning, use `voice_type=cloned` and then
    `POST /profiles/{id}/samples` with a reference audio file (2-10s).
    For text-described voices, use `voice_type=designed` with a
    `design_prompt`. Both paths are documented in
    `pmoves/docs/architecture/voice-chain-end-to-end.md`.
"""

import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class VoiceboxError(RuntimeError):
    """Base exception for Voicebox provider failures."""


class VoiceboxNoProfileError(VoiceboxError):
    """Raised when synthesis is attempted but Voicebox has no voice profiles.

    This is the canonical "first-run not complete" signal — the service is
    reachable but the user has not yet created a voice profile via the
    Voicebox UI. Distinct from `VoiceboxBusyError` (transient) and
    connection failures (caught by health_check).
    """


class VoiceboxBusyError(VoiceboxError):
    """Raised when Voicebox reports it cannot accept a synthesis request right now."""


class VoiceboxProvider(VoiceProvider):
    """Voicebox synthesis + transcription provider.

    Talks to a Voicebox HTTP server (default port 17493 via Pinokio). Uses
    the synchronous /generate/stream endpoint for synthesis (not the async
    /generate which queues a background task).
    """

    DEFAULT_ENGINE = "qwen"
    DEFAULT_MODEL_SIZE = "1.7B"

    def __init__(self, base_url: str = "http://host.docker.internal:17493"):
        """Initialize Voicebox provider.

        Args:
            base_url: Voicebox server base URL. Defaults to host.docker.internal:17493
                so the gateway can reach a Pinokio-managed Voicebox running on the host.
        """
        super().__init__(base_url.rstrip("/"))
        self.generate_endpoint = f"{self.base_url}/generate/stream"
        self.transcribe_endpoint = f"{self.base_url}/transcribe"
        self.profiles_endpoint = f"{self.base_url}/profiles"
        self.health_endpoint = f"{self.base_url}/health"
        self._timeout = float(os.getenv("VOICEBOX_TIMEOUT_SEC", "120"))
        self._cached_profile_id: Optional[str] = None

    async def _resolve_profile_id(self, voice: Optional[str]) -> str:
        """Resolve the profile_id for a synthesis call.

        If `voice` is explicitly provided, use it as the profile_id.
        Otherwise auto-select the first available profile from /profiles
        (cached after first lookup).

        Raises:
            VoiceboxNoProfileError: If no profiles are available on the server.
        """
        if voice:
            return voice
        if self._cached_profile_id:
            return self._cached_profile_id

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.profiles_endpoint)
                response.raise_for_status()
                profiles = response.json()
        except httpx.HTTPError as exc:
            raise VoiceboxError(f"Failed to fetch Voicebox profiles: {exc}") from exc

        if not profiles:
            raise VoiceboxNoProfileError(
                "Voicebox has no voice profiles. Create a profile via the Voicebox UI "
                "(http://localhost:17493) and download Qwen3-TTS 1.7B before synthesizing."
            )

        first = profiles[0]
        profile_id = first.get("id") if isinstance(first, dict) else None
        if not profile_id:
            raise VoiceboxError(f"Unexpected /profiles response shape: {first!r}")

        self._cached_profile_id = profile_id
        logger.info("Voicebox auto-selected profile_id=%s (%s)", profile_id, first.get("name", "?"))
        return profile_id

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """Synthesize speech from text via /generate/stream (batch mode).

        Args:
            text: Text to synthesize.
            voice: Voicebox profile_id. If None, auto-selects the first profile.
            **kwargs: engine, model_size, language, seed, instruct, normalize,
                max_chunk_chars, crossfade_ms

        Returns:
            Complete WAV audio as bytes.
        """
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text, voice, **kwargs):
            chunks.append(chunk)
        audio = b"".join(chunks)
        if not audio:
            raise VoiceboxError("Voicebox produced no audio bytes")
        return audio

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech as WAV chunks via /generate/stream.

        Args:
            text: Text to synthesize.
            voice: Voicebox profile_id. If None, auto-selects the first profile.
            **kwargs: engine, model_size, language, seed, instruct, normalize,
                max_chunk_chars, crossfade_ms

        Yields:
            WAV audio chunks (full WAV file split across chunks).
        """
        profile_id = await self._resolve_profile_id(voice)

        payload: Dict[str, Any] = {
            "profile_id": profile_id,
            "text": text,
            "engine": kwargs.get("engine", self.DEFAULT_ENGINE),
            "model_size": kwargs.get("model_size", self.DEFAULT_MODEL_SIZE),
            "language": kwargs.get("language"),
            "seed": kwargs.get("seed"),
            "instruct": kwargs.get("instruct"),
            "normalize": kwargs.get("normalize", True),
            "max_chunk_chars": kwargs.get("max_chunk_chars"),
            "crossfade_ms": kwargs.get("crossfade_ms"),
        }
        # Drop None values so Voicebox uses its own defaults
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", self.generate_endpoint, json=payload) as response:
                    if response.status_code == 404:
                        raise VoiceboxNoProfileError(
                            f"Voicebox returned 404 for profile_id={profile_id} — "
                            "profile may have been deleted between resolve and synthesize."
                        )
                    if response.status_code == 503:
                        raise VoiceboxBusyError(f"Voicebox busy: {response.status_code}")
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise VoiceboxError(
                            f"Voicebox /generate/stream failed: {response.status_code} {body[:200]!r}"
                        )
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if chunk:
                            yield chunk
        except httpx.TimeoutException as exc:
            logger.error("Voicebox synthesis timed out after %ss", self._timeout)
            raise VoiceboxError(f"Voicebox synthesis timed out: {exc}") from exc
        except (VoiceboxError, VoiceboxBusyError, VoiceboxNoProfileError):
            raise
        except httpx.HTTPError as exc:
            logger.error("Voicebox synthesis HTTP error: %s", exc)
            raise VoiceboxError(f"Voicebox HTTP error: {exc}") from exc

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Transcribe audio via /transcribe (multipart upload).

        Args:
            audio_data: Audio file bytes (WAV preferred).
            language: ISO language code, or None for auto-detect.
            **kwargs: model (whisper model size override)

        Returns:
            Dictionary with 'text', 'duration', 'language'.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                files = {"file": ("audio.wav", audio_data, "audio/wav")}
                data: Dict[str, str] = {}
                if language:
                    data["language"] = language
                if "model" in kwargs and kwargs["model"]:
                    data["model"] = kwargs["model"]

                response = await client.post(
                    self.transcribe_endpoint,
                    files=files,
                    data=data,
                )

                if response.status_code == 202:
                    # Whisper model is downloading — surface as a transient error
                    detail = response.json().get("detail", {}) if response.text else {}
                    raise VoiceboxBusyError(
                        f"Voicebox is downloading whisper model: {detail.get('message', '')}"
                    )

                response.raise_for_status()
                result = response.json()
                return {
                    "text": (result.get("text") or "").strip(),
                    "duration": result.get("duration", 0.0),
                    "language": language or "auto",
                }
        except VoiceboxBusyError:
            raise
        except httpx.HTTPError as exc:
            logger.error("Voicebox transcription failed: %s", exc)
            raise VoiceboxError(f"Voicebox transcription error: {exc}") from exc

    async def health_check(self) -> bool:
        """Check if Voicebox service is reachable.

        Returns True if the /health endpoint responds with 200, regardless of
        whether a model is loaded or any profiles exist. Use `health_status()`
        for richer diagnostics that distinguish "down" from "up but unconfigured".
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_endpoint)
                return response.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Voicebox health check failed: %s", exc)
            return False

    async def health_status(self) -> Dict[str, Any]:
        """Return rich health diagnostics for Voicebox.

        Combines /health and /profiles into a single status payload that
        distinguishes 'service down', 'service up but no model', and
        'service up but no profiles'.

        Returns:
            Dictionary with keys: reachable, model_loaded, model_downloaded,
            gpu_available, gpu_type, profiles_count, ready_for_synthesis.
        """
        status: Dict[str, Any] = {
            "reachable": False,
            "model_loaded": False,
            "model_downloaded": None,
            "gpu_available": False,
            "gpu_type": None,
            "profiles_count": 0,
            "ready_for_synthesis": False,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health_resp = await client.get(self.health_endpoint)
                if health_resp.status_code == 200:
                    health = health_resp.json()
                    status.update(
                        {
                            "reachable": True,
                            "model_loaded": bool(health.get("model_loaded")),
                            "model_downloaded": health.get("model_downloaded"),
                            "gpu_available": bool(health.get("gpu_available")),
                            "gpu_type": health.get("gpu_type"),
                        }
                    )
                profiles_resp = await client.get(self.profiles_endpoint)
                if profiles_resp.status_code == 200:
                    profiles = profiles_resp.json() or []
                    status["profiles_count"] = len(profiles)
        except httpx.HTTPError as exc:
            logger.debug("Voicebox health_status failed: %s", exc)

        status["ready_for_synthesis"] = (
            status["reachable"] and status["profiles_count"] > 0
        )
        return status
