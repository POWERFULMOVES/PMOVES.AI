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
import json
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


def test_the_ref_is_read_from_the_published_image_dockerfile(mod):
    """Dockerfile.multiarch builds the PUBLISHED image and is the file the
    auto-bump workflow rewrites, so it is the only authority on the ref."""
    assert mod.PUBLISHED_DOCKERFILE.name == "Dockerfile.multiarch"
    assert mod.dockerfile_ref(mod.PUBLISHED_DOCKERFILE), (
        "ARG AGENT_ZERO_REF must be readable from the published-image Dockerfile"
    )


def test_both_build_definitions_currently_agree(mod):
    """They may legitimately diverge mid-bump, but the tool must NOTICE."""
    assert mod.dockerfile_ref(mod.PUBLISHED_DOCKERFILE) == mod.dockerfile_ref(
        mod.COMPOSE_DOCKERFILE
    )


def test_dockerfile_ref_parses_a_version_tag_not_just_a_branch(mod, tmp_path):
    """The auto-bump workflow writes version TAGS; a branch-only reader breaks."""
    f = tmp_path / "Dockerfile.multiarch"
    f.write_text("FROM x\nARG AGENT_ZERO_REF=v2.10.1\nRUN true\n", encoding="utf-8")
    assert mod.dockerfile_ref(f) == "v2.10.1"


def test_dockerfile_ref_returns_none_for_a_missing_or_refless_file(mod, tmp_path):
    assert mod.dockerfile_ref(tmp_path / "nope") is None
    f = tmp_path / "Dockerfile"
    f.write_text("FROM scratch\n", encoding="utf-8")
    assert mod.dockerfile_ref(f) is None


# --- resolve_ref_sha: mocked, never a real request ---------------------------
#
# The previous version of this test made a live 30s-timeout GitHub call on every
# suite run, so an offline runner paid the full delay and then PASSED because
# None was accepted -- neither success nor failure was actually exercised.


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def read(self):
        return json.dumps(self._payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_resolve_ref_sha_reads_the_object_sha(mod, monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(
        mod.urllib.request, "urlopen",
        lambda url, timeout=None: _Resp({"object": {"sha": sha}}),
    )
    assert mod.resolve_ref_sha("PMOVES.AI-Edition-Hardened") == sha


def test_resolve_ref_sha_falls_back_from_heads_to_tags(mod, monkeypatch):
    """`git clone --branch` accepts a tag, and the bump workflow writes tags."""
    sha = "b" * 40
    seen = []

    def fake(url, timeout=None):
        seen.append(url)
        if "/heads/" in url:
            raise OSError("404")
        return _Resp({"object": {"sha": sha}})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    assert mod.resolve_ref_sha("v2.10.1") == sha
    assert any("/heads/" in u for u in seen) and any("/tags/" in u for u in seen)


def test_resolve_ref_sha_returns_none_when_both_lookups_fail(mod, monkeypatch):
    def boom(url, timeout=None):
        raise OSError("rate limited")
    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert mod.resolve_ref_sha("anything") is None


def test_resolve_ref_sha_handles_an_empty_ref_without_calling_out(mod, monkeypatch):
    def boom(url, timeout=None):
        raise AssertionError("must not make a request for an empty ref")
    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert mod.resolve_ref_sha(None) is None
    assert mod.resolve_ref_sha("") is None


def test_unresolvable_tip_FAILS_rather_than_using_the_gitlink(mod, monkeypatch):
    """The merge gate reads the exit STATUS, not stderr. A quiet downgrade to the
    gitlink under API rate-limiting is indistinguishable from success."""
    monkeypatch.setattr(mod, "resolve_ref_sha", lambda ref: None)
    monkeypatch.setattr(mod, "gitlink_sha", lambda: "c" * 40)
    problems = []
    assert mod.read_fork_requirements(None, problems) is None
    assert problems, "an unresolvable tip must be reported as an input failure"
    assert "Refusing to fall back" in " ".join(problems)


def test_disagreeing_build_definitions_are_an_input_failure(mod, monkeypatch):
    monkeypatch.setattr(mod, "dockerfile_ref",
                        lambda p: "v2.10.1" if p is mod.PUBLISHED_DOCKERFILE else "main")
    problems = []
    assert mod.read_fork_requirements(None, problems) is None
    assert "disagree" in " ".join(problems)
