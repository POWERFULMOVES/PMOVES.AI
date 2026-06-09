import jsonschema
import pytest
from operator_helpers import parse_workorder, assemble_result
from fixtures import VALID_WORKORDER


def test_parse_workorder_validates():
    wo = parse_workorder(VALID_WORKORDER)
    assert wo["workflow_id"] == "image.ideogram-ultra"


def test_parse_workorder_rejects_bad():
    with pytest.raises(jsonschema.ValidationError):
        parse_workorder({"workorder_id": "x"})


def test_assemble_result_ok():
    r = assemble_result(
        "wo_test1",
        artifact={"kind": "image", "path": "/out/x.png", "preview_url": None},
        api_prompt={"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
        transcript=[{"step": "set seed", "knob": "seed", "teaches": "determinism"}],
    )
    assert r["status"] == "ok" and r["error"] is None
    assert r["api_prompt"]["3"]["class_type"] == "KSampler"


def test_assemble_result_error_path():
    r = assemble_result("wo_test1", artifact=None, api_prompt=None,
                        transcript=[{"step": "load workflow"}], error="node missing")
    assert r["status"] == "error" and r["artifact"] is None
