import asyncio

from omnivoice_client import FakeOmniVoiceClient
from voice_operator import run_voice
from schemas import validate_result
from fanout import emit_result


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


class _FakeSinks:
    def __init__(self):
        self.nats = []
        self.notebook = []
        self.discord = []
        self.n8n = []

    async def publish_nats(self, s, p):
        self.nats.append((s, p))

    async def write_notebook(self, t):
        self.notebook.append(t)

    async def notify_discord(self, s, a):
        self.discord.append((s, a))

    async def save_n8n(self, w):
        self.n8n.append(w)


def test_voice_result_fans_out(tmp_path):
    wo = {"workorder_id": "wo_v3", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "fleet voice", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    sinks = _FakeSinks()
    asyncio.run(emit_result(r, wo, sinks, model_id="k2-fsa/OmniVoice", license_name="apache-2.0"))
    assert sinks.nats and sinks.nats[0][0] == "creator.operator.result.v1"
    assert sinks.discord and sinks.discord[0][1]["kind"] == "audio"
    assert sinks.n8n  # exported
