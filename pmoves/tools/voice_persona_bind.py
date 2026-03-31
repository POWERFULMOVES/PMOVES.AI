#!/usr/bin/env python3
"""Voice Persona Binding — maps agent identity to TTS engine + prosodic parameters.

Resolves an agent's voice descriptor (from agent_signatures.yaml) to a concrete
TTS engine configuration including engine name, voice ID, speech rate, pause
duration, and emphasis level.  Optionally calls Flute-Gateway to synthesize
a greeting.

Usage:
    python pmoves/tools/voice_persona_bind.py resolve --agent claude-opus
    python pmoves/tools/voice_persona_bind.py resolve --agent claude-opus --json
    python pmoves/tools/voice_persona_bind.py list
    python pmoves/tools/voice_persona_bind.py list --json
    python pmoves/tools/voice_persona_bind.py synthesize --agent claude-opus --text "Hello world"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
_PMOVES_ROOT = _TOOLS_DIR.parent
_SIGNATURES_PATH = _PMOVES_ROOT / "config" / "agent_signatures.yaml"
_FLUTE_URL = os.getenv("FLUTE_GATEWAY_URL", "http://localhost:8055")

# ---------------------------------------------------------------------------
# Voice descriptor -> TTS engine config mapping
# ---------------------------------------------------------------------------
VOICE_MAP: Dict[str, Dict[str, Any]] = {
    "analytical": {
        "engine": "Kokoro TTS",
        "voice_id": "af_heart",
        "rate": 0.95,
        "pause_ms": 300,
        "emphasis": "moderate",
    },
    "architectural": {
        "engine": "Kokoro TTS",
        "voice_id": "am_michael",
        "rate": 0.90,
        "pause_ms": 350,
        "emphasis": "moderate",
    },
    "terse": {
        "engine": "KittenTTS",
        "voice_id": "expr-voice-2-m",
        "rate": 1.15,
        "pause_ms": 100,
        "emphasis": "low",
    },
    "conversational": {
        "engine": "ChatterboxTTS",
        "voice_id": "default",
        "rate": 1.05,
        "pause_ms": 200,
        "emphasis": "high",
    },
    "companion": {
        "engine": "F5-TTS",
        "voice_id": "default",
        "rate": 1.00,
        "pause_ms": 250,
        "emphasis": "moderate",
    },
    "witness": {
        "engine": "IndexTTS2",
        "voice_id": "default",
        "rate": 0.85,
        "pause_ms": 400,
        "emphasis": "high",
    },
    "dimensional": {
        "engine": "Higgs Audio",
        "voice_id": "default",
        "rate": 1.00,
        "pause_ms": 300,
        "emphasis": "high",
    },
    "directive": {
        "engine": "KittenTTS",
        "voice_id": "expr-voice-3-m",
        "rate": 0.95,
        "pause_ms": 200,
        "emphasis": "high",
    },
    "strategic": {
        "engine": "Kokoro TTS",
        "voice_id": "am_adam",
        "rate": 0.90,
        "pause_ms": 350,
        "emphasis": "moderate",
    },
    "broadcast": {
        "engine": "Kokoro TTS",
        "voice_id": "am_adam",
        "rate": 0.90,
        "pause_ms": 300,
        "emphasis": "high",
    },
}

# ---------------------------------------------------------------------------
# Data loading (pattern from botz_cli.py)
# ---------------------------------------------------------------------------
def _load_signatures() -> Dict[str, Any]:
    """Load agent signatures from YAML."""
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml required (pip install pyyaml)", file=sys.stderr)
        return {}
    if not _SIGNATURES_PATH.exists():
        print(f"ERROR: {_SIGNATURES_PATH} not found", file=sys.stderr)
        return {}
    with open(_SIGNATURES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("signatures", {})


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def resolve_voice_profile(agent_id: str) -> dict:
    """Look up an agent's voice descriptor and return the TTS engine config.

    Returns a dict with keys: agent_id, display_name, voice_descriptor, engine,
    voice_id, rate, pause_ms, emphasis.  If the agent or voice descriptor is
    not found, the returned dict contains an ``error`` key instead.
    """
    sigs = _load_signatures()
    sig = sigs.get(agent_id)
    if not sig:
        return {"error": f"Agent '{agent_id}' not found", "agent_id": agent_id}

    voice_descriptor = sig.get("voice", "unknown")
    engine_cfg = VOICE_MAP.get(voice_descriptor)
    if not engine_cfg:
        return {
            "error": f"No engine mapping for voice descriptor '{voice_descriptor}'",
            "agent_id": agent_id,
            "voice_descriptor": voice_descriptor,
        }

    return {
        "agent_id": agent_id,
        "display_name": sig.get("display_name", agent_id),
        "glyph": sig.get("glyph", "?"),
        "color": sig.get("color", "#888888"),
        "voice_descriptor": voice_descriptor,
        **engine_cfg,
    }


def synthesize_agent_greeting(
    agent_id: str,
    text: str | None = None,
) -> Optional[str]:
    """Call Flute-Gateway prosodic synthesis for *agent_id*.

    Returns the JSON response body as a string on success, or ``None`` if the
    gateway is unreachable or returns an error.
    """
    profile = resolve_voice_profile(agent_id)
    if "error" in profile:
        print(f"ERROR: {profile['error']}", file=sys.stderr)
        return None

    if text is None:
        display = profile.get("display_name", agent_id)
        text = f"Hello, I am {display}. How can I help you today?"

    payload = json.dumps({
        "text": text,
        "engine": profile["engine"],
        "voice_id": profile["voice_id"],
        "prosody": {
            "rate": profile["rate"],
            "pause_ms": profile["pause_ms"],
            "emphasis": profile["emphasis"],
        },
        "agent_id": agent_id,
    }).encode("utf-8")

    # Validate URL scheme to prevent SSRF via env var injection
    if not _FLUTE_URL.startswith(("http://", "https://")):
        print(f"[voice] Invalid FLUTE_GATEWAY_URL scheme: {_FLUTE_URL}", file=sys.stderr)
        return None

    url = f"{_FLUTE_URL}/v1/voice/synthesize/prosodic"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — validated above
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"WARNING: Flute-Gateway unavailable ({exc})", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve voice profile for a given agent."""
    profile = resolve_voice_profile(args.agent)
    if "error" in profile:
        if args.json:
            print(json.dumps(profile, indent=2))
        else:
            print(f"ERROR: {profile['error']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(profile, indent=2))
    else:
        print(f"{profile.get('glyph', '?')} {profile['display_name']}")
        print(f"  voice:    {profile['voice_descriptor']}")
        print(f"  engine:   {profile['engine']}")
        print(f"  voice_id: {profile['voice_id']}")
        print(f"  rate:     {profile['rate']}")
        print(f"  pause:    {profile['pause_ms']}ms")
        print(f"  emphasis: {profile['emphasis']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all agents with their voice-to-engine mappings."""
    sigs = _load_signatures()
    if not sigs:
        print("ERROR: No signatures loaded", file=sys.stderr)
        return 1

    entries = []
    for aid, sig in sigs.items():
        voice = sig.get("voice", "unknown")
        engine_cfg = VOICE_MAP.get(voice)
        entry = {
            "agent_id": aid,
            "display_name": sig.get("display_name", aid),
            "glyph": sig.get("glyph", "?"),
            "voice_descriptor": voice,
            "engine": engine_cfg["engine"] if engine_cfg else None,
            "voice_id": engine_cfg["voice_id"] if engine_cfg else None,
            "mapped": engine_cfg is not None,
        }
        entries.append(entry)

    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        mapped_count = sum(1 for e in entries if e["mapped"])
        print(f"Voice Persona Bindings ({mapped_count}/{len(entries)} mapped)\n")
        for e in entries:
            status = e["engine"] if e["mapped"] else "(unmapped)"
            glyph = e["glyph"]
            name = e["display_name"]
            voice = e["voice_descriptor"]
            print(f"  {glyph} {name:<22} {voice:<16} -> {status}")
        print()
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize a greeting for a given agent via Flute-Gateway."""
    result = synthesize_agent_greeting(args.agent, args.text)
    if result is None:
        if args.json:
            print(json.dumps({"error": "Synthesis failed or gateway unavailable"}, indent=2))
        else:
            print("ERROR: Synthesis failed or Flute-Gateway unavailable", file=sys.stderr)
        return 1

    if args.json:
        # Try to parse and re-pretty-print; fall back to raw string
        try:
            parsed = json.loads(result)
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(json.dumps({"raw_response": result}, indent=2))
    else:
        print(f"Synthesis complete. Response:\n{result}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Voice Persona Binding CLI entry point."""
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="voice-persona-bind",
        description="Voice Persona Binding — maps agent identity to TTS engine + prosodic parameters",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Shared parent for --json
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--json", action="store_true", help="JSON output")

    # resolve
    resolve_p = subparsers.add_parser(
        "resolve",
        help="Resolve voice profile for an agent",
        parents=[json_parent],
    )
    resolve_p.add_argument("--agent", required=True, help="Agent ID")

    # list
    subparsers.add_parser(
        "list",
        help="List all agents with voice-to-engine mappings",
        parents=[json_parent],
    )

    # synthesize
    synth_p = subparsers.add_parser(
        "synthesize",
        help="Synthesize speech via Flute-Gateway for an agent",
        parents=[json_parent],
    )
    synth_p.add_argument("--agent", required=True, help="Agent ID")
    synth_p.add_argument("--text", default=None, help="Text to synthesize (default: greeting)")

    args = parser.parse_args()

    if args.command == "resolve":
        return cmd_resolve(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "synthesize":
        return cmd_synthesize(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
