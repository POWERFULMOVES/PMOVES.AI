"""CGP attribution + teaching-summary helpers."""


def build_cgp_point(result: dict, workorder: dict, *, model_id: str, license_name: str) -> dict:
    """A CGP point whose meta carries full provenance + a ref to the harvested recipe."""
    return {
        "meta": {
            "source": "creator-operator",
            "workflow_id": workorder["workflow_id"],
            "model": model_id,
            "license": license_name,
            "knobs": workorder.get("knobs", {}),
            "has_api_prompt": result.get("api_prompt") is not None,
            "workorder_id": result["workorder_id"],
        }
    }


def summarize_transcript(transcript: list) -> str:
    """One short teaching line per knob, truncated for Discord (<=280 chars)."""
    parts = []
    for entry in transcript:
        knob = entry.get("knob")
        teaches = entry.get("teaches")
        if knob and teaches:
            parts.append(f"{knob}: {teaches}")
    text = " · ".join(parts) if parts else "run complete"
    return text[:280]
