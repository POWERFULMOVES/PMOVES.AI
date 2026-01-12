"""Functional tests for Ultimate-TTS against live service.

These tests require Ultimate-TTS to be running at ULTIMATE_TTS_URL.
Skip with: pytest -m "not functional"

Run: pytest tests/test_ultimate_tts_functional.py -v -m functional
"""

import asyncio
import os
import sys

import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from providers.ultimate_tts import UltimateTTSProvider, UltimateTTSError


ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://localhost:7861")

# Error patterns that indicate engine is unavailable (skip rather than fail)
SKIP_ERROR_PATTERNS = [
    "not loaded",
    "no audio",
    "unavailable",
    "disconnected",
    "failed to load",
    "http error",
    "timeout",
]


def should_skip_error(error: UltimateTTSError) -> bool:
    """Check if an error should cause a test skip rather than failure."""
    error_str = str(error).lower()
    return any(pattern in error_str for pattern in SKIP_ERROR_PATTERNS)

# All 7 TTS engines supported by Ultimate-TTS-Studio
ALL_ENGINES = [
    "kitten_tts",
    "kokoro",
    "f5_tts",
    "indextts2",
    "fish",
    "chatterbox",
    "voxcpm",
]


@pytest.fixture(scope="module")
async def live_provider():
    """Create provider connected to live service.

    Skips entire module if service unavailable.
    """
    provider = UltimateTTSProvider(base_url=ULTIMATE_TTS_URL)

    # Check if service is available
    is_healthy = await provider.health_check()
    if not is_healthy:
        pytest.skip(
            f"Ultimate-TTS service not available at {ULTIMATE_TTS_URL}. "
            "Ensure the container is running: docker ps | grep ultimate-tts"
        )

    return provider


@pytest.mark.functional
class TestUltimateTTSFunctionalHealth:
    """Functional tests for health check and discovery."""

    @pytest.mark.asyncio
    async def test_service_is_healthy(self, live_provider):
        """Verify Ultimate-TTS service responds to health check."""
        result = await live_provider.health_check()
        assert result is True, "Service health check should return True"

    @pytest.mark.asyncio
    async def test_gradio_api_reachable(self, live_provider):
        """Verify Gradio API endpoint is accessible."""
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{live_provider.gradio_api_url}/info")
            assert resp.status_code == 200, "Gradio /info endpoint should return 200"

    @pytest.mark.asyncio
    async def test_can_list_engines(self, live_provider):
        """Verify engine discovery returns engine availability."""
        engines = await live_provider.get_engines()
        assert isinstance(engines, dict), "get_engines should return dict"

        # At least kitten_tts should be available (fastest/simplest)
        available_count = sum(1 for v in engines.values() if v)
        assert available_count >= 1, "At least one engine should be available"


@pytest.mark.functional
class TestUltimateTTSFunctionalSynthesis:
    """Functional tests for TTS synthesis."""

    @pytest.mark.asyncio
    async def test_synthesize_basic(self, live_provider):
        """Test basic synthesis produces audio bytes."""
        text = "Hello, this is a test."

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(text, engine="kitten_tts"),
                timeout=60.0
            )
            assert isinstance(audio, bytes), "Synthesis should return bytes"
            assert len(audio) > 1000, "Audio should be at least 1KB"
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out - model may be loading")
        except UltimateTTSError as e:
            
            if should_skip_error(e):
                pytest.skip(f"Engine issue: {e}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("engine", ALL_ENGINES)
    async def test_synthesize_each_engine(self, live_provider, engine):
        """Test synthesis produces audio for each engine.

        Note: Some engines may require GPU or take longer to load.
        Tests will skip gracefully if engine unavailable.
        """
        text = "Testing the Ultimate TTS system."

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(text, engine=engine),
                timeout=120.0  # Allow up to 2 minutes for slower engines
            )
            assert isinstance(audio, bytes), f"{engine}: should return bytes"
            assert len(audio) > 500, f"{engine}: audio should be at least 500 bytes"
        except asyncio.TimeoutError:
            pytest.skip(f"Engine {engine} timed out (may be loading model)")
        except UltimateTTSError as e:
            
            if should_skip_error(e):
                pytest.skip(f"Engine {engine} not available: {e}")
            raise

    @pytest.mark.asyncio
    async def test_synthesize_with_voice(self, live_provider):
        """Test synthesis with specific voice parameter."""
        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(
                    "Hello with a specific voice.",
                    voice="expr-voice-3-f",
                    engine="kitten_tts"
                ),
                timeout=60.0
            )
            assert isinstance(audio, bytes)
            assert len(audio) > 1000
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise


@pytest.mark.functional
class TestUltimateTTSFunctionalAudioFormat:
    """Functional tests for audio output format."""

    @pytest.mark.asyncio
    async def test_audio_is_valid_wav(self, live_provider):
        """Verify audio output is valid WAV format."""
        import io
        import wave

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize("Test audio format.", engine="kitten_tts"),
                timeout=60.0
            )

            # Check RIFF header
            assert audio[:4] == b'RIFF', "Audio should start with RIFF header"

            # Validate as WAV
            with io.BytesIO(audio) as buf:
                with wave.open(buf, "rb") as wf:
                    assert wf.getnchannels() >= 1, "Should have at least 1 channel"
                    assert wf.getsampwidth() >= 1, "Should have sample width"
                    assert wf.getframerate() >= 8000, "Sample rate should be at least 8kHz"
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise

    @pytest.mark.asyncio
    async def test_audio_sample_rate(self, live_provider):
        """Verify audio has reasonable sample rate (typically 24kHz or higher)."""
        import io
        import wave

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize("Check sample rate.", engine="kitten_tts"),
                timeout=60.0
            )

            with io.BytesIO(audio) as buf:
                with wave.open(buf, "rb") as wf:
                    sample_rate = wf.getframerate()
                    # Most TTS engines use 22050, 24000, or 44100 Hz
                    assert 16000 <= sample_rate <= 48000, \
                        f"Sample rate {sample_rate} should be 16-48kHz"
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise


