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

        try:
            load_data = load_data_map.get(engine, [])
            data = await self._call_gradio(client, endpoint, load_data, timeout=60.0)

            if isinstance(data, list) and len(data) > 0:
                status = str(data[0]) if data[0] else ""
                if "✅" in status or "Loaded" in status or "already" in status.lower():
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
        """Build the full 121-parameter list for generate_unified_tts.

        Parameter positions are derived from the Gradio API info endpoint.
        """
        api_engine = self.ENGINE_NAMES.get(engine, engine)

        # Total 121 parameters (Gradio 4.x API)
        data: list = [None] * 121

        # [0-2] Core params
        data[0] = text          # text_input
        data[1] = api_engine    # tts_engine
        data[2] = "wav"         # audio_format

        # [3-8] Chatterbox
        data[4] = 0.5    # exaggeration
        data[5] = 0.8    # temperature
        data[6] = 0.5    # cfg_weight
        data[7] = 300    # chunk_size
        data[8] = 0      # seed

        # [9-18] Chatterbox MTL
        data[10] = "en"
        data[11] = 0.5
        data[12] = 0.8
        data[13] = 0.5
        data[14] = 2.0
        data[15] = 0.05
        data[16] = 1.0
        data[17] = 300
        data[18] = 0

        # [19-27] Chatterbox Turbo
        data[20] = 0.5   # turbo_exaggeration
        data[21] = 0.8   # turbo_temperature
        data[22] = 0.5   # turbo_cfg_weight
        data[23] = 1.2   # turbo_repetition_penalty
        data[24] = 0.05  # turbo_min_p
        data[25] = 0.95  # turbo_top_p
        data[26] = 300   # turbo_chunk_size
        data[27] = 0     # turbo_seed

        # [28-29] Kokoro
        data[28] = voice if engine == "kokoro" else "af_heart"
        data[29] = 1.0   # speed

        # [30-36] Fish Speech S1
        data[31] = ""     # ref_text
        data[32] = 0.8   # temperature
        data[33] = 0.8   # top_p
        data[34] = 1.1   # repetition_penalty
        data[35] = 1024  # max_tokens
        data[36] = 0     # seed

        # [37-43] Fish Speech S2 Pro
        data[38] = ""     # ref_text
        data[39] = 0.8   # temperature
        data[40] = 0.8   # top_p
        data[41] = 1.1   # repetition_penalty
        data[42] = 2048  # max_tokens
        data[43] = 0     # seed

        # [44-46] IndexTTS
        data[45] = 0.8   # temperature
        data[46] = 0     # seed

        # [47-66] IndexTTS2
        data[48] = "audio_reference"  # emotion_mode
        data[50] = ""     # emotion_description (REQUIRED)
        data[51] = 1.0   # emo_alpha
        data[59] = 1.0   # calm
        data[60] = 0.8   # temperature
        data[61] = 0.9   # top_p
        data[62] = 50    # top_k
        data[63] = 1.1   # repetition_penalty
        data[64] = 1500  # max_mel_tokens
        data[65] = 0     # seed
        data[66] = False  # use_random

        # [67-72] F5-TTS
        data[68] = ""     # ref_text
        data[69] = 1.0   # speed
        data[70] = 0.15  # cross_fade
        data[71] = False  # remove_silence
        data[72] = 0     # seed

        # [73-82] Higgs Audio
        data[74] = ""     # ref_text
        data[75] = "EMPTY"  # voice_preset
        data[76] = ""     # system_prompt (REQUIRED)
        data[77] = 1.0   # temperature
        data[78] = 0.95  # top_p
        data[79] = 50    # top_k
        data[80] = 1024  # max_tokens
        data[81] = 7     # ras_win_len
        data[82] = 2     # ras_win_max_num_repeat

        # [83] KittenTTS voice
        data[83] = voice if engine == "kitten_tts" else "expr-voice-2-f"

        # [84-93] VoxCPM
        data[85] = ""     # ref_text
        data[86] = 2.0   # cfg_value
        data[87] = 10    # inference_timesteps
        data[88] = True   # normalize
        data[89] = True   # denoise
        data[90] = True   # retry_badcase
        data[91] = 3     # retry_badcase_max_times
        data[92] = 6.0   # retry_badcase_ratio_threshold
        data[93] = -1    # seed

        # [94-106] Qwen TTS
        data[94] = "voice_design"  # mode
        data[95] = "A warm, clear, professional English-speaking voice"  # voice_description (REQUIRED)
        data[97] = ""     # ref_text (REQUIRED)
        data[99] = "1.7B"  # clone_model_size
        data[100] = 200   # chunk_size
        data[101] = 10    # chunk_gap
        data[102] = "Ryan"  # speaker
        data[103] = "1.7B"  # custom_model_size
        data[104] = ""     # style_instruct (REQUIRED)
        data[105] = "Auto"  # language
        data[106] = 0     # seed

        # [107-120] Audio effects
        data[107] = 0      # gain_db
        data[108] = False  # enable_eq
        data[109] = 0      # eq_bass
        data[110] = 0      # eq_mid
        data[111] = 0      # eq_treble
        data[112] = False  # enable_reverb
        data[113] = 0.3   # reverb_room
        data[114] = 0.5   # reverb_damping
        data[115] = 0.3   # reverb_wet
        data[116] = False  # enable_echo
        data[117] = 0.3   # echo_delay
        data[118] = 0.5   # echo_decay
        data[119] = False  # enable_pitch
        data[120] = 0     # pitch_semitones

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

            # Build full parameter list
            data = self._build_params(text, engine, voice)

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
