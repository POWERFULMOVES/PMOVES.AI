"""Unit tests for OmniVoiceProvider with mocks.

Tests the OmniVoiceProvider class without requiring the live OmniVoice service.
Uses mocked httpx responses to simulate the /synthesize and /healthz endpoints.

Mirrors the structure of test_voicebox.py: a fake/mocked AsyncClient transport
(no live server), asserting the X-OmniVoice-Token header is sent when
OMNIVOICE_TOKEN is set, the voice-design -> instruct mapping, WAV bytes
returned, and error raised on non-200.
"""

import io
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

from providers.omnivoice import (
    OmniVoiceBusyError,
    OmniVoiceError,
    OmniVoiceProvider,
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


def _make_async_client_mock(get_response=None, post_response=None):
    """Build an AsyncClient mock that supports get / post / context manager."""
    mock_client = AsyncMock()
    if get_response is not None:
        mock_client.get = AsyncMock(return_value=get_response)
    if post_response is not None:
        mock_client.post = AsyncMock(return_value=post_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestOmniVoiceProviderInit:
    """Test provider initialization."""

    def test_init_default_url(self):
        provider = OmniVoiceProvider()
        assert provider.base_url == "http://127.0.0.1:8002"
        assert provider.synthesize_endpoint == "http://127.0.0.1:8002/synthesize"
        assert provider.health_endpoint == "http://127.0.0.1:8002/healthz"

    def test_init_custom_url_strips_trailing_slash(self):
        provider = OmniVoiceProvider(base_url="http://omnivoice:8002/")
        assert provider.base_url == "http://omnivoice:8002"
        assert provider.synthesize_endpoint == "http://omnivoice:8002/synthesize"

    def test_init_no_token_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("OMNIVOICE_TOKEN", raising=False)
        provider = OmniVoiceProvider()
        assert provider._token is None
        assert provider._auth_headers() == {}

    def test_init_token_from_env(self, monkeypatch):
        monkeypatch.setenv("OMNIVOICE_TOKEN", "s3cret")
        provider = OmniVoiceProvider()
        assert provider._token == "s3cret"
        assert provider._auth_headers() == {"X-OmniVoice-Token": "s3cret"}


class TestOmniVoiceProviderHealthCheck:
    """Test the simple bool health_check for the gateway aggregator."""

    @pytest.fixture
    def provider(self):
        return OmniVoiceProvider(base_url="http://127.0.0.1:8002")

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


class TestOmniVoiceProviderSynthesize:
    """Test synthesis via /synthesize."""

    @pytest.fixture
    def provider(self, monkeypatch):
        monkeypatch.delenv("OMNIVOICE_TOKEN", raising=False)
        return OmniVoiceProvider(base_url="http://127.0.0.1:8002")

    @pytest.mark.asyncio
    async def test_synthesize_returns_wav_bytes(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("hello world")

        assert result == wav

    @pytest.mark.asyncio
    async def test_synthesize_sends_token_header_when_set(self, monkeypatch):
        monkeypatch.setenv("OMNIVOICE_TOKEN", "tok-123")
        provider = OmniVoiceProvider(base_url="http://127.0.0.1:8002")
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello")

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"]["X-OmniVoice-Token"] == "tok-123"

    @pytest.mark.asyncio
    async def test_synthesize_omits_token_header_when_unset(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello")

        _, kwargs = mock_client.post.call_args
        assert "X-OmniVoice-Token" not in kwargs["headers"]

    @pytest.mark.asyncio
    async def test_synthesize_maps_instruct_kwarg_to_payload(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello", instruct="calm, slow, low pitch")

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["instruct"] == "calm, slow, low pitch"

    @pytest.mark.asyncio
    async def test_synthesize_maps_voice_design_kwarg_to_instruct(self, provider):
        """The gateway voice-design attribute maps onto the server's instruct."""
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello", voice_design="excited, fast")

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["instruct"] == "excited, fast"

    @pytest.mark.asyncio
    async def test_synthesize_maps_voice_to_ref_audio(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello", voice="darkxside")

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["ref_audio"] == "darkxside"

    @pytest.mark.asyncio
    async def test_synthesize_drops_none_values(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.synthesize("hello")

        _, kwargs = mock_client.post.call_args
        # Only `text` should be present when no optional kwargs are passed.
        assert kwargs["json"] == {"text": "hello"}

    @pytest.mark.asyncio
    async def test_synthesize_503_raises_busy_error(self, provider):
        mock_response = MagicMock(status_code=503, content=b"model not loaded yet")
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceBusyError):
                await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_401_raises_error(self, provider):
        mock_response = MagicMock(status_code=401, content=b'{"detail":"unauthorized"}')
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceError, match="401"):
                await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_500_raises_error(self, provider):
        mock_response = MagicMock(status_code=500, content=b"synthesis failed")
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceError, match="500"):
                await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_empty_audio_raises(self, provider):
        mock_response = MagicMock(status_code=200, content=b"")
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceError, match="no audio bytes"):
                await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_timeout_raises(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceError, match="timed out"):
                await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_connect_error_raises(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OmniVoiceError, match="HTTP error"):
                await provider.synthesize("hello")


class TestOmniVoiceProviderStream:
    """Test the single-chunk streaming wrapper."""

    @pytest.fixture
    def provider(self, monkeypatch):
        monkeypatch.delenv("OMNIVOICE_TOKEN", raising=False)
        return OmniVoiceProvider(base_url="http://127.0.0.1:8002")

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_full_wav(self, provider):
        wav = create_mock_wav_bytes()
        mock_response = MagicMock(status_code=200, content=wav)
        mock_client = _make_async_client_mock(post_response=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            collected = [chunk async for chunk in provider.synthesize_stream("hello")]

        assert collected == [wav]


class TestOmniVoiceProviderRecognize:
    """OmniVoice is TTS-only — recognize should raise NotImplementedError."""

    @pytest.mark.asyncio
    async def test_recognize_not_implemented(self):
        provider = OmniVoiceProvider(base_url="http://127.0.0.1:8002")
        with pytest.raises(NotImplementedError):
            await provider.recognize(b"audio")
