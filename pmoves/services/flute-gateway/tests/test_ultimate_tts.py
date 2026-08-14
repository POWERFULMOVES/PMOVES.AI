"""Unit tests for Ultimate-TTS provider with mocks.

Tests the UltimateTTSProvider class without requiring the live service.
Uses mocked httpx responses to simulate Gradio API behavior.
"""

import io
import json
import os
import sys
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from providers.ultimate_tts import UltimateTTSProvider, UltimateTTSError


def create_mock_wav_bytes(duration_samples: int = 24000) -> bytes:
    """Create valid WAV bytes for testing.

    Args:
        duration_samples: Number of samples (24000 = 1 second at 24kHz)

    Returns:
        WAV file as bytes
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(24000)
        # Write silence
        wf.writeframes(b"\x00\x00" * duration_samples)
    return buf.getvalue()


def mock_schema_params() -> list:
    """A minimal but REALISTIC /generate_unified_tts parameter schema.

    Since #2400 the provider discovers parameters from the studio's own
    /gradio_api/info rather than assuming a positional layout, so every
    synthesis test has to serve a schema. Shape matches what Gradio
    publishes: parameter_name, parameter_default, python_type.type.

    Deliberately NOT 121 entries and deliberately not in the studio's
    order. Discovery resolves by NAME, so neither the count nor the
    ordering may matter — if a change to the provider ever makes this
    fixture's arbitrary length or order significant, these tests should
    start failing, and that failure is the point.
    """
    def p(name, default=None, ptype="str"):
        return {
            "parameter_name": name,
            "parameter_default": default,
            "python_type": {"type": ptype},
        }

    return [
        p("audio_format", "wav"),
        p("kokoro_speed", 1.0, "float"),
        p("text_input", ""),
        p("kitten_voice", "expr-voice-2-f"),
        p("tts_engine", "KittenTTS"),
        p("kokoro_voice", "af_heart"),
        p("indextts2_emotion_mode", "audio_prompt"),
        p("indextts2_happy", 0.0, "float"),
        p("indextts2_angry", 0.0, "float"),
        p("indextts2_sad", 0.0, "float"),
        p("indextts2_afraid", 0.0, "float"),
        p("indextts2_disgusted", 0.0, "float"),
        p("indextts2_melancholic", 0.0, "float"),
        p("indextts2_surprised", 0.0, "float"),
        p("indextts2_calm", 0.0, "float"),
    ]


def mock_info_response(params: list = None) -> MagicMock:
    """Mock the GET /gradio_api/info schema-discovery response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json.return_value = {
        "named_endpoints": {
            "/generate_unified_tts": {
                "parameters": mock_schema_params() if params is None else params
            }
        }
    }
    return resp


class _MockSSEStream:
    """Mock SSE stream for Gradio 4.x event API responses.

    Simulates the server-sent events returned by
    GET /gradio_api/call/<endpoint>/<event_id>.
    """

    def __init__(self, lines: list):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestUltimateTTSProviderInit:
    """Test provider initialization."""

    def test_init_default_values(self):
        """Test provider initializes with correct defaults."""
        provider = UltimateTTSProvider()
        assert provider.base_url == "http://localhost:7860"
        assert provider.call_api_url == "http://localhost:7860/gradio_api/call"
        assert provider.gradio_api_url == "http://localhost:7860/gradio_api"

    def test_init_custom_url(self):
        """Test provider accepts custom base_url."""
        provider = UltimateTTSProvider(base_url="http://custom:8080")
        assert provider.base_url == "http://custom:8080"
        assert provider.call_api_url == "http://custom:8080/gradio_api/call"
        assert provider.gradio_api_url == "http://custom:8080/gradio_api"

    def test_engine_names_mapping(self):
        """Test ENGINE_NAMES contains all 14 engines."""
        provider = UltimateTTSProvider()
        expected_engines = {
            "kitten_tts", "kokoro", "f5_tts", "indextts2", "indextts",
            "fish", "fish_s2", "chatterbox", "chatterbox_turbo",
            "chatterbox_multilingual", "voxcpm", "higgs", "qwen", "vibevoice",
        }
        assert set(provider.ENGINE_NAMES.keys()) == expected_engines

    def test_default_voices_defined(self):
        """Test DEFAULT_VOICES mapping exists."""
        provider = UltimateTTSProvider()
        assert "kitten_tts" in provider.DEFAULT_VOICES
        assert "kokoro" in provider.DEFAULT_VOICES

    def test_engine_timeouts_keys_are_valid_engines(self):
        """Test ENGINE_TIMEOUTS only references known engines."""
        provider = UltimateTTSProvider()
        for engine in provider.ENGINE_TIMEOUTS:
            assert engine in provider.ENGINE_NAMES, f"Unknown engine in ENGINE_TIMEOUTS: {engine}"

    def test_engine_timeouts_fish_s2_is_elevated(self):
        """Test Fish S2 Pro has a higher timeout than the default."""
        provider = UltimateTTSProvider()
        assert provider.ENGINE_TIMEOUTS["fish_s2"] > provider._timeout


