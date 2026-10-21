"""models_sync writes an A0 v2 preset collection: Default first, hand presets kept.

A0 v2 requires a preset named "Default"; when it is missing, A0's startup
migration inserts upstream's (OpenRouter) Default and every chat uses it. On
SPARK 2026-10-20 that silently moved A0 onto a paid cloud model. A sync also
replaced the whole file, dropping the operator's cloud presets; a node's
collection must stay hybrid: generated local lanes plus hand-kept presets.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "models_sync_a0_default", REPO_ROOT / "pmoves" / "tools" / "models" / "models_sync.py")
assert SPEC is not None and SPEC.loader is not None
ms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ms)

ROWS = [{"service_name": "agent_zero", "function_name": "chat", "model_type": "chat",
         "model_id": "qwen2.5:14b", "provider_name": "ollama", "provider_type": "ollama",
         "context_length": 32768}]
CLOUD = {"name": "Cloud: GLM-5.3 (TensorZero)",
         "chat": {"provider": "tensorzero", "name": "tensorzero::model_name::chat_zai_glm53"}}


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "ROOT", tmp_path)  # review/backup copies stay in tmp
    return tmp_path / "presets.yaml"


def _names(path):
    return [p["name"] for p in yaml.safe_load(path.read_text())]


def test_first_generated_preset_is_named_default(out):
    ms._write_a0_presets(ROWS, [], out, apply=True)
    assert _names(out)[0] == "Default"


def test_hand_presets_survive_a_sync(out):
    out.write_text(yaml.safe_dump([{"name": "Registry", "chat": {}}, CLOUD]))
    ms._write_a0_presets(ROWS, [], out, apply=True)
    # The stale generator-owned "Registry" is regenerated (as Default), not
    # carried over; the hand-kept cloud preset survives after it.
    assert _names(out) == ["Default", CLOUD["name"]]


def test_stale_generated_names_are_not_carried_over(out):
    stale = [{"name": n, "chat": {}} for n in ("Default", "TensorZero", "Fallback-7")]
    out.write_text(yaml.safe_dump(stale))
    ms._write_a0_presets(ROWS, [], out, apply=True)
    assert "Fallback-7" not in _names(out) and _names(out).count("Default") == 1


def test_check_is_clean_after_apply_with_hand_presets(out):
    out.write_text(yaml.safe_dump([CLOUD]))
    ms._write_a0_presets(ROWS, [], out, apply=True)
    ms._write_a0_presets(ROWS, [], out, check=True)  # raises SystemExit(1) on drift
