import io
import wave
import numpy as np
from fastapi.testclient import TestClient
from app import create_app, get_embedder, _redact_url


class _FakeEmbedder:
    def embed_audio(self, audio, sr):
        return [0.1] * 512
    def embed_text(self, texts):
        return [[0.2] * 512 for _ in texts]


def _wav_bytes(seconds=1, sr=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        samples = (np.zeros(sr * seconds) * 32767).astype("<i2")
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def _client():
    app = create_app()
    app.dependency_overrides[get_embedder] = lambda: _FakeEmbedder()
    return TestClient(app)


def test_healthz_ok():
    r = _client().get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["model_id"]


def test_embed_audio_returns_512():
    r = _client().post("/embed/audio", files={"file": ("x.wav", _wav_bytes(), "audio/wav")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["embedding"]) == 512 and body["model_rev"]


def test_embed_text_returns_512():
    r = _client().post("/embed/text", json={"texts": ["dark techno"]})
    assert r.status_code == 200
    assert len(r.json()["embeddings"][0]) == 512


def test_metrics_exposed():
    c = _client()
    c.get("/healthz")
    r = c.get("/metrics")
    assert r.status_code == 200 and b"clap_embed_requests_total" in r.content


def test_redact_url_strips_credentials():
    # credentials must never survive into a log line
    out = _redact_url("nats://user:s3cr3t@nats.internal:4222")
    assert "s3cr3t" not in out and "user" not in out
    assert "nats.internal:4222" in out


def test_redact_url_passthrough_and_unset():
    assert _redact_url("nats://nats:4222") == "nats://nats:4222"
    assert _redact_url(None) == "<unset>"
    assert _redact_url("") == "<unset>"
