import base64
import io
import json
import wave
import numpy as np
from nats_responder import handle_request


class _FakeEmbedder:
    def embed_audio(self, audio, sr):
        return [0.3] * 512


def _wav_b64(sr=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.zeros(sr) * 32767).astype("<i2").tobytes())
    return base64.b64encode(buf.getvalue()).decode()


def test_handle_request_returns_embedding_and_context():
    msg = {"context_id": "ctx-1", "audio_b64": _wav_b64()}
    out = json.loads(handle_request(json.dumps(msg).encode(), _FakeEmbedder()))
    assert out["context_id"] == "ctx-1"
    assert len(out["embedding"]) == 512
    assert out["ok"] is True


def test_handle_request_bad_payload_is_flagged_not_raised():
    out = json.loads(handle_request(b"not-json", _FakeEmbedder()))
    assert out["ok"] is False and "error" in out


def test_handle_request_rejects_oversized_audio(monkeypatch):
    # an oversized base64 blob must be rejected BEFORE librosa.load (memory-DoS)
    import config
    monkeypatch.setattr(config.Config, "MAX_UPLOAD_BYTES", 1024)
    big_b64 = base64.b64encode(b"\x00" * 4096).decode()  # 4 KB decoded, over 1 KB cap
    msg = {"context_id": "ctx-big", "audio_b64": big_b64}
    out = json.loads(handle_request(json.dumps(msg).encode(), _FakeEmbedder()))
    assert out["ok"] is False and "error" in out
