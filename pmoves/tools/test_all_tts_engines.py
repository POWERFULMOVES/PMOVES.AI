#!/usr/bin/env python3
"""Test all 14 TTS engines via gradio_client.

Uses the Gradio Python client with named kwargs — Gradio auto-fills defaults
for all 121 unified synthesis parameters. No positional array indexing needed.

Aligned with PMOVES-Ultimate-TTS-Studio fork (tools/test_engines.py pattern).

Supports 14 engines: KittenTTS, Kokoro TTS, F5-TTS, IndexTTS, IndexTTS2,
Fish Speech S1, Fish Speech S2 Pro, ChatterboxTTS, Chatterbox Turbo,
Chatterbox Multilingual, VoxCPM, Higgs Audio, Qwen Voice Design, VibeVoice.

Per-engine client isolation: each engine load/synth reconnects the Gradio
client on connection errors, preventing cascade failures when one engine
OOM-crashes the server.

Usage:
    python pmoves/tools/test_all_tts_engines.py [--no-play] [--engine ENGINE] [--load-only]

Options:
    --no-play       Skip audio playback, only save files
    --engine NAME   Test only specified engine (e.g., kitten_tts)
    --load-only     Only test model loading, skip synthesis
    --url URL       Override TTS Studio URL (default: http://127.0.0.1:7860/)
    --no-pterm      Skip pterm pre-flight (auto-start via Pinokio)
    --metrics       Capture GPU VRAM via GPU Orchestrator (port 8200)
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

try:
    from gradio_client import Client
except ImportError:
    print("ERROR: gradio_client required. Install with: pip install gradio_client")
    sys.exit(1)


# Configuration
DEFAULT_URL = os.getenv("ULTIMATE_TTS_URL", "http://127.0.0.1:7860")
_default_output = (
    Path(os.environ["TEMP"]) / "pmoves-tts-test"
    if platform.system() == "Windows" and "TEMP" in os.environ
    else Path("/tmp/pmoves-tts-test")
)
OUTPUT_DIR = Path(os.getenv("TTS_TEST_OUTPUT", str(_default_output)))
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
        "name": "Fish Speech S1",
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
        "name": "Qwen Voice Design",
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
        "id": "chatterbox_multilingual",
        "name": "Chatterbox Multilingual",
        "load_api": "/handle_load_chatterbox_multilingual",
        "load_kwargs": {},
        "synth_kwargs": {
            "chatterbox_mtl_language": "en",
            "chatterbox_mtl_exaggeration": 0.5,
            "chatterbox_mtl_temperature": 0.8,
            "chatterbox_mtl_cfg_weight": 0.5,
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

# ---------------------------------------------------------------------------
# GPU Metrics via GPU Orchestrator (port 8200)
# ---------------------------------------------------------------------------
GPU_ORCHESTRATOR_URL = os.getenv("GPU_ORCHESTRATOR_URL", "http://127.0.0.1:8200")


def capture_gpu_metrics() -> dict | None:
    """Snapshot VRAM via GPU Orchestrator API (total + per-process).

    Returns dict with total_vram_mb, used_vram_mb, free_vram_mb,
    utilization_pct, temperature_c, and processes list.
    Returns None if orchestrator is offline.
    """
    try:
        req = urllib.request.Request(
            f"{GPU_ORCHESTRATOR_URL}/api/gpu/status",
            headers={"Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        metrics = data.get("data", {}).get("metrics", {})
        processes = data.get("data", {}).get("processes", [])
        return {
            "total_vram_mb": metrics.get("total_vram_mb"),
            "used_vram_mb": metrics.get("used_vram_mb"),
            "free_vram_mb": metrics.get("free_vram_mb"),
            "utilization_pct": metrics.get("utilization_percent"),
            "temperature_c": metrics.get("temperature_c"),
            "processes": processes,
        }
    except Exception:
        return None  # Orchestrator offline, skip metrics


def print_gpu_delta(
    label: str, before: dict | None, after: dict | None,
) -> None:
    """Print a VRAM delta report between two GPU snapshots."""
    if before is None or after is None:
        print(f"  {label} metrics: GPU orchestrator unavailable")
        return

    used_b = before.get("used_vram_mb") or 0
    used_a = after.get("used_vram_mb") or 0
    total = before.get("total_vram_mb") or 0
    delta = used_a - used_b

    util_b = before.get("utilization_pct") or 0
    util_a = after.get("utilization_pct") or 0

    temp_b = before.get("temperature_c") or 0
    temp_a = after.get("temperature_c") or 0

    pct_b = (used_b / total * 100) if total else 0
    pct_a = (used_a / total * 100) if total else 0

    print(f"  {label} metrics:")
    print(f"    VRAM before:  {used_b:,.0f} MB used / {total:,.0f} MB total ({pct_b:.0f}%)")
    print(f"    VRAM after:   {used_a:,.0f} MB used / {total:,.0f} MB total ({pct_a:.0f}%)")
    sign = "+" if delta >= 0 else ""
    print(f"    VRAM delta:   {sign}{delta:,.0f} MB")
    if util_b or util_a:
        print(f"    GPU util:     {util_b:.0f}% \u2192 {util_a:.0f}%")
    if temp_b or temp_a:
        print(f"    Temperature:  {temp_b:.0f}\u00b0C \u2192 {temp_a:.0f}\u00b0C")

    # Per-process breakdown from after snapshot
    procs = after.get("processes", [])
    if procs:
        print(f"    Processes:")
        for p in procs[:5]:  # Show top 5
            pid = p.get("pid", "?")
            name = p.get("name", p.get("container", "unknown"))
            mem = p.get("vram_mb", p.get("gpu_memory_mb", 0))
            print(f"      {name} (PID {pid}): {mem:,.0f} MB")


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


def _is_connection_error(error: Exception) -> bool:
    """Check if an exception indicates a broken Gradio client connection.

    Also returns True for empty/very-short messages — when the gradio_client
    SSE thread handles the real error internally, predict() often raises with
    an empty or opaque message.
    """
    msg = str(error).lower()
    if len(msg.strip()) < 5:
        # Empty or near-empty error — server likely crashed
        return True
    return any(kw in msg for kw in (
        "connection", "timeout", "timed out", "closed", "eof",
        "broken pipe", "reset by peer", "httpx", "stream",
        "disconnect", "forcibly", "winerror", "readerror",
    ))


def _reconnect_client(url: str, verbose: bool = False) -> Client | None:
    """Attempt to create a fresh Gradio client connection."""
    try:
        return Client(url, verbose=verbose)
    except Exception:
        return None


def load_engine(
    client: Client, engine: dict, url: str,
) -> tuple[bool, str, Client]:
    """Load a TTS engine model via gradio_client.

    Reconnects the Gradio client on connection errors to prevent cascade
    failures when an engine OOM-crashes the server.

    Returns:
        (success, message, client) — client may be a new instance after reconnection.
    """
    load_kwargs = engine["load_kwargs"]

    if load_kwargs == "skip":
        return False, "skipped (requires setup)", client

    try:
        result = client.predict(**load_kwargs, api_name=engine["load_api"])

        # Result is a tuple — first element is status string
        status = str(result[0]) if result else ""

        if "\u2705" in status or "loaded" in status.lower() or "ready" in status.lower():
            return True, "loaded", client
        if "download" in status.lower():
            return False, "needs download", client
        if "\u274c" in status or "failed" in status.lower() or "not available" in status.lower():
            error = status.replace("\u2705", "").replace("\u274c", "").strip()[:60]
            return False, error or "failed", client

        # Unknown status — treat as success if non-empty
        if status:
            return True, f"status: {status[:40]}", client
        return False, "empty response", client

    except Exception as e:
        msg = str(e)[:60]
        # Always reconnect after failure — a fresh Client() is cheap,
        # and the old one may be silently broken (SSE stream dead).
        new_client = _reconnect_client(url)
        if new_client is not None:
            conn_tag = "conn-err" if _is_connection_error(e) else "err"
            return False, f"{msg} ({conn_tag}, reconnected)", new_client
        return False, f"{msg} (reconnect failed)", client


def synthesize_engine(
    client: Client, engine: dict, text: str, url: str,
) -> tuple[bool, str, str, Client]:
    """Synthesize speech via gradio_client using named kwargs.

    Reconnects the Gradio client on connection errors.

    Returns:
        (success, audio_path_or_empty, message, client)
    """
    if engine["synth_kwargs"] is None:
        return False, "", "separate endpoint (skip)", client

    # Build kwargs: common + required-but-unused + engine-specific.
    # Gradio marks several Textbox params as "required" (no Python default)
    # even though they are only used by their respective engine. We must
    # provide them in every call to satisfy the gradio_client validator.
    kwargs = {
        "text_input": text,
        "tts_engine": engine["name"],
        "audio_format": "wav",
        # Required params with no Gradio defaults (used by specific engines only)
        "indextts2_emotion_description": "",
        "higgs_system_prompt": "",
        "qwen_voice_description": "A warm, clear, professional English-speaking voice",
        "qwen_ref_text": "",
        "qwen_style_instruct": "",
        **engine["synth_kwargs"],
    }

    try:
        result = client.predict(**kwargs, api_name="/generate_unified_tts")

        if not result:
            return False, "", "no result", client

        # Result is (audio_path, status_message)
        audio_path = result[0] if isinstance(result, (tuple, list)) else result
        status_msg = result[1] if isinstance(result, (tuple, list)) and len(result) > 1 else ""

        if isinstance(status_msg, str) and "\u274c" in status_msg:
            return False, "", status_msg.replace("\u274c", "").strip()[:60], client

        if not audio_path:
            return False, "", "no audio path", client

        # Handle dict result (Gradio file info)
        if isinstance(audio_path, dict):
            audio_path = audio_path.get("path", audio_path.get("url", ""))

        if not audio_path or not os.path.exists(str(audio_path)):
            return False, "", f"audio file not found: {audio_path}", client

        return True, str(audio_path), "ok", client

    except Exception as e:
        msg = str(e)[:60]
        # Always reconnect after failure — cheap insurance against dead SSE streams.
        new_client = _reconnect_client(url)
        if new_client is not None:
            conn_tag = "conn-err" if _is_connection_error(e) else "err"
            return False, "", f"{msg} ({conn_tag}, reconnected)", new_client
        return False, "", f"{msg} (reconnect failed)", client


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


def _resolve_pterm() -> str | None:
    """Resolve the pterm binary path.

    Per Pinokio-SKILL.md Control Plane: check PATH first, then
    platform-specific fallback locations.
    """
    # 1. Check if pterm is already on PATH
    found = shutil.which("pterm")
    if found:
        return found

    # 2. Windows: check Pinokio install locations
    if platform.system() == "Windows":
        candidates = [
            Path("D:/pinokio/bin/npm/pterm.cmd"),
            Path(os.environ.get("LOCALAPPDATA", ""), "pinokio/bin/npm/pterm.cmd"),
            Path(os.environ.get("APPDATA", ""), "pinokio/bin/npm/pterm.cmd"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)

    # 3. Linux/macOS: common locations
    for p in [Path.home() / ".pinokio" / "bin" / "pterm", Path("/usr/local/bin/pterm")]:
        if p.exists():
            return str(p)

    return None


def _run_pterm(pterm: str, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess | None:
    """Run a pterm command and return the result, or None on failure."""
    try:
        return subprocess.run(
            [pterm, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _parse_pterm_status(output: str) -> dict:
    """Parse key=value fields from pterm status output.

    Handles both JSON and plain-text output formats.
    """
    # Try JSON first
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to key=value parsing
    result = {}
    for line in output.splitlines():
        line = line.strip()
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
        elif ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def pterm_preflight(skip: bool = False) -> str | None:
    """Use pterm to check/start TTS Studio per Pinokio-SKILL.md lifecycle.

    Returns the ready_url if TTS Studio is running, or None to fall back
    to direct connection.
    """
    if skip:
        return None

    pterm = _resolve_pterm()
    if not pterm:
        print("  Pterm: not found (will connect directly)")
        return None

    print(f"  Pterm: {pterm}")

    # 1. Search for TTS Studio app
    result = _run_pterm(pterm, ["search", "ultimate tts"])
    if not result or result.returncode != 0:
        print("  Pterm: search failed (will connect directly)")
        return None

    # Parse app_id from search results — look for first line with an app path/id
    app_id = None
    app_path = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Try JSON
        try:
            items = json.loads(result.stdout)
            if isinstance(items, list) and items:
                item = items[0]
                app_id = item.get("app_id") or item.get("id")
                app_path = item.get("path")
                break
        except (json.JSONDecodeError, ValueError):
            pass
        # Plain text: look for path-like lines containing "tts" or "ultimate"
        lower = line.lower()
        if "ultimate" in lower or "tts" in lower:
            # Could be "app_id: xxx" or just a path
            if ":" in line and not line.startswith("/") and not line[1:2] == ":":
                _, _, val = line.partition(":")
                app_id = val.strip()
            else:
                app_path = line
            break

    if not app_id and not app_path:
        print("  Pterm: TTS Studio not found in local apps")
        return None

    identifier = app_id or app_path
    print(f"  Pterm: found app → {identifier}")

    # 2. Check status
    status_arg = app_id or app_path
    result = _run_pterm(pterm, ["status", status_arg])
    if not result or result.returncode != 0:
        print("  Pterm: status check failed")
        return None

    status = _parse_pterm_status(result.stdout)
    ready = str(status.get("ready", "")).lower() == "true"
    ready_url = status.get("ready_url", "")
    state = status.get("state", "offline")
    path_val = status.get("path", app_path or "")

    if ready and ready_url:
        print(f"  Pterm: already running at {ready_url}")
        return ready_url

    # 3. If offline, start it
    if state == "offline" or not ready:
        run_target = path_val or status_arg
        print(f"  Pterm: app is {state}, starting via pterm run...")
        run_result = _run_pterm(pterm, ["run", run_target], timeout=60)
        if not run_result or run_result.returncode != 0:
            stderr = (run_result.stderr[:100] if run_result else "timeout").strip()
            print(f"  Pterm: run failed — {stderr}")
            return None

        # 4. Poll status until ready (180s timeout per SKILL.md)
        deadline = time.time() + 180
        poll_interval = 2
        while time.time() < deadline:
            time.sleep(poll_interval)
            result = _run_pterm(pterm, ["status", status_arg])
            if not result:
                continue
            status = _parse_pterm_status(result.stdout)
            ready = str(status.get("ready", "")).lower() == "true"
            ready_url = status.get("ready_url", "")
            state = status.get("state", "")

            if ready and ready_url:
                print(f"  Pterm: started successfully at {ready_url}")
                return ready_url

            if state == "offline":
                print("  Pterm: app dropped back to offline during startup")
                return None

            # Ramp up poll interval slightly
            poll_interval = min(poll_interval + 1, 5)

        print("  Pterm: startup timed out (180s)")
        return None

    return None


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test all 14 TTS engines")
    parser.add_argument("--no-play", action="store_true", help="Skip audio playback")
    parser.add_argument("--engine", type=str, help="Test only specified engine (e.g., kitten_tts)")
    parser.add_argument("--load-only", action="store_true", help="Only test model loading")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="TTS Studio URL")
    parser.add_argument("--no-pterm", action="store_true", help="Skip pterm pre-flight")
    parser.add_argument("--metrics", action="store_true",
                        help="Capture GPU VRAM via GPU Orchestrator (port 8200)")
    args = parser.parse_args()

    url = args.url.rstrip("/") + "/"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print_header("TTS Engine Test Suite (gradio_client)")
    print(f"  Target: {url}")
    print(f"  Output: {OUTPUT_DIR}")

    # Pterm pre-flight: auto-start TTS Studio if possible
    # Skip pterm if user explicitly provided --url or set ULTIMATE_TTS_URL env var
    env_url_set = "ULTIMATE_TTS_URL" in os.environ
    skip_pterm = args.no_pterm or (args.url != DEFAULT_URL) or env_url_set
    print("\n  Pterm pre-flight...")
    ready_url = pterm_preflight(skip=skip_pterm)
    if ready_url:
        url = ready_url.rstrip("/") + "/"
        print(f"  Using pterm-resolved URL: {url}")

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

    # GPU metrics pre-check
    if args.metrics:
        print("\n  GPU Orchestrator: ", end="", flush=True)
        probe = capture_gpu_metrics()
        if probe:
            total = probe.get("total_vram_mb", 0)
            used = probe.get("used_vram_mb", 0)
            print(f"connected ({used:,.0f}/{total:,.0f} MB used)")
        else:
            print(f"unavailable at {GPU_ORCHESTRATOR_URL} (metrics will be skipped)")

    # ── Phase 1: Load Models ──────────────────────────────────────────
    print_header("Phase 1: Loading Models")

    load_results = {}
    for engine in engines_to_test:
        print(f"  {engine['name']}...", end=" ", flush=True)

        gpu_before = capture_gpu_metrics() if args.metrics else None

        start = time.time()
        success, message, client = load_engine(client, engine, url)
        elapsed = time.time() - start

        load_results[engine["id"]] = success
        if success:
            print(f"✓ ({elapsed:.1f}s)")
        elif message.startswith("skipped"):
            print(f"⏭ {message}")
        elif "reconnected" in message:
            print(f"❌ {message} — client refreshed for next engine")
        else:
            print(f"❌ {message}")

        # GPU metrics delta after load
        if args.metrics and success:
            gpu_after = capture_gpu_metrics()
            print_gpu_delta(engine["name"], gpu_before, gpu_after)

    loaded = sum(1 for v in load_results.values() if v)
    print(f"\n  Models loaded: {loaded}/{len(engines_to_test)}")

    if args.load_only:
        print("\n  (--load-only mode, skipping synthesis)")
        # Fail if fewer than half the tested engines loaded
        if loaded == 0:
            return 1
        if loaded < len(engines_to_test) / 2:
            print(f"\n  WARNING: Only {loaded}/{len(engines_to_test)} engines loaded — failing.")
            return 1
        return 0

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
        gpu_before_synth = capture_gpu_metrics() if args.metrics else None

        start = time.time()
        success, audio_path, message, client = synthesize_engine(
            client, engine, TEST_TEXT, url,
        )
        elapsed = time.time() - start

        if not success:
            extra = " — client refreshed" if "reconnected" in message else ""
            print(f"      ❌ FAIL: {message}{extra}")
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

        # GPU metrics delta after synthesis
        if args.metrics:
            gpu_after_synth = capture_gpu_metrics()
            print_gpu_delta(f"{engine['name']} synth", gpu_before_synth, gpu_after_synth)

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
    # Fail if fewer than half the testable engines (excluding skips) synthesized
    testable = synth_pass + synth_fail
    if testable == 0:
        return 1
    if synth_pass < testable / 2:
        print(f"\n  WARNING: Only {synth_pass}/{testable} testable engines passed — failing.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
