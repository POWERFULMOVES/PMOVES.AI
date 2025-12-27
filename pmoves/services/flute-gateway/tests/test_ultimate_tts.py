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


class TestUltimateTTSProviderInit:
    """Test provider initialization."""

    def test_init_default_values(self):
        """Test provider initializes with correct defaults."""
        provider = UltimateTTSProvider()
        assert provider.base_url == "http://localhost:7861"
        assert provider.gradio_api_url == "http://localhost:7861/gradio_api"

    def test_init_custom_url(self):
        """Test provider accepts custom base_url."""
        provider = UltimateTTSProvider(base_url="http://custom:8080")
        assert provider.base_url == "http://custom:8080"
        assert provider.gradio_api_url == "http://custom:8080/gradio_api"

    def test_engine_names_mapping(self):
        """Test ENGINE_NAMES contains all 7 engines."""
        provider = UltimateTTSProvider()
        expected_engines = {
            "kitten_tts", "kokoro", "f5_tts", "indextts2",
            "fish", "chatterbox", "voxcpm"
        }
        assert set(provider.ENGINE_NAMES.keys()) == expected_engines

    def test_default_voices_defined(self):
        """Test DEFAULT_VOICES mapping exists."""
        provider = UltimateTTSProvider()
        assert "kitten_tts" in provider.DEFAULT_VOICES
        assert "kokoro" in provider.DEFAULT_VOICES


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

    def _create_mock_client(self, audio_url: str = "/file=test.wav"):
        """Create a mock httpx client for synthesis tests."""
        mock_client = AsyncMock()

        # Mock model load response
        mock_load_response = MagicMock()
        mock_load_response.status_code = 200
        mock_load_response.json.return_value = {"event_id": "load-123"}

        # Mock model load result (SSE)
        mock_load_result = MagicMock()
        mock_load_result.iter_lines.return_value = ['data: ["\\u2705 Loaded"]']

        # Mock synthesis call response
        mock_synth_response = MagicMock()
        mock_synth_response.status_code = 200
        mock_synth_response.json.return_value = {"event_id": "synth-456"}

        # Mock synthesis result (SSE with audio URL)
        mock_synth_result = MagicMock()
        audio_data = json.dumps([{"url": audio_url}, "Success"])
        mock_synth_result.iter_lines.return_value = [f'data: {audio_data}']

        # Mock audio download
        mock_audio_response = MagicMock()
        mock_audio_response.status_code = 200
        mock_audio_response.content = create_mock_wav_bytes()

        # Setup side effects for different URLs
        async def mock_post(url, **kwargs):
            if "handle_load" in url:
                return mock_load_response
            return mock_synth_response

        async def mock_get(url, **kwargs):
            if "handle_load" in url:
                return mock_load_result
            if "generate_unified_tts" in url:
                return mock_synth_result
            return mock_audio_response

        mock_client.post = AsyncMock(side_effect=mock_post)
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
        "kitten_tts", "kokoro", "f5_tts", "indextts2",
        "fish", "chatterbox", "voxcpm"
    ])
    async def test_synthesize_each_engine(self, provider, engine):
        """Test synthesize works for each engine type."""
        mock_client = self._create_mock_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("Test text", engine=engine)
            assert isinstance(result, bytes)

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

        mock_load_response = MagicMock()
        mock_load_response.status_code = 200
        mock_load_response.json.return_value = {"event_id": "load-123"}

        mock_load_result = MagicMock()
        mock_load_result.iter_lines.return_value = ['data: ["Loaded"]']

        # Synthesis fails
        mock_synth_response = MagicMock()
        mock_synth_response.status_code = 500

        async def mock_post(url, **kwargs):
            if "handle_load" in url:
                return mock_load_response
            return mock_synth_response

        async def mock_get(url, **kwargs):
            return mock_load_result

        mock_client.post = AsyncMock(side_effect=mock_post)
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UltimateTTSError, match="API call failed"):
                await provider.synthesize("Test", engine="kitten_tts")

    @pytest.mark.asyncio
    async def test_synthesize_timeout_error(self, provider):
        """Test synthesize handles timeout gracefully."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
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
    """Test parameter building for Gradio API."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return UltimateTTSProvider(base_url="http://localhost:7861")

    def test_build_params_returns_92_elements(self, provider):
        """Test _build_params returns exactly 92 parameters."""
        params = provider._build_params("Hello", "kitten_tts")
        assert len(params) == 92

    def test_build_params_text_at_index_0(self, provider):
        """Test text is at index 0."""
        params = provider._build_params("Test text", "kitten_tts")
        assert params[0] == "Test text"

    def test_build_params_engine_at_index_1(self, provider):
        """Test engine name is at index 1."""
        params = provider._build_params("Test", "kitten_tts")
        assert params[1] == "KittenTTS"

        params = provider._build_params("Test", "kokoro")
        assert params[1] == "Kokoro TTS"

    def test_build_params_audio_format_wav(self, provider):
        """Test audio format is WAV at index 2."""
        params = provider._build_params("Test", "kitten_tts")
        assert params[2] == "wav"

    def test_build_params_kitten_voice_at_index_67(self, provider):
        """Test KittenTTS voice is at index 67."""
        params = provider._build_params("Test", "kitten_tts", voice="expr-voice-3-f")
        assert params[67] == "expr-voice-3-f"

    def test_build_params_kokoro_voice_at_index_19(self, provider):
        """Test Kokoro voice is at index 19."""
        params = provider._build_params("Test", "kokoro", voice="af_bella")
        assert params[19] == "af_bella"
