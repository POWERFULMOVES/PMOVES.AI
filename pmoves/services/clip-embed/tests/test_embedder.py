import numpy as np
from embedder import Embedder


class _FakeModel:
    def embed_images(self, images):
        return np.stack([np.full(768, float(np.mean(img)), dtype="float32") for img in images])
    def embed_text(self, texts):
        return np.stack([np.full(768, 0.5, dtype="float32") for _ in texts])


def test_embed_image_is_l2_normalised():
    emb = Embedder(model=_FakeModel())
    img = np.ones((224, 224, 3), dtype="uint8")
    vec = emb.embed_image(img)
    assert len(vec) == 768
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-6)


def test_embed_image_is_deterministic():
    emb = Embedder(model=_FakeModel())
    img = np.random.RandomState(42).randint(0, 255, (224, 224, 3), dtype="uint8")
    v1 = emb.embed_image(img)
    v2 = emb.embed_image(img)
    assert v1 == v2


def test_embed_multiple_images():
    emb = Embedder(model=_FakeModel())
    imgs = [np.ones((224, 224, 3), dtype="uint8"), np.zeros((224, 224, 3), dtype="uint8")]
    results = emb.embed_images(imgs)
    assert len(results) == 2
    assert all(len(r) == 768 for r in results)
