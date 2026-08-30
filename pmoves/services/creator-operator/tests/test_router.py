import copy
import pytest
from router import select_node, route, load_nodes
from fixtures import VALID_WORKORDER

NODES = [
    {"node_id": "jetson", "vram_gb": 8, "caps": ["comfyui", "browser"], "reach": "pmoves-jetson"},
    {"node_id": "4090", "vram_gb": 24, "caps": ["comfyui", "browser"], "reach": "pmoves-laptop"},
]
MODELS = {"image.ideogram-ultra": {"model_id": "ideogram-4", "requires_ack": True}}


def test_select_node_impedance_picks_lowest_capacity():
    n = select_node({"min_vram_gb": 6, "needs": ["comfyui"]}, NODES)
    assert n["node_id"] == "jetson"  # lowest VRAM that satisfies


def test_select_node_respects_min_vram():
    n = select_node({"min_vram_gb": 16, "needs": ["comfyui"]}, NODES)
    assert n["node_id"] == "4090"


def test_select_node_missing_cap_returns_none():
    assert select_node({"min_vram_gb": 6, "needs": ["tpu"]}, NODES) is None


def test_route_ok():
    r = route(VALID_WORKORDER, NODES, MODELS)
    assert r["ok"] is True and r["node_id"] in {"jetson", "4090"}


def test_route_refuses_unacked_nc_model():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["license_ack"]["ack"] = False
    r = route(bad, NODES, MODELS)
    assert r["ok"] is False and r["reason"] == "license-not-acked"


def test_route_parks_when_no_capacity():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["node_caps"] = {"min_vram_gb": 999, "needs": ["comfyui"]}
    r = route(bad, NODES, MODELS)
    assert r["ok"] is False and r["reason"] == "no-capacity"


def test_route_unknown_workflow_does_not_crash():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["workflow_id"] = "image.not-registered"  # schema-valid string, not in MODELS
    r = route(bad, NODES, MODELS)
    assert r["ok"] is False and r["reason"] == "unknown-workflow"


