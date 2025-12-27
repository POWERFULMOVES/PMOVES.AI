"""Tests for Flute Gateway API endpoints."""

import io
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables before importing
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("FLUTE_API_KEY", "test-api-key")

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Check if all required dependencies are available
try:
    import prometheus_client
    import httpx
    import websockets
    from fastapi.testclient import TestClient
    DEPS_AVAILABLE = True
except ImportError as e:
    DEPS_AVAILABLE = False
    DEPS_ERROR = str(e)

# Skip decorator for tests requiring full dependencies
requires_deps = pytest.mark.skipif(
    not DEPS_AVAILABLE,
    reason=f"Missing test dependencies: {DEPS_ERROR if not DEPS_AVAILABLE else ''}"
)


@requires_deps
class TestHealthEndpoint:
    """Tests for /healthz endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for all health tests."""
        # Mock providers at module level before app creation
        self.mock_vibevoice = MagicMock()
        self.mock_vibevoice.health_check = AsyncMock(return_value=True)

        self.mock_whisper = MagicMock()
        self.mock_whisper.health_check = AsyncMock(return_value=True)

        with patch("main.vibevoice_provider", self.mock_vibevoice), \
             patch("main.whisper_provider", self.mock_whisper), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_health_check_returns_200(self):
        """Health endpoint returns 200 with provider status."""
        response = self.client.get("/healthz")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "providers" in data
        assert "timestamp" in data

    def test_health_check_includes_providers(self):
        """Health check includes vibevoice and whisper status."""
        response = self.client.get("/healthz")
        data = response.json()

        assert "vibevoice" in data["providers"]
        assert "whisper" in data["providers"]

    def test_health_check_shows_nats_status(self):
        """Health check includes NATS connection status."""
        response = self.client.get("/healthz")
        data = response.json()

        assert "nats" in data
        # With nats_client=None, should be disconnected
        assert data["nats"] == "disconnected"


@requires_deps
class TestConfigEndpoint:
    """Tests for /v1/voice/config endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for config tests."""
        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_config_returns_200(self):
        """Config endpoint returns 200 with service configuration."""
        response = self.client.get("/v1/voice/config")
        assert response.status_code == 200

    def test_config_contains_providers(self):
        """Config includes list of available providers."""
        response = self.client.get("/v1/voice/config")
        data = response.json()

        assert "providers" in data
        assert "vibevoice" in data["providers"]
        assert "whisper" in data["providers"]

    def test_config_contains_features(self):
        """Config includes feature flags."""
        response = self.client.get("/v1/voice/config")
        data = response.json()

        assert "features" in data
        assert "tts_batch" in data["features"]
        assert "stt_batch" in data["features"]
        assert "personas" in data["features"]

    def test_config_contains_audio_settings(self):
        """Config includes audio format settings."""
        response = self.client.get("/v1/voice/config")
        data = response.json()

        assert data["sample_rate"] == 24000
        assert data["format"] == "pcm16"


