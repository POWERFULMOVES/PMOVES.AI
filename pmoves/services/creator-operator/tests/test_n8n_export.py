from n8n_export import to_n8n_workflow
from fixtures import VALID_RESULT


def test_to_n8n_workflow_minimal_importable():
    wf = to_n8n_workflow(VALID_RESULT, workflow_id="image.ideogram-ultra")
    assert wf["name"].startswith("creator-run-")
    assert isinstance(wf["nodes"], list) and len(wf["nodes"]) == 1
    node = wf["nodes"][0]
    assert node["type"] == "n8n-nodes-base.noOp"
    assert node["parameters"]["workorder_id"] == "wo_test1"
    assert node["parameters"]["artifact_path"] == "/out/x.png"
    assert wf["connections"] == {}
