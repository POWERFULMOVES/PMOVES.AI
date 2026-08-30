import pytest
from jsonschema import ValidationError

from pmoves.tools.chit.floos_resolver import _build_hook_envelope


def test_registered_hook_subject_validates_against_topics_json(monkeypatch):
    monkeypatch.delenv("FLOOS_STRICT_HOOKS", raising=False)
    payload = {
        "namespace": "pmoves.tokenism",
        "modality": "economic_simulation",
        "pack_id": "sim-week-1",
        "status": "active",
        "best_fitness": 0.7,
        "metrics": {"gini": 0.3},
        "timestamp": "2026-05-22T00:00:00Z",
    }

    env = _build_hook_envelope("tokenism.swarm.population.v1", payload)

    assert env["topic"] == "tokenism.swarm.population.v1"
    assert env["payload"] == payload


def test_registered_hook_subject_rejects_invalid_payload(monkeypatch):
    monkeypatch.delenv("FLOOS_STRICT_HOOKS", raising=False)
    payload = {
        "namespace": "pmoves.tokenism",
        "modality": "economic_simulation",
        "pack_id": "sim-week-1",
        "status": "active",
        "best_fitness": 2.0,
        "timestamp": "2026-05-22T00:00:00Z",
    }

    with pytest.raises(ValidationError):
        _build_hook_envelope("tokenism.swarm.population.v1", payload)


def test_unregistered_hook_subject_warns_by_default(monkeypatch, capsys):
    monkeypatch.delenv("FLOOS_STRICT_HOOKS", raising=False)

    env = _build_hook_envelope("floos.custom.completed.v1", {"ok": True})

    assert env["topic"] == "floos.custom.completed.v1"
    assert "not registered in topics.json" in capsys.readouterr().err


def test_unregistered_hook_subject_fails_when_strict(monkeypatch):
    monkeypatch.setenv("FLOOS_STRICT_HOOKS", "true")

    with pytest.raises(KeyError):
        _build_hook_envelope("floos.custom.completed.v1", {"ok": True})