@requires_deps
class TestApiKeyAuthentication:
    """Tests for API key authentication."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for auth tests."""
        self.mock_vibevoice = MagicMock()
        self.mock_vibevoice.health_check = AsyncMock(return_value=True)
        self.mock_vibevoice.synthesize = AsyncMock(return_value=b"\x00" * 48000)

        with patch("main.vibevoice_provider", self.mock_vibevoice), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_synthesize_requires_api_key(self):
        """Synthesize endpoint requires valid API key."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello world"}
        )
        assert response.status_code == 401

    def test_synthesize_rejects_invalid_key(self):
        """Synthesize endpoint rejects invalid API key."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello world"},
            headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_synthesize_accepts_valid_key(self):
        """Synthesize endpoint accepts valid API key."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello world"},
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200

    def test_recognize_requires_api_key(self):
        """Recognize endpoint requires valid API key."""
        audio_data = b"\x00" * 1000  # Dummy audio
        response = self.client.post(
            "/v1/voice/recognize",
            files={"audio": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        )
        assert response.status_code == 401

    def test_personas_requires_api_key(self):
        """Personas endpoint requires valid API key."""
        response = self.client.get("/v1/voice/personas")
        assert response.status_code == 401


@requires_deps
class TestSynthesizeEndpoint:
    """Tests for /v1/voice/synthesize endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for TTS tests."""
        self.mock_vibevoice = MagicMock()
        self.mock_vibevoice.health_check = AsyncMock(return_value=True)
        self.mock_vibevoice.synthesize = AsyncMock(return_value=b"\x00" * 48000)

        with patch("main.vibevoice_provider", self.mock_vibevoice), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_synthesize_returns_audio_metadata(self):
        """Synthesize returns audio duration and format."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello world"},
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200

        data = response.json()
        assert "duration_seconds" in data
        assert "sample_rate" in data
        assert data["sample_rate"] == 24000
        assert data["format"] == "pcm16"

    def test_synthesize_calls_provider(self):
        """Synthesize calls vibevoice provider with text."""
        self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello world"},
            headers={"X-API-Key": "test-api-key"}
        )
        self.mock_vibevoice.synthesize.assert_called_once()

    def test_synthesize_handles_empty_text(self):
        """Synthesize handles empty text (provider-dependent behavior)."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": ""},
            headers={"X-API-Key": "test-api-key"}
        )
        # Empty text may be accepted (provider handles it) or rejected
        assert response.status_code in [200, 400, 422]

    def test_synthesize_unavailable_provider(self):
        """Synthesize returns error for unavailable provider."""
        response = self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello", "provider": "nonexistent"},
            headers={"X-API-Key": "test-api-key"}
        )
        # May return 400 (Bad Request) or 500 if exception bubbles up
        assert response.status_code in [400, 500]

    def test_synthesize_respects_voice_parameter(self):
        """Synthesize passes voice parameter to provider."""
        self.client.post(
            "/v1/voice/synthesize",
            json={"text": "Hello", "voice": "custom-voice"},
            headers={"X-API-Key": "test-api-key"}
        )
        call_args = self.mock_vibevoice.synthesize.call_args
        assert call_args.kwargs.get("voice") == "custom-voice"

    def test_synthesize_audio_returns_wav_bytes(self):
        """Synthesize/audio returns audio/wav payload."""
        response = self.client.post(
            "/v1/voice/synthesize/audio",
            json={"text": "Hello world", "output_format": "wav"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("audio/wav")
        assert len(response.content) > 44  # WAV header + frames

    def test_synthesize_audio_rejects_empty_audio(self):
        """Synthesize/audio must not return a header-only WAV on upstream failures."""
        self.mock_vibevoice.synthesize = AsyncMock(return_value=b"")
        response = self.client.post(
            "/v1/voice/synthesize/audio",
            json={"text": "Hello world", "output_format": "wav"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 502


@requires_deps
class TestRecognizeEndpoint:
    """Tests for /v1/voice/recognize endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for STT tests."""
        self.mock_whisper = MagicMock()
        self.mock_whisper.health_check = AsyncMock(return_value=True)
        self.mock_whisper.recognize = AsyncMock(return_value={
            "text": "Hello world",
            "confidence": 0.95,
            "language": "en"
        })

        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", self.mock_whisper), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_recognize_returns_transcription(self):
        """Recognize returns transcribed text."""
        audio_data = b"\x00" * 1000
        response = self.client.post(
            "/v1/voice/recognize",
            files={"audio": ("test.wav", io.BytesIO(audio_data), "audio/wav")},
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["text"] == "Hello world"
        assert data["confidence"] == 0.95
        assert data["language"] == "en"

    def test_recognize_calls_provider(self):
        """Recognize calls whisper provider with audio data."""
        audio_data = b"\x00" * 1000
        self.client.post(
            "/v1/voice/recognize",
            files={"audio": ("test.wav", io.BytesIO(audio_data), "audio/wav")},
            headers={"X-API-Key": "test-api-key"}
        )
        self.mock_whisper.recognize.assert_called_once()

    def test_recognize_passes_language(self):
        """Recognize passes language parameter to provider."""
        audio_data = b"\x00" * 1000
        self.client.post(
            "/v1/voice/recognize",
            files={"audio": ("test.wav", io.BytesIO(audio_data), "audio/wav")},
            data={"language": "es"},
            headers={"X-API-Key": "test-api-key"}
        )
        call_args = self.mock_whisper.recognize.call_args
        assert call_args.kwargs.get("language") == "es"


@requires_deps
class TestPersonasEndpoints:
    """Tests for voice personas endpoints."""

    @staticmethod
    def _make_mock_httpx_class(response_data):
        """Create a mock httpx.AsyncClient class that returns specific data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, *args, **kwargs):
                return mock_response

        return MockAsyncClient

    def test_list_personas_returns_list(self):
        """List personas returns array of personas."""
        mock_data = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "slug": "narrator",
                "name": "Narrator",
                "voice_provider": "vibevoice",
                "is_active": True
            }
        ]

        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None), \
             patch("main.httpx.AsyncClient", self._make_mock_httpx_class(mock_data)):
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app)

            response = client.get(
                "/v1/voice/personas",
                headers={"X-API-Key": "test-api-key"}
            )
            assert response.status_code == 200

            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["slug"] == "narrator"

    def test_get_persona_by_id(self):
        """Get persona by ID returns single persona."""
        mock_data = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "slug": "narrator",
                "name": "Narrator"
            }
        ]

        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None), \
             patch("main.httpx.AsyncClient", self._make_mock_httpx_class(mock_data)):
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app)

            response = client.get(
                "/v1/voice/personas/123e4567-e89b-12d3-a456-426614174000",
                headers={"X-API-Key": "test-api-key"}
            )
            assert response.status_code == 200

    def test_get_persona_not_found(self):
        """Get non-existent persona returns 404."""
        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None), \
             patch("main.httpx.AsyncClient", self._make_mock_httpx_class([])):
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app)

            response = client.get(
                "/v1/voice/personas/nonexistent",
                headers={"X-API-Key": "test-api-key"}
            )
            assert response.status_code == 404


