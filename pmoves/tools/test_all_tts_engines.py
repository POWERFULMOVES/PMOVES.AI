#!/usr/bin/env python3
"""Test all 7 TTS engines with audio playback.

This script:
1. Loads all 7 TTS engine models via Gradio API
2. Tests synthesis for each loaded engine
3. Saves audio files to /tmp/pmoves-tts-test/
4. Plays audio via ffplay and PowerShell (WSL2)

Usage:
    python3 pmoves/tools/test_all_tts_engines.py [--no-play] [--engine ENGINE]

Options:
    --no-play       Skip audio playback, only save files
    --engine NAME   Test only specified engine (e.g., kitten_tts)
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Install with: pip install httpx")
    sys.exit(1)


# Configuration
ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://localhost:7861")
GRADIO_API = f"{ULTIMATE_TTS_URL}/gradio_api"
OUTPUT_DIR = Path("/tmp/pmoves-tts-test")
TEST_TEXT = "Hello! This is a test of the text to speech engine. Can you hear me clearly?"

# Engine definitions: (id, display_name, load_endpoint, default_voice)
ENGINES = [
    ("kitten_tts", "KittenTTS", "handle_load_kitten", "expr-voice-2-f"),
    ("kokoro", "Kokoro TTS", "handle_load_kokoro", "af_heart"),
    ("f5_tts", "F5-TTS", "handle_f5_load", None),
    ("indextts2", "IndexTTS2", "handle_load_indextts2", None),
    ("fish", "Fish Speech", "handle_fish_load", None),
    ("chatterbox", "ChatterboxTTS", "handle_chatterbox_load", None),
    ("voxcpm", "VoxCPM", "handle_load_voxcpm", None),
]

# Engine display names for Gradio API
ENGINE_DISPLAY_NAMES = {
    "kitten_tts": "KittenTTS",
    "kokoro": "Kokoro TTS",
    "f5_tts": "F5-TTS",
    "indextts2": "IndexTTS2",
    "fish": "Fish Speech",
    "chatterbox": "ChatterboxTTS",
    "voxcpm": "VoxCPM",
}


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f" {text}")
    print('=' * 50)


def print_status(name: str, success: bool, message: str = "") -> None:
    """Print status with emoji."""
    icon = "✓" if success else "❌"
    msg = f" ({message})" if message else ""
    print(f"  {icon} {name}{msg}")


async def check_service_health() -> bool:
    """Check if Ultimate-TTS service is healthy."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GRADIO_API}/info")
            return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: Cannot connect to Ultimate-TTS at {ULTIMATE_TTS_URL}: {e}")
        return False


async def load_model(client: httpx.AsyncClient, load_endpoint: str) -> tuple[bool, str]:
    """Load a TTS model via Gradio API.

    Returns:
        Tuple of (success, message)
    """
    try:
        # POST to initiate model loading
        resp = await client.post(
            f"{GRADIO_API}/call/{load_endpoint}",
            json={"data": []},
            timeout=30.0
        )

        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"

        event_id = resp.json().get("event_id")
        if not event_id:
            return False, "No event_id"

        # Poll for result via SSE
        result_resp = await client.get(
            f"{GRADIO_API}/call/{load_endpoint}/{event_id}",
            timeout=120.0  # Models can take time to load
        )

        # Parse SSE response
        for line in result_resp.iter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:])
                    if isinstance(data, list) and len(data) > 0:
                        status = str(data[0]) if data[0] else ""
                        if "✅" in status or "Loaded" in status.lower():
                            return True, "loaded"
                        if "❌" in status or "Failed" in status or "not available" in status.lower():
                            # Extract error message
                            error = status.replace("❌", "").strip()
                            return False, error or "failed"
                except json.JSONDecodeError:
                    continue

        return False, "no response"

    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:50]