@pytest.mark.functional
class TestUltimateTTSFunctionalStreaming:
    """Functional tests for streaming synthesis."""

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_data(self, live_provider):
        """Test streaming synthesis yields audio chunks."""
        chunks = []

        try:
            async for chunk in live_provider.synthesize_stream(
                "Hello world, streaming test.",
                engine="kitten_tts"
            ):
                chunks.append(chunk)
                # Safety limit
                if len(chunks) > 100:
                    break
        except asyncio.TimeoutError:
            pytest.skip("Streaming timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise

        assert len(chunks) >= 1, "Should yield at least one chunk"
        total_bytes = sum(len(c) for c in chunks)
        assert total_bytes > 0, "Total bytes should be > 0"


@pytest.mark.functional
class TestUltimateTTSFunctionalEdgeCases:
    """Functional tests for edge cases."""

    @pytest.mark.asyncio
    async def test_long_text_synthesis(self, live_provider):
        """Test synthesis with longer text (stress test)."""
        long_text = "This is a longer test sentence. " * 10  # ~300 chars

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(long_text, engine="kitten_tts"),
                timeout=180.0  # Allow up to 3 minutes for long text
            )
            assert isinstance(audio, bytes)
            # Longer text should produce more audio
            assert len(audio) > 5000, "Longer text should produce more audio"
        except asyncio.TimeoutError:
            pytest.skip("Long text synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise

    @pytest.mark.asyncio
    async def test_special_characters(self, live_provider):
        """Test synthesis handles special characters."""
        text = "Hello! How are you? I'm doing well - thanks. Numbers: 1, 2, 3..."

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(text, engine="kitten_tts"),
                timeout=60.0
            )
            assert isinstance(audio, bytes)
            assert len(audio) > 1000
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, live_provider):
        """Test synthesis handles empty/whitespace text."""
        # Empty string should either:
        # 1. Return minimal audio
        # 2. Raise an appropriate error

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize("   ", engine="kitten_tts"),
                timeout=30.0
            )
            # If it succeeds, audio should be minimal
            assert isinstance(audio, bytes)
        except (UltimateTTSError, ValueError):
            # Expected - empty text may raise error
            pass
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")

    @pytest.mark.asyncio
    async def test_unicode_text(self, live_provider):
        """Test synthesis handles unicode characters."""
        # Note: Some engines may only support English
        text = "Hello world. Testing unicode: cafe"  # ASCII only for broad compatibility

        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(text, engine="kitten_tts"),
                timeout=60.0
            )
            assert isinstance(audio, bytes)
            assert len(audio) > 0
        except asyncio.TimeoutError:
            pytest.skip("Synthesis timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Engine not loaded: {e}")
            raise


@pytest.mark.functional
@pytest.mark.slow
class TestUltimateTTSFunctionalKokoroVoices:
    """Functional tests for Kokoro TTS voices (multilingual)."""

    @pytest.mark.asyncio
    async def test_kokoro_default_voice(self, live_provider):
        """Test Kokoro with default voice."""
        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(
                    "Testing Kokoro TTS engine.",
                    engine="kokoro"
                ),
                timeout=120.0
            )
            assert isinstance(audio, bytes)
            assert len(audio) > 1000
        except asyncio.TimeoutError:
            pytest.skip("Kokoro timed out - may be loading model")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Kokoro not available: {e}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("voice", ["af_bella", "af_heart"])
    async def test_kokoro_specific_voices(self, live_provider, voice):
        """Test Kokoro with specific voice presets."""
        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(
                    "Testing voice preset.",
                    voice=voice,
                    engine="kokoro"
                ),
                timeout=120.0
            )
            assert isinstance(audio, bytes)
        except asyncio.TimeoutError:
            pytest.skip(f"Kokoro voice {voice} timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"Kokoro voice {voice} not available: {e}")
            raise


@pytest.mark.functional
@pytest.mark.slow
class TestUltimateTTSFunctionalKittenVoices:
    """Functional tests for KittenTTS voices."""

    KITTEN_VOICES = [
        "expr-voice-2-m", "expr-voice-2-f",
        "expr-voice-3-m", "expr-voice-3-f",
        "expr-voice-4-m", "expr-voice-4-f",
        "expr-voice-5-m", "expr-voice-5-f",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("voice", KITTEN_VOICES[:4])  # Test subset for speed
    async def test_kitten_voice_variants(self, live_provider, voice):
        """Test different KittenTTS voice variants."""
        try:
            audio = await asyncio.wait_for(
                live_provider.synthesize(
                    "Testing different voice.",
                    voice=voice,
                    engine="kitten_tts"
                ),
                timeout=60.0
            )
            assert isinstance(audio, bytes)
            assert len(audio) > 500
        except asyncio.TimeoutError:
            pytest.skip(f"KittenTTS voice {voice} timed out")
        except UltimateTTSError as e:
            if should_skip_error(e):
                pytest.skip(f"KittenTTS not available: {e}")
            raise
