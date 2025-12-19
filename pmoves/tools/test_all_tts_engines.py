#!/usr/bin/env python3
"""Test all 7 TTS engines with audio playback via gradio_client.

This script:
1. Connects to Ultimate-TTS-Studio via gradio_client
2. Loads all 7 TTS engine models
3. Tests synthesis for each loaded engine
4. Saves audio files to /tmp/pmoves-tts-test/
5. Plays audio via available methods

Usage:
    python3 pmoves/tools/test_all_tts_engines.py [OPTIONS]

Options:
    --url URL       Ultimate-TTS URL (default: http://172.21.112.1:42074/)
    --no-play       Skip audio playback, only save files
    --engine NAME   Test only specified engine (e.g., kitten_tts)

Requirements:
    pip install gradio_client
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from gradio_client import Client
except ImportError:
    print("ERROR: gradio_client required. Install with: pip install gradio_client")
    sys.exit(1)


# Configuration
DEFAULT_URL = os.getenv("ULTIMATE_TTS_URL", "http://172.21.112.1:42074/")
OUTPUT_DIR = Path("/tmp/pmoves-tts-test")
TEST_TEXT = "Hello! This is a test of the text to speech engine. Can you hear me clearly?"

# Engine definitions: (id, display_name, load_endpoint, requires_reference_audio, voice_index, default_voice)
ENGINES = [
    ("kitten_tts", "KittenTTS", "handle_load_kitten", False, 67, "expr-voice-2-f"),
    ("kokoro", "Kokoro TTS", "handle_load_kokoro", False, 19, "af_heart"),
    ("f5_tts", "F5-TTS", "handle_f5_load", True, None, None),
    ("indextts2", "IndexTTS2", "handle_load_indextts2", True, None, None),
    ("fish", "Fish Speech", "handle_load_fish", True, None, None),
    ("chatterbox", "ChatterboxTTS", "handle_load_chatterbox", True, None, None),
    ("voxcpm", "VoxCPM", "handle_load_voxcpm", True, None, None),
]


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f" {text}")
    print('=' * 50)


def play_audio_powershell(filepath: Path) -> bool:
    """Play audio via PowerShell (WSL2 host speakers)."""
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(filepath)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False

        win_path = result.stdout.strip()
        ps_cmd = f"(New-Object Media.SoundPlayer '{win_path}').PlaySync()"
        result = subprocess.run(
            ["powershell.exe", "-c", ps_cmd],
            timeout=30,
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def play_audio_ffplay(filepath: Path) -> bool:
    """Play audio via ffplay."""
    try:
        result = subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(filepath)],
            timeout=15,
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def play_audio(filepath: Path, skip_play: bool = False) -> None:
    """Play audio using available methods."""
    if skip_play:
        print("      (playback skipped)")
        return

    print("      🔊 Playing audio...")
    if play_audio_ffplay(filepath):
        print("      ✓ ffplay playback complete")
    else:
        print("      ⚠ ffplay not available")

    if play_audio_powershell(filepath):
        print("      ✓ PowerShell playback complete")
    else:
        print("      ⚠ PowerShell not available")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test all TTS engines via gradio_client")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="Ultimate-TTS URL")
    parser.add_argument("--no-play", action="store_true", help="Skip audio playback")
    parser.add_argument("--engine", type=str, help="Test only specified engine")
    args = parser.parse_args()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print_header("TTS Engine Test Suite (gradio_client)")
    print(f"Target: {args.url}")
    print(f"Output: {OUTPUT_DIR}")

    # Connect to Ultimate-TTS
    print("\nConnecting...")
    try:
        client = Client(args.url, verbose=False)
        print("✓ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return 1

    # Filter engines if specified
    engines_to_test = ENGINES
    if args.engine:
        engines_to_test = [e for e in ENGINES if e[0] == args.engine]
        if not engines_to_test:
            print(f"ERROR: Unknown engine '{args.engine}'")
            print(f"Available: {', '.join(e[0] for e in ENGINES)}")
            return 1

    # Phase 1: Load all models
    print_header("Loading TTS Models")

    loaded_engines = {}
    for engine_id, display_name, load_endpoint, requires_ref, voice_idx, default_voice in engines_to_test:
        print(f"  Loading {display_name}...", end=" ", flush=True)
        try:
            result = client.predict(api_name=f"/{load_endpoint}")
            status = str(result[0]) if result else "Unknown"
            if "✅" in status or "Loaded" in status.lower():
                print(f"✓ ({status[:40]})")
                loaded_engines[engine_id] = True
            else:
                print(f"❌ ({status[:60]})")
                loaded_engines[engine_id] = False
        except Exception as e:
            print(f"❌ ({str(e)[:50]})")
            loaded_engines[engine_id] = False

    loaded_count = sum(1 for v in loaded_engines.values() if v)
    print(f"\nModels loaded: {loaded_count}/{len(engines_to_test)}")

    if loaded_count == 0:
        print("\nERROR: No models loaded. Cannot proceed with synthesis tests.")
        return 1

    # Phase 2: Test synthesis
    print_header("Testing Synthesis")

    results = {}
    for i, (engine_id, display_name, load_endpoint, requires_ref, voice_idx, default_voice) in enumerate(engines_to_test, 1):
        print(f"\n[{i}/{len(engines_to_test)}] {display_name}")

        if not loaded_engines.get(engine_id):
            print("      ⏭️  SKIP (model not loaded)")
            results[engine_id] = False
            continue

        if requires_ref:
            print("      ⚠️  SKIP (requires reference audio)")
            results[engine_id] = "ref_required"
            continue

        # Build 92-element param list
        params = [None] * 92
        params[0] = TEST_TEXT
        params[1] = display_name
        params[2] = "wav"

        # Set voice parameter
        if voice_idx is not None and default_voice is not None:
            params[voice_idx] = default_voice

        print(f"      Synthesizing: \"{TEST_TEXT[:40]}...\"")

        try:
            result = client.predict(*params, api_name="/generate_unified_tts")

            if result and len(result) >= 2:
                audio_path = result[0]  # Path string (may be temp path)
                status_msg = result[1]  # Status message

                # Check for error in status
                if "❌" in str(status_msg) or "error" in str(status_msg).lower():
                    print(f"      ❌ FAIL: {str(status_msg)[:60]}")
                    results[engine_id] = False
                    continue

                # gradio_client downloads files to /tmp/gradio/{hash}/
                # The returned path may be a string path to the downloaded file
                src_path = None
                if isinstance(audio_path, str) and os.path.exists(audio_path):
                    src_path = audio_path
                elif isinstance(audio_path, dict) and 'path' in audio_path:
                    src_path = audio_path['path']

                # If path doesn't exist directly, search gradio temp
                if not src_path or not os.path.exists(src_path):
                    # Find most recent WAV in /tmp/gradio
                    gradio_wavs = list(Path("/tmp/gradio").rglob("*.wav"))
                    if gradio_wavs:
                        # Get most recently modified
                        src_path = str(max(gradio_wavs, key=lambda p: p.stat().st_mtime))

                if src_path and os.path.exists(src_path):
                    size = os.path.getsize(src_path)
                    dest_path = OUTPUT_DIR / f"{engine_id}.wav"
                    shutil.copy(src_path, dest_path)

                    print(f"      ✓ Generated {size:,} bytes")
                    print(f"      📁 Saved: {dest_path}")

                    play_audio(dest_path, skip_play=args.no_play)
                    results[engine_id] = True
                else:
                    print(f"      ❌ FAIL: Output file not found")
                    results[engine_id] = False
            else:
                print("      ❌ FAIL: No result returned")
                results[engine_id] = False

        except Exception as e:
            error_msg = str(e)
            if "Reference audio is required" in error_msg:
                print("      ⚠️  SKIP: Requires reference audio")
                results[engine_id] = "ref_required"
            else:
                print(f"      ❌ FAIL: {error_msg[:60]}")
                results[engine_id] = False

    # Summary
    print_header("Summary")

    passed = sum(1 for v in results.values() if v is True)
    ref_required = sum(1 for v in results.values() if v == "ref_required")
    failed = sum(1 for v in results.values() if v is False)

    print(f"✓ Working:           {passed}/{len(results)}")
    print(f"⚠️  Needs ref audio:  {ref_required}/{len(results)}")
    print(f"❌ Failed:            {failed}/{len(results)}")

    print("\nAudio files saved:")
    for engine_id, success in results.items():
        if success is True:
            filepath = OUTPUT_DIR / f"{engine_id}.wav"
            if filepath.exists():
                size = filepath.stat().st_size
                print(f"  ✓ {filepath}: {size:,} bytes")

    if ref_required > 0:
        print("\nEngines requiring reference audio:")
        for engine_id, success in results.items():
            if success == "ref_required":
                print(f"  ⚠️  {engine_id}")

    if failed > 0:
        print("\nFailed engines:")
        for engine_id, success in results.items():
            if success is False:
                print(f"  ❌ {engine_id}")

    return 0 if passed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
