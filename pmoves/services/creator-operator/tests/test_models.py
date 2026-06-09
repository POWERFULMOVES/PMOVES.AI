import pytest
from pathlib import Path
from model_registry import load_models, lookup_model, requires_ack

MODELS = Path(__file__).resolve().parents[3] / "config/creator_models.yaml"


def test_lookup_ideogram_requires_ack():
    m = lookup_model(load_models(MODELS), "image.ideogram-ultra")
    assert m["model_id"] == "Comfy-Org/Ideogram-4"  # LOCAL weights, not the paid API
    assert m["mode"] == "local" and m["provider"] == "local"
    assert requires_ack(m) is True  # license:other not confirmed commercial-OK
    assert m["swap_for"] == "Qwen/Qwen-Image"


def test_lookup_qwen_no_ack():
    m = lookup_model(load_models(MODELS), "image.qwen")
    assert requires_ack(m) is False


def test_unknown_workflow_raises():
    with pytest.raises(KeyError):
        lookup_model(load_models(MODELS), "image.nope")
