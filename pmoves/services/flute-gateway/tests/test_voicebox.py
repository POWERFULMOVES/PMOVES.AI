"""Unit tests for VoiceboxProvider with mocks.

Tests the VoiceboxProvider class without requiring the live Voicebox service.
Uses mocked httpx responses to simulate the /generate/stream, /transcribe,
/profiles, and /health endpoints.

Functional tests (live service required) are marked with @pytest.mark.functional
and can be deselected with `pytest -m "not functional"`.
"""

import io
import json
import os
import sys
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from providers.voicebox import (
    VoiceboxBusyError,
    VoiceboxError,
    VoiceboxNoProfileError,
    VoiceboxProvider,
)


def create_mock_wav_bytes(duration_samples: int = 24000) -> bytes:
    """Create valid WAV bytes for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * duration_samples)
    return buf.getvalue()


def _make_async_client_mock(get_response=None, post_response=None, stream_response=None):
    """Build an AsyncClient mock that supports get / post / stream / context manager."""
    mock_client = AsyncMock()
    if get_response is not None:
        mock_client.get = AsyncMock(return_value=get_response)
    if post_response is not None:
        mock_client.post = AsyncMock(return_value=post_response)
    if stream_response is not None:
        # stream() returns an async context manager
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(return_value=stream_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=stream_cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class _MockStreamResponse:
    """Mock httpx streaming response for /generate/stream tests."""

    def __init__(self, status_code: int, chunks: list[bytes] | None = None, body: bytes = b""):
        self.status_code = status_code
        self._chunks = chunks or []
        self._body = body

    async def aiter_bytes(self, chunk_size: int = 65536):
        for chunk in self._chunks:
            yield chunk

    async def aread(self) -> bytes:
        return self._body


class TestVoiceboxProviderInit:
    """Test provider initialization."""

    def test_init_default_url(self):
        provider = VoiceboxProvider()
        assert provider.base_url == "http://host.docker.internal:17493"
        assert provider.generate_endpoint == "http://host.docker.internal:17493/generate/stream"
        assert provider.transcribe_endpoint == "http://host.docker.internal:17493/transcribe"
        assert provider.profiles_endpoint == "http://host.docker.internal:17493/profiles"
        assert provider.health_endpoint == "http://host.docker.internal:17493/health"

    def test_init_custom_url_strips_trailing_slash(self):
        provider = VoiceboxProvider(base_url="http://localhost:17493/")
        assert provider.base_url == "http://localhost:17493"
        assert provider.generate_endpoint == "http://localhost:17493/generate/stream"

    def test_init_default_engine_and_model_size(self):
        provider = VoiceboxProvider()
        assert provider.DEFAULT_ENGINE == "qwen"
        assert provider.DEFAULT_MODEL_SIZE == "1.7B"

    def test_init_no_cached_profile(self):
        provider = VoiceboxProvider()
        assert provider._cached_profile_id is None


class TestVoiceboxProviderHealthCheck:
    """Test the simple bool health_check for the gateway aggregator."""

    @pytest.fixture
    def provider(self):
        return VoiceboxProvider(base_url="http://localhost:17493")

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self, provider):
        mock_response = MagicMock(status_code=200)
        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(get_response=mock_response)):
            assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_500(self, provider):
        mock_response = MagicMock(status_code=500)
        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(get_response=mock_response)):
            assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_connect_error(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_client):
            assert await provider.health_check() is False


class TestVoiceboxProviderHealthStatus:
    """Test the rich health_status method."""

    @pytest.fixture
    def provider(self):
        return VoiceboxProvider(base_url="http://localhost:17493")

    @pytest.mark.asyncio
    async def test_health_status_ready_for_synthesis(self, provider):
        """Service up + model loaded + at least one profile = ready."""
        mock_client = AsyncMock()

        async def mock_get(url, *args, **kwargs):
            response = MagicMock()
            if "/health" in url:
                response.status_code = 200
                response.json.return_value = {
                    "model_loaded": True,
                    "model_downloaded": True,
                    "gpu_available": True,
                    "gpu_type": "CUDA (RTX 5090)",
                }
            elif "/profiles" in url:
                response.status_code = 200
                response.json.return_value = [{"id": "abc-123", "name": "Default"}]
            return response

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await provider.health_status()

        assert status["reachable"] is True
        assert status["model_loaded"] is True
        assert status["model_downloaded"] is True
        assert status["gpu_available"] is True
        assert status["gpu_type"] == "CUDA (RTX 5090)"
        assert status["profiles_count"] == 1
        assert status["ready_for_synthesis"] is True

    @pytest.mark.asyncio
    async def test_health_status_no_profiles_not_ready(self, provider):
        """Service up but zero profiles = NOT ready for synthesis."""
        mock_client = AsyncMock()

        async def mock_get(url, *args, **kwargs):
            response = MagicMock()
            if "/health" in url:
                response.status_code = 200
                response.json.return_value = {"model_loaded": False, "gpu_available": True}
            elif "/profiles" in url:
                response.status_code = 200
                response.json.return_value = []
            return response

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await provider.health_status()

        assert status["reachable"] is True
        assert status["profiles_count"] == 0
        assert status["ready_for_synthesis"] is False

    @pytest.mark.asyncio
    async def test_health_status_unreachable(self, provider):
        """Service down = unreachable, not ready."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await provider.health_status()

        assert status["reachable"] is False
        assert status["ready_for_synthesis"] is False


