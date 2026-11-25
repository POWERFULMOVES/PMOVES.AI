"""extract-worker /ingest: oversized-text guard and replace-by-doc_id.

Defence in depth for the 8192-token clipping measured in layer map #3406:
whatever the upstream chunker did, /ingest must not send a text over
EXTRACT_MAX_EMBED_CHARS to the embedder. Over-threshold texts are counted
(log + Prometheus) and re-split with the shared helper.

Qdrant and sentence-transformers are stubbed; nothing here touches a live
service.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("numpy")
pytest.importorskip("prometheus_client")
pytest.importorskip("requests")

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SERVICE_DIR = Path(__file__).resolve().parents[1] / "services" / "extract-worker"
MODULE_NAME = "_extract_worker_under_test"


class _Model:
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        self._args = args


class FakeQdrant:
    calls: list = []
    existing: list = []

    def __init__(self, *args, **kwargs):
        pass

    def get_collection(self, name):
        return types.SimpleNamespace(config=types.SimpleNamespace(params={"vectors": {"size": 4}}))

    def recreate_collection(self, *a, **k):  # pragma: no cover - not hit
        FakeQdrant.calls.append(("recreate", a, k))

    def scroll(self, collection_name, scroll_filter=None, limit=256, offset=None,
               with_payload=True, with_vectors=False):
        FakeQdrant.calls.append(("scroll", scroll_filter))
        pts = [types.SimpleNamespace(id=f"pid-{i}", payload={"chunk_id": cid})
               for i, cid in enumerate(FakeQdrant.existing)]
        return pts, None

    def delete(self, collection_name, points_selector, **kwargs):
        FakeQdrant.calls.append(("delete", points_selector))

    def upsert(self, collection_name, points):
        FakeQdrant.calls.append(("upsert", points))


def _install_stubs():
    qc = types.ModuleType("qdrant_client")
    qc.QdrantClient = FakeQdrant
    http = types.ModuleType("qdrant_client.http")
    models = types.ModuleType("qdrant_client.http.models")
    for name in ("VectorParams", "PointStruct", "Filter", "FieldCondition", "MatchValue",
                 "FilterSelector", "PointIdsList"):
        setattr(models, name, type(name, (_Model,), {}))
    models.Distance = types.SimpleNamespace(COSINE="Cosine")
    http.models = models
    qc.http = http
    st = types.ModuleType("sentence_transformers")
    st.SentenceTransformer = object
    return {
        "qdrant_client": qc,
        "qdrant_client.http": http,
        "qdrant_client.http.models": models,
        "sentence_transformers": st,
    }


@pytest.fixture(scope="module")
def worker():
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    stubs = _install_stubs()
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    sys.path.insert(0, str(SERVICE_DIR))
    try:
        spec = importlib.util.spec_from_file_location(MODULE_NAME, SERVICE_DIR / "worker.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(SERVICE_DIR))
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return mod


@pytest.fixture
def harness(worker, monkeypatch):
    FakeQdrant.calls = []
    FakeQdrant.existing = []
    embedded: list[list[str]] = []
    meili: list[tuple] = []

    def fake_embed(texts):
        embedded.append(list(texts))
        return np.ones((len(texts), 4), dtype=float)

    monkeypatch.setattr(worker, "_embed", fake_embed)
    monkeypatch.setattr(worker, "_meili", lambda method, path, **kw: meili.append((method, path, kw)))
    monkeypatch.setattr(worker, "QdrantClient", FakeQdrant)
    monkeypatch.setattr(worker, "CGP_PUBLISH_ENABLED", False)
    monkeypatch.setattr(worker, "EXTRACT_MAX_EMBED_CHARS", 8000)
    monkeypatch.delenv("LANGEXTRACT_MAX_CHARS", raising=False)
    monkeypatch.delenv("LANGEXTRACT_OVERLAP_CHARS", raising=False)
    return types.SimpleNamespace(
        client=TestClient(worker.app), embedded=embedded, meili=meili, worker=worker
    )


def _long(n=200):
    return " ".join(f"Sentence number {i} talks about retrieval and embeddings." for i in range(n))


def _counter_value(counter):
    return counter._value.get()


def test_oversized_text_is_counted_and_resplit_not_sent_whole(harness):
    big = _long(200)
    assert len(big) > 8000
    before = _counter_value(harness.worker.oversized_texts_total)
    resp = harness.client.post("/ingest", json={"chunks": [
        {"doc_id": "d", "section_id": "s1", "chunk_id": "d-s1-1", "namespace": "ns", "text": "tiny"},
        {"doc_id": "d", "section_id": "s2", "chunk_id": "d-s2-1", "namespace": "ns", "text": big},
    ]})
    assert resp.status_code == 200, resp.text
    sent = [t for batch in harness.embedded for t in batch]
    assert max(len(t) for t in sent) <= 2000
    assert big not in sent
    assert _counter_value(harness.worker.oversized_texts_total) - before == 1
    upserts = [c for c in FakeQdrant.calls if c[0] == "upsert"]
    points = upserts[0][1]
    assert len(points) == len(sent)
    payloads = [p.payload for p in points]
    assert any(p.get("parent_chunk_id") == "d-s2-1" for p in payloads)
    assert resp.json()["chunks"] == len(sent)
    assert resp.json()["resplit"] == 1


def test_text_under_threshold_is_sent_unchanged(harness):
    medium = "m" * 3000
    resp = harness.client.post("/ingest", json={"chunks": [
        {"doc_id": "d", "chunk_id": "c1", "text": medium},
    ]})
    assert resp.status_code == 200
    assert harness.embedded == [[medium]]


def test_replace_true_deletes_doc_points_before_upsert(harness):
    FakeQdrant.existing = ["d-sec1-1", "d-sec1-2"]
    resp = harness.client.post("/ingest", json={"replace": True, "chunks": [
        {"doc_id": "d", "section_id": "sec1", "chunk_id": "d-sec1-p1", "namespace": "ns", "text": "new"},
    ]})
    assert resp.status_code == 200, resp.text
    ops = [c[0] for c in FakeQdrant.calls]
    assert "delete" in ops and "upsert" in ops
    assert ops.index("delete") < ops.index("upsert")
    delete_selector = [c[1] for c in FakeQdrant.calls if c[0] == "delete"][0]
    conds = delete_selector.filter.must
    keys = {(c.key, c.match.value) for c in conds}
    assert keys == {("doc_id", "d"), ("namespace", "ns")}
    meili_deletes = [m for m in harness.meili if m[1].endswith("/documents/delete-batch")]
    assert meili_deletes and meili_deletes[0][2]["json"] == ["d-sec1-1", "d-sec1-2"]
    assert resp.json()["replaced_doc_ids"] == ["d"]


def test_replace_default_false_never_deletes(harness):
    FakeQdrant.existing = ["d-sec1-1"]
    resp = harness.client.post("/ingest", json={"chunks": [
        {"doc_id": "d", "chunk_id": "d-sec1-p1", "text": "new"},
    ]})
    assert resp.status_code == 200
    assert not [c for c in FakeQdrant.calls if c[0] in ("delete", "scroll")]
    assert not [m for m in harness.meili if "delete" in m[1]]
