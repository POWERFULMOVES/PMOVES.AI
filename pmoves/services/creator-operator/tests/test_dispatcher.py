import copy
from dispatcher import handle_workorder
from fixtures import VALID_WORKORDER

NODES = [{"node_id": "4090", "vram_gb": 24, "caps": ["comfyui", "browser"], "reach": "pmoves-laptop"}]
MODELS = {"image.ideogram-ultra": {"model_id": "ideogram-4", "requires_ack": True}}


def test_handle_workorder_assigns():
    out = handle_workorder(VALID_WORKORDER, NODES, MODELS)
    assert out["decision"] == "assigned"
    assert out["node_id"] == "4090"
    assert out["subject"] == "creator.operator.assigned.v1"


def test_handle_workorder_refuses_unacked():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["license_ack"]["ack"] = False
    out = handle_workorder(bad, NODES, MODELS)
    assert out["decision"] == "refused" and out["reason"] == "license-not-acked"


def test_handle_workorder_parks_no_capacity():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["node_caps"] = {"min_vram_gb": 999, "needs": ["comfyui"]}
    out = handle_workorder(bad, NODES, MODELS)
    assert out["decision"] == "parked" and out["reason"] == "no-capacity"


def test_handle_workorder_rejects_invalid():
    out = handle_workorder({"workorder_id": "x"}, NODES, MODELS)
    assert out["decision"] == "rejected"


def test_handle_workorder_rejects_unknown_workflow():
    # schema-valid work-order whose workflow_id is not in the model registry:
    # must be rejected (not crash, not parked).
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["workflow_id"] = "image.not-registered"
    out = handle_workorder(bad, NODES, MODELS)
    assert out["decision"] == "rejected" and out["reason"] == "unknown-workflow"


import json as _json
from pathlib import Path
from dispatcher import park_workorder


def test_park_workorder_persists(tmp_path):
    path = park_workorder(VALID_WORKORDER, tmp_path)
    assert Path(path).exists()
    saved = _json.loads(Path(path).read_text(encoding="utf-8"))
    assert saved["workorder_id"] == VALID_WORKORDER["workorder_id"]
    assert Path(path).name == VALID_WORKORDER["workorder_id"] + ".json"
