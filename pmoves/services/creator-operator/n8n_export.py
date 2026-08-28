"""Serialize one operator run as a minimal importable n8n workflow (single node).
The capacity seam: real but single-node; a fleet pipeline is a later slice."""


def to_n8n_workflow(result: dict, *, workflow_id: str) -> dict:
    wo = result["workorder_id"]
    artifact = result.get("artifact") or {}
    return {
        "name": f"creator-run-{wo}",
        "nodes": [
            {
                "id": "run",
                "name": "creator-operator-run",
                "type": "n8n-nodes-base.noOp",
                "typeVersion": 1,
                "position": [0, 0],
                "parameters": {
                    "workorder_id": wo,
                    "workflow_id": workflow_id,
                    "status": result.get("status"),
                    "artifact_path": artifact.get("path"),
                    "has_api_prompt": result.get("api_prompt") is not None,
                },
            }
        ],
        "connections": {},
    }
