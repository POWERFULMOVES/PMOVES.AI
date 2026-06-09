"""Agent-side helpers used by the chrome-devtools operator run. The agent drives
the ComfyUI UI per the comfy-operate-image SKILL, records steps, captures the
harvested /prompt payload, then calls assemble_result and hands it to the service."""
from schemas import validate_workorder, validate_result


def parse_workorder(raw: dict) -> dict:
    validate_workorder(raw)
    return raw


def assemble_result(workorder_id: str, *, artifact, api_prompt, transcript, error=None) -> dict:
    status = "error" if error else "ok"
    result = {
        "workorder_id": workorder_id,
        "status": status,
        "artifact": artifact if status == "ok" else None,
        "api_prompt": api_prompt,
        "transcript": transcript,
        "cgp_point": None,        # filled by fanout
        "error": error,
    }
    validate_result(result)
    return result
