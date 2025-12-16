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

    # Engine name mapping (internal -> API)
    ENGINE_NAMES = {
        "kitten_tts": "KittenTTS",
        "kokoro": "Kokoro TTS",
        "f5_tts": "F5-TTS",
        "indextts2": "IndexTTS2",
        "fish": "Fish Speech",
        "chatterbox": "ChatterboxTTS",
        "voxcpm": "VoxCPM",
    }

    # Default voices per engine
    DEFAULT_VOICES = {
        "kitten_tts": "expr-voice-2-f",
        "kokoro": "af_bella",
        "f5_tts": None,
        "indextts2": None,
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

    def _build_params(
        self,
        text: str,
        engine: str,
        voice: Optional[str] = None
    ) -> list:
        """Build the full 92-parameter list for generate_unified_tts."""
        api_engine = self.ENGINE_NAMES.get(engine, engine)

        # Total 92 parameters
        data: list = [None] * 92

        # Core params
        data[0] = text          # text_input
        data[1] = api_engine    # tts_engine
        data[2] = "wav"         # audio_format

        # Chatterbox params (3-8)
        data[4] = 0.5    # exaggeration
        data[5] = 0.8    # temperature
        data[6] = 0.5    # cfg_weight
        data[7] = 300    # chunk_size
        data[8] = 0      # seed

        # Chatterbox MTL params (9-18)
        data[10] = "en"
        data[11] = 0.5
        data[12] = 0.8
        data[13] = 0.5
        data[14] = 2.0
        data[15] = 0.05
        data[16] = 1.0
        data[17] = 300
        data[18] = 0

        # Kokoro (19-20)
        data[19] = voice if engine == "kokoro" else "af_heart"
        data[20] = 1.0

        # Fish (21-27)
        data[22] = ""
        data[23] = 0.8
        data[24] = 0.8
        data[25] = 1.1
        data[26] = 1024

        # IndexTTS (28-30)
        data[29] = 0.8

        # IndexTTS2 (31-50)
        data[32] = "audio_reference"
        data[34] = ""     # indextts2_emotion_description (REQUIRED)
        data[35] = 1.0
        data[43] = 1      # calm
        data[44] = 0.8
        data[45] = 0.9
        data[46] = 50
        data[47] = 1.1
        data[48] = 1500
        data[50] = False

        # F5 (51-56)
        data[53] = 1.0
        data[54] = 0.15
        data[55] = False
        data[56] = 0

        # Higgs (57-66)
        data[58] = ""
        data[59] = "EMPTY"
        data[60] = ""
        data[61] = 1.0
        data[62] = 0.95
        data[63] = 50
        data[64] = 1024
        data[65] = 7
        data[66] = 2

        # KittenTTS voice (67)
        data[67] = voice if engine == "kitten_tts" else "expr-voice-2-f"

        # VoxCPM (68-77)
        data[70] = 2.0
        data[71] = 10
        data[72] = True
        data[73] = True
        data[74] = True
        data[75] = 3
        data[76] = 6.0
        data[77] = -1

        # Audio effects (78-91)
        data[78] = 0      # gain_db
        data[79] = False  # enable_eq
        data[80] = 0
        data[81] = 0
        data[82] = 0
        data[83] = False  # enable_reverb
        data[84] = 0.3
        data[85] = 0.5
        data[86] = 0.3
        data[87] = False  # enable_echo
        data[88] = 0.3
        data[89] = 0.5
        data[90] = False  # enable_pitch
        data[91] = 0

        return data

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
        voice = voice or self.DEFAULT_VOICES.get(engine)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Ensure model is loaded
            await self._load_model(client, engine)

            # Build full parameter list
            data = self._build_params(text, engine, voice)
            payload = {"data": data}

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
                error_msg = None
                for line in result_resp.iter_lines():
                    if line.startswith("data:"):
                        try:
                            data = json.loads(line[5:])
                            if isinstance(data, list) and len(data) >= 2:
                                # First element is audio info
                                audio_info = data[0]
                                status = data[1] if len(data) > 1 else ""

                                if isinstance(status, str) and "❌" in status:
                                    error_msg = status
                                    break

                                if isinstance(audio_info, dict) and "url" in audio_info:
                                    audio_url = audio_info["url"]
                                    break
                        except json.JSONDecodeError:
                            continue

                if error_msg:
                    raise UltimateTTSError(error_msg)

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
