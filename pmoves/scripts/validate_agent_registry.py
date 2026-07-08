#!/usr/bin/env python3
"""Pydantic-backed gate for the PMOVES agent registry <-> teams coupling.

Replaces the informational one-liner in the agent-teams.yaml header with an
enforceable check (``tool can tool``: deterministic, reproducible grounding).

What it enforces
----------------
1. **Naming convention** (best practice, already used across the repo):
   - ``snake_case`` for registry keys and team ``agents:`` entries (YAML/Python
     identifiers), e.g. ``fordham_steward``.
   - ``kebab-case`` for agent-facing runtime ids (room ``agent_id``, mint
     ``agent_name``, external contributors like ``4090-claude``), derived
     deterministically as ``snake.replace("_", "-")``.
2. **Coupling**: every registry agent belongs to exactly one team, and every
   team agent exists in the registry.
3. **Ratchet**: the coupling is already broken on ``main`` (legacy drift). That
   drift is baselined below so the gate is GREEN today but FAILS on any *new*
   violation. Do not grow the baselines — reconcile them separately.
4. **Room cross-check** (advisory): every room manifest ``agent_id`` resolves to
   a registry agent (via kebab->snake) or an external contributor.

Exit code: 0 = pass (baseline-only), 1 = new violation (CI gate).
Run:  python pmoves/scripts/validate_agent_registry.py [-v]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "pmoves" / "config" / "agent_registry.yaml"
TEAMS = ROOT / "pmoves" / "configs" / "agent-teams.yaml"
ROOMS_DIR = ROOT / "pmoves" / "config" / "rooms"

SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
KEBAB = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


def snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


def kebab_to_snake(name: str) -> str:
    return name.replace("-", "_")


# --- Ratchet baseline -------------------------------------------------------
# Pre-existing origin/main coupling drift. Allowed so the gate is green today;
# NEW entries outside these sets fail. Reconcile these separately (do NOT add).
# Fully reconciled 2026-07-07 — the registry↔teams coupling is now clean, so both
# baselines are EMPTY and the gate enforces zero drift (any future violation fails).
# Round 1: botz×3 + space_agent -> orchestration, cipher_beats_analyst -> media,
#   notebooklm_agent -> research (each per its own registry topology.team).
# Round 2: a0_plugins/hermes_agent -> orchestration, autoresearch -> research,
#   clawz/pmoves_ci_bot/pr_hedge_trim -> automation; and registry entries authored for
#   nemoclaw/container_agent (infra), nemotron_claw (evolution), podcast_producer/
#   remotion_renderer/youtube_publisher (media).
BASELINE_UNTEAMED: frozenset = frozenset()
BASELINE_UNREGISTERED: frozenset = frozenset()


# --- Pydantic models (structural + naming validation) -----------------------
class AgentEntry(BaseModel):
    """A registry agent. Only the fields we gate on are typed; the rich
    taxonomy fields are permitted via ``extra='allow'``."""
    model_config = ConfigDict(extra="allow")
    name: str


class Team(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    agents: list[str] = []

    @field_validator("agents")
    @classmethod
    def _agents_snake(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if not SNAKE.match(a)]
        if bad:
            raise ValueError(f"team agent ids must be snake_case, got: {bad}")
        return v


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    errors: list[str] = []
    warnings: list[str] = []

    reg_raw = _load_yaml(REGISTRY)
    teams_raw = _load_yaml(TEAMS)

    # 1. Structural + naming validation via Pydantic ------------------------
    registry_keys: set[str] = set()
    for key, entry in (reg_raw.get("agents") or {}).items():
        if not SNAKE.match(key):
            errors.append(f"registry key not snake_case: {key!r}")
        try:
            AgentEntry.model_validate(entry or {})
        except Exception as exc:  # noqa: BLE001 - surface the pydantic error text
            errors.append(f"registry[{key}] invalid: {exc}")
        registry_keys.add(key)

    team_map: dict[str, list[str]] = {}
    for tkey, tval in (teams_raw.get("teams") or {}).items():
        if not SNAKE.match(tkey):
            errors.append(f"team key not snake_case: {tkey!r}")
        try:
            team = Team.model_validate(tval or {})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"team[{tkey}] invalid: {exc}")
            continue
        for a in team.agents:
            team_map.setdefault(a, []).append(tkey)

    external = set(reg_raw.get("external_contributors") or [])

    # 2. Coupling with ratchet ---------------------------------------------
    teamed = set(team_map)
    new_unteamed = sorted((registry_keys - teamed) - BASELINE_UNTEAMED)
    new_unreg = sorted((teamed - registry_keys) - BASELINE_UNREGISTERED)
    dups = {a: t for a, t in team_map.items() if len(t) > 1}

    for a in new_unteamed:
        errors.append(f"registry agent in NO team (new drift): {a} "
                      f"-> add it to a team in agent-teams.yaml")
    for a in new_unreg:
        errors.append(f"team agent NOT in registry (new drift): {a} "
                      f"(teams {team_map[a]}) -> add it to agent_registry.yaml")
    for a, t in sorted(dups.items()):
        errors.append(f"agent in >1 team: {a} -> {t}")

    # Baseline still-open drift is reported as a warning, never fatal.
    still_unteamed = sorted((registry_keys - teamed) & BASELINE_UNTEAMED)
    still_unreg = sorted((teamed - registry_keys) & BASELINE_UNREGISTERED)
    if still_unteamed:
        warnings.append(f"baseline unteamed (reconcile separately): {still_unteamed}")
    if still_unreg:
        warnings.append(f"baseline unregistered (reconcile separately): {still_unreg}")

    # 3. Room cross-check (advisory) ---------------------------------------
    for manifest in sorted(ROOMS_DIR.glob("*.json")):
        if manifest.name == "catalog.json":
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"room {manifest.name}: unreadable ({exc})")
            continue
        owner = data.get("agent_id")
        if not owner:
            continue
        if owner in external or kebab_to_snake(owner) in registry_keys:
            continue
        warnings.append(
            f"room {manifest.name}: owner agent_id {owner!r} resolves to neither "
            f"a registry agent ({kebab_to_snake(owner)!r}) nor an external contributor")

    # --- Report ------------------------------------------------------------
    print(f"registry agents: {len(registry_keys)} | team agents: {len(teamed)} "
          f"| external contributors: {len(external)}")
    if verbose or warnings:
        for w in warnings:
            print(f"  WARN  {w}")
    if errors:
        print(f"\nFAIL — {len(errors)} new violation(s):")
        for e in errors:
            print(f"  ERROR {e}")
        return 1
    print("OK — registry/teams coupling clean (no new drift); naming conventions hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
