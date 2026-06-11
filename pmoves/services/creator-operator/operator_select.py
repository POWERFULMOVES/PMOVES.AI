"""Map a workflow_id to its L1 operator kind. Voice uses the API-client voice
operator; everything else uses the chrome-devtools ComfyUI operator (slice 1)."""


def operator_kind(workflow_id: str) -> str:
    return "voice" if workflow_id.startswith("voice.") else "comfyui"
