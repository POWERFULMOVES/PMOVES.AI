from omnivoice_client import FakeOmniVoiceClient
from voice_operator import run_voice
from schemas import validate_result


def test_run_voice_produces_audio_result(tmp_path):
    wo = {"workorder_id": "wo_v1", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "hello from the fleet", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    validate_result(r)  # conforms to the operator-result contract
    assert r["status"] == "ok"
    assert r["artifact"]["kind"] == "audio" and r["artifact"]["path"].endswith(".wav")
    assert r["api_prompt"] is None  # voice is not a ComfyUI graph -> no harvest
    assert any(s["step"] == "synthesize" for s in r["transcript"])


def test_run_voice_error_path(tmp_path):
    wo = {"workorder_id": "wo_v2", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    assert r["status"] == "error" and r["artifact"] is None and r["error"]
