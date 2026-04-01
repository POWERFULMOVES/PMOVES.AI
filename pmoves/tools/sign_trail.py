#!/usr/bin/env python3
"""Sign a Graphiti trail entry with CHIT HMAC.

CLI tool that creates an agent.graphiti.signed.v1 payload and HMAC-signs it
using sign_cgp() from chit_security.py.  Never contains its own crypto —
chit_security is the single source of truth.

Usage:
    python tools/sign_trail.py --agent-id claude-opus --summary "Completed X"
    python tools/sign_trail.py --agent-id 4090-claude --alter 4090-field --summary "Infra work"
    python tools/sign_trail.py --stdin < payload.json
    echo '{"agent_id":"claude-opus","summary":"test"}' | python tools/sign_trail.py --stdin
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Resolve project root (pmoves/) so sibling imports work when invoked from
# Make or hooks without PYTHONPATH gymnastics.
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
_PMOVES_ROOT = _TOOLS_DIR.parent
if str(_PMOVES_ROOT) not in sys.path:
    sys.path.insert(0, str(_PMOVES_ROOT))

from tools.chit_security import sign_cgp  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SIGNATURES_PATH = _PMOVES_ROOT / "config" / "agent_signatures.yaml"
_SCHEMA_PATH = (
    _PMOVES_ROOT / "contracts" / "schemas" / "agent-graphiti" / "signature.v1.schema.json"
)
_LOG_PATH = _PMOVES_ROOT / "docs" / "logs" / "graphiti_signed_latest.json"

# Fallback glyph/color when agent_signatures.yaml is unavailable
_FALLBACK = {"glyph": "\u25C6", "color": "#7C3AED", "accent": "#A78BFA", "voice": "analytical"}


def _load_signature(agent_id: str) -> Dict[str, Any]:
    """Look up glyph, color, voice from agent_signatures.yaml."""
    try:
        import yaml  # type: ignore[import-untyped]

        with open(_SIGNATURES_PATH, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        sigs = data.get("signatures", {})
        if agent_id in sigs:
            return sigs[agent_id]
    except Exception:
        pass
    # Return a minimal fallback so the tool never hard-fails on missing YAML
    return {"agent_id": agent_id, **_FALLBACK}


def _resolve_alter(sig: Dict[str, Any], alter_name: str) -> Optional[Dict[str, Any]]:
    """Find an alter by name within an agent's signature entry.

    Returns the alter dict if found, or None.
    """
    alters = sig.get("alters", [])
    for alter in alters:
        if alter_name in {
            alter.get("name"),
            alter.get("id"),
            alter.get("display_name"),
        }:
            return alter
    return None


def _validate_schema(payload: Dict[str, Any]) -> Optional[str]:
    """Validate payload against signature.v1.schema.json.  Returns error or None."""
    try:
        import jsonschema  # type: ignore[import-untyped]

        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(payload, schema)
        return None
    except ImportError:
        return None  # soft-skip if jsonschema not installed
    except Exception as exc:
        return str(exc)


def build_payload(
    agent_id: str,
    summary: str,
    phase: str = "Phase H",
    resonance: Optional[list] = None,
    alter: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an unsigned Graphiti signature payload.

    If *alter* is provided, override visual identity fields (glyph, color,
    accent, voice, resonance) with the named alter from the agent's ``alters``
    array.  The ``agent_id`` stays the same — ``selected_alter`` records which
    persona was active.
    """
    sig = _load_signature(agent_id)

    # Resolve alter overlay if requested
    alter_data: Optional[Dict[str, Any]] = None
    if alter:
        alter_data = _resolve_alter(sig, alter)
        if alter_data is None:
            available = [
                a.get("name") or a.get("id") or a.get("display_name", "?")
                for a in sig.get("alters", [])
            ]
            print(
                f"[warn] alter '{alter}' not found for {agent_id}; "
                f"available: {available or 'none'}",
                file=sys.stderr,
            )

    # Build identity — alter fields override primary when present
    identity = alter_data if alter_data else sig

    payload: Dict[str, Any] = {
        "agent_id": agent_id,
        "display_name": sig.get("display_name", agent_id),
        "glyph": identity.get("glyph", _FALLBACK["glyph"]),
        "color": identity.get("color", _FALLBACK["color"]),
        "accent": identity.get("accent", _FALLBACK.get("accent")),
        "voice": identity.get("voice", _FALLBACK["voice"]),
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resonance": resonance or identity.get("resonance", sig.get("resonance", [])),
        "summary": summary[:200],
    }

    # Record which alter was selected (agent_id stays primary)
    if alter_data:
        payload["selected_alter"] = alter

    return payload


def sign_trail(
    agent_id: str,
    summary: str,
    phase: str = "Phase H",
    resonance: Optional[list] = None,
    passphrase: Optional[str] = None,
    alter: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and optionally HMAC-sign a Graphiti trail payload.

    Args:
        agent_id: Must match a key in agent_signatures.yaml.
        summary: One-line summary of the work (max 200 chars).
        phase: Project phase label.
        resonance: Optional list of resonance domains.
        passphrase: CHIT_PASSPHRASE.  If None, returns unsigned payload.
        alter: Optional alter name to select from the agent's alters array.

    Returns:
        Signed (or unsigned) payload dict.
    """
    payload = build_payload(agent_id, summary, phase, resonance, alter)

    # Schema validation (advisory)
    err = _validate_schema(payload)
    if err:
        print(f"[warn] schema validation: {err}", file=sys.stderr)

    if passphrase:
        payload = sign_cgp(payload, passphrase)
    else:
        print("[warn] CHIT_PASSPHRASE not set — payload is unsigned", file=sys.stderr)

    return payload


def _write_log(payload: Dict[str, Any]) -> None:
    """Persist latest signed payload to docs/logs/."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def main() -> None:
    """CLI entry point for signing a Graphiti trail entry."""
    parser = argparse.ArgumentParser(
        description="Sign a Graphiti trail entry with CHIT HMAC"
    )
    parser.add_argument(
        "--agent-id",
        default="claude-opus",
        help="Agent identifier (must match agent_signatures.yaml key)",
    )
    parser.add_argument(
        "--summary",
        default="Trail entry signed",
        help="One-line summary of work (max 200 chars)",
    )
    parser.add_argument(
        "--phase",
        default="Phase H",
        help="Project phase label",
    )
    parser.add_argument(
        "--alter",
        default=None,
        help="Select an alternate identity from the agent's alters array",
    )
    parser.add_argument(
        "--resonance",
        nargs="*",
        help="Resonance domains (space-separated)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON payload from stdin (overrides --agent-id/--summary/--phase)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Skip writing to docs/logs/graphiti_signed_latest.json",
    )
    args = parser.parse_args()

    passphrase = os.environ.get("CHIT_PASSPHRASE")

    if args.stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            print("[error] --stdin specified but no data received", file=sys.stderr)
            sys.exit(1)
        data = json.loads(raw)
        agent_id = data.get("agent_id", args.agent_id)
        summary = data.get("summary", args.summary)
        phase = data.get("phase", args.phase)
        resonance = data.get("resonance", args.resonance)
        alter = data.get("alter", args.alter)
    else:
        agent_id = args.agent_id
        summary = args.summary
        phase = args.phase
        resonance = args.resonance
        alter = args.alter

    payload = sign_trail(agent_id, summary, phase, resonance, passphrase, alter)

    # Write log artifact
    if not args.no_log:
        _write_log(payload)

    # Print to stdout for downstream piping
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()


