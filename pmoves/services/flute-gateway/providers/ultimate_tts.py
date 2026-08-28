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

    Supports 14 TTS engines:
      - kitten_tts (KittenTTS) - Ultra-lightweight, fast
      - kokoro (Kokoro TTS) - Multilingual ONNX
      - f5_tts (F5-TTS) - High quality voice cloning
      - indextts (IndexTTS) - Index-based synthesis
      - indextts2 (IndexTTS2) - Emotion vector control
      - fish (Fish Speech S1) - Zero-shot cloning
      - fish_s2 (Fish Speech S2 Pro) - 13-language zero-shot
      - chatterbox (ChatterboxTTS) - Expressive narration
      - chatterbox_turbo (Chatterbox Turbo) - Fast multilingual
      - chatterbox_multilingual (Chatterbox Multilingual) - 17-language synthesis
      - voxcpm (VoxCPM) - Voice cloning + transcription
      - higgs (Higgs Audio) - Streaming capable
      - qwen (Qwen Voice Design) - Alibaba multilingual
      - vibevoice (VibeVoice) - Style transfer synthesis

    Audio format: WAV, 24kHz sample rate (varies by engine).
    """

    # Engine name mapping (internal -> API)
    ENGINE_NAMES = {
        "kitten_tts": "KittenTTS",
        "kokoro": "Kokoro TTS",
        "f5_tts": "F5-TTS",
        "indextts2": "IndexTTS2",
        "indextts": "IndexTTS",
        "fish": "Fish Speech S1",
        "fish_s2": "Fish Speech S2 Pro",
        "chatterbox": "ChatterboxTTS",
        "chatterbox_turbo": "Chatterbox Turbo",
        "chatterbox_multilingual": "Chatterbox Multilingual",
        "voxcpm": "VoxCPM",
        "higgs": "Higgs Audio",
        "qwen": "Qwen Voice Design",
        "vibevoice": "VibeVoice",
    }

    # Default voices per engine
    DEFAULT_VOICES = {
        "kitten_tts": "expr-voice-2-f",
        "kokoro": "af_bella",
        "f5_tts": None,
        "indextts2": None,
    }

    # Per-engine synthesis timeout overrides (seconds).
    # Heavier models (large vocab, zero-shot cloning, streaming decode) need
    # more headroom than the global default.
    ENGINE_TIMEOUTS: Dict[str, float] = {
        "fish_s2": 300.0,              # 13-lang zero-shot, 2048 max tokens
        "higgs": 240.0,                # streaming-capable, large context
        "qwen": 240.0,                 # Alibaba multilingual, voice design mode
        "voxcpm": 240.0,               # voice cloning + transcription pipeline
        "chatterbox_multilingual": 180.0,  # 17-language synthesis
        "f5_tts": 180.0,               # high-quality voice cloning
        "indextts2": 180.0,            # emotion vector control
    }

    # Available KittenTTS voices
    KITTEN_VOICES = [
        "expr-voice-2-m", "expr-voice-2-f",
        "expr-voice-3-m", "expr-voice-3-f",
        "expr-voice-4-m", "expr-voice-4-f",
        "expr-voice-5-m", "expr-voice-5-f",
    ]

    def __init__(self, base_url: str = "http://localhost:7860"):
        """Initialize Ultimate-TTS provider.

        Args:
            base_url: Gradio server URL (e.g., 'http://localhost:7860')
        """
        self._schema_params = None  # lazy /gradio_api/info cache
        super().__init__(base_url)
        # Gradio 4.x+ uses event-based API at /gradio_api/call/.
        # The old /api/ synchronous predict endpoint is removed (404).
        self.call_api_url = f"{base_url}/gradio_api/call"
        self.gradio_api_url = f"{base_url}/gradio_api"
        self._health_last_log_ts: float = 0.0
        self._health_log_interval_sec: float = float(
            os.getenv("ULTIMATE_TTS_HEALTH_LOG_INTERVAL_SEC", "60")
        )
        self._default_engine = os.getenv("ULTIMATE_TTS_DEFAULT_ENGINE", "kitten_tts")
        self._timeout = float(os.getenv("ULTIMATE_TTS_TIMEOUT_SEC", "120"))

    async def _call_gradio(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        data: list,
        timeout: float = 120.0,
    ) -> list:
        """Call a Gradio endpoint via the event-based API.

        1. POST /gradio_api/call/<endpoint> with {"data": [...]} -> {"event_id": "..."}
        2. GET  /gradio_api/call/<endpoint>/<event_id> -> SSE stream
        3. Parse the SSE stream for the "complete" event containing results.

        Returns the result data list.
        """
        # Step 1: Submit the call
        resp = await client.post(
            f"{self.call_api_url}{endpoint}",
            json={"data": data},
            timeout=30.0,
        )
        if resp.status_code != 200:
            raise UltimateTTSError(
                f"Gradio call submit failed: {resp.status_code} — {resp.text[:200]}"
            )
        event_id = resp.json().get("event_id")
        if not event_id:
            raise UltimateTTSError("No event_id in Gradio call response")

        # Step 2: Poll the SSE stream for results
        result_data = []
        async with client.stream(
            "GET",
            f"{self.call_api_url}{endpoint}/{event_id}",
            timeout=timeout,
        ) as stream:
            current_event = ""
            current_data_lines = []
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    current_data_lines = []
                elif line.startswith("data:"):
                    current_data_lines.append(line[5:].strip())
                elif line == "":
                    # End of SSE message
                    if current_event == "complete" and current_data_lines:
                        raw = "\n".join(current_data_lines)
                        parsed = json.loads(raw)
                        result_data = parsed if isinstance(parsed, list) else parsed.get("data", parsed)
                        break
                    elif current_event == "error" and current_data_lines:
                        raw = "\n".join(current_data_lines)
                        raise UltimateTTSError(f"Gradio error: {raw[:200]}")
                    current_event = ""
                    current_data_lines = []

        return result_data

    async def _load_model(self, client: httpx.AsyncClient, engine: str) -> bool:
        """Load a TTS model if not already loaded.

        Uses Gradio's event-based API (/gradio_api/call/).

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
            "indextts": "/handle_load_indextts",
            "fish": "/handle_load_fish",
            "fish_s2": "/handle_load_fish_s2",
            "chatterbox": "/handle_load_chatterbox",
            "chatterbox_turbo": "/handle_load_chatterbox_turbo",
            "chatterbox_multilingual": "/handle_load_chatterbox_multilingual",
            "voxcpm": "/handle_load_voxcpm",
            "higgs": "/handle_load_higgs",
            "qwen": "/handle_load_qwen",
            "vibevoice": "/handle_vibevoice_load",
        }
        # Some engines require load parameters (positional)
        load_data_map = {
            "f5_tts": ["F5-TTS Base"],        # model_name
            "qwen": ["Base", "1.7B"],          # model_type, model_size
            "vibevoice": ["", "models/VibeVoice-1.5B", False],  # selected_model_path, path, use_flash_attention
        }
        endpoint = endpoint_map.get(engine)
        if not endpoint:
            logger.warning("Unknown engine %s, skipping model load", engine)
            return True

        # Some engines require a setup step before loading (repo clone, weight download)
        setup_map = {
            "fish_s2": "/handle_setup_fish_s2",
        }
        setup_endpoint = setup_map.get(engine)
        if setup_endpoint:
            try:
                await self._call_gradio(client, setup_endpoint, [], timeout=600.0)
                logger.info("Ultimate-TTS %s setup complete", engine)
            except Exception as exc:
                logger.warning("Setup for %s failed (continuing to load): %s", engine, exc)

        # Heavy models need more than 60s to load
        load_timeout_map = {
            "fish_s2": 120.0,
            "higgs": 120.0,
            "qwen": 90.0,
        }

        try:
            load_data = load_data_map.get(engine, [])
            load_timeout = load_timeout_map.get(engine, 60.0)
            data = await self._call_gradio(client, endpoint, load_data, timeout=load_timeout)

            if isinstance(data, list) and len(data) > 0:
                status = str(data[0]) if data[0] else ""
                if "✅" in status or "Loaded" in status or "already" in status.lower():
                    logger.info("Ultimate-TTS %s model loaded", engine)
                    return True
            return True  # Assume loaded if no error
        except Exception as exc:
            logger.warning("Failed to load %s model: %s", engine, exc)
            return False

    async def _get_schema_params(self, client: "httpx.AsyncClient") -> list:
        """Fetch the LIVE parameter schema for /generate_unified_tts.

        Discovery over hardcoding: the positional layout has drifted twice
        (121 -> "101" -> 121) and every drift null-crashed synthesis. The
        studio publishes its own schema at /gradio_api/info — consume it.
        Cached per provider instance; a studio restart with a changed schema
        needs a flute recreate (or TTL, future). Raises loudly on failure:
        guessing positions is exactly the bug class this replaces.
        """
        if self._schema_params is not None:
            return self._schema_params
        resp = await client.get(f"{self.base_url}/gradio_api/info", timeout=15.0)
        resp.raise_for_status()
        info = resp.json()
        ep = (info.get("named_endpoints") or {}).get("/generate_unified_tts")
        if not ep or not ep.get("parameters"):
            raise UltimateTTSError(
                "/generate_unified_tts not present in /gradio_api/info — "
                "studio version incompatible or endpoint renamed"
            )
        self._schema_params = ep["parameters"]
        logger.info(
            "Ultimate-TTS schema discovered: %d params for generate_unified_tts",
            len(self._schema_params),
        )
        return self._schema_params

    # Per-engine opinionated overrides, resolved BY PARAMETER NAME against the
    # live schema (never by position). Values may be callables taking `voice`.
    ENGINE_NAME_OVERRIDES = {
        "kokoro": {"kokoro_voice": (lambda v: v or "af_heart"), "kokoro_speed": 1.0},
        "kitten_tts": {"kitten_voice": (lambda v: v or "expr-voice-2-f")},
        # IndexTTS2 emotion vectors — 8 emotions [0,1].
        # Caller passes emotion as voice="indextts2:{happy}:{angry}:{sad}:{afraid}:{disgusted}:{melancholic}:{surprised}:{calm}"
        # or use presets: voice="happy", voice="angry", voice="excited", voice="calm"
    }

    # IndexTTS2 emotion presets — 8-vector [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
    INDEXTTS2_EMOTION_PRESETS = {
        "neutral":  [0, 0, 0, 0, 0, 0, 0, 1.0],
        "happy":    [0.8, 0, 0, 0, 0, 0, 0.3, 0.5],
        "excited":  [1.0, 0, 0, 0, 0, 0, 0.6, 0.3],
        "angry":    [0, 1.0, 0, 0, 0, 0, 0, 0],
        "sad":      [0, 0, 1.0, 0, 0, 0, 0, 0],
        "afraid":   [0, 0, 0, 1.0, 0, 0, 0, 0],
        "disgusted":[0, 0, 0, 0, 1.0, 0, 0, 0],
        "melancholic":[0, 0, 0.3, 0, 0, 1.0, 0, 0.3],
        "surprised":[0.3, 0, 0, 0, 0, 0, 1.0, 0.3],
        "calm":     [0, 0, 0, 0, 0, 0, 0, 1.0],
    }

    def _build_params(
        self,
        schema_params: list,
        text: str,
        engine: str,
        voice: Optional[str] = None,
    ) -> list:
        """Build the generate_unified_tts arg list FROM THE LIVE SCHEMA.

        Every slot takes the studio's own parameter_default; we override only
        by name: the three core params plus the selected engine's named
        opinions (ENGINE_NAME_OVERRIDES). Unknown-to-us engines run entirely
        on studio defaults — the engine author's defaults beat our guesses.
        Positional drift (121 vs "101") can no longer break the call; a
        RENAMED core param fails loudly below instead of null-crashing.
        """
        api_engine = self.ENGINE_NAMES.get(engine, engine)
        if engine == "vibevoice":
            raise UltimateTTSError(
                "vibevoice is not supported via the unified /generate_unified_tts "
                "endpoint. Use the dedicated VibeVoice panel "
                "(handle_vibevoice_generation) via gradio_client, or pick a "
                "different engine."
            )
        if engine not in self.ENGINE_NAMES:
            raise UltimateTTSError(
                f"Unknown engine '{engine}'. Supported: {list(self.ENGINE_NAMES)}."
            )

        data = []
        for p in schema_params:
            val = p.get("parameter_default")
            if val is None and p.get("python_type", {}).get("type") == "str":
                val = ""
            data.append(val)
        name_to_idx = {
            p.get("parameter_name"): i for i, p in enumerate(schema_params)
        }

        def set_by_name(name: str, value, required: bool = False) -> None:
            idx = name_to_idx.get(name)
            if idx is None:
                if required:
                    raise UltimateTTSError(
                        f"Core param '{name}' missing from live schema — "
                        f"studio API changed shape; refusing to guess"
                    )
                logger.warning(
                    "Ultimate-TTS schema drift: param '%s' not in live schema; "
                    "using studio default", name,
                )
                return
            data[idx] = value

        set_by_name("text_input", text, required=True)
        set_by_name("tts_engine", api_engine, required=True)
        set_by_name("audio_format", "wav")

        for name, value in self.ENGINE_NAME_OVERRIDES.get(engine, {}).items():
            set_by_name(name, value(voice) if callable(value) else value)

        # IndexTTS2 emotion vector support
        if engine == "indextts2" and voice:
            preset = self.INDEXTTS2_EMOTION_PRESETS.get(voice)
            if preset:
                emotion_names = ["indextts2_happy", "indextts2_angry", "indextts2_sad",
                                 "indextts2_afraid", "indextts2_disgusted", "indextts2_melancholic",
                                 "indextts2_surprised", "indextts2_calm"]
                for ename, eval in zip(emotion_names, preset):
                    set_by_name(ename, eval)
                set_by_name("indextts2_emotion_mode", "vector_control")
            elif voice.startswith("indextts2:"):
                # Custom 8-vector: "indextts2:0.8:0:0:0:0:0:0.3:0.5"
                parts = voice.split(":")
                if len(parts) == 9:
                    emotion_names = ["indextts2_happy", "indextts2_angry", "indextts2_sad",
                                     "indextts2_afraid", "indextts2_disgusted", "indextts2_melancholic",
                                     "indextts2_surprised", "indextts2_calm"]
                    for ename, eval in zip(emotion_names, parts[1:]):
                        try:
                            set_by_name(ename, float(eval))
                        except ValueError:
                            pass
                    set_by_name("indextts2_emotion_mode", "vector_control")

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

        engine_timeout = self.ENGINE_TIMEOUTS.get(engine, self._timeout)

        async with httpx.AsyncClient(timeout=engine_timeout) as client:
            # Ensure model is loaded
            await self._load_model(client, engine)

            # Build full parameter list from the LIVE schema (discovery
            # over hardcoding — see _get_schema_params).
            schema_params = await self._get_schema_params(client)
            data = self._build_params(schema_params, text, engine, voice)

            try:
                # Use Gradio's event-based API (/gradio_api/call/).
                result_data = await self._call_gradio(
                    client, "/generate_unified_tts", data, timeout=engine_timeout,
                )

                if not isinstance(result_data, list) or len(result_data) < 2:
                    raise UltimateTTSError(
                        f"Unexpected response shape: {str(result_data)[:200]}"
                    )

                # Check for error status (second element)
                status = result_data[1] if len(result_data) > 1 else ""
                if isinstance(status, str) and "❌" in status:
                    raise UltimateTTSError(status)

                # First element contains audio info with a URL
                audio_info = result_data[0]
                audio_url = None
                if isinstance(audio_info, dict) and "url" in audio_info:
                    audio_url = audio_info["url"]
                elif isinstance(audio_info, str) and audio_info.startswith("http"):
                    audio_url = audio_info
                elif isinstance(audio_info, str) and audio_info.startswith("/"):
                    audio_url = f"{self.base_url}{audio_info}"

                if not audio_url:
                    raise UltimateTTSError(
                        f"No audio URL in response: {str(audio_info)[:200]}"
                    )

                # Download the audio file
                audio_resp = await client.get(audio_url, timeout=30.0)
                if audio_resp.status_code != 200:
                    raise UltimateTTSError(
                        f"Failed to download audio: {audio_resp.status_code}"
                    )

                wav_bytes = audio_resp.content
                logger.info(
                    "Ultimate-TTS synthesized %d bytes (engine=%s, voice=%s)",
                    len(wav_bytes), engine, voice
                )
                return wav_bytes

            except httpx.TimeoutException as exc:
                raise UltimateTTSError(
                    f"Timeout during {engine} synthesis ({engine_timeout}s): {exc}"
                ) from exc
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
                        "indextts": "/handle_load_indextts" in endpoints,
                        "fish": "/handle_load_fish" in endpoints,
                        "fish_s2": "/handle_load_fish_s2" in endpoints,
                        "chatterbox": "/handle_load_chatterbox" in endpoints,
                        "chatterbox_turbo": "/handle_load_chatterbox_turbo" in endpoints,
                        "voxcpm": "/handle_load_voxcpm" in endpoints,
                        "higgs": "/handle_load_higgs" in endpoints,
                        "qwen": "/handle_load_qwen" in endpoints,
                        "vibevoice": "/handle_vibevoice_load" in endpoints,
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