def build_synthesis_params(text: str, engine_id: str, voice: Optional[str] = None) -> list:
    """Build the 92-parameter list for unified TTS synthesis.

    The Gradio API expects parameters in a specific order.
    """
    params = [None] * 92

    # Core parameters
    params[0] = text  # text_input
    params[1] = ENGINE_DISPLAY_NAMES.get(engine_id, engine_id)  # tts_engine
    params[2] = "wav"  # audio_format

    # ChatterboxTTS params (indices 3-18)
    params[4] = 0.5   # chatterbox_exaggeration
    params[5] = 0.8   # chatterbox_temperature
    params[6] = 0.5   # chatterbox_cfg_weight
    params[7] = 300   # chatterbox_chunk_size
    params[8] = 0     # chatterbox_seed
    params[10] = "en"  # chatterbox_mtl_language

    # Kokoro params (indices 19-20)
    if engine_id == "kokoro":
        params[19] = voice or "af_heart"  # kokoro_voice
    else:
        params[19] = "af_heart"
    params[20] = 1.0  # kokoro_speed

    # Fish Speech params (indices 21-27)
    params[23] = 0.8   # fish_temperature
    params[24] = 0.8   # fish_top_p
    params[25] = 1.1   # fish_repetition_penalty
    params[26] = 1024  # fish_max_tokens

    # IndexTTS params (indices 28-30)
    params[29] = 0.8  # indextts_temperature

    # IndexTTS2 params (indices 31-50)
    params[32] = "audio_reference"  # indextts2_emotion_mode
    params[34] = ""    # indextts2_emotion_description (required, can be empty)
    params[35] = 1.0   # indextts2_emo_alpha
    params[43] = 1.0   # indextts2_calm
    params[44] = 0.8   # indextts2_temperature
    params[45] = 0.9   # indextts2_top_p
    params[46] = 50    # indextts2_top_k
    params[47] = 1.1   # indextts2_repetition_penalty
    params[48] = 1500  # indextts2_max_mel_tokens
    params[50] = False  # indextts2_use_random

    # F5-TTS params (indices 51-56)
    params[53] = 1.0   # f5_speed
    params[54] = 0.15  # f5_cross_fade
    params[55] = False  # f5_remove_silence
    params[56] = 0     # f5_seed

    # Higgs Audio params (indices 57-66)
    params[59] = "EMPTY"  # higgs_voice_preset
    params[61] = 1.0   # higgs_temperature
    params[62] = 0.95  # higgs_top_p
    params[63] = 50    # higgs_top_k
    params[64] = 1024  # higgs_max_tokens

    # KittenTTS params (index 67)
    if engine_id == "kitten_tts":
        params[67] = voice or "expr-voice-2-f"  # kitten_voice
    else:
        params[67] = "expr-voice-2-f"

    # VoxCPM params (indices 68-77)
    params[70] = 2.0   # voxcpm_cfg_value
    params[71] = 10    # voxcpm_inference_timesteps
    params[72] = True  # voxcpm_normalize
    params[73] = True  # voxcpm_denoise
    params[74] = True  # voxcpm_retry_badcase
    params[75] = 3     # voxcpm_retry_badcase_max_times
    params[76] = 6.0   # voxcpm_retry_badcase_ratio_threshold

    # Audio effects params (indices 78-91) - all disabled
    params[78] = 0     # gain_db
    params[79] = False  # enable_eq
    params[83] = False  # enable_reverb
    params[87] = False  # enable_echo
    params[90] = False  # enable_pitch

    return params


async def synthesize(client: httpx.AsyncClient, text: str, engine_id: str,
                     voice: Optional[str] = None) -> tuple[bool, bytes, str]:
    """Synthesize speech via Gradio API.

    Returns:
        Tuple of (success, audio_bytes, message)
    """
    try:
        params = build_synthesis_params(text, engine_id, voice)

        # POST to initiate synthesis
        resp = await client.post(
            f"{GRADIO_API}/call/generate_unified_tts",
            json={"data": params},
            timeout=30.0
        )

        if resp.status_code != 200:
            return False, b"", f"HTTP {resp.status_code}"

        event_id = resp.json().get("event_id")
        if not event_id:
            return False, b"", "No event_id"

        # Poll for result via SSE
        result_resp = await client.get(
            f"{GRADIO_API}/call/generate_unified_tts/{event_id}",
            timeout=180.0  # Synthesis can take time
        )

        audio_url = None
        error_msg = None

        for line in result_resp.iter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:])
                    if isinstance(data, list) and len(data) >= 1:
                        audio_info = data[0]
                        status = data[1] if len(data) > 1 else ""

                        # Check for error
                        if isinstance(status, str) and "❌" in status:
                            error_msg = status.replace("❌", "").strip()
                            break

                        # Get audio URL
                        if isinstance(audio_info, dict) and "url" in audio_info:
                            audio_url = audio_info["url"]
                            break
                except json.JSONDecodeError:
                    continue

        if error_msg:
            return False, b"", error_msg

        if not audio_url:
            return False, b"", "No audio URL in response"

        # Download audio file
        audio_resp = await client.get(audio_url, timeout=30.0)
        if audio_resp.status_code != 200:
            return False, b"", f"Download failed: HTTP {audio_resp.status_code}"

        audio_bytes = audio_resp.content

        # Validate WAV format
        if not audio_bytes or audio_bytes[:4] != b'RIFF':
            return False, b"", "Invalid WAV format"

        return True, audio_bytes, f"{len(audio_bytes):,} bytes"

    except httpx.TimeoutException:
        return False, b"", "timeout"
    except Exception as e:
        return False, b"", str(e)[:50]


def play_audio_ffplay(filepath: Path) -> bool:
    """Play audio via ffplay (terminal audio)."""
    try:
        result = subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(filepath)],
            timeout=15,
            capture_output=True
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return True  # Audio played (timeout is expected for long audio)
    except FileNotFoundError:
        return False  # ffplay not installed
    except Exception:
        return False