@requires_deps
class TestMetricsEndpoint:
    """Tests for /metrics Prometheus endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mocks for metrics tests."""
        with patch("main.vibevoice_provider", None), \
             patch("main.whisper_provider", None), \
             patch("main.nats_client", None):
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
            yield

    def test_metrics_returns_prometheus_format(self):
        """Metrics endpoint returns Prometheus format."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or \
               "text/plain" in str(response.headers.get("content-type", ""))

    def test_metrics_includes_request_counter(self):
        """Metrics includes request counters."""
        # Make a request first
        self.client.get("/healthz")

        response = self.client.get("/metrics")
        assert b"flute_requests_total" in response.content


class TestProviders:
    """Tests for voice provider classes."""

    def test_vibevoice_provider_initialization(self):
        """VibeVoiceProvider initializes with correct URLs."""
        from providers.vibevoice import VibeVoiceProvider

        provider = VibeVoiceProvider("http://localhost:3000")
        assert provider.base_url == "http://localhost:3000"
        assert provider.ws_url == "ws://localhost:3000/stream"
        assert provider.config_url == "http://localhost:3000/config"

    def test_vibevoice_https_to_wss(self):
        """VibeVoiceProvider converts https to wss."""
        from providers.vibevoice import VibeVoiceProvider

        provider = VibeVoiceProvider("https://secure.example.com")
        assert provider.ws_url == "wss://secure.example.com/stream"

    def test_whisper_provider_initialization(self):
        """WhisperProvider initializes with correct URLs."""
        from providers.whisper import WhisperProvider

        provider = WhisperProvider("http://localhost:8078")
        assert provider.base_url == "http://localhost:8078"
        assert provider.transcribe_endpoint == "http://localhost:8078/transcribe"
        assert provider.health_endpoint == "http://localhost:8078/healthz"

    @pytest.mark.asyncio
    async def test_vibevoice_recognize_not_implemented(self):
        """VibeVoiceProvider.recognize raises NotImplementedError."""
        from providers.vibevoice import VibeVoiceProvider

        provider = VibeVoiceProvider("http://localhost:3000")
        with pytest.raises(NotImplementedError):
            await provider.recognize(b"audio")

    @pytest.mark.asyncio
    async def test_whisper_synthesize_not_implemented(self):
        """WhisperProvider.synthesize raises NotImplementedError."""
        from providers.whisper import WhisperProvider

        provider = WhisperProvider("http://localhost:8078")
        with pytest.raises(NotImplementedError):
            await provider.synthesize("text")
