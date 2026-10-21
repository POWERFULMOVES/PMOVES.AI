"""Ollama model suits name tags that exist in the Ollama registry.

gemma4-dense, qwen3.6 and nemotron-3-super named "gemma4:31b-q4",
"qwen3.6:q4_k_m" and "nemotron-3-super:q4". All three 404 at
registry.ollama.ai, so models-seed-ollama could never install them and
models-suit-ollama skipped them forever ("base not installed"). Ollama library
tags lead with the parameter size (31b, 27b, 120b, 4b), optionally followed by
a variant and quantization, or are exactly "latest".
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SUITS = Path(__file__).resolve().parents[1] / "configs" / "model-suits"
# A bare "q4" segment is never an Ollama quantization (real ones: q4_K_M, q8_0, fp16).
TAG = re.compile(r"^[a-z0-9][a-z0-9._-]*:(latest|\d+(\.\d+)?[bm](-(?!q\d+(?:-|$))[A-Za-z0-9_.]+)*)$")


def _ollama_suits():
    for path in sorted(SUITS.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if str(doc.get("provider", "")).startswith("ollama"):
            yield pytest.param(path.name, doc["model_config"]["model_name"], id=path.stem)


@pytest.mark.parametrize("suit,tag", list(_ollama_suits()))
def test_ollama_suit_tag_has_a_registry_shape(suit, tag):
    assert TAG.match(tag), f"{suit}: {tag!r} is not an Ollama library tag (size first, e.g. gemma4:31b)"


@pytest.mark.parametrize("bad", ["gemma4:31b-q4", "qwen3.6:q4_k_m", "nemotron-3-super:q4", "qwen3.6"])
def test_the_tags_that_404_are_rejected(bad):
    assert not TAG.match(bad)


@pytest.mark.parametrize("good", ["gemma4:31b-it-q4_K_M", "nemotron-3-super:120b-a12b-q4_K_M",
                                  "qwen3.6:27b-q4_K_M", "qwen3-embedding:4b", "qwen3.6:latest"])
def test_real_registry_tags_are_accepted(good):
    assert TAG.match(good)
