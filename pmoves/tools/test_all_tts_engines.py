#!/usr/bin/env python3
"""Test all 13 TTS engines via gradio_client.

Uses the Gradio Python client with named kwargs — Gradio auto-fills defaults
for all 121 unified synthesis parameters. No positional array indexing needed.

Aligned with PMOVES-Ultimate-TTS-Studio fork (tools/test_engines.py pattern).

Supports 13 engines: KittenTTS, Kokoro, F5-TTS, IndexTTS, IndexTTS2,
Fish Speech, Fish Speech S2 Pro, ChatterboxTTS, Chatterbox Turbo,
VoxCPM, Higgs Audio, Qwen3 TTS, VibeVoice.

Usage:
    python pmoves/tools/test_all_tts_engines.py [--no-play] [--engine ENGINE] [--load-only]

Options:
    --no-play       Skip audio playback, only save files
    --engine NAME   Test only specified engine (e.g., kitten_tts)
    --load-only     Only test model loading, skip synthesis
    --url URL       Override TTS Studio URL (default: http://127.0.0.1:7860/)
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

try:
    from gradio_client import Client
except ImportError:
    print("ERROR: gradio_client required. Install with: pip install gradio_client")
    sys.exit(1)


# Configuration
DEFAULT_URL = os.getenv("ULTIMATE_TTS_URL", "http://127.0.0.1:7860")
OUTPUT_DIR = Path(os.getenv("TTS_TEST_OUTPUT", "/tmp/pmoves-tts-test"))
TEST_TEXT = "Hello! This is a test of the text to speech engine. Can you hear me clearly?"

# ---------------------------------------------------------------------------
# Engine definitions — source truth from launch.py (lines 9145–10880)
#
# Each engine dict contains:
#   id:           Internal identifier
#   name:         Display name (matches Gradio dropdown)
#   load_api:     Gradio API name for loading the model
#   load_kwargs:  Named kwargs for loading (empty dict = no params)
#                 "skip" = skip loading entirely
#   synth_kwargs: Named kwargs for synthesis (merged with common params)
#                 None = skip synthesis (e.g., VibeVoice uses separate endpoint)
# ---------------------------------------------------------------------------
ENGINES = [
    {
        "id": "kitten_tts",
        "name": "KittenTTS",
        "load_api": "/handle_load_kitten",
        "load_kwargs": {},
        "synth_kwargs": {"kitten_voice": "expr-voice-2-f"},
    },
    {
        "id": "kokoro",
        "name": "Kokoro TTS",
        "load_api": "/handle_load_kokoro",
        "load_kwargs": {},
        "synth_kwargs": {"kokoro_voice": "af_heart", "kokoro_speed": 1.0},
    },
    {
        "id": "f5_tts",
        "name": "F5-TTS",
        "load_api": "/handle_f5_load",
        "load_kwargs": {"model_name": "F5-TTS Base"},
        "synth_kwargs": {"f5_speed": 1.0},
    },
    {
        "id": "indextts2",
        "name": "IndexTTS2",
        "load_api": "/handle_load_indextts2",
        "load_kwargs": {},
        "synth_kwargs": {
            "indextts2_emotion_mode": "audio_reference",
            "indextts2_calm": 1.0,
            "indextts2_temperature": 0.8,
        },
    },
    {
        "id": "fish",
        "name": "Fish Speech",
        "load_api": "/handle_load_fish",
        "load_kwargs": {},
        "synth_kwargs": {
            "fish_temperature": 0.8,
            "fish_top_p": 0.8,
            "fish_repetition_penalty": 1.1,
            "fish_max_tokens": 1024,
        },
    },
    {
        "id": "chatterbox",
        "name": "ChatterboxTTS",
        "load_api": "/handle_load_chatterbox",
        "load_kwargs": {},
        "synth_kwargs": {
            "chatterbox_exaggeration": 0.5,
            "chatterbox_temperature": 0.8,
            "chatterbox_cfg_weight": 0.5,
            "chatterbox_chunk_size": 300,
        },
    },
    {
        "id": "voxcpm",
        "name": "VoxCPM",
        "load_api": "/handle_load_voxcpm",
        "load_kwargs": {},
        "synth_kwargs": {
            "voxcpm_cfg_value": 2.0,
            "voxcpm_inference_timesteps": 10,
            "voxcpm_normalize": True,
            "voxcpm_denoise": True,
        },
    },
    {
        "id": "higgs",
        "name": "Higgs Audio",
        "load_api": "/handle_load_higgs",
        "load_kwargs": {},
        "synth_kwargs": {
            "higgs_voice_preset": "EMPTY",
            "higgs_temperature": 1.0,
            "higgs_top_p": 0.95,
            "higgs_top_k": 50,
            "higgs_max_tokens": 1024,
        },
    },
    {
        "id": "qwen",
        "name": "Qwen3 TTS",
        "load_api": "/handle_load_qwen",
        "load_kwargs": {"model_type": "Base", "model_size": "1.7B"},
        "synth_kwargs": {
            "qwen_mode": "voice_design",
            "qwen_clone_model_size": "1.7B",
            "qwen_chunk_size": 200,
            "qwen_speaker": "Ryan",
            "qwen_language": "Auto",
        },
    },
    {
        "id": "indextts",
        "name": "IndexTTS",
        "load_api": "/handle_load_indextts",
        "load_kwargs": {},
        "synth_kwargs": {"indextts_temperature": 0.8},
    },
    {
        "id": "fish_s2",
        "name": "Fish Speech S2 Pro",
        "load_api": "/handle_load_fish_s2",
        "load_kwargs": {},
        "synth_kwargs": {
            "fish_s2_temperature": 0.8,
            "fish_s2_top_p": 0.8,
            "fish_s2_repetition_penalty": 1.1,
            "fish_s2_max_tokens": 1024,
        },
    },
    {
        "id": "chatterbox_turbo",
        "name": "Chatterbox Turbo",
        "load_api": "/handle_load_chatterbox_turbo",
        "load_kwargs": {},
        "synth_kwargs": {
            "chatterbox_turbo_exaggeration": 0.5,
            "chatterbox_turbo_temperature": 0.8,
            "chatterbox_turbo_cfg_weight": 0.5,
        },
    },
    {
        # VibeVoice uses a separate panel (generate_vibevoice_podcast),
        # NOT the unified generate_unified_tts endpoint.
        "id": "vibevoice",
        "name": "VibeVoice",
        "load_api": "/handle_vibevoice_load",
        "load_kwargs": {
            "selected_model_path": "",
            "path": "models/VibeVoice-1.5B",
            "use_flash_attention": False,
        },
        "synth_kwargs": None,  # Separate endpoint — skip unified synth
    },
]

ENGINE_IDS = [e["id"] for e in ENGINES]


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print("=" * 60)


def validate_wav(filepath: str) -> dict:
    """Validate WAV file and return metadata."""
    result = {"valid": False, "size": 0, "duration": 0.0, "sample_rate": 0, "errors": []}

    if not os.path.exists(filepath):
        result["errors"].append("File does not exist")
        return result

    result["size"] = os.path.getsize(filepath)
    if result["size"] < 100:
        result["errors"].append(f"File too small ({result['size']} bytes)")
        return result

    try:
        with wave.open(filepath, "rb") as wf:
            result["sample_rate"] = wf.getframerate()
            frames = wf.getnframes()
            result["duration"] = frames / result["sample_rate"] if result["sample_rate"] else 0
            if result["duration"] < 0.1:
                result["errors"].append(f"Duration too short ({result['duration']:.2f}s)")
            else:
                result["valid"] = True
    except wave.Error as e:
        result["errors"].append(f"Invalid WAV: {e}")
    except Exception as e:
        result["errors"].append(f"Error: {e}")

    return result


def load_engine(client: Client, engine: dict) -> tuple[bool, str]:
    """Load a TTS engine model via gradio_client.

    Returns:
        (success, message)
    """
    load_kwargs = engine["load_kwargs"]

    if load_kwargs == "skip":
        return False, "skipped (requires setup)"

    try:
        result = client.predict(**load_kwargs, api_name=engine["load_api"])

        # Result is a tuple — first element is status string
        status = str(result[0]) if result else ""

        if "\u2705" in status or "loaded" in status.lower() or "ready" in status.lower():
            return True, "loaded"
        if "download" in status.lower():
            return False, "needs download"
        if "\u274c" in status or "failed" in status.lower() or "not available" in status.lower():
            error = status.replace("\u2705", "").replace("\u274c", "").strip()[:60]
            return False, error or "failed"

        # Unknown status — treat as success if non-empty
        if status:
            return True, f"status: {status[:40]}"
        return False, "empty response"

    except Exception as e:
        return False, str(e)[:60]


def synthesize_engine(client: Client, engine: dict, text: str) -> tuple[bool, str, str]:
    """Synthesize speech via gradio_client using named kwargs.

    Returns:
        (success, audio_path_or_empty, message)
    """
    if engine["synth_kwargs"] is None:
        return False, "", "separate endpoint (skip)"

    # Build kwargs: common + engine-specific
    kwargs = {
        "text_input": text,
        "tts_engine": engine["name"],
        "audio_format": "wav",
        **engine["synth_kwargs"],
    }

    try:
        result = client.predict(**kwargs, api_name="/generate_unified_tts")

        if not result:
            return False, "", "no result"

        # Result is (audio_path, status_message)
        audio_path = result[0] if isinstance(result, (tuple, list)) else result
        status_msg = result[1] if isinstance(result, (tuple, list)) and len(result) > 1 else ""

        if isinstance(status_msg, str) and "\u274c" in status_msg:
            return False, "", status_msg.replace("\u274c", "").strip()[:60]

        if not audio_path:
            return False, "", "no audio path"

        # Handle dict result (Gradio file info)
        if isinstance(audio_path, dict):
            audio_path = audio_path.get("path", audio_path.get("url", ""))

        if not audio_path or not os.path.exists(str(audio_path)):
            return False, "", f"audio file not found: {audio_path}"

        return True, str(audio_path), "ok"

    except Exception as e:
        return False, "", str(e)[:60]


def play_audio(filepath: Path, skip_play: bool = False) -> None:
    """Play audio via ffplay or PowerShell."""
    if skip_play:
        print("      (playback skipped)")
        return

    # Try ffplay
    try:
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(filepath)],
            timeout=15, capture_output=True,
        )
        print("      ✓ Playback complete")
        return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try PowerShell (Windows native)
    try:
        ps_cmd = f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"
        subprocess.run(["powershell.exe", "-c", ps_cmd], timeout=30, capture_output=True)
        print("      ✓ PowerShell playback complete")
        return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print("      (no audio player available)")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test all 13 TTS engines")
    parser.add_argument("--no-play", action="store_true", help="Skip audio playback")
    parser.add_argument("--engine", type=str, help="Test only specified engine (e.g., kitten_tts)")
    parser.add_argument("--load-only", action="store_true", help="Only test model loading")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="TTS Studio URL")
    args = parser.parse_args()

    url = args.url.rstrip("/") + "/"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print_header("TTS Engine Test Suite (gradio_client)")
    print(f"  Target: {url}")
    print(f"  Output: {OUTPUT_DIR}")

    # Connect to Gradio
    print("\n  Connecting to Gradio...")
    try:
        client = Client(url, verbose=False)
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ERROR: Cannot connect to {url}: {e}")
        return 1

    # Filter engines
    engines_to_test = ENGINES
    if args.engine:
        engines_to_test = [e for e in ENGINES if e["id"] == args.engine]
        if not engines_to_test:
            print(f"  ERROR: Unknown engine '{args.engine}'")
            print(f"  Available: {', '.join(ENGINE_IDS)}")
            return 1

    # ── Phase 1: Load Models ──────────────────────────────────────────
    print_header("Phase 1: Loading Models")

    load_results = {}
    for engine in engines_to_test:
        print(f"  {engine['name']}...", end=" ", flush=True)
        start = time.time()
        success, message = load_engine(client, engine)
        elapsed = time.time() - start

        load_results[engine["id"]] = success
        if success:
            print(f"✓ ({elapsed:.1f}s)")
        elif message.startswith("skipped"):
            print(f"⏭ {message}")
        else:
            print(f"❌ {message}")

    loaded = sum(1 for v in load_results.values() if v)
    print(f"\n  Models loaded: {loaded}/{len(engines_to_test)}")

    if args.load_only:
        print("\n  (--load-only mode, skipping synthesis)")
        return 0 if loaded > 0 else 1

    if loaded == 0:
        print("\n  ERROR: No models loaded. Cannot test synthesis.")
        return 1

    # ── Phase 2: Test Synthesis ───────────────────────────────────────
    print_header("Phase 2: Synthesis Tests")

    synth_results = {}
    for i, engine in enumerate(engines_to_test, 1):
        eid = engine["id"]
        print(f"\n  [{i}/{len(engines_to_test)}] {engine['name']}")

        if not load_results.get(eid):
            print("      ⏭ SKIP (not loaded)")
            synth_results[eid] = "skip"
            continue

        if engine["synth_kwargs"] is None:
            print("      ⏭ SKIP (separate endpoint)")
            synth_results[eid] = "skip"
            continue

        print(f"      Synthesizing: \"{TEST_TEXT[:40]}...\"")
        start = time.time()
        success, audio_path, message = synthesize_engine(client, engine, TEST_TEXT)
        elapsed = time.time() - start

        if not success:
            print(f"      ❌ FAIL: {message}")
            synth_results[eid] = False
            continue

        # Validate WAV
        validation = validate_wav(audio_path)
        if not validation["valid"]:
            print(f"      ❌ Invalid WAV: {', '.join(validation['errors'])}")
            synth_results[eid] = False
            continue

        # Copy to output directory
        output_path = OUTPUT_DIR / f"{eid}.wav"
        shutil.copy(audio_path, output_path)

        size_kb = validation["size"] / 1024
        print(f"      ✓ {size_kb:.0f}KB, {validation['duration']:.1f}s @ {validation['sample_rate']}Hz ({elapsed:.1f}s)")
        print(f"      Saved: {output_path}")

        play_audio(output_path, skip_play=args.no_play)
        synth_results[eid] = True

    # ── Summary ───────────────────────────────────────────────────────
    print_header("Summary")

    synth_pass = sum(1 for v in synth_results.values() if v is True)
    synth_fail = sum(1 for v in synth_results.values() if v is False)
    synth_skip = sum(1 for v in synth_results.values() if v == "skip")

    print(f"  Load:  {loaded}/{len(engines_to_test)} engines")
    print(f"  Synth: {synth_pass} pass / {synth_fail} fail / {synth_skip} skip")

    if synth_pass > 0:
        print("\n  Working engines:")
        for eid, status in synth_results.items():
            if status is True:
                name = next(e["name"] for e in ENGINES if e["id"] == eid)
                print(f"    ✓ {name}")

    if synth_fail > 0:
        print("\n  Failed engines:")
        for eid, status in synth_results.items():
            if status is False:
                name = next(e["name"] for e in ENGINES if e["id"] == eid)
                loaded_str = "loaded" if load_results.get(eid) else "not loaded"
                print(f"    ❌ {name} ({loaded_str})")

    print(f"\n  Audio files: {OUTPUT_DIR}")
    return 0 if synth_pass > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
