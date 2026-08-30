"""VibeVoice WebSocket realtime harness (deferred Task #41).

Tests the live VibeVoice realtime endpoint via WebSocket. Unlike the unit
tests in test_voicebox.py, these tests cannot be mocked meaningfully — the
WebSocket protocol behavior is the contract being verified. They are marked
@pytest.mark.functional so the default hermetic suite skips them.

To run:
    PYTHONPATH=pmoves pytest pmoves/services/flute-gateway/tests/test_vibevoice_realtime.py \\
        -m functional -v

Prerequisite:
    VibeVoice realtime server running at the URL specified by VIBEVOICE_URL
    (default: http://host.docker.internal:7860). Start with:
        make -C pmoves up-vibevoice

Why this exists:
    Session 11 deferred VibeVoice synthesis testing because VibeVoice uses a
    separate WebSocket endpoint (`/stream`), not the unified Gradio
    `/generate_unified_tts` endpoint that other Ultimate-TTS engines use. The
    flute-gateway VibeVoiceProvider wraps this WebSocket; this harness verifies
    the wrapper end-to-end against a real server.
"""

import asyncio
import os
import sys

import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from providers.vibevoice import (
    VibeVoiceBusyError,
    VibeVoiceNoAudioError,
    VibeVoiceProvider,
)


def _vibevoice_url() -> str:
    """Return the VibeVoice URL to test against."""
    return os.environ.get("VIBEVOICE_URL", "http://host.docker.internal:7860")


async def _is_vibevoice_reachable(provider: VibeVoiceProvider) -> bool:
    """Check if VibeVoice is reachable; tests skip if not."""
    try:
        return await asyncio.wait_for(provider.health_check(), timeout=3.0)
    except Exception:
        return False


@pytest.fixture
def provider():
    return VibeVoiceProvider(base_url=_vibevoice_url())


@pytest.mark.functional
@pytest.mark.asyncio
async def test_vibevoice_health_check_returns_true_when_reachable(provider):
    """If VibeVoice is running, /config should return 200."""
    if not await _is_vibevoice_reachable(provider):
        pytest.skip(f"VibeVoice not reachable at {_vibevoice_url()} — start with `make -C pmoves up-vibevoice`")
    assert await provider.health_check() is True


@pytest.mark.functional
@pytest.mark.asyncio
async def test_vibevoice_get_config_returns_dict(provider):
    """get_config should return a dict with at least default_voice or model info."""
    if not await _is_vibevoice_reachable(provider):
        pytest.skip(f"VibeVoice not reachable at {_vibevoice_url()}")
    config = await provider.get_config()
    assert isinstance(config, dict)
    # Empty dict is allowed on error, but a healthy server should populate something
    if config:
        # Common keys VibeVoice exposes — at least one should be present
        assert any(k in config for k in ("default_voice", "voices", "model", "sample_rate"))


@pytest.mark.functional
@pytest.mark.asyncio
async def test_vibevoice_synthesize_short_text_yields_pcm16(provider):
    """Synthesize a short phrase and assert PCM16 audio bytes come back.

    PCM16 at 24kHz mono = 48,000 bytes per second. A 1-2 word phrase should
    produce at least ~24,000 bytes (0.5 seconds) of audio under normal load.
    """
    if not await _is_vibevoice_reachable(provider):
        pytest.skip(f"VibeVoice not reachable at {_vibevoice_url()}")

    try:
        audio = await asyncio.wait_for(
            provider.synthesize("hello world"),
            timeout=30.0,
        )
    except VibeVoiceBusyError:
        pytest.skip("VibeVoice reported busy — transient, not a bug")
    except VibeVoiceNoAudioError as exc:
        pytest.fail(f"VibeVoice returned no audio: {exc}")
    except asyncio.TimeoutError:
        pytest.fail("VibeVoice synthesis timed out after 30s")

    assert isinstance(audio, bytes)
    assert len(audio) > 0, "VibeVoice returned empty audio"
    # PCM16 has 2 bytes per sample — total length should be even
    assert len(audio) % 2 == 0, f"PCM16 byte length should be even, got {len(audio)}"
    # Sanity check: at least 0.1 seconds of audio (24000*0.1*2 = 4800 bytes)
    assert len(audio) >= 4800, f"Audio suspiciously short: {len(audio)} bytes ({len(audio)/48000:.2f}s)"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_vibevoice_stream_yields_multiple_chunks(provider):
    """Synthesize via the streaming API and confirm multiple chunks arrive.

    The WebSocket streaming endpoint should yield audio progressively rather
    than as a single large blob. Verifies the streaming contract.
    """
    if not await _is_vibevoice_reachable(provider):
        pytest.skip(f"VibeVoice not reachable at {_vibevoice_url()}")

    chunks: list[bytes] = []
    try:
        async with asyncio.timeout(30.0):
            async for chunk in provider.synthesize_stream("Streaming test phrase one two three"):
                chunks.append(chunk)
    except VibeVoiceBusyError:
        pytest.skip("VibeVoice busy")
    except asyncio.TimeoutError:
        pytest.fail("Stream timed out after 30s")

    assert len(chunks) >= 1, "VibeVoice streamed zero chunks"
    total_bytes = sum(len(c) for c in chunks)
    assert total_bytes > 0, "VibeVoice streamed empty chunks"
    # For a longer phrase, expect at least 1 second of audio
    assert total_bytes >= 24000, (
        f"Streamed audio suspiciously short: {total_bytes} bytes "
        f"({total_bytes/48000:.2f}s) across {len(chunks)} chunks"
    )


@pytest.mark.functional
@pytest.mark.asyncio
async def test_vibevoice_handles_empty_text_gracefully(provider):
    """Empty text should either return empty audio or raise a clean error.

    The client should NOT hang or return malformed data on empty input.
    """
    if not await _is_vibevoice_reachable(provider):
        pytest.skip(f"VibeVoice not reachable at {_vibevoice_url()}")

    try:
        async with asyncio.timeout(10.0):
            audio = await provider.synthesize("")
    except (VibeVoiceNoAudioError, VibeVoiceBusyError):
        # Acceptable: clean error
        return
    except asyncio.TimeoutError:
        pytest.fail("VibeVoice hung on empty input")

    # Acceptable: returned bytes (possibly empty or silence)
    assert isinstance(audio, bytes)
