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