def play_audio_powershell(filepath: Path) -> bool:
    """Play audio via PowerShell (WSL2 host speakers)."""
    try:
        # Convert WSL path to Windows path
        result = subprocess.run(
            ["wslpath", "-w", str(filepath)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False

        win_path = result.stdout.strip()

        # Play via PowerShell
        ps_cmd = f"(New-Object Media.SoundPlayer '{win_path}').PlaySync()"
        result = subprocess.run(
            ["powershell.exe", "-c", ps_cmd],
            timeout=30,
            capture_output=True
        )
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return True  # Audio played
    except FileNotFoundError:
        return False  # Not in WSL2 or PowerShell unavailable
    except Exception:
        return False


def play_audio(filepath: Path, skip_play: bool = False) -> None:
    """Play audio using all available methods."""
    if skip_play:
        print("      (playback skipped)")
        return

    print("      🔊 Playing audio...")

    # Try ffplay first
    if play_audio_ffplay(filepath):
        print("      ✓ ffplay playback complete")
    else:
        print("      ⚠ ffplay not available")

    # Try PowerShell (WSL2)
    if play_audio_powershell(filepath):
        print("      ✓ PowerShell playback complete")
    else:
        print("      ⚠ PowerShell not available (not in WSL2?)")


async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test all TTS engines")
    parser.add_argument("--no-play", action="store_true", help="Skip audio playback")
    parser.add_argument("--engine", type=str, help="Test only specified engine")
    args = parser.parse_args()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print_header("TTS Engine Test Suite")
    print(f"Target: {ULTIMATE_TTS_URL}")
    print(f"Output: {OUTPUT_DIR}")

    # Check service health
    print("\nChecking service health...")
    if not await check_service_health():
        print("ERROR: Ultimate-TTS service not available")
        return 1

    print("✓ Service is healthy")

    # Filter engines if specified
    engines_to_test = ENGINES
    if args.engine:
        engines_to_test = [(e, n, l, v) for e, n, l, v in ENGINES if e == args.engine]
        if not engines_to_test:
            print(f"ERROR: Unknown engine '{args.engine}'")
            print(f"Available: {', '.join(e[0] for e in ENGINES)}")
            return 1

    # Phase 1: Load all models
    print_header("Loading TTS Models")

    loaded_engines = {}
    async with httpx.AsyncClient(timeout=180.0) as client:
        for engine_id, name, load_endpoint, default_voice in engines_to_test:
            print(f"  Loading {name}...", end=" ", flush=True)
            start = time.time()
            success, message = await load_model(client, load_endpoint)
            elapsed = time.time() - start

            loaded_engines[engine_id] = success
            if success:
                print(f"✓ ({elapsed:.1f}s)")
            else:
                print(f"❌ {message}")

    loaded_count = sum(1 for v in loaded_engines.values() if v)
    print(f"\nModels loaded: {loaded_count}/{len(engines_to_test)}")

    if loaded_count == 0:
        print("\nERROR: No models loaded. Cannot proceed with synthesis tests.")
        return 1

    # Phase 2: Test synthesis
    print_header("Testing Synthesis")

    results = {}
    async with httpx.AsyncClient(timeout=180.0) as client:
        for i, (engine_id, name, load_endpoint, default_voice) in enumerate(engines_to_test, 1):
            print(f"\n[{i}/{len(engines_to_test)}] {name}")

            if not loaded_engines.get(engine_id):
                print("      ⏭️  SKIP (model not loaded)")
                results[engine_id] = False
                continue

            # Synthesize
            print(f"      Synthesizing: \"{TEST_TEXT[:40]}...\"")
            start = time.time()
            success, audio_bytes, message = await synthesize(
                client, TEST_TEXT, engine_id, default_voice
            )
            elapsed = time.time() - start

            if not success:
                print(f"      ❌ FAIL: {message}")
                results[engine_id] = False
                continue

            # Save to file
            filepath = OUTPUT_DIR / f"{engine_id}.wav"
            filepath.write_bytes(audio_bytes)
            print(f"      ✓ Generated {message} in {elapsed:.1f}s")
            print(f"      📁 Saved: {filepath}")

            # Play audio
            play_audio(filepath, skip_play=args.no_play)

            results[engine_id] = True

    # Summary
    print_header("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Engines working: {passed}/{total}")

    print("\nAudio files saved:")
    for engine_id, success in results.items():
        if success:
            print(f"  ✓ {OUTPUT_DIR}/{engine_id}.wav")

    if passed < total:
        print("\nFailed engines:")
        for engine_id, success in results.items():
            if not success:
                print(f"  ❌ {engine_id}")

    return 0 if passed > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
