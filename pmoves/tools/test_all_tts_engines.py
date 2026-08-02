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

Pinokio integration (Lane 4 redo, 2026-08-01):
  * pterm pre-flight — auto-starts Ultimate-TTS-Studio via the real pterm CLI
    (subcommands: list, status, start, running). Falls back to direct
    connection at http://127.0.0.1:7860/ if pterm is not installed.
  * gepeto launcher — `pmoves/tools/test_all_tts_engines/pinokio/` provides
    a 1-click Pinokio UI (install.js, start.js, start-one.js, pinokio.js,
    pinokio.json) that drives this script. The launcher adds pterm push
    notifications + clipboard sharing of the run summary.
  * Per-engine review READMEs — `pmoves/tools/test_all_tts_engines/engines/`
    captures the contract an implementer/reviewer needs without re-reading
    launch.py.

Usage:
    python pmoves/tools/test_all_tts_engines.py [--no-play] [--engine ENGINE] [--load-only]

Options:
    --no-play       Skip audio playback, only save files
    --engine NAME   Test only specified engine (e.g., kitten_tts)
    --load-only     Only test model loading, skip synthesis
    --url URL       Override TTS Studio URL (default: http://127.0.0.1:7860/)
    --no-pterm      Skip pterm pre-flight (auto-start via Pinokio)
    --metrics       Capture GPU VRAM via GPU Orchestrator (port 8200)
    --notify        Send a pterm desktop notification when the run finishes
    --clip-report   Copy the run summary to the system clipboard via pterm
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
        "unload_api": "/handle_unload_kitten",
        "load_kwargs": {},
        "synth_kwargs": {"kitten_voice": "expr-voice-2-f"},
    },
    {
        "id": "kokoro",
        "name": "Kokoro TTS",
        "load_api": "/handle_load_kokoro",
        "unload_api": "/handle_unload_kokoro",
        "load_kwargs": {},
        "synth_kwargs": {"kokoro_voice": "af_heart", "kokoro_speed": 1.0},
    },
    {
        "id": "f5_tts",
        "name": "F5-TTS",
        # F5-TTS needs model download before first load.
        "setup_api": "/handle_f5_download",
        "load_api": "/handle_f5_load",
        "unload_api": "/handle_f5_unload",
        "load_kwargs": {"model_name": "F5-TTS Base"},
        "synth_kwargs": {"f5_speed": 1.0},
    },
    {
        "id": "indextts2",
        "name": "IndexTTS2",
        "load_api": "/handle_load_indextts2",
        "unload_api": "/handle_unload_indextts2",
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
        "unload_api": "/handle_unload_fish",
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
        "unload_api": "/handle_unload_chatterbox",
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
        "unload_api": "/handle_unload_voxcpm",
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
        "unload_api": "/handle_unload_higgs",
        "load_kwargs": {},
        "synth_kwargs": {
            "higgs_voice_preset": "EMPTY",
            "higgs_system_prompt": "Read the following text naturally and clearly.",
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
        "unload_api": "/handle_unload_qwen",
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
        "unload_api": "/handle_unload_indextts",
        "load_kwargs": {},
        "synth_kwargs": {"indextts_temperature": 0.8},
    },
    {
        "id": "fish_s2",
        "name": "Fish Speech S2 Pro",
        "load_api": "/handle_load_fish_s2",
        "unload_api": "/handle_unload_fish_s2",
        # S2 Pro (4.56B params) needs repo clone + weight download first.
        # setup_api is called before load_api if present.
        "setup_api": "/handle_setup_fish_s2",
        "load_kwargs": {},
        "synth_kwargs": {
            "fish_s2_temperature": 0.8,
            "fish_s2_top_p": 0.8,
            "fish_s2_repetition_penalty": 1.1,
            "fish_s2_max_tokens": 2048,
        },
    },
    {
        "id": "chatterbox_turbo",
        "name": "Chatterbox Turbo",
        "load_api": "/handle_load_chatterbox_turbo",
        "unload_api": "/handle_unload_chatterbox_turbo",
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
        "unload_api": "/handle_unload_chatterbox_multilingual",
        "load_kwargs": {},
        "synth_kwargs": {
            "chatterbox_mtl_language": "en",
            "chatterbox_mtl_exaggeration": 0.5,
            "chatterbox_mtl_temperature": 0.8,
            "chatterbox_mtl_cfg_weight": 0.5,
        },
    },
    {
        # VibeVoice uses a separate panel (handle_vibevoice_generation),
        # NOT the unified generate_unified_tts endpoint.
        # Model download must happen first via /handle_vibevoice_download.
        "id": "vibevoice",
        "name": "VibeVoice",
        "setup_api": "/handle_vibevoice_download",
        "load_api": "/handle_vibevoice_load",
        "unload_api": "/handle_vibevoice_unload",
        "load_kwargs": {
            "selected_model_path": "models\\VibeVoice-1.5B",
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
        print("    Processes:")
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

    # Some engines need a setup step (repo clone + weight download) before loading.
    setup_api = engine.get("setup_api")
    if setup_api:
        try:
            setup_result = client.predict(api_name=setup_api)
            setup_msg = str(setup_result) if setup_result else ""
            # Check for success FIRST — some engines return "pull failed,
            # using existing ✅" which contains both "failed" and "✅".
            # The ✅ indicates the setup ultimately succeeded.
            if "\u2705" in setup_msg:
                pass  # Setup succeeded despite partial warnings
            elif "\u274c" in setup_msg:
                return False, f"setup failed: {setup_msg[:60]}", client
            elif "failed" in setup_msg.lower() and "existing" not in setup_msg.lower():
                return False, f"setup failed: {setup_msg[:60]}", client
        except Exception as e:
            return False, f"setup error: {str(e)[:50]}", client

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


def unload_engine(
    client: Client, engine: dict, url: str,
) -> tuple[bool, str, Client]:
    """Unload a TTS engine to free VRAM.

    Calls the engine's Gradio unload endpoint which runs:
    del model; gc.collect(); torch.cuda.empty_cache()

    Returns:
        (success, message, client) — client may be refreshed after errors.
    """
    unload_api = engine.get("unload_api")
    if not unload_api:
        return False, "no unload endpoint", client

    try:
        result = client.predict(api_name=unload_api)
        status = str(result) if result else ""
        if "✅" in status or "unloaded" in status.lower() or "freed" in status.lower():
            return True, "unloaded", client
        # Non-error response — treat as success
        if status and "❌" not in status:
            return True, f"status: {status[:40]}", client
        return False, status[:60] or "empty response", client
    except Exception as e:
        msg = str(e)[:60]
        new_client = _reconnect_client(url)
        if new_client is not None:
            return False, f"{msg} (reconnected)", new_client
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


# ---------------------------------------------------------------------------
# Pinokio pterm pre-flight (Lane 4 redo, 2026-08-01)
# ---------------------------------------------------------------------------
# Replaces the original hand-rolled 180-line wrapper that called `pterm search`
# and `pterm run` (subcommands that do NOT exist in the real pterm CLI) and
# had a 50-line JSON→key=value→colon-separated text fallback parser.
#
# Per the pterm skill (pmoves/AGENTS.md → pterm), pterm is the Pinokio CLI
# for managing apps, clipboard, and notifications. The real subcommands:
#
#   pterm list                     — discover installed apps (JSON array)
#   pterm status <id>              — JSON { state, ready, ready_url, path }
#   pterm start <id>               — daemon: boot the app, returns immediately
#   pterm running <id>             — JSON { running, ready_url } (truthful poll)
#   pterm push "msg" --title "..."  — desktop notification
#   pterm clipboard write "..."    — system clipboard
#
# This is the wrap-don't-reinvent path: pterm does the work, we just orchestrate
# the subcommands. We don't reimplement PATH resolution (pterm knows itself),
# don't reimplement status parsing (pterm outputs JSON), and don't reimplement
# polling (pterm running is the truthful source of truth).
# ---------------------------------------------------------------------------

# TTS Studio app identifiers we search for in `pterm list`. The curated
# YAML at pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml is the
# source of truth for the canonical slug.
TTS_APP_HINTS = ("ultimate-tts-studio", "ultimate_tts", "tts-studio")
PTERM_READY_TIMEOUT_S = 180
PTERM_POLL_INTERVAL_S = 2


def _pterm_path() -> str | None:
    """Return the pterm binary path, or None if not installed.

    pterm is bundled with Pinokio (per the pterm skill). We don't try
    platform-specific candidate paths — pterm itself is the right place to
    know where it lives, and `shutil.which` is the standard discovery.
    """
    return shutil.which("pterm")


def _pterm_call(args: list[str], timeout: int = 30) -> dict | list | None:
    """Run a pterm subcommand and return parsed JSON output.

    Returns None on: pterm missing, non-zero exit, non-JSON output, timeout.
    Per the original hand-rolled code's learnings, ALWAYS pin
    `encoding="utf-8"` on Windows — the default `text=True` masks real
    numbers with the system code page.
    """
    pterm = _pterm_path()
    if not pterm:
        return None
    try:
        result = subprocess.run(
            [pterm, *args],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, (dict, list)) else None


def _pterm_find_tts_app() -> dict | None:
    """Find the TTS Studio app in `pterm list` output.

    pterm list output schema varies across Pinokio versions — check all the
    typical identifier fields and match on the curated YAML's slug.
    """
    data = _pterm_call(["list"])
    if not isinstance(data, list):
        return None
    for app in data:
        if not isinstance(app, dict):
            continue
        # Slug is the canonical id; name/title/path are fallbacks
        joined = " ".join(
            str(app.get(k, "")) for k in ("slug", "name", "title", "path", "app_id", "id")
        ).lower()
        if any(hint in joined for hint in TTS_APP_HINTS):
            return app
    return None


def _pterm_wait_ready(
    identifier: str, timeout_s: int = PTERM_READY_TIMEOUT_S,
) -> str | None:
    """Poll `pterm running <id>` until the app is serving HTTP or we time out.

    Per the pterm skill, `pterm running` is the truthful polling primitive —
    it doesn't lie about "started" until the app is actually serving traffic.
    Returns the ready_url (e.g., http://127.0.0.1:7860/) or None.
    """
    deadline = time.time() + timeout_s
    poll_interval = PTERM_POLL_INTERVAL_S
    while time.time() < deadline:
        data = _pterm_call(["running", identifier])
        if isinstance(data, dict) and data.get("running") is True:
            ready_url = data.get("ready_url") or data.get("url")
            if ready_url:
                return str(ready_url)
        time.sleep(poll_interval)
        # Back off slightly so we don't hammer the running daemon
        poll_interval = min(poll_interval + 1, 5)
    return None


def pterm_bring_up_tts_studio() -> tuple[str | None, str | None]:
    """Discover, start, and wait for Ultimate-TTS-Studio via pterm.

    Returns (ready_url, identifier) on success, (None, None) on failure.
    On failure, the harness falls back to direct connection at the curated
    YAML's documented port (http://127.0.0.1:7860/).
    """
    if not _pterm_path():
        print("  Pterm: not installed (will connect directly)")
        return None, None
    print(f"  Pterm: {_pterm_path()}")

    app = _pterm_find_tts_app()
    if not app:
        print("  Pterm: TTS Studio not found in app list")
        return None, None

    # Prefer the slug (canonical id), fall back to path
    identifier = str(
        app.get("slug") or app.get("app_id") or app.get("id") or app.get("path", "")
    )
    if not identifier:
        print("  Pterm: TTS Studio found but has no identifier")
        return None, None
    print(f"  Pterm: found app -> {identifier}")

    # 1. Check status — if already running, we're done
    status = _pterm_call(["status", identifier])
    if isinstance(status, dict):
        ready_url = str(status.get("ready_url") or status.get("url") or "")
        if bool(status.get("ready")) and ready_url:
            print(f"  Pterm: already running at {ready_url}")
            return ready_url, identifier

    # 2. Boot the app — pterm start is daemon, returns immediately
    print(f"  Pterm: starting {identifier}...")
    started = _pterm_call(["start", identifier])
    # pterm start returns { ok: bool, ... } on success/failure;
    # `None` here means pterm is unreachable, which is already a fail
    if started is None:
        print("  Pterm: start call failed")
        return None, identifier

    # 3. Poll for readiness via pterm running (truthful)
    print(f"  Pterm: waiting for readiness (timeout {PTERM_READY_TIMEOUT_S}s)...")
    ready_url = _pterm_wait_ready(identifier)
    if ready_url:
        print(f"  Pterm: ready at {ready_url}")
        return ready_url, identifier

    print(f"  Pterm: {identifier} did not become ready in {PTERM_READY_TIMEOUT_S}s")
    return None, identifier


def pterm_notify(title: str, message: str) -> bool:
    """Push a desktop notification via `pterm push`. Returns True on success.

    Used by the gepeto launcher (pinokio/start.js) and the --notify flag.
    """
    pterm = _pterm_path()
    if not pterm:
        return False
    try:
        result = subprocess.run(
            [pterm, "push", message, "--title", title],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def pterm_clipboard_write(text: str) -> bool:
    """Copy text to the system clipboard via `pterm clipboard write`.

    Used by the gepeto launcher (pinokio/start.js) and the --clip-report flag.
    """
    pterm = _pterm_path()
    if not pterm:
        return False
    try:
        result = subprocess.run(
            [pterm, "clipboard", "write", text],
            input=text,
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


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
    parser.add_argument("--notify", action="store_true",
                        help="Send a pterm desktop notification when the run finishes")
    parser.add_argument("--clip-report", action="store_true",
                        help="Copy the run summary to the system clipboard via pterm")
    args = parser.parse_args()

    url = args.url.rstrip("/") + "/"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print_header("TTS Engine Test Suite (gradio_client)")
    print(f"  Target: {url}")
    print(f"  Output: {OUTPUT_DIR}")

    # Pterm pre-flight: auto-start TTS Studio if possible.
    # Skip pterm if user explicitly provided --url or set ULTIMATE_TTS_URL env var
    # (the gepeto launcher also wires this via start.js; see pinokio/).
    env_url_set = "ULTIMATE_TTS_URL" in os.environ
    skip_pterm = args.no_pterm or (args.url != DEFAULT_URL) or env_url_set
    if not skip_pterm:
        print("\n  Pterm pre-flight...")
        ready_url, _identifier = pterm_bring_up_tts_studio()
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

    # ── Per-engine: Load → Synth → Unload ────────────────────────────
    # Each engine is loaded, tested, then unloaded before the next one.
    # This keeps max 1 engine in VRAM at a time (~44GB total vs 32GB GPU).
    print_header("Engine Tests (load → synth → unload)")

    load_results = {}
    synth_results = {}
    for i, engine in enumerate(engines_to_test, 1):
        eid = engine["id"]
        print(f"\n  [{i}/{len(engines_to_test)}] {engine['name']}")

        # ── Load ──
        print("      Loading...", end=" ", flush=True)
        gpu_before = capture_gpu_metrics() if args.metrics else None

        start = time.time()
        success, message, client = load_engine(client, engine, url)
        elapsed = time.time() - start

        load_results[eid] = success
        if success:
            print(f"✓ ({elapsed:.1f}s)")
        elif message.startswith("skipped"):
            print(f"⏭ {message}")
            synth_results[eid] = "skip"
            continue
        elif "reconnected" in message:
            print(f"❌ {message} — client refreshed")
            synth_results[eid] = False
            continue
        else:
            print(f"❌ {message}")
            synth_results[eid] = False
            continue

        # GPU metrics after load
        if args.metrics:
            gpu_after_load = capture_gpu_metrics()
            print_gpu_delta(f"{engine['name']} load", gpu_before, gpu_after_load)

        # ── Synth (unless --load-only or separate endpoint) ──
        if args.load_only:
            synth_results[eid] = "skip"
        elif engine["synth_kwargs"] is None:
            print("      ⏭ Synth: separate endpoint (skip)")
            synth_results[eid] = "skip"
        else:
            print(f"      Synthesizing: \"{TEST_TEXT[:40]}...\"")
            gpu_before_synth = capture_gpu_metrics() if args.metrics else None

            start = time.time()
            synth_ok, audio_path, synth_msg, client = synthesize_engine(
                client, engine, TEST_TEXT, url,
            )
            elapsed = time.time() - start

            if not synth_ok:
                extra = " — client refreshed" if "reconnected" in synth_msg else ""
                print(f"      ❌ FAIL: {synth_msg}{extra}")
                synth_results[eid] = False
            else:
                # Validate WAV
                validation = validate_wav(audio_path)
                if not validation["valid"]:
                    print(f"      ❌ Invalid WAV: {', '.join(validation['errors'])}")
                    synth_results[eid] = False
                else:
                    output_path = OUTPUT_DIR / f"{eid}.wav"
                    shutil.copy(audio_path, output_path)
                    size_kb = validation["size"] / 1024
                    print(f"      ✓ {size_kb:.0f}KB, {validation['duration']:.1f}s @ {validation['sample_rate']}Hz ({elapsed:.1f}s)")
                    print(f"      Saved: {output_path}")
                    synth_results[eid] = True

                    if args.metrics:
                        gpu_after_synth = capture_gpu_metrics()
                        print_gpu_delta(f"{engine['name']} synth", gpu_before_synth, gpu_after_synth)

                    play_audio(output_path, skip_play=args.no_play)

        # ── Unload — free VRAM for next engine ──
        print("      Unloading...", end=" ", flush=True)
        ul_ok, ul_msg, client = unload_engine(client, engine, url)
        if ul_ok:
            print("✓ VRAM freed")
        else:
            print(f"⚠ {ul_msg}")

        if args.metrics:
            gpu_after_unload = capture_gpu_metrics()
            if gpu_before and gpu_after_unload:
                freed = (gpu_before.get("used_vram_mb") or 0) - (gpu_after_unload.get("used_vram_mb") or 0)
                if abs(freed) > 10:
                    print(f"      VRAM net: {'+' if freed < 0 else '-'}{abs(freed):,.0f} MB")

    loaded = sum(1 for v in load_results.values() if v)
    if args.load_only:
        print("\n  (--load-only mode, all engines unloaded after metrics)")
        return 0 if loaded > 0 else 1

    # ── Summary ───────────────────────────────────────────────────────
    print_header("Summary")

    synth_pass = sum(1 for v in synth_results.values() if v is True)
    synth_fail = sum(1 for v in synth_results.values() if v is False)
    synth_skip = sum(1 for v in synth_results.values() if v == "skip")

    print(f"  Load:  {loaded}/{len(engines_to_test)} engines")
    if not args.load_only:
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

    # Build a single-line run summary for notify + clipboard.
    run_summary = (
        f"TTS test: {synth_pass} pass / {synth_fail} fail / {synth_skip} skip "
        f"({loaded} loaded) → {OUTPUT_DIR}"
    )

    # Pterm notify — pterm push is the right primitive for desktop notifications.
    # The gepeto launcher (pinokio/start.js) does this after the shell.run, so
    # the --notify flag is for direct CLI users.
    if args.notify:
        if pterm_notify("PMOVES TTS Test", run_summary):
            print(f"  Notify: ✓ pterm push sent")
        else:
            print(f"  Notify: ⚠ pterm not available (skip)")

    # Pterm clipboard — copy the summary so it's paste-able from anywhere.
    # Same rationale: the gepeto launcher does this, --clip-report is for CLI.
    if args.clip_report:
        if pterm_clipboard_write(run_summary):
            print(f"  Clipboard: ✓ pterm clipboard write done")
        else:
            print(f"  Clipboard: ⚠ pterm not available (skip)")

    return 0 if (loaded > 0 if args.load_only else synth_pass > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
