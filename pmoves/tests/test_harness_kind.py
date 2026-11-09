"""`kind: harness` marks the registry entries a fitting may point at."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_the_two_genuine_harnesses_are_marked():
    f = _fittings()
    harnesses = f.load_harnesses()
    assert "clawz" in harnesses
    assert "kilocode_glm" in harnesses


def test_non_harness_agents_are_not_marked():
    """agent_zero and archon are agent services; a2ui is a UI. None hosts a model."""
    f = _fittings()
    harnesses = f.load_harnesses()
    for key in ("agent_zero", "archon", "a2ui"):
        assert key not in harnesses, f"{key} is not a harness"


def test_kind_values_are_from_a_known_set():
    with open(REGISTRY, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    allowed = {"harness"}
    for key, entry in (doc.get("agents") or {}).items():
        kind = (entry or {}).get("kind")
        if kind is not None:
            assert kind in allowed, f"registry[{key}].kind={kind!r} is not a known kind"
