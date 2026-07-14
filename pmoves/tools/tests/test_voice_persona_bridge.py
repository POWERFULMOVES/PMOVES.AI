# pmoves/tools/tests/test_voice_persona_bridge.py
"""Tests for the CHIT-sign -> Flute-Gateway persona/intent bridge (Phase 0)."""

from pmoves.tools.voice_persona_bridge import BRIDGE, DEFAULT, resolve


def test_resolve_known_alter_mr_clean():
    payload = {"agent_id": "4090-claude", "selected_alter": "mr-clean", "voice": "command"}
    result = resolve(payload)
    assert result == {
        "intent": "dramatic",
        "persona_id": "mr-clean",
        "exaggeration": 0.6,
        "temperature": 0.9,
    }


def test_resolve_falls_back_to_voice_descriptor_when_no_alter():
    payload = {"agent_id": "claude-opus", "voice": "analytical"}
    result = resolve(payload)
    assert result["intent"] == "narrate"
    assert result["persona_id"] == "dr-bean"
    assert result["exaggeration"] == 0.3
    assert result["temperature"] == 0.7


def test_resolve_unknown_key_returns_default():
    payload = {"agent_id": "some-agent", "selected_alter": "totally-unknown-alter"}
    intent, persona_id, exaggeration, temperature = DEFAULT
    result = resolve(payload)
    assert result == {
        "intent": intent,
        "persona_id": persona_id,
        "exaggeration": exaggeration,
        "temperature": temperature,
    }


def test_resolve_empty_payload_returns_default():
    intent, persona_id, exaggeration, temperature = DEFAULT
    result = resolve({})
    assert result == {
        "intent": intent,
        "persona_id": persona_id,
        "exaggeration": exaggeration,
        "temperature": temperature,
    }


def test_resolve_none_payload_returns_default():
    intent, persona_id, exaggeration, temperature = DEFAULT
    result = resolve(None)
    assert result == {
        "intent": intent,
        "persona_id": persona_id,
        "exaggeration": exaggeration,
        "temperature": temperature,
    }


def test_bridge_covers_all_five_floos_suits():
    expected_alters = {
        "mr-clean",
        "dr-bean",
        "powerpuff-buttercup",
        "powerpuff-blossom",
        "powerpuff-bubbles",
    }
    assert expected_alters.issubset(BRIDGE.keys())
