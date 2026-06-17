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


from model_registry import lookup_caps  # noqa: E402


def test_lookup_caps_voice_is_light_fleetwide():
    m = lookup_model(load_models(MODELS), "voice.omnivoice")
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] == 4 and caps["needs"] == ["voice"]
    assert requires_ack(m) is False


def test_lookup_caps_video_is_cuda_heavy():
    m = lookup_model(load_models(MODELS), "video.ltx")
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] == 24 and "cuda" in caps["needs"]
    assert requires_ack(m) is True


def test_lookup_caps_missing_returns_none():
    assert lookup_caps({"model_id": "x"}) is None


# --- WS-I image + WS-A2 anime license-clean operators (handoff 2026-06-08) ---

def test_flux_schnell_apache_no_ack():
    m = lookup_model(load_models(MODELS), "image.flux-schnell")
    assert m["model_id"] == "black-forest-labs/FLUX.1-schnell"
    assert m["license"] == "apache-2.0"
    assert requires_ack(m) is False  # Apache => commercial-OK, no ack gate
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] >= 1
    assert "cuda" in caps["needs"] and "comfyui" in caps["needs"]


def test_animagine_xl_openrail_no_ack():
    m = lookup_model(load_models(MODELS), "anime.animagine-xl")
    assert m["model_id"] == "cagliostrolab/animagine-xl-4.0"
    assert m["license"] == "openrail++"  # commercial-permitted-with-restrictions
    assert requires_ack(m) is False
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] >= 1
    assert "cuda" in caps["needs"] and "comfyui" in caps["needs"]


def test_qwen_image_caps_valid():
    m = lookup_model(load_models(MODELS), "image.qwen")
    caps = lookup_caps(m)
    assert "cuda" in caps["needs"] and "comfyui" in caps["needs"]
    assert requires_ack(m) is False


def test_clean_swap_targets_resolve_to_registered_no_ack_models():
    # Each non-commercial try-locally model must swap_for a registered,
    # commercial-OK (requires_ack=false) model.
    models = load_models(MODELS)
    for wf in ("image.ideogram-ultra", "anime.anima"):
        swap = models[wf]["swap_for"]
        assert swap is not None
        clean = next(m for m in models.values() if m["model_id"] == swap)
        assert requires_ack(clean) is False