class TestUltimateTTSProviderHealthCheck:
    """Test health check functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test health_check returns True when service healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await provider.health_check()
            assert result is True
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure_status(self, provider):
        """Test health_check returns False on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await provider.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure_exception(self, provider):
        """Test health_check returns False on connection error."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await provider.health_check()
            assert result is False


class TestUltimateTTSProviderGetEngines:
    """Test engine discovery functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    @pytest.mark.asyncio
    async def test_get_engines_returns_dict(self, provider):
        """Test get_engines returns dictionary."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "named_endpoints": {
                "/handle_load_kitten": {},
                "/handle_f5_load": {},
                "/handle_load_kokoro": {},
                "/handle_load_indextts2": {},
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await provider.get_engines()
            assert isinstance(result, dict)
            assert result.get("kitten_tts") is True
            assert result.get("f5_tts") is True
            assert result.get("kokoro") is True
            assert result.get("indextts2") is True

    @pytest.mark.asyncio
    async def test_get_engines_handles_error(self, provider):
        """Test get_engines returns empty dict on error."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await provider.get_engines()
            assert result == {}


class TestUltimateTTSProviderSynthesize:
    """Test synthesis functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    def _create_mock_client(self, audio_url: str = "http://localhost:7861/file=test.wav"):
        """Create a mock httpx client for synthesis tests.

        Mocks the Gradio 4.x event-based API (/gradio_api/call/) which
        uses a POST→event_id then GET→SSE stream polling pattern.
        """
        mock_client = AsyncMock()

        # All Gradio call POSTs return an event_id
        mock_event_response = MagicMock()
        mock_event_response.status_code = 200
        mock_event_response.json.return_value = {"event_id": "mock-evt-123"}
        mock_client.post = AsyncMock(return_value=mock_event_response)

        # SSE streams: model-load vs synthesis have different payloads
        load_sse = [
            "event: complete",
            "data: " + json.dumps(["\u2705 Loaded"]),
            "",
        ]
        synth_sse = [
            "event: complete",
            "data: " + json.dumps([{"url": audio_url}, "\u2705 Done"]),
            "",
        ]

        def mock_stream(method, url, **kwargs):
            if "generate_unified_tts" in url:
                return _MockSSEStream(synth_sse)
            return _MockSSEStream(load_sse)

        mock_client.stream = MagicMock(side_effect=mock_stream)

        # GET serves two different things and MUST be routed by URL:
        #   /gradio_api/info -> the parameter schema (discovery, since #2400)
        #   anything else    -> the rendered audio file
        # Returning audio for both is what made every synthesis test fail with
        # "Core param 'text_input' missing from live schema" — the provider
        # asked for a schema and got a MagicMock.
        mock_audio_response = MagicMock()
        mock_audio_response.status_code = 200
        mock_audio_response.content = create_mock_wav_bytes()

        async def mock_get(url, **kwargs):
            if "/gradio_api/info" in url:
                return mock_info_response()
            return mock_audio_response

        mock_client.get = AsyncMock(side_effect=mock_get)

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        return mock_client

    @pytest.mark.asyncio
    async def test_synthesize_returns_bytes(self, provider):
        """Test synthesize returns audio bytes."""
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("Hello world", engine="kitten_tts")
            assert isinstance(result, bytes)
            assert len(result) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("engine", [
        "kitten_tts", "kokoro", "f5_tts", "indextts2", "indextts",
        "fish", "fish_s2", "chatterbox", "chatterbox_turbo",
        "chatterbox_multilingual", "voxcpm", "higgs", "qwen",
    ])
    async def test_synthesize_each_engine(self, provider, engine):
        """Test synthesize works for each engine type.

        vibevoice is deliberately absent — it is not reachable through
        /generate_unified_tts. See test_synthesize_vibevoice_rejected.
        """
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("Test text", engine=engine)
            assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_synthesize_vibevoice_rejected(self, provider):
        """vibevoice must be refused on the unified endpoint, not attempted.

        It has no /generate_unified_tts path — it needs the dedicated
        VibeVoice panel via gradio_client. This test previously asserted
        vibevoice SUCCEEDED, which only passed while the provider silently
        guessed at parameters. Refusing is the correct behaviour, so the
        test now pins the refusal.
        """
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="vibevoice is not supported"):
                await provider.synthesize("Test text", engine="vibevoice")

    @pytest.mark.asyncio
    async def test_synthesize_unknown_engine_rejected(self, provider):
        """An engine absent from ENGINE_NAMES must raise, not guess."""
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="Unknown engine"):
                await provider.synthesize("Test text", engine="not_a_real_engine")

    @pytest.mark.asyncio
    async def test_synthesize_raises_when_core_param_missing(self, provider):
        """A schema without text_input must fail loudly rather than guess.

        This is the guard #2400 added: if the studio renames a core param,
        the provider refuses instead of null-crashing at a stale position.
        Nothing covered it, so a regression that reinstated positional
        guessing would have gone unnoticed.
        """
        mock_client = self._create_mock_client()
        stripped = [p for p in mock_schema_params()
                    if p["parameter_name"] != "text_input"]

        async def mock_get(url, **kwargs):
            if "/gradio_api/info" in url:
                return mock_info_response(stripped)
            resp = MagicMock()
            resp.status_code = 200
            resp.content = create_mock_wav_bytes()
            return resp

        mock_client.get = AsyncMock(side_effect=mock_get)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="missing from live schema"):
                await provider.synthesize("Test text", engine="kitten_tts")

    @pytest.mark.asyncio
    async def test_synthesize_with_custom_voice(self, provider):
        """Test synthesize accepts custom voice parameter."""
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize(
                "Hello",
                voice="expr-voice-3-m",
                engine="kitten_tts"
            )
            assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_synthesize_api_error(self, provider):
        """Test synthesize raises error on API failure."""
        mock_client = AsyncMock()

        # Model load POST succeeds with event_id
        mock_load_post = MagicMock()
        mock_load_post.status_code = 200
        mock_load_post.json.return_value = {"event_id": "load-evt"}

        # Synthesis POST fails with 500
        mock_synth_post = MagicMock()
        mock_synth_post.status_code = 500
        mock_synth_post.text = "Internal Server Error"

        async def mock_post(url, **kwargs):
            if "generate_unified_tts" in url:
                return mock_synth_post
            return mock_load_post

        mock_client.post = AsyncMock(side_effect=mock_post)

        # SSE stream for model load
        load_sse = ["event: complete", "data: " + json.dumps(["Loaded"]), ""]
        mock_client.stream = MagicMock(
            side_effect=lambda method, url, **kw: _MockSSEStream(load_sse)
        )
        # Schema discovery runs BEFORE the synthesis POST, so this GET has to
        # serve a real schema. A bare AsyncMock() returned a coroutine whose
        # .json() was itself a coroutine -> "'coroutine' object has no
        # attribute 'get'", masking the 500 this test exists to assert.
        mock_client.get = AsyncMock(return_value=mock_info_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="Gradio call submit failed: 500"):
                await provider.synthesize("Test", engine="kitten_tts")

    @pytest.mark.asyncio
    async def test_synthesize_timeout_error(self, provider):
        """Test synthesize handles timeout gracefully."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        # Schema discovery precedes the POST; serve it so the timeout under
        # test is the one raised by synthesis and not an artefact of an
        # unmocked GET.
        mock_client.get = AsyncMock(return_value=mock_info_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="Timeout"):
                await provider.synthesize("Test", engine="kitten_tts")


