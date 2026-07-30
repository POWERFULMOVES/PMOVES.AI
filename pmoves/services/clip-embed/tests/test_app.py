import io
from fastapi.testclient import TestClient
from app import create_app, get_embedder


class _FakeEmbedder:
    def embed_image(self, image):
        return [0.1] * 768
    def embed_images(self, images):
        return [[0.1] * 768 for _ in images]
    def embed_text(self, texts):
        return [[0.2] * 768 for _ in texts]


def _png_bytes(size=224):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (128, 128, 128)).save(buf, "PNG")
    return buf.getvalue()


def _client():
    app = create_app()
    app.dependency_overrides[get_embedder] = lambda: _FakeEmbedder()
    return TestClient(app)


def test_healthz_ok():
    r = _client().get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["model_id"]


def test_embed_image_returns_768():
    r = _client().post("/embed/image", files={"file": ("x.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["embedding"]) == 768 and body["model_rev"]


def test_embed_text_returns_768():
    r = _client().post("/embed/text", json={"texts": ["a cat sitting on a chair"]})
    assert r.status_code == 200
    assert len(r.json()["embeddings"][0]) == 768


def test_metrics_exposed():
    c = _client()
    c.get("/healthz")
    r = c.get("/metrics")
    assert r.status_code == 200 and b"clip_embed_requests_total" in r.content
