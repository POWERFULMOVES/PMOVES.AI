#!/usr/bin/env python3
"""Audio Playback Functional Tests for Ultimate-TTS and Flute-Gateway.

These tests:
1. Generate actual audio from TTS services
2. Save audio files to disk for manual verification
3. Validate audio properties (format, duration, non-silence)
4. Print clear diagnostics for debugging

Run:
    # Quick test (saves audio files)
    python tests/test_audio_playback.py

    # Full pytest run
    pytest tests/test_audio_playback.py -v -s

Audio files saved to: /tmp/pmoves-tts-test/

Requirements:
    pip install httpx scipy numpy
"""

import asyncio
import io
import os
import struct
import sys
import wave
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


# Output directory for test audio files
TEST_OUTPUT_DIR = Path("/tmp/pmoves-tts-test")


class AudioProperties(NamedTuple):
    """Properties of an audio file."""
    channels: int
    sample_width: int  # bytes per sample
    sample_rate: int
    num_frames: int
    duration_seconds: float
    file_size: int
    peak_amplitude: float
    rms_amplitude: float
    is_silence: bool


def ensure_output_dir() -> Path:
    """Create output directory for test audio files."""
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_OUTPUT_DIR


def analyze_wav_bytes(audio_bytes: bytes) -> AudioProperties:
    """Analyze WAV audio and return properties.

    Args:
        audio_bytes: Raw WAV file bytes

    Returns:
        AudioProperties with format info and amplitude analysis
    """
    with io.BytesIO(audio_bytes) as buf:
        with wave.open(buf, "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            duration = num_frames / sample_rate

            # Read all frames
            raw_data = wf.readframes(num_frames)

    # Calculate amplitude statistics
    if sample_width == 2:  # 16-bit audio
        fmt = f"<{len(raw_data) // 2}h"
        samples = struct.unpack(fmt, raw_data)
    elif sample_width == 1:  # 8-bit audio
        samples = [s - 128 for s in raw_data]  # Convert to signed
    else:
        samples = [0]  # Unknown format

    if samples:
        peak = max(abs(s) for s in samples)
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        # Normalize to 0-1 range
        max_val = 32767 if sample_width == 2 else 127
        peak_normalized = peak / max_val
        rms_normalized = rms / max_val
    else:
        peak_normalized = 0.0
        rms_normalized = 0.0

    # Consider audio "silence" if RMS is very low
    is_silence = rms_normalized < 0.01  # Less than 1% RMS

    return AudioProperties(
        channels=channels,
        sample_width=sample_width,
        sample_rate=sample_rate,
        num_frames=num_frames,
        duration_seconds=duration,
        file_size=len(audio_bytes),
        peak_amplitude=peak_normalized,
        rms_amplitude=rms_normalized,
        is_silence=is_silence,
    )


def save_audio_file(audio_bytes: bytes, name: str) -> Path:
    """Save audio bytes to a file.

    Args:
        audio_bytes: Raw WAV audio data
        name: Base name for the file (without extension)

    Returns:
        Path to saved file
    """
    output_dir = ensure_output_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{name}_{timestamp}.wav"
    filepath = output_dir / filename

    filepath.write_bytes(audio_bytes)
    return filepath


def print_audio_analysis(props: AudioProperties, filepath: Path | None = None) -> None:
    """Print detailed audio analysis to stdout.

    Args:
        props: Audio properties to display
        filepath: Optional path to saved file
    """
    print("\n" + "=" * 60)
    print("AUDIO ANALYSIS")
    print("=" * 60)

    if filepath:
        print(f"File: {filepath}")
        print(f"Size: {props.file_size:,} bytes")

    print(f"\nFormat:")
    print(f"  Channels:    {props.channels}")
    print(f"  Sample Rate: {props.sample_rate} Hz")
    print(f"  Bit Depth:   {props.sample_width * 8} bits")
    print(f"  Duration:    {props.duration_seconds:.2f} seconds")
    print(f"  Frames:      {props.num_frames:,}")

    print(f"\nAmplitude Analysis:")
    print(f"  Peak:        {props.peak_amplitude:.4f} ({props.peak_amplitude * 100:.1f}%)")
    print(f"  RMS:         {props.rms_amplitude:.4f} ({props.rms_amplitude * 100:.1f}%)")

    if props.is_silence:
        print("\n  ⚠️  WARNING: Audio appears to be SILENCE!")
        print("     RMS amplitude is below 1% - no audible content detected.")
    else:
        print("\n  ✓ Audio contains audible content")

    print("=" * 60)


async def test_ultimate_tts_direct() -> bool:
    """Test Ultimate-TTS directly via Gradio API.

    Returns:
        True if test passed, False otherwise
    """
    try:
        from providers.ultimate_tts import UltimateTTSProvider, UltimateTTSError
    except ImportError:
        print("ERROR: Cannot import UltimateTTSProvider")
        print("Run this from the flute-gateway service directory")
        return False

    url = os.getenv("ULTIMATE_TTS_URL", "http://localhost:7861")
    provider = UltimateTTSProvider(base_url=url)

    print(f"\n🔍 Testing Ultimate-TTS at {url}")

    # Health check
    is_healthy = await provider.health_check()
    if not is_healthy:
        print(f"❌ Ultimate-TTS service not responding at {url}")
        return False
    print("✓ Service is healthy")

    # Get available engines
    engines = await provider.get_engines()
    available = [e for e, v in engines.items() if v]
    print(f"✓ Available engines: {available}")

    if not available:
        print("❌ No TTS engines available")
        return False

    # Test synthesis with first available engine
    test_engine = available[0]
    test_text = "Hello! This is a test of the text to speech system. Can you hear me?"

    print(f"\n📢 Synthesizing with {test_engine}...")
    print(f"   Text: \"{test_text}\"")

    try:
        audio_bytes = await asyncio.wait_for(
            provider.synthesize(test_text, engine=test_engine),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        print("❌ Synthesis timed out after 120 seconds")
        return False
    except UltimateTTSError as e:
        print(f"❌ Synthesis error: {e}")
        return False

    # Validate audio
    if not audio_bytes:
        print("❌ No audio data returned")
        return False

    if audio_bytes[:4] != b'RIFF':
        print(f"❌ Invalid WAV format (header: {audio_bytes[:4]!r})")
        return False

    # Analyze and save
    props = analyze_wav_bytes(audio_bytes)
    filepath = save_audio_file(audio_bytes, f"ultimate_tts_{test_engine}")
    print_audio_analysis(props, filepath)

    if props.is_silence:
        print("\n❌ TEST FAILED: Audio is silent")
        return False

    if props.duration_seconds < 0.5:
        print(f"\n❌ TEST FAILED: Audio too short ({props.duration_seconds:.2f}s)")
        return False

    print(f"\n✓ TEST PASSED: Audio saved to {filepath}")
    print(f"  Play with: aplay {filepath}")
    print(f"  Or copy:   scp {filepath} local:~/")

    return True


async def test_flute_gateway_prosodic() -> bool:
    """Test Flute-Gateway prosodic TTS endpoint.

    Returns:
        True if test passed, False otherwise
    """
    import httpx

    flute_url = os.getenv("FLUTE_URL", "http://localhost:8055")
    api_key = os.getenv("FLUTE_API_KEY", "test-key")

    print(f"\n🔍 Testing Flute-Gateway at {flute_url}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Health check
        try:
            resp = await client.get(f"{flute_url}/healthz")
            if resp.status_code != 200:
                print(f"❌ Flute-Gateway not healthy (status {resp.status_code})")
                return False
            health = resp.json()
            print(f"✓ Service healthy: {health}")
        except httpx.ConnectError:
            print(f"❌ Cannot connect to Flute-Gateway at {flute_url}")
            return False

        # Test prosodic synthesis
        test_text = "Hello! This is a test of the prosodic synthesis system. Natural pauses should be added."

        print(f"\n📢 Synthesizing prosodic audio...")
        print(f"   Text: \"{test_text}\"")

        try:
            resp = await client.post(
                f"{flute_url}/v1/voice/synthesize/prosodic",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "text": test_text,
                    "voice": "default",
                    "format": "wav"
                }
            )
        except httpx.TimeoutException:
            print("❌ Request timed out")
            return False

        if resp.status_code != 200:
            print(f"❌ Synthesis failed (status {resp.status_code})")
            print(f"   Response: {resp.text[:500]}")
            return False

        audio_bytes = resp.content

        if not audio_bytes:
            print("❌ No audio data returned")
            return False

        if audio_bytes[:4] != b'RIFF':
            print(f"❌ Invalid WAV format (header: {audio_bytes[:4]!r})")
            print(f"   First 100 bytes: {audio_bytes[:100]!r}")
            return False

        # Analyze and save
        props = analyze_wav_bytes(audio_bytes)
        filepath = save_audio_file(audio_bytes, "flute_prosodic")
        print_audio_analysis(props, filepath)

        if props.is_silence:
            print("\n❌ TEST FAILED: Audio is silent")
            return False

        print(f"\n✓ TEST PASSED: Audio saved to {filepath}")
        print(f"  Play with: aplay {filepath}")

        return True


async def test_all_engines() -> dict[str, bool]:
    """Test all available TTS engines and save audio for each.

    Returns:
        Dict mapping engine name to test result
    """
    try:
        from providers.ultimate_tts import UltimateTTSProvider, UltimateTTSError
    except ImportError:
        print("ERROR: Cannot import UltimateTTSProvider")
        return {}

    url = os.getenv("ULTIMATE_TTS_URL", "http://localhost:7861")
    provider = UltimateTTSProvider(base_url=url)

    engines = await provider.get_engines()
    available = [e for e, v in engines.items() if v]

    results = {}
    test_text = "Testing this TTS engine."

    for engine in available:
        print(f"\n{'=' * 40}")
        print(f"Testing engine: {engine}")
        print('=' * 40)

        try:
            audio_bytes = await asyncio.wait_for(
                provider.synthesize(test_text, engine=engine),
                timeout=120.0
            )

            if audio_bytes and audio_bytes[:4] == b'RIFF':
                props = analyze_wav_bytes(audio_bytes)
                filepath = save_audio_file(audio_bytes, f"engine_{engine}")

                if not props.is_silence and props.duration_seconds >= 0.3:
                    print(f"✓ {engine}: PASS ({props.duration_seconds:.1f}s, {filepath})")
                    results[engine] = True
                else:
                    print(f"❌ {engine}: FAIL (silence or too short)")
                    results[engine] = False
            else:
                print(f"❌ {engine}: FAIL (invalid format)")
                results[engine] = False

        except asyncio.TimeoutError:
            print(f"⏱️ {engine}: TIMEOUT")
            results[engine] = False
        except UltimateTTSError as e:
            print(f"❌ {engine}: ERROR - {e}")
            results[engine] = False

    return results


async def main():
    """Run all audio playback tests."""
    print("=" * 60)
    print("PMOVES TTS Audio Playback Tests")
    print("=" * 60)
    print(f"Output directory: {TEST_OUTPUT_DIR}")
    print(f"Time: {datetime.now().isoformat()}")

    ensure_output_dir()

    # Run tests
    results = {}

    # Test 1: Ultimate-TTS direct
    print("\n" + "-" * 60)
    print("TEST 1: Ultimate-TTS Direct (Gradio API)")
    print("-" * 60)
    results["ultimate_tts_direct"] = await test_ultimate_tts_direct()

    # Test 2: Flute-Gateway prosodic
    print("\n" + "-" * 60)
    print("TEST 2: Flute-Gateway Prosodic TTS")
    print("-" * 60)
    results["flute_gateway_prosodic"] = await test_flute_gateway_prosodic()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "✓ PASS" if passed_flag else "❌ FAIL"
        print(f"  {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"\nAudio files saved to: {TEST_OUTPUT_DIR}")
    print("List files: ls -la", TEST_OUTPUT_DIR)
    print("Play audio: aplay <file.wav>")

    return passed == total


# pytest integration
import pytest


@pytest.mark.functional
@pytest.mark.asyncio
async def test_ultimate_tts_produces_audible_audio():
    """Verify Ultimate-TTS produces non-silent audio."""
    result = await test_ultimate_tts_direct()
    assert result, "Ultimate-TTS should produce audible audio"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_flute_gateway_produces_audible_audio():
    """Verify Flute-Gateway produces non-silent audio."""
    result = await test_flute_gateway_prosodic()
    assert result, "Flute-Gateway should produce audible audio"


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
