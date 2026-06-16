# pmoves/design/generate.py
"""DL-1 design token generator. Reads pmoves/config/agent_signatures.yaml
(registry owned by the W1 theme lane — 4090-claude PRs #1065/#1101; do NOT
modify the registry schema here) + base/theme JSON, emits CSS + TS tokens."""
from __future__ import annotations
import json, pathlib
DESIGN = pathlib.Path(__file__).resolve().parent
REPO = DESIGN.parents[1]
REGISTRY = REPO / "pmoves" / "config" / "agent_signatures.yaml"

def load_registry() -> dict:
    import yaml
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    return data.get("signatures", {})

def _agent(reg: dict, agent_id: str) -> dict:
    if agent_id not in reg:
        raise KeyError(f"theme references unknown agent id: {agent_id!r}")
    return reg[agent_id]

def resolve_theme(theme: dict, reg: dict) -> dict:
    base = json.loads((DESIGN / "tokens.base.json").read_text(encoding="utf-8"))
    v: dict[str, str] = {}
    # structural base
    for k, val in base["color"].items():
        v[f"--pm-{k}"] = val
    v["--pm-radius"] = base["radius"]["lg"]
    for k, val in base["space"].items():
        v[f"--pm-space-{k}"] = val
    v["--pm-font-display"] = base["font"]["display"]
    v["--pm-font-body"] = base["font"]["body"]
    v["--pm-font-mono"] = base["font"]["mono"]
    # registry-sourced accents
    acc = theme["accents"]
    primary = _agent(reg, acc["primary"]); secondary = _agent(reg, acc["secondary"]); sig = _agent(reg, acc["signature"])
    v["--pm-accent"] = primary["color"]
    v["--pm-accent-soft"] = primary["accent"]
    v["--pm-accent-2"] = secondary["color"]
    v["--pm-signature"] = sig["color"]
    # theme overrides last
    for k, val in theme.get("overrides", {}).get("color", {}).items():
        v[f"--pm-{k}"] = val
    return v
