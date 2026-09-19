#!/usr/bin/env python3
"""Resolve THIS node's Docker MCP Toolkit gateway profile.

WHY THIS EXISTS. The gateway profile was the literal ``pmoves_5090_web`` in
three places at once -- ``pmoves/scripts/mcp-toolkit-connect.sh`` (which writes
the per-node ``.mcp.json``), ``.claude/mcp.json`` (the FLEET roster, which
``deploy/provision/claude-pmoves.sh`` reads from ``origin/main`` on every node
whatever branch it sits on), and ``pmoves/config/mcp_inventory.json`` (which
renders the crush/kimi/opencode configs). One node's name, baked into fleet
configuration, so every other node launched a gateway for the 5090's profile.

It failed SILENTLY rather than loudly: measured on the 4090 on 2026-09-13,
``docker mcp profile ls`` lists both ``pmoves_4090_web`` and ``pmoves_5090_web``,
so the wrong-profile launch succeeds. Nothing errors; the node just serves the
other node's server set.

RESOLUTION ORDER, and why each step is where it is:

1. ``PMOVES_MCP_PROFILE_ID`` -- the variable
   ``scripts/mcp-toolkit-gateway-listen.sh`` already uses for the SSE path.
   An explicit operator override outranks any inference.
2. The PINNED profile (``~/.pmoves/profile.json``, written by
   ``pmoves mini profile use``). An operator who pinned a profile has stated
   which node this is; that beats re-deriving it.
3. HARDWARE DETECTION via ``profile_loader.detect_profiles`` -- the same scorer
   ``pmoves mini profile detect`` uses, so this agrees with the rest of the
   tooling instead of inventing a second notion of "which node am I".
4. Nothing. Deliberately not a default.

WHY NO FALLBACK DEFAULT. A node-named default reports the same answer on every
node no matter what its gateway runs -- exactly the defect this module removes,
and the same reasoning ``docker_mcp_secrets_hydrate.discover_profiles`` records
for refusing to mirror the listener script's default. No config is not a licence
to guess. Callers get ``None`` and a reason string, and are expected to say so.

AMBIGUITY. Two profiles can tie at the top detection score -- ``workstation_5090``
is a declared ``alias_of: desktop-9950xd`` and matches the same hardware. A tie
is fatal only when the tied profiles declare DIFFERENT gateway profiles; when
they agree there is nothing to disambiguate and the shared value is returned.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pmoves.tools.profile_loader import (  # noqa: E402
    Profile,
    detect_profiles,
    load_active_profile_id,
    load_profiles,
)

ENV_OVERRIDE = "PMOVES_MCP_PROFILE_ID"

#: Key a node profile YAML uses to declare its gateway profile.
#: Deliberately NOT the existing ``mcp:`` list. That list is a mixed bag --
#: ``laptop-4090.yaml`` has ``[docker, compose, pmoves-cipher, huggingface,
#: pmoves_4090_web]``, mixing server names with one gateway-profile name, while
#: ``desktop-9950xd.yaml`` has ``[docker, compose, host, telemetry]`` and names
#: no profile at all. Keying off it would mean guessing which entry is the
#: profile, and guessing wrong on the 5090.
DECL_SECTION = "docker_mcp"
DECL_KEY = "gateway_profile"


def declared_profile(profile: Profile) -> Optional[str]:
    """The gateway profile a node profile YAML declares, or None."""
    section = (profile.raw or {}).get(DECL_SECTION)
    if not isinstance(section, dict):
        return None
    value = section.get(DECL_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def resolve(
    directory: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Tuple[Optional[str], str]:
    """Return ``(gateway_profile, reason)`` for this node.

    ``gateway_profile`` is None when it cannot be resolved; ``reason`` always
    explains which step answered, or which steps came up empty, so a caller can
    print something an operator can act on.
    """
    environ = os.environ if environ is None else environ

    override = (environ.get(ENV_OVERRIDE) or "").strip()
    if override:
        return override, f"{ENV_OVERRIDE} override"

    profiles = load_profiles(directory)
    if not profiles:
        return None, f"no node profiles found in {directory or 'pmoves/config/profiles'}"

    pinned_id = load_active_profile_id()
    if pinned_id:
        pinned = profiles.get(pinned_id)
        if pinned is None:
            return None, (
                f"pinned profile '{pinned_id}' (~/.pmoves/profile.json) is not in "
                "pmoves/config/profiles -- re-run `pmoves mini profile detect`"
            )
        value = declared_profile(pinned)
        if value:
            return value, f"pinned profile '{pinned_id}'"
        return None, (
            f"pinned profile '{pinned_id}' declares no {DECL_SECTION}.{DECL_KEY} -- "
            f"add it to pmoves/config/profiles/{pinned_id}.yaml"
        )

    scored = detect_profiles(profiles.values())
    if not scored:
        return None, (
            "hardware matched no node profile, and none is pinned -- run "
            "`pmoves mini profile detect` or set " + ENV_OVERRIDE
        )

    top_score = scored[0][0]
    tied = [prof for score, prof in scored if score == top_score]
    values = {declared_profile(p) for p in tied}
    values.discard(None)

    if len(values) > 1:
        names = ", ".join(sorted(p.id for p in tied))
        return None, (
            f"hardware detection tied ({names}) on profiles declaring different "
            f"{DECL_SECTION}.{DECL_KEY} values -- pin one with "
            f"`pmoves mini profile use <id>` or set {ENV_OVERRIDE}"
        )
    if not values:
        names = ", ".join(sorted(p.id for p in tied))
        return None, (
            f"detected profile(s) {names} declare no {DECL_SECTION}.{DECL_KEY} -- "
            "add it to the matching pmoves/config/profiles/<id>.yaml"
        )

    return values.pop(), f"hardware detection (profile '{tied[0].id}', score {top_score})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
        help="override the node-profile directory (testing)",
    )
    ap.add_argument(
        "--why",
        action="store_true",
        help="also print the resolution reason to stderr",
    )
    args = ap.parse_args(argv)

    value, reason = resolve(args.profiles_dir)
    if value is None:
        print(f"[node-gateway-profile] cannot resolve: {reason}", file=sys.stderr)
        return 1
    if args.why:
        print(f"[node-gateway-profile] {value} via {reason}", file=sys.stderr)
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