class TestUltimateTTSProviderStream:
    """Test streaming synthesis functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_chunks(self, provider):
        """Test streaming synthesis yields audio chunks."""
        wav_bytes = create_mock_wav_bytes()

        with patch.object(provider, "synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = wav_bytes

            chunks = []
            async for chunk in provider.synthesize_stream("Hello", engine="kitten_tts"):
                chunks.append(chunk)

            assert len(chunks) >= 1
            total_bytes = sum(len(c) for c in chunks)
            assert total_bytes > 0

    @pytest.mark.asyncio
    async def test_synthesize_stream_handles_invalid_wav(self, provider):
        """Test streaming handles non-WAV audio gracefully."""
        non_wav_bytes = b"not a wav file"

        with patch.object(provider, "synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = non_wav_bytes

            chunks = []
            async for chunk in provider.synthesize_stream("Hello", engine="kitten_tts"):
                chunks.append(chunk)

            # Should yield raw bytes if not valid WAV
            assert len(chunks) == 1
            assert chunks[0] == non_wav_bytes


class TestUltimateTTSProviderRecognize:
    """Test STT (recognize) functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    @pytest.mark.asyncio
    async def test_recognize_raises_not_implemented(self, provider):
        """Test recognize raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="does not support speech recognition"):
            await provider.recognize(b"audio data")


class TestUltimateTTSProviderBuildParams:
    """Test parameter building against a DISCOVERED schema.

    This class previously asserted a fixed positional contract — 121
    elements, text at index 0, engine at 1, kokoro voice at 28, kitten
    voice at 83. #2400 ("schema-driven generate_unified_tts — discovery
    over hardcoding") deleted that contract: the provider now reads the
    studio's published schema and resolves every parameter BY NAME, and
    its own docstring notes the layout had already drifted 121 -> "101"
    -> 121, null-crashing synthesis each time.

    Those assertions could not be repaired, only removed — under
    discovery an index is not a property of the system. What replaces
    them tests the guarantee that actually exists now: resolution by
    name, independent of order and count.
    """

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    def _named(self, schema, params, name):
        """Read a built param by NAME, resolved against the schema USED.

        Takes the caller's schema rather than re-deriving one. The first
        version of this helper called mock_schema_params() itself and
        ignored the schema the params were actually built from — which
        works only while every caller happens to use the default. Hand a
        test a permuted schema and it would have read the wrong slot and
        reported a pass or a failure for the wrong reason: a helper that
        claims to resolve by name while secretly resolving by a fixed
        assumption. That is the same defect this whole file exists to
        remove, so it does not get to live in the fixture either.
        """
        idx = {p["parameter_name"]: i for i, p in enumerate(schema)}[name]
        return params[idx]

    def test_build_params_length_matches_schema_not_a_constant(self, provider):
        """Output length tracks the schema it was given, whatever that is."""
        schema = mock_schema_params()
        params = provider._build_params(schema, "Hello", "kitten_tts")
        assert len(params) == len(schema)

    def test_build_params_sets_core_params_by_name(self, provider):
        """text_input / tts_engine / audio_format land by name, not position."""
        schema = mock_schema_params()
        params = provider._build_params(schema, "Test text", "kitten_tts")
        assert self._named(schema, params, "text_input") == "Test text"
        assert self._named(schema, params, "tts_engine") == "KittenTTS"
        assert self._named(schema, params, "audio_format") == "wav"

    def test_build_params_engine_display_name_is_mapped(self, provider):
        """Engine keys map to the studio's display names."""
        schema = mock_schema_params()
        params = provider._build_params(schema, "Test", "kokoro")
        assert self._named(schema, params, "tts_engine") == "Kokoro TTS"

    def test_build_params_engine_overrides_applied_by_name(self, provider):
        """Per-engine voice overrides resolve by name for each engine."""
        schema = mock_schema_params()

        kitten = provider._build_params(schema, "Test", "kitten_tts",
                                        voice="expr-voice-3-f")
        assert self._named(schema, kitten, "kitten_voice") == "expr-voice-3-f"

        kokoro = provider._build_params(schema, "Test", "kokoro", voice="af_bella")
        assert self._named(schema, kokoro, "kokoro_voice") == "af_bella"

    def test_build_params_is_order_independent(self, provider):
        """A reordered schema must produce the same values by name.

        This is the property the deleted index assertions actively
        prevented anyone from having.
        """
        schema = mock_schema_params()
        reversed_schema = list(reversed(schema))

        params = provider._build_params(reversed_schema, "Hello", "kokoro",
                                        voice="af_bella")
        idx = {p["parameter_name"]: i for i, p in enumerate(reversed_schema)}
        assert params[idx["text_input"]] == "Hello"
        assert params[idx["tts_engine"]] == "Kokoro TTS"
        assert params[idx["kokoro_voice"]] == "af_bella"

    def test_build_params_by_name_under_a_permuted_schema(self, provider):
        """Overrides resolve by name even when the schema is permuted.

        Distinct from test_build_params_is_order_independent: that one
        reverses and checks core params, this one rotates and checks the
        per-engine overrides, which take a different code path
        (ENGINE_NAME_OVERRIDES, callables resolved against the schema).

        It also exercises _named against a schema that is NOT the default
        — the case the first version of that helper got silently wrong.
        """
        schema = mock_schema_params()
        rotated = schema[7:] + schema[:7]

        params = provider._build_params(rotated, "Hello", "kokoro",
                                        voice="af_bella")
        assert self._named(rotated, params, "text_input") == "Hello"
        assert self._named(rotated, params, "kokoro_voice") == "af_bella"
        assert self._named(rotated, params, "kokoro_speed") == 1.0
        assert self._named(rotated, params, "tts_engine") == "Kokoro TTS"

    def test_build_params_unknown_param_uses_studio_default(self, provider):
        """Slots we do not override keep the studio's own default."""
        schema = mock_schema_params()
        params = provider._build_params(schema, "Test", "kokoro")
        idx = {p["parameter_name"]: i for i, p in enumerate(schema)}
        assert params[idx["indextts2_emotion_mode"]] == "audio_prompt"

    def test_build_params_missing_core_param_raises(self, provider):
        """A renamed core param fails loudly instead of null-crashing."""
        schema = [p for p in mock_schema_params()
                  if p["parameter_name"] != "text_input"]
        with pytest.raises(UltimateTTSError, match="missing from live schema"):
            provider._build_params(schema, "Test", "kitten_tts")

    def test_build_params_indextts2_emotion_preset_by_name(self, provider):
        """IndexTTS2 emotion presets write the 8 vector slots by name."""
        schema = mock_schema_params()
        params = provider._build_params(schema, "Test", "indextts2", voice="angry")
        idx = {p["parameter_name"]: i for i, p in enumerate(schema)}
        assert params[idx["indextts2_angry"]] == 1.0
        assert params[idx["indextts2_emotion_mode"]] == "vector_control"
