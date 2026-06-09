import copy
from router import select_node, route
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
