"""Ultimate-TTS-Studio provider integration via Gradio API."""

import io
import json
import logging
import os
import time
import wave
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger(__name__)


class UltimateTTSError(RuntimeError):
    """Raised when Ultimate-TTS-Studio returns an error."""


class UltimateTTSProvider(VoiceProvider):
    """Ultimate-TTS-Studio provider via Gradio API.

    Supports multiple TTS engines:
      - kitten_tts (KittenTTS) - Ultra-lightweight, fast
      - f5_tts (F5-TTS) - High quality
      - kokoro (Kokoro TTS) - Multilingual
      - indextts2 (IndexTTS2) - Modular system

    Audio format: WAV, 24kHz sample rate (varies by engine).
    """

    # Default voices per engine
    DEFAULT_VOICES = {
        "kitten_tts": "expr-voice-2-f",
        "f5_tts": "default",
        "kokoro": "af_bella",
        "indextts2": "default",
    }

    # Available KittenTTS voices
    KITTEN_VOICES = [
        "expr-voice-2-m", "expr-voice-2-f",
        "expr-voice-3-m", "expr-voice-3-f",
        "expr-voice-4-m", "expr-voice-4-f",
        "expr-voice-5-m", "expr-voice-5-f",
    ]

    def __init__(self, base_url: str = "http://localhost:7861"):
        """Initialize Ultimate-TTS provider.

        Args:
            base_url: Gradio server URL (e.g., 'http://localhost:7861')
        """
        super().__init__(base_url)
        self.gradio_api_url = f"{base_url}/gradio_api"
        self._health_last_log_ts: float = 0.0
        self._health_log_interval_sec: float = float(
            os.getenv("ULTIMATE_TTS_HEALTH_LOG_INTERVAL_SEC", "60")
        )
        self._default_engine = os.getenv("ULTIMATE_TTS_DEFAULT_ENGINE", "kitten_tts")
        self._timeout = float(os.getenv("ULTIMATE_TTS_TIMEOUT_SEC", "120"))

    async def _load_model(self, client: httpx.AsyncClient, engine: str) -> bool:
        """Load a TTS model if not already loaded.

        Args:
            client: HTTP client
            engine: Engine name (kitten_tts, f5_tts, etc.)

        Returns:
            True if model is ready
        """
        endpoint_map = {
            "kitten_tts": "/handle_load_kitten",
            "f5_tts": "/handle_f5_load",
            "kokoro": "/handle_load_kokoro",
            "indextts2": "/handle_load_indextts2",
        }
        endpoint = endpoint_map.get(engine)
        if not endpoint:
            logger.warning("Unknown engine %s, skipping model load", engine)
            return True

        try:
            # Call the load endpoint
            resp = await client.post(
                f"{self.gradio_api_url}/call{endpoint}",
                json={"data": []},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning("Model load call returned %s", resp.status_code)
                return False

            result = resp.json()
            event_id = result.get("event_id")
            if not event_id:
                return False

            # Get result
            result_resp = await client.get(
                f"{self.gradio_api_url}/call{endpoint}/{event_id}",
                timeout=60.0,
            )
            # Check for success in SSE response
            for line in result_resp.iter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:])
                    if isinstance(data, list) and len(data) > 0:
                        status = str(data[0]) if data[0] else ""
                        if "✅" in status or "Loaded" in status:
                            logger.info("Ultimate-TTS %s model loaded", engine)
                            return True
            return True  # Assume loaded if no error
        except Exception as exc:
            logger.warning("Failed to load %s model: %s", engine, exc)
            return False

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Synthesize speech from text (batch mode).

        Args:
            text: Text to synthesize
            voice: Voice preset (e.g., 'expr-voice-2-f' for KittenTTS)
            **kwargs: engine (kitten_tts, f5_tts, kokoro, indextts2)

        Returns:
            WAV audio as bytes
        """
        engine = kwargs.get("engine", self._default_engine)
        voice = voice or self.DEFAULT_VOICES.get(engine, "default")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Ensure model is loaded
            await self._load_model(client, engine)

            # Build payload for generate_unified_tts
            # Signature: (text, tab, voice, ref_audio, emotion_desc, style_mode, ...)
            payload = {
                "data": [
                    text,           # text
                    f"{engine}_tab" if engine != "kitten_tts" else "kitten_tab",
                    voice,          # voice
                    "",             # ref_audio (empty for non-cloning)
                    "",             # emotion description
                    "",             # style mode
                    "",             # extra param
                    None,           # reference file
                ]
            }

            try:
                # Start generation
                resp = await client.post(
                    f"{self.gradio_api_url}/call/generate_unified_tts",
                    json=payload,
                    timeout=30.0,
                )
                if resp.status_code != 200:
                    raise UltimateTTSError(f"API call failed: {resp.status_code}")

                result = resp.json()
                event_id = result.get("event_id")
                if not event_id:
                    raise UltimateTTSError("No event_id in response")

                # Poll for result (SSE stream)
                result_resp = await client.get(
                    f"{self.gradio_api_url}/call/generate_unified_tts/{event_id}",
                    timeout=self._timeout,
                )

                audio_url = None
                for line in result_resp.iter_lines():
                    if line.startswith("data:"):
                        try:
                            data = json.loads(line[5:])
                            if isinstance(data, list) and len(data) >= 2:
                                # First element is audio info
                                audio_info = data[0]
                                status = data[1] if len(data) > 1 else ""

                                if isinstance(status, str) and "❌" in status:
                                    raise UltimateTTSError(status)

                                if isinstance(audio_info, dict) and "url" in audio_info:
                                    audio_url = audio_info["url"]
                                    break
                        except json.JSONDecodeError:
                            continue

                if not audio_url:
                    raise UltimateTTSError("No audio URL in response")

                # Download the audio file
                audio_resp = await client.get(audio_url, timeout=30.0)
                if audio_resp.status_code != 200:
                    raise UltimateTTSError(f"Failed to download audio: {audio_resp.status_code}")

                wav_bytes = audio_resp.content
                logger.info(
                    "Ultimate-TTS synthesized %d bytes (engine=%s, voice=%s)",
                    len(wav_bytes), engine, voice
                )
                return wav_bytes

            except httpx.TimeoutException as exc:
                raise UltimateTTSError(f"Timeout during synthesis: {exc}") from exc
            except httpx.HTTPError as exc:
                raise UltimateTTSError(f"HTTP error: {exc}") from exc

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech chunks.

        Note: Ultimate-TTS-Studio doesn't support true streaming,
        so this falls back to batch mode and yields the full audio.
        """
        audio = await self.synthesize(text, voice, **kwargs)
        # Convert WAV to PCM16 for streaming compatibility
        try:
            with io.BytesIO(audio) as buf:
                with wave.open(buf, "rb") as wf:
                    pcm_data = wf.readframes(wf.getnframes())
                    yield pcm_data
        except wave.Error:
            # If not a valid WAV, yield as-is
            yield audio

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Ultimate-TTS is TTS-only, does not support STT."""
        raise NotImplementedError("Ultimate-TTS does not support speech recognition")

    async def get_engines(self) -> Dict[str, Any]:
        """Get available TTS engines and their status."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.gradio_api_url}/info")
                if resp.status_code == 200:
                    info = resp.json()
                    endpoints = info.get("named_endpoints", {})
                    return {
                        "kitten_tts": "/handle_load_kitten" in endpoints,
                        "f5_tts": "/handle_f5_load" in endpoints,
                        "kokoro": "/handle_load_kokoro" in endpoints,
                        "indextts2": "/handle_load_indextts2" in endpoints,
                    }
        except Exception as exc:
            logger.warning("Failed to get Ultimate-TTS engines: %s", exc)
        return {}

    async def health_check(self) -> bool:
        """Check if Ultimate-TTS-Studio is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Gradio API info endpoint
                resp = await client.get(f"{self.gradio_api_url}/info")
                return resp.status_code == 200
        except Exception as exc:
            now = time.monotonic()
            if now - self._health_last_log_ts >= self._health_log_interval_sec:
                self._health_last_log_ts = now
                logger.warning(
                    "Ultimate-TTS health check failed (%s). Is the studio running? "
                    "Expected Gradio API at %s",
                    exc,
                    self.gradio_api_url,
                )
            else:
                logger.debug("Ultimate-TTS health check failed: %s", exc)
            return False