class TestVoiceboxProviderProfileResolution:
    """Test profile_id resolution and caching."""

    @pytest.fixture
    def provider(self):
        return VoiceboxProvider(base_url="http://localhost:17493")

    @pytest.mark.asyncio
    async def test_resolve_explicit_voice_passes_through(self, provider):
        """If voice is explicitly provided, use it directly without HTTP call."""
        result = await provider._resolve_profile_id("explicit-profile-id")
        assert result == "explicit-profile-id"
        # Cached profile should NOT be set when voice is explicit
        assert provider._cached_profile_id is None

    @pytest.mark.asyncio
    async def test_resolve_no_voice_fetches_first_profile(self, provider):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = [
            {"id": "first-id", "name": "Alice"},
            {"id": "second-id", "name": "Bob"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(get_response=mock_response)):
            result = await provider._resolve_profile_id(None)

        assert result == "first-id"
        assert provider._cached_profile_id == "first-id"

    @pytest.mark.asyncio
    async def test_resolve_cached_profile_skips_http(self, provider):
        provider._cached_profile_id = "cached-id"
        # If called with no voice, cached value should be used without HTTP
        result = await provider._resolve_profile_id(None)
        assert result == "cached-id"

    @pytest.mark.asyncio
    async def test_resolve_empty_profiles_raises_no_profile_error(self, provider):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(get_response=mock_response)):
            with pytest.raises(VoiceboxNoProfileError, match="no voice profiles"):
                await provider._resolve_profile_id(None)

    @pytest.mark.asyncio
    async def test_resolve_http_error_raises_voicebox_error(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxError, match="Failed to fetch Voicebox profiles"):
                await provider._resolve_profile_id(None)


class TestVoiceboxProviderSynthesize:
    """Test synthesis via /generate/stream."""

    @pytest.fixture
    def provider(self):
        provider = VoiceboxProvider(base_url="http://localhost:17493")
        provider._cached_profile_id = "test-profile"
        return provider

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_chunks(self, provider):
        wav = create_mock_wav_bytes()
        # Split into 3 chunks for streaming test
        chunk_size = len(wav) // 3
        chunks = [wav[i:i+chunk_size] for i in range(0, len(wav), chunk_size)]
        stream_response = _MockStreamResponse(status_code=200, chunks=chunks)

        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            collected = []
            async for chunk in provider.synthesize_stream("hello", voice="test-profile"):
                collected.append(chunk)

        assert len(collected) == len(chunks)
        assert b"".join(collected) == wav

    @pytest.mark.asyncio
    async def test_synthesize_returns_concatenated_bytes(self, provider):
        wav = create_mock_wav_bytes()
        stream_response = _MockStreamResponse(status_code=200, chunks=[wav])
        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("hello world", voice="test-profile")

        assert result == wav

    @pytest.mark.asyncio
    async def test_synthesize_404_raises_no_profile_error(self, provider):
        stream_response = _MockStreamResponse(status_code=404, body=b'{"detail":"Profile not found"}')
        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxNoProfileError):
                await provider.synthesize("hello", voice="missing")

    @pytest.mark.asyncio
    async def test_synthesize_503_raises_busy_error(self, provider):
        stream_response = _MockStreamResponse(status_code=503, body=b"busy")
        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxBusyError):
                await provider.synthesize("hello", voice="test-profile")

    @pytest.mark.asyncio
    async def test_synthesize_500_raises_voicebox_error(self, provider):
        stream_response = _MockStreamResponse(status_code=500, body=b"internal error")
        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxError, match="500"):
                await provider.synthesize("hello", voice="test-profile")

    @pytest.mark.asyncio
    async def test_synthesize_empty_audio_raises(self, provider):
        stream_response = _MockStreamResponse(status_code=200, chunks=[])
        mock_client = _make_async_client_mock(stream_response=stream_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxError, match="no audio bytes"):
                await provider.synthesize("hello", voice="test-profile")

    @pytest.mark.asyncio
    async def test_synthesize_timeout_raises(self, provider):
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxError, match="timed out"):
                await provider.synthesize("hello", voice="test-profile")


class TestVoiceboxProviderRecognize:
    """Test STT via /transcribe."""

    @pytest.fixture
    def provider(self):
        return VoiceboxProvider(base_url="http://localhost:17493")

    @pytest.mark.asyncio
    async def test_recognize_returns_text_and_duration(self, provider):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"text": "  hello world  ", "duration": 1.42}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(post_response=mock_response)):
            result = await provider.recognize(b"audio bytes", language="en")

        assert result["text"] == "hello world"
        assert result["duration"] == 1.42
        assert result["language"] == "en"

    @pytest.mark.asyncio
    async def test_recognize_202_raises_busy_error(self, provider):
        """Voicebox returns 202 while downloading whisper model."""
        mock_response = MagicMock(status_code=202)
        mock_response.text = '{"detail": {"message": "downloading"}}'
        mock_response.json.return_value = {"detail": {"message": "Whisper model downloading"}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=_make_async_client_mock(post_response=mock_response)):
            with pytest.raises(VoiceboxBusyError, match="downloading"):
                await provider.recognize(b"audio bytes")

    @pytest.mark.asyncio
    async def test_recognize_http_error_raises_voicebox_error(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceboxError, match="transcription error"):
                await provider.recognize(b"audio")
