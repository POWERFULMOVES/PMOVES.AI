from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def provenance_module():
    qdrant_store = {"upserts": [], "dims": []}
    stubs: dict[str, types.ModuleType | None] = {}

    def _install(name: str, module: types.ModuleType) -> None:
        stubs[name] = sys.modules.get(name)
        sys.modules[name] = module

    config = types.ModuleType("config")
    config.COLL = "pmoves_chunks_qwen3"
    config.MEILI_API_KEY = ""
    config.MEILI_URL = "http://meili:7700"
    config.NAMESPACE_DEFAULT = "pmoves"
    config.logger = types.SimpleNamespace(exception=lambda *args, **kwargs: None)
    _install("config", config)

    embeddings = types.ModuleType("embeddings")
    embeddings.embed_query = lambda text: [float(len(text.split())), 0.5, 0.25]
    _install("embeddings", embeddings)

    clients_qdrant = types.ModuleType("clients.qdrant")

    class FakePointStruct:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeQdrant:
        def upsert(self, collection_name, points):
            qdrant_store["upserts"].append({"collection_name": collection_name, "points": points})

    clients_qdrant.PointStruct = FakePointStruct
    clients_qdrant.qdrant = FakeQdrant()
    clients_qdrant.ensure_qdrant_collection = lambda dim: qdrant_store["dims"].append(dim)
    _install("clients.qdrant", clients_qdrant)

    requests_mod = types.ModuleType("requests")

    class Response:
        def __init__(self, ok=True):
            self.ok = ok

    requests_mod.post = lambda *args, **kwargs: Response(True)
    _install("requests", requests_mod)

    path = Path(__file__).resolve().parents[1] / "provenance_ingest.py"
    spec = importlib.util.spec_from_file_location("hirag_provenance_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["hirag_provenance_test"] = module
    spec.loader.exec_module(module)

    try:
        yield module, qdrant_store
    finally:
        sys.modules.pop("hirag_provenance_test", None)
        for name, original in stubs.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def _sample_payload() -> dict:
    return {
        "content_id": "transcript:vid-123",
        "text": "Semantic provenance attestation for HiRAG starts with contextual anchors and merkle traces.",
        "source_ref": "http://minio:9000/assets/audio.wav",
        "shape_id": "shape-abc123",
        "merkle_root": "0x" + "a" * 64,
        "graphiti_mark": "graphiti:shape-abc123:deadbeef",
        "kb_namespace": "hirag-provenance",
        "accepted_reason": "provenance_gate_passed",
        "provenance_refs": ["http://minio:9000/assets/audio.wav", "shape:shape-abc123"],
        "favorite_words": ["provenance", "anchors"],
        "anchor_terms": ["provenance", "anchors"],
        "semantic_weights": [{"term": "provenance", "weight": 0.7, "favorite": True}],
        "scorecard": {"noise_score": 0.1},
        "meta": {"worker": "content-provenance-gate"},
    }


def test_provenance_payload_to_upsert_item_preserves_metadata(provenance_module):
    module, _ = provenance_module
    item = module.provenance_payload_to_upsert_item(_sample_payload())

    assert item["doc_id"] == "provenance:transcript:vid-123"
    assert item["chunk_id"] == "shape-abc123"
    assert item["namespace"] == "hirag-provenance"
    assert item["payload"]["merkle_root"].startswith("0x")
    assert item["payload"]["source_topic"] == "content.hirag.accepted.v1"


def test_upsert_provenance_payloads_pushes_to_qdrant_and_meili(provenance_module):
    module, qdrant_store = provenance_module
    result = module.upsert_provenance_payloads([_sample_payload()])

    assert result["ok"] is True
    assert result["upserted"] == 1
    assert result["lexical_indexed"] == 1
    assert qdrant_store["dims"] == [3]
    assert len(qdrant_store["upserts"]) == 1
    first_point = qdrant_store["upserts"][0]["points"][0]
    assert first_point.payload["shape_id"] == "shape-abc123"
