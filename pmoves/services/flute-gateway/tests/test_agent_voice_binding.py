"""Tests for the agent → VoiceBinding resolver (persona_selector.resolve_agent_voice).

The seam both the CLI and the room read
(pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md). Import-guarded: skips if the
gateway import chain (httpx, services.common) is unavailable. Async resolver is
driven via asyncio.run() so no pytest-asyncio marker is required.
"""

import asyncio
import os
import sys

import pytest

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    import persona_selector as ps
    _PS_AVAILABLE = True
except Exception:  # pragma: no cover - import chain may be absent
    _PS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")

_URL = "http://host.docker.internal:7860"


def _run(coro):
    return asyncio.run(coro)


def test_known_agent_resolves_descriptor_engine():
    # claude-opus voice descriptor = analytical → kokoro floor (no persona/Supabase).
    b = _run(ps.resolve_agent_voice("claude-opus"))
    assert b["engine"] == "kokoro"
    assert b["provider"] == "ultimate_tts"
    assert b["floos_suit"] is None
    assert "signature" in b["source"] and "descriptor" in b["source"]


def test_floos_suit_carries_prosody():
    b = _run(ps.resolve_agent_voice("kilocode", alter="mr-clean"))
    assert b["floos_suit"] == "mr-clean"
    assert b["prosody"] == {"bpm": 120, "rate": 1.1, "expressivity": 0.1}
    assert "floos" in b["source"]


def test_unknown_agent_falls_back_to_default():
    b = _run(ps.resolve_agent_voice("no-such-agent-xyz"))
    assert b["engine"] == ps._DEFAULT_ENGINE  # kitten_tts
    assert b["prosody"] is None
    assert b["floos_suit"] is None
    assert b["source"] == "default"


def test_affinity_off_is_failopen_url_passthrough(monkeypatch):
    monkeypatch.delenv("VOICE_HOST_AFFINITY", raising=False)
    b = _run(ps.resolve_agent_voice("claude-opus", configured_url=_URL))
    assert b["node"] is None
    assert b["target_url"] == _URL
    assert "affinity" not in b["source"]


def test_affinity_on_host_swaps_to_node(monkeypatch):
    # codex = terse → kokoro (a CPU engine with a host_affinity row).
    monkeypatch.setenv("VOICE_HOST_AFFINITY", "1")
    monkeypatch.delenv("VOICE_FLEET_NODES", raising=False)  # None → preferred
    b = _run(ps.resolve_agent_voice("codex", configured_url=_URL))
    assert b["engine"] == "kokoro"
    assert b["node"] == "kvm4-2"
    assert b["target_url"] == "http://pmoves-kvm4-2:7860"
    assert "affinity" in b["source"]


def test_binding_shape_is_complete():
    b = _run(ps.resolve_agent_voice("claude-opus"))
    for key in ("agent_id", "alter", "engine", "voice_id", "provider",
                "prosody", "node", "target_url", "floos_suit", "source"):
        assert key in b, f"VoiceBinding missing key: {key}"
    assert b["agent_id"] == "claude-opus"


def test_alter_inherits_base_voice_when_not_a_suit():
    # kilocode-glm alter is not a FlOO$ suit → no prosody, but engine still resolves.
    b = _run(ps.resolve_agent_voice("kilocode", alter="kilocode-glm"))
    assert b["floos_suit"] is None
    assert b["engine"]  # some engine resolved, fail-open never leaves it blank
