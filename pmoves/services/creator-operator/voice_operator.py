"""Voice operator (L1 for voice.omnivoice). Unlike the ComfyUI image operator,
this is an API client, not a UI-driver: it calls OmniVoice and assembles an audio
operator-result. No /prompt harvest (voice isn't a ComfyUI graph) -> api_prompt None."""
from operator_helpers import assemble_result
from omnivoice_client import OmniVoiceError


def run_voice(workorder: dict, client) -> dict:
    knobs = workorder.get("knobs", {})
    transcript = [{"step": "synthesize", "knob": "text",
                   "teaches": "OmniVoice clones a voice and reads your text"}]
    try:
        path = client.synthesize(
            text=knobs.get("text", ""),
            voice_ref=knobs.get("voice_ref"),
            voice_design=knobs.get("voice_design"),
        )
    except OmniVoiceError as exc:
        return assemble_result(workorder["workorder_id"], artifact=None,
                               api_prompt=None, transcript=transcript, error=str(exc))
    return assemble_result(
        workorder["workorder_id"],
        artifact={"kind": "audio", "path": path, "preview_url": None},
        api_prompt=None,
        transcript=transcript,
    )
