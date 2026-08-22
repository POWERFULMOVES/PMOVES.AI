"""Guards for the agent-zero pin check's two silent-pass defects (review on #2676).

Both are the same shape: the gate kept reporting success while measuring
something other than what ships.

1. It compared against the GITLINK, but the image clones the BRANCH TIP
   (Dockerfile:21 `git clone --branch ${AGENT_ZERO_REF}`). Those diverge in this
   repo today, so a fork constraint could conflict with our overlay lock while a
   required check stayed green.
2. `norm()` folded `_` but not `.`, so `zope.interface` and `zope-interface`
   keyed differently and a real override was invisible to both the constraint
   lookup and the duplicate-declaration intersection.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "agent_zero_pin_check.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("agent_zero_pin_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "a,b",
    [
        ("zope.interface", "zope-interface"),
        ("zope_interface", "zope.interface"),
        ("ruamel.yaml", "ruamel-yaml"),
        ("backports.zoneinfo", "backports-zoneinfo"),
        ("A__B..C", "a-b-c"),
    ],
)
def test_pep503_equivalent_spellings_collapse_to_one_key(mod, a, b):
    """Runs of -, _ and . are ALL equivalent. Folding only `_` misses overrides."""
    assert mod.norm(a) == mod.norm(b)


def test_norm_lowercases(mod):
    assert mod.norm("Django") == "django"


def test_norm_collapses_runs_not_just_single_separators(mod):
    """PEP 503 normalises RUNS, so `a...b` and `a-b` are the same distribution."""
    assert mod.norm("a...b") == "a-b"
    assert mod.norm("a_-_b") == "a-b"


def test_the_branch_the_tool_checks_is_the_branch_the_image_clones(mod):
    """If these drift apart, the gate silently starts checking the wrong tree."""
    dockerfile = (
        Path(__file__).resolve().parents[1]
        / "services" / "agent-zero" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert f"ARG AGENT_ZERO_REF={mod.BRANCH}" in dockerfile, (
        "agent_zero_pin_check.BRANCH must match the Dockerfile's AGENT_ZERO_REF "
        "default, or the check validates a revision the image does not build"
    )


def test_branch_tip_resolver_is_wired_and_returns_a_sha_or_none(mod):
    """Never raises: an unreachable API must fall back loudly, not explode."""
    out = mod.branch_tip_sha()
    assert out is None or (isinstance(out, str) and len(out) == 40)
