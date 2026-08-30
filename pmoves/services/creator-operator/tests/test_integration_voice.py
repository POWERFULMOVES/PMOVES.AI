import os
import pytest

pytestmark = pytest.mark.requires_ui
RUN = os.getenv("CREATOR_VOICE_TEST") == "1"


@pytest.mark.skipif(not RUN, reason="set CREATOR_VOICE_TEST=1 with OmniVoice up at :8001")
def test_live_omnivoice_synthesizes_audio(tmp_path):
    """Acceptance: a live OmniVoice synth returns a real audio file, and the
    voice operator assembles a valid operator-result with an audio artifact."""
    from omnivoice_client import RealOmniVoiceClient
    from voice_operator import run_voice
    from schemas import validate_result
    wo = {"workorder_id": "wo_live", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "Powerful moves, fleetwide.", "voice_ref": None},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = RealOmniVoiceClient(out_dir=str(tmp_path))
    r = run_voice(wo, client)
    validate_result(r)
    assert r["status"] == "ok" and r["artifact"]["kind"] == "audio"
    assert os.path.exists(r["artifact"]["path"]) and os.path.getsize(r["artifact"]["path"]) > 1000
