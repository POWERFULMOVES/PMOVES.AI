"""Shared test fixtures for creator-operator."""

VALID_WORKORDER = {
    "workorder_id": "wo_test1",
    "workflow_id": "image.ideogram-ultra",
    "knobs": {"prompt": "a neon city", "seed": 42, "input_image": None},
    "node_caps": {"min_vram_gb": 8, "needs": ["comfyui", "browser"]},
    "teach": True,
    "creator_ref": "creator_demo",
    "license_ack": {"model": "ideogram-ultra", "mode": "local", "ack": True},
}

VALID_RESULT = {
    "workorder_id": "wo_test1",
    "status": "ok",
    "artifact": {"kind": "image", "path": "/out/x.png", "preview_url": None},
    "api_prompt": {"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
    "transcript": [{"step": "set seed", "knob": "seed", "teaches": "determinism"}],
    "cgp_point": None,
    "error": None,
}
