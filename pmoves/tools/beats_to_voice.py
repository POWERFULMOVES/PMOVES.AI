#!/usr/bin/env python3
"""
beats_to_voice.py -- Beats-to-Voice Pipeline Orchestrator

End-to-end pipeline: Audio analysis -> BPM encoding -> Prosodic profile -> Voice synthesis.

Stages:
    1. (Optional) Spectral analysis via analyze_beats.extract_all()
    2. Prosodic encoding via bpm_encoder.encode_prosodic_profile()
    3. CGP packet generation via bpm_encoder.build_cgp_packet()
    4. (Optional) Voice synthesis via Flute-Gateway POST /v1/voice/synthesize/prosodic

CLI:
    python beats_to_voice.py from-bpm --bpm 120 --text "Hello world" [--voice default]
    python beats_to_voice.py analyze-only --audio track.mp3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import sibling modules with graceful fallback
# ---------------------------------------------------------------------------

# bpm_encoder is a hard dependency -- same directory
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

from bpm_encoder import (  # noqa: E402
    encode_prosodic_profile,
    build_cgp_packet,
    midi_to_freq,
    midi_to_note_name,
    boundary_to_bpm,
    bpm_to_tempo_label,
)

# analyze_beats is optional (heavy deps: numpy, sklearn, etc.)
_HAS_ANALYZE_BEATS = False
try:
    import analyze_beats  # noqa: E402
    _HAS_ANALYZE_BEATS = True
except ImportError:
    analyze_beats = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FLUTE_GATEWAY_URL = os.environ.get("FLUTE_GATEWAY_URL", "http://localhost:8055")
DEFAULT_VOICE = os.environ.get("BEATS_VOICE", "default")
DEFAULT_AGENT_ID = os.environ.get("BEATS_AGENT_ID", "4090-claude")
NATS_SUBJECT = "tokenism.prosodic.bpm.v1"


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only -- no new deps)
# ---------------------------------------------------------------------------

def _post_json(url: str, payload: dict, timeout: int = 30) -> dict[str, Any] | None:
    """POST JSON via urllib.request. Returns parsed JSON or None on failure."""
    if not url.startswith(("http://", "https://")):
        sys.stderr.write(f"[beats_to_voice] Invalid URL scheme: {url}\n")
        return None
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        sys.stderr.write(
            f"[beats_to_voice] HTTP {e.code} from {url}: {err_body}\n"
        )
        return None
    except (urllib.error.URLError, OSError) as e:
        sys.stderr.write(f"[beats_to_voice] Connection failed to {url}: {e}\n")
        return None


def _get_json(url: str, timeout: int = 5) -> dict[str, Any] | None:
    """GET JSON via urllib.request. Returns parsed JSON or None."""
    if not url.startswith(("http://", "https://")):
        return None
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — validated above
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError):
        return None


def _check_flute_health(base_url: str) -> bool:
    """Check if Flute-Gateway is reachable."""
    result = _get_json(f"{base_url}/healthz", timeout=3)
    return result is not None


# ---------------------------------------------------------------------------
# Audio analysis stage
# ---------------------------------------------------------------------------

def analyze_audio(audio_path: str) -> dict[str, Any] | None:
    """Run spectral analysis on an audio file via analyze_beats.

    Returns the feature dict from extract_all(), or None if analyze_beats
    is not available or the file cannot be processed.
    """
    if not _HAS_ANALYZE_BEATS:
        sys.stderr.write(
            "[beats_to_voice] analyze_beats not available "
            "(install deps: numpy, scikit-learn, httpx, typer, rich)\n"
        )
        return None

    path = Path(audio_path)
    if not path.exists():
        sys.stderr.write(f"[beats_to_voice] Audio file not found: {audio_path}\n")
        return None

    try:
        # Use glaze mode (ffmpeg lavfi) -- doesn't require ML models
        features = analyze_beats.extract_all(path, mode=analyze_beats.SenseMode.glaze)
        return features
    except Exception as e:
        sys.stderr.write(f"[beats_to_voice] Audio analysis failed: {e}\n")
        return None


# ---------------------------------------------------------------------------
# Flute-Gateway synthesis stage
# ---------------------------------------------------------------------------

def synthesize_prosodic(
    profile: dict[str, Any],
    voice: str = "default",
    flute_url: str = FLUTE_GATEWAY_URL,
) -> dict[str, Any] | None:
    """Send prosodic profile to Flute-Gateway for voice synthesis.

    Endpoint: POST /v1/voice/synthesize/prosodic

    Returns the synthesis result dict or None if Flute is unavailable.
    """
    chunks = profile.get("chunks", [])
    if not chunks:
        sys.stderr.write("[beats_to_voice] No chunks in profile -- nothing to synthesize\n")
        return None

    # Build the Flute prosodic request
    prosodic_chunks = []
    for chunk in chunks:
        prosodic_chunks.append({
            "text":           chunk.get("text", ""),
            "boundary_type":  chunk.get("boundary", "NONE"),
            "pause_ms":       chunk.get("pause_ms", 0),
            "duration_sec":   chunk.get("duration_sec", 0.5),
            "pitch_hz":       chunk.get("freq", 262.0),
            "position_ratio": chunk.get("position_ratio", 0.0),
        })

    # Flute-Gateway /v1/voice/synthesize/prosodic accepts: text, voice, format
    payload = {
        "text":    profile.get("text", ""),
        "voice":   voice,
        "format":  "wav",
    }

    url = f"{flute_url}/v1/voice/synthesize/prosodic"
    return _post_json(url, payload, timeout=60)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    audio_path: str | None = None,
    text: str | None = None,
    bpm: int = 120,
    voice: str = "default",
    agent_id: str = DEFAULT_AGENT_ID,
    flute_url: str = FLUTE_GATEWAY_URL,
) -> dict[str, Any]:
    """Run the full Beats-to-Voice pipeline.

    Stages:
        1. If audio_path provided: analyze spectral data
        2. Encode prosodic profile from text + BPM
        3. Build CGP v0.2 packet
        4. If Flute available: synthesize voice

    Returns a results dict with all stage outputs.
    """
    started_at = time.time()
    results: dict[str, Any] = {
        "status":    "ok",
        "agent_id":  agent_id,
        "stages":    {},
        "errors":    [],
        "timing_sec": 0.0,
    }

    # ---- Stage 1: Audio analysis (optional) ----
    spectral_data = None
    if audio_path:
        spectral_data = analyze_audio(audio_path)
        if spectral_data:
            results["stages"]["analyze"] = {
                "file":             spectral_data.get("file", audio_path),
                "tempo_bpm":        spectral_data.get("tempo_bpm", 0),
                "tempo_label":      spectral_data.get("tempo_label", ""),
                "loudness_I":       spectral_data.get("loudness_I", 0),
                "spectral_centroid": spectral_data.get("spectral_centroid", 0),
                "energy_label":     spectral_data.get("energy_label", ""),
                "timbre":           spectral_data.get("timbre", ""),
                "character":        spectral_data.get("character", ""),
                "sense_mode":       spectral_data.get("sense_mode", ""),
            }
            # Override BPM from analysis if not explicitly set
            if spectral_data.get("tempo_bpm"):
                bpm = round(spectral_data["tempo_bpm"])
                sys.stderr.write(
                    f"[beats_to_voice] Using detected BPM: {bpm} "
                    f"({spectral_data.get('tempo_label', '')})\n"
                )
        else:
            results["errors"].append("Audio analysis returned no data")

    # ---- Stage 2: Prosodic encoding ----
    if not text:
        text = "The rhythm speaks through silence and sound."

    profile = encode_prosodic_profile(text, bpm=bpm)
    results["stages"]["encode"] = {
        "bpm":                bpm,
        "tempo_label":        profile.get("tempo_label", ""),
        "chunk_count":        len(profile.get("chunks", [])),
        "total_duration_sec": profile.get("total_duration_sec", 0.0),
        "text":               text,
    }

    # ---- Stage 3: CGP packet ----
    cgp_packet = build_cgp_packet(profile, agent_id=agent_id)
    results["stages"]["cgp"] = {
        "spec":   cgp_packet.get("spec", ""),
        "type":   cgp_packet.get("type", ""),
        "id":     cgp_packet.get("id", ""),
        "label":  cgp_packet.get("label", ""),
        "nats_subject": NATS_SUBJECT,
    }
    results["cgp_packet"] = cgp_packet

    # ---- Stage 4: Voice synthesis (optional) ----
    flute_available = _check_flute_health(flute_url)
    results["stages"]["voice"] = {"flute_available": flute_available}

    if flute_available:
        synth_result = synthesize_prosodic(profile, voice=voice, flute_url=flute_url)
        if synth_result:
            results["stages"]["voice"]["synthesis"] = synth_result
            results["stages"]["voice"]["status"] = "synthesized"
        else:
            results["stages"]["voice"]["status"] = "synthesis_failed"
            results["errors"].append("Voice synthesis returned no result")
    else:
        results["stages"]["voice"]["status"] = "flute_offline"
        sys.stderr.write(
            f"[beats_to_voice] Flute-Gateway not available at {flute_url} -- "
            "skipping voice synthesis\n"
        )

    # ---- Wrap up ----
    elapsed = time.time() - started_at
    results["timing_sec"] = round(elapsed, 3)
    if results["errors"]:
        results["status"] = "partial"

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_from_bpm(args: argparse.Namespace) -> None:
    """Run the pipeline from BPM + text."""
    results = run_pipeline(
        audio_path=None,
        text=args.text,
        bpm=args.bpm,
        voice=args.voice,
        agent_id=args.agent_id,
        flute_url=args.flute_url,
    )

    if args.cgp_only:
        print(json.dumps(results.get("cgp_packet", {}), indent=2))
    else:
        # Don't dump the full CGP packet in the summary view
        output = {k: v for k, v in results.items() if k != "cgp_packet"}
        print(json.dumps(output, indent=2))


def _cmd_analyze_only(args: argparse.Namespace) -> None:
    """Run audio analysis only."""
    if not _HAS_ANALYZE_BEATS:
        sys.stderr.write(
            "ERROR: analyze_beats module not available.\n"
            "Install dependencies: pip install numpy scikit-learn httpx typer rich\n"
        )
        sys.exit(1)

    features = analyze_audio(args.audio)
    if features:
        print(json.dumps(features, indent=2, default=str))
    else:
        sys.stderr.write(f"No features extracted from {args.audio}\n")
        sys.exit(1)


def _cmd_full(args: argparse.Namespace) -> None:
    """Run the full pipeline with audio + text."""
    results = run_pipeline(
        audio_path=args.audio,
        text=args.text,
        bpm=args.bpm,
        voice=args.voice,
        agent_id=args.agent_id,
        flute_url=args.flute_url,
    )

    output = {k: v for k, v in results.items() if k != "cgp_packet"}
    print(json.dumps(output, indent=2))

    if args.save_cgp:
        cgp_path = Path(args.save_cgp)
        cgp_path.parent.mkdir(parents=True, exist_ok=True)
        cgp_path.write_text(json.dumps(results.get("cgp_packet", {}), indent=2))
        sys.stderr.write(f"[beats_to_voice] CGP packet saved to {cgp_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="beats_to_voice",
        description="Beats-to-Voice Pipeline Orchestrator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- from-bpm --
    p_bpm = sub.add_parser("from-bpm", help="Generate prosodic profile from BPM + text")
    p_bpm.add_argument("--bpm", type=int, default=120, help="Beats per minute (default: 120)")
    p_bpm.add_argument("--text", type=str, default="The rhythm speaks through silence and sound.",
                       help="Text to encode")
    p_bpm.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="Voice profile name")
    p_bpm.add_argument("--agent-id", type=str, default=DEFAULT_AGENT_ID, help="Agent ID for CGP")
    p_bpm.add_argument("--flute-url", type=str, default=FLUTE_GATEWAY_URL,
                       help="Flute-Gateway base URL")
    p_bpm.add_argument("--cgp-only", action="store_true", help="Output only the CGP packet")
    p_bpm.set_defaults(func=_cmd_from_bpm)

    # -- analyze-only --
    p_analyze = sub.add_parser("analyze-only", help="Run spectral analysis on audio file")
    p_analyze.add_argument("--audio", type=str, required=True, help="Path to audio file")
    p_analyze.set_defaults(func=_cmd_analyze_only)

    # -- full --
    p_full = sub.add_parser("full", help="Run full pipeline: audio analysis + encoding + synthesis")
    p_full.add_argument("--audio", type=str, default=None, help="Path to audio file (optional)")
    p_full.add_argument("--text", type=str, default="The rhythm speaks through silence and sound.",
                        help="Text to encode")
    p_full.add_argument("--bpm", type=int, default=120, help="Beats per minute (default: 120)")
    p_full.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="Voice profile name")
    p_full.add_argument("--agent-id", type=str, default=DEFAULT_AGENT_ID, help="Agent ID for CGP")
    p_full.add_argument("--flute-url", type=str, default=FLUTE_GATEWAY_URL,
                        help="Flute-Gateway base URL")
    p_full.add_argument("--save-cgp", type=str, default="", help="Save CGP packet to file path")
    p_full.set_defaults(func=_cmd_full)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