def test_load_nodes_rejects_malformed(tmp_path):
    # Node missing `reach` must fail at load, not later on node["reach"] access.
    bad_yaml = tmp_path / "operator_nodes.yaml"
    bad_yaml.write_text(
        "nodes:\n"
        '  - node_id: "broken"\n'
        "    vram_gb: 8\n"
        '    caps: ["comfyui"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_nodes(bad_yaml)


FLEET = [
    {"node_id": "4090", "reach": "pmoves-laptop", "vram_gb": 16, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "5090", "reach": "pmoves-5090", "vram_gb": 32, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "spark", "reach": "pmoves-spark", "vram_gb": 128, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "z890", "reach": "pmoves-z890", "vram_gb": 24, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "knuckles", "reach": "knuckles", "vram_gb": 32, "caps": ["rocm", "voice"]},
]


def test_voice_routes_to_lowest_vram_incl_knuckles():
    n = select_node({"min_vram_gb": 4, "needs": ["voice"]}, FLEET)
    assert n["node_id"] == "4090"


def test_video_excludes_knuckles_via_cuda_and_vram():
    n = select_node({"min_vram_gb": 24, "needs": ["cuda", "comfyui"]}, FLEET)
    assert n["node_id"] == "z890"


def test_image_excludes_knuckles():
    n = select_node({"min_vram_gb": 16, "needs": ["cuda", "comfyui"]}, FLEET)
    assert n["node_id"] == "4090"
    assert n["node_id"] != "knuckles"


def test_cuda_workflow_never_selects_rocm_node():
    rocm_only = [{"node_id": "knuckles", "reach": "knuckles", "vram_gb": 32, "caps": ["rocm", "voice"]}]
    assert select_node({"min_vram_gb": 8, "needs": ["cuda"]}, rocm_only) is None


MODELS_CAPS = {
    "voice.omnivoice": {"model_id": "k2-fsa/OmniVoice", "requires_ack": False,
                        "caps": {"min_vram_gb": 4, "needs": ["voice"]}},
    "video.ltx": {"model_id": "Lightricks/LTX-Video", "requires_ack": True,
                  "caps": {"min_vram_gb": 24, "needs": ["cuda", "comfyui"]}},
}


def test_route_derives_caps_from_workflow_when_omitted():
    wo = {"workorder_id": "wo_v", "workflow_id": "voice.omnivoice", "knobs": {},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}  # no node_caps
    r = route(wo, FLEET, MODELS_CAPS)
    assert r["ok"] is True and r["node_id"] == "4090"


def test_route_explicit_node_caps_overrides_workflow():
    wo = {"workorder_id": "wo_v", "workflow_id": "voice.omnivoice",
          "knobs": {}, "node_caps": {"min_vram_gb": 24, "needs": ["cuda", "voice"]},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    r = route(wo, FLEET, MODELS_CAPS)
    assert r["ok"] is True and r["node_id"] == "z890"


def test_route_no_caps_anywhere_returns_no_caps():
    wo = {"workorder_id": "wo_x", "workflow_id": "voice.omnivoice", "knobs": {},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    models_nocaps = {"voice.omnivoice": {"model_id": "x", "requires_ack": False}}
    r = route(wo, FLEET, models_nocaps)
    assert r["ok"] is False and r["reason"] == "no-caps"


# --- WS-I image + WS-A2 anime route off the real registry (handoff 2026-06-08) ---

from pathlib import Path  # noqa: E402
from model_registry import load_models  # noqa: E402
from operator_select import operator_kind  # noqa: E402

REGISTRY = Path(__file__).resolve().parents[3] / "config/creator_models.yaml"


@pytest.mark.parametrize("workflow_id", ["image.flux-schnell", "anime.animagine-xl"])
def test_clean_image_anime_route_on_cuda_comfyui_node(workflow_id):
    # Apache/OpenRAIL clean models: no ack needed, route to a cuda+comfyui node.
    models = load_models(REGISTRY)
    wo = {"workorder_id": "wo_clean", "workflow_id": workflow_id, "knobs": {},
          "license_ack": {"ack": False}}  # no ack supplied -> still must route
    r = route(wo, FLEET, models)
    assert r["ok"] is True, r
    node = next(n for n in FLEET if n["node_id"] == r["node_id"])
    assert "cuda" in node["caps"] and "comfyui" in node["caps"]
    assert r["node_id"] != "knuckles"  # rocm-only node excluded by cuda gate


@pytest.mark.parametrize("workflow_id", ["image.flux-schnell", "anime.animagine-xl"])
def test_clean_image_anime_use_comfyui_operator(workflow_id):
    assert operator_kind(workflow_id) == "comfyui"  # only voice.* is special


# ── schedulable flag ────────────────────────────────────────────────
# The capacity registry must name every machine on the fleet (the anchor
# validator derives known hostnames from it), but naming a box is not the same
# claim as "a worker can consume a job there". Because select_node() picks the
# LOWEST-VRAM match, an un-bootstrapped edge node would otherwise WIN every
# small job it nominally qualifies for.

_UNBOOTSTRAPPED = [
    {"node_id": "nano-1", "vram_gb": 8, "caps": ["cuda", "edge"],
     "reach": "pmoves-nano-1", "schedulable": False},
    {"node_id": "4090", "vram_gb": 24, "caps": ["cuda", "edge"],
     "reach": "pmoves-laptop"},
]


def test_unschedulable_node_is_never_selected():
    pick = select_node({"needs": ["cuda"], "min_vram_gb": 4}, _UNBOOTSTRAPPED)
    assert pick is not None
    assert pick["node_id"] == "4090"


def test_schedulable_flag_is_load_bearing():
    """Flipping the flag must change the outcome, or the test proves nothing."""
    nodes = copy.deepcopy(_UNBOOTSTRAPPED)
    for n in nodes:
        if n["node_id"] == "nano-1":
            n["schedulable"] = True
    pick = select_node({"needs": ["cuda"], "min_vram_gb": 4}, nodes)
    assert pick["node_id"] == "nano-1"


def test_schedulable_defaults_to_true():
    """Existing registry entries carry no flag and must keep their behaviour."""
    nodes = [{"node_id": "edge", "vram_gb": 8, "caps": ["cuda"], "reach": "pmoves-edge"}]
    assert select_node({"needs": ["cuda"]}, nodes)["node_id"] == "edge"


def test_all_unschedulable_parks_rather_than_misroutes():
    nodes = [dict(_UNBOOTSTRAPPED[0])]
    assert select_node({"needs": ["cuda"], "min_vram_gb": 4}, nodes) is None
