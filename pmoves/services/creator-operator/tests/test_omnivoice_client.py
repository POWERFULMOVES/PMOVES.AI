import json

import httpx
import pytest
from omnivoice_client import FakeOmniVoiceClient, OmniVoiceError, ServerOmniVoiceClient

_WAV = (b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")


def test_fake_client_synthesizes_to_path(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    path = client.synthesize(text="hello fleet", voice_ref="bean")
    assert path.endswith(".wav")
    import os
    assert os.path.exists(path)


def test_fake_client_raises_on_empty_text(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="", voice_ref="bean")


def _transport(captured: dict, *, status: int = 200, body: bytes = _WAV):
    """Build an httpx.MockTransport that records the request and returns a fixed reply."""
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content) if request.content else {}
        return httpx.Response(status, content=body)
    return httpx.MockTransport(handler)


def test_server_client_sends_token_header_and_persists_wav(tmp_path):
    captured = {}
    client = ServerOmniVoiceClient(
        out_dir=tmp_path, token="s3cret", transport=_transport(captured),
    )
    path = client.synthesize(text="hello from prod", voice_design="female, british accent")

    # token header forwarded for the server's X-OmniVoice-Token gate
    assert captured["headers"]["x-omnivoice-token"] == "s3cret"
    # POST /synthesize on the configured base_url
    assert captured["url"].endswith("/synthesize")
    # wav body persisted to out_dir/voice.wav
    assert path.endswith("voice.wav")
    assert (tmp_path / "voice.wav").read_bytes() == _WAV


def test_server_client_maps_voice_design_and_ref(tmp_path):
    captured = {}
    client = ServerOmniVoiceClient(out_dir=tmp_path, transport=_transport(captured))
    client.synthesize(text="clone me", voice_ref="bean", voice_design="warm, slow")

    # voice_design -> instruct, voice_ref (catalog id) -> ref_audio
    assert captured["json"]["instruct"] == "warm, slow"
    assert captured["json"]["ref_audio"] == "bean"
    assert captured["json"]["text"] == "clone me"


def test_server_client_omits_token_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNIVOICE_TOKEN", raising=False)
    captured = {}
    client = ServerOmniVoiceClient(out_dir=tmp_path, transport=_transport(captured))
    client.synthesize(text="no auth")
    assert "x-omnivoice-token" not in captured["headers"]


def test_server_client_reads_token_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIVOICE_TOKEN", "env-tok")
    captured = {}
    client = ServerOmniVoiceClient(out_dir=tmp_path, transport=_transport(captured))
    client.synthesize(text="env auth")
    assert captured["headers"]["x-omnivoice-token"] == "env-tok"


def test_server_client_raises_on_empty_text(tmp_path):
    client = ServerOmniVoiceClient(out_dir=tmp_path, transport=_transport({}))
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="   ")


def test_server_client_raises_on_error_status(tmp_path):
    client = ServerOmniVoiceClient(
        out_dir=tmp_path,
        transport=_transport({}, status=500, body=b"boom"),
    )
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="will fail")


def test_server_client_raises_on_empty_body(tmp_path):
    client = ServerOmniVoiceClient(
        out_dir=tmp_path,
        transport=_transport({}, status=200, body=b""),
    )
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="empty body")


def test_run_voice_works_with_server_client_unchanged(tmp_path):
    """run_voice depends only on the synthesize interface — ServerOmniVoiceClient
    drops in for FakeOmniVoiceClient with no operator changes."""
    from voice_operator import run_voice
    from schemas import validate_result

    captured = {}
    client = ServerOmniVoiceClient(out_dir=tmp_path, transport=_transport(captured))
    wo = {"workorder_id": "wo_srv", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "fleet voice", "voice_ref": "bean", "voice_design": "warm"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    r = run_voice(wo, client)
    validate_result(r)
    assert r["status"] == "ok"
    assert r["artifact"]["kind"] == "audio" and r["artifact"]["path"].endswith(".wav")
