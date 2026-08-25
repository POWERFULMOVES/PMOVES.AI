"""The seeded fit data, and the guarantee that cross_agent was not touched."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"

CLAWZ_FULL = ["claude-haiku-4", "claude-opus-4", "claude-sonnet-4", "claude-sonnet"]
CLAWZ_LIMITED = ["gemma4-dense", "minimax-m2.1", "minimax-m2.7",
                 "nemotron-3-super", "qwen3.6"]
KILOCODE_FULL = ["minimax-m2.1", "minimax-m2.7"]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def _fit_block(stem: str) -> dict:
    with open(SUITS_DIR / f"{stem}.yaml", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return doc.get("fit") or {}


# Matches the `cross_agent:` header line plus every following line that is
# indented (its children) -- i.e. the raw text of the block, stopping at the
# next top-level key or the blank line before it. Used for a byte comparison,
# not a parsed-value comparison: a comment or key-reorder inside the block
# must also fail this test, since the constraint is on the bytes themselves.
CROSS_AGENT_BLOCK = re.compile(r"^cross_agent:\n(?:[ \t]+.*\n?)*", re.MULTILINE)


def _cross_agent_block(text: str) -> str:
    match = CROSS_AGENT_BLOCK.search(text)
    assert match, "no cross_agent: block found"
    return match.group(0)


def test_clawz_verdicts_match_the_recorded_measurement():
    f = _fittings()
    for stem in CLAWZ_FULL:
        obs = _fit_block(stem).get("clawz", {}).get("*", [])
        assert f.effective_fit(obs) == "full", stem
    for stem in CLAWZ_LIMITED:
        obs = _fit_block(stem).get("clawz", {}).get("*", [])
        assert f.effective_fit(obs) == "limited", stem


def test_kilocode_is_seeded_under_its_registry_key():
    """cross_agent spells it `kilocode`; the registry key is `kilocode_glm`.
    Seeding fresh lets the fit key be the resolvable one."""
    f = _fittings()
    for stem in KILOCODE_FULL:
        block = _fit_block(stem)
        assert "kilocode" not in block, f"{stem}: unresolvable cross_agent spelling"
        obs = block.get("kilocode_glm", {}).get("*", [])
        assert f.effective_fit(obs) == "full", stem


def test_every_observation_carries_provenance():
    for stem in CLAWZ_FULL + CLAWZ_LIMITED:
        for harness, roles in _fit_block(stem).items():
            for role, observations in roles.items():
                for obs in observations:
                    assert obs.get("by"), f"{stem}/{harness}/{role} has no `by`"
                    assert obs.get("method") in ("hand", "measured"), stem
                    assert obs.get("on"), f"{stem}/{harness}/{role} has no date"


def test_cross_agent_is_byte_identical_to_origin_main():
    """The spec's first acceptance criterion. A value-diff would pass while the
    referent moved, so this compares the raw text of the `cross_agent:` block
    (not the parsed YAML value) against origin/main -- a comment or key-reorder
    inside the block must fail this test too, since the constraint really is on
    the bytes. Compared against origin/main (not HEAD -- once this change is
    committed, HEAD equals the working tree and a HEAD-based comparison would
    be vacuously true).

    If `origin/main` is unreachable (e.g. a shallow `actions/checkout` on a
    pull_request event does not create refs/remotes/origin/main), this must
    not report green having asserted nothing -- it skips loudly instead."""
    compared = 0
    for stem in CLAWZ_FULL + CLAWZ_LIMITED:
        rel = f"pmoves/configs/model-suits/{stem}.yaml"
        before = subprocess.run(
            ["git", "show", f"origin/main:{rel}"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        if before.returncode != 0:
            continue
        old_block = _cross_agent_block(before.stdout)
        with open(REPO_ROOT / rel, encoding="utf-8") as handle:
            new_block = _cross_agent_block(handle.read())
        assert old_block == new_block, (
            f"{stem}: cross_agent changed. It must be left exactly as it is."
        )
        compared += 1
    if compared == 0:
        pytest.skip(
            "origin/main is unreachable in this checkout (`git show "
            "origin/main:<path>` failed for all 9 seeded files) -- this "
            "environment has no refs/remotes/origin/main to compare against "
            "(e.g. actions/checkout with the default fetch-depth: 1 on a "
            "pull_request event does not create it). No comparison was made."
        )
