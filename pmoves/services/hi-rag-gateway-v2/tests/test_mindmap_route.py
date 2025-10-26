from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _install_stub(name: str, module: types.ModuleType, stash: dict[str, types.ModuleType | None]) -> None:
    stash[name] = sys.modules.get(name)
    sys.modules[name] = module


def _load_gateway_module(monkeypatch: pytest.MonkeyPatch):
    stubs: dict[str, types.ModuleType | None] = {}

    sentence_mod = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, normalize_embeddings=True):
            return [[0.0, 0.0, 0.0] for _ in texts]

    sentence_mod.SentenceTransformer = _SentenceTransformer
    _install_stub("sentence_transformers", sentence_mod, stubs)

    flag_mod = types.ModuleType("FlagEmbedding")

    class _FlagReranker:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return [0.0]

    flag_mod.FlagReranker = _FlagReranker
    _install_stub("FlagEmbedding", flag_mod, stubs)

    qdrant_mod = types.ModuleType("qdrant_client")

    class _QdrantClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, *args, **kwargs):
            return []

        def get_collection(self, *args, **kwargs):
            raise RuntimeError("no collection")

        def recreate_collection(self, *args, **kwargs):
            return None

        def upsert(self, *args, **kwargs):
            return None

    qdrant_mod.QdrantClient = _QdrantClient
    _install_stub("qdrant_client", qdrant_mod, stubs)

    http_mod = types.ModuleType("qdrant_client.http")
    models_mod = types.ModuleType("qdrant_client.http.models")

    class _Stub:
        def __init__(self, *args, **kwargs):
            pass

    models_mod.Filter = _Stub
    models_mod.FieldCondition = _Stub
    models_mod.MatchValue = _Stub
    models_mod.Distance = types.SimpleNamespace(COSINE="COSINE")
    models_mod.VectorParams = _Stub
    models_mod.PointStruct = _Stub
    _install_stub("qdrant_client.http", http_mod, stubs)
    _install_stub("qdrant_client.http.models", models_mod, stubs)

    rapidfuzz_mod = types.ModuleType("rapidfuzz")

    class _Fuzz:
        @staticmethod
        def token_set_ratio(*args, **kwargs):
            return 100.0

    rapidfuzz_mod.fuzz = _Fuzz()
    _install_stub("rapidfuzz", rapidfuzz_mod, stubs)

    requests_mod = types.ModuleType("requests")

    class _Response:
        def __init__(self, ok=True):
            self.ok = ok

        def json(self):
            return {}

        def raise_for_status(self):
            return None

    def _dummy_post(*args, **kwargs):
        return _Response()

    def _dummy_get(*args, **kwargs):
        return _Response()

    requests_mod.post = _dummy_post
    requests_mod.get = _dummy_get
    _install_stub("requests", requests_mod, stubs)

    libs_mod = types.ModuleType("libs")
    providers_mod = types.ModuleType("libs.providers")
    embedding_mod = types.ModuleType("libs.providers.embedding")

    def _embed_text(text: str):
        return [0.0]

    embedding_mod.embed_text = _embed_text
    providers_mod.embedding = embedding_mod
    libs_mod.providers = providers_mod

    _install_stub("libs", libs_mod, stubs)
    _install_stub("libs.providers", providers_mod, stubs)
    _install_stub("libs.providers.embedding", embedding_mod, stubs)

    services_mod = types.ModuleType("services")
    services_common_mod = types.ModuleType("services.common")
    geometry_params_mod = types.ModuleType("services.common.geometry_params")
    hrm_sidecar_mod = types.ModuleType("services.common.hrm_sidecar")

    def _get_decoder_pack(*args, **kwargs):
        return None

    def _clear_cache():
        return None

    geometry_params_mod.get_decoder_pack = _get_decoder_pack
    geometry_params_mod.clear_cache = _clear_cache
    services_common_mod.geometry_params = geometry_params_mod

    class _HrmDecoderController:
        def __init__(self, *args, **kwargs):
            pass

        def warm(self):
            return None

    hrm_sidecar_mod.HrmDecoderController = _HrmDecoderController
    services_common_mod.hrm_sidecar = hrm_sidecar_mod
    services_mod.common = services_common_mod

    _install_stub("services", services_mod, stubs)
    _install_stub("services.common", services_common_mod, stubs)
    _install_stub("services.common.geometry_params", geometry_params_mod, stubs)
    _install_stub("services.common.hrm_sidecar", hrm_sidecar_mod, stubs)

    psycopg_mod = types.ModuleType("psycopg")

    def _connect_psycopg(*args, **kwargs):
        raise RuntimeError("psycopg stub invoked")

    psycopg_mod.connect = _connect_psycopg
    _install_stub("psycopg", psycopg_mod, stubs)

    nats_mod = types.ModuleType("nats")

    class _NatsClient:
        async def publish(self, *args, **kwargs):
            return None

        async def flush(self):
            return None

        async def drain(self):
            return None

    async def _nats_connect(*args, **kwargs):
        return _NatsClient()

    nats_mod.connect = _nats_connect
    _install_stub("nats", nats_mod, stubs)

    neo4j_mod = types.ModuleType("neo4j")

    class _GraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            class _Driver:
                def session(self):
                    raise RuntimeError("neo4j stub driver inactive")

            return _Driver()

    neo4j_mod.GraphDatabase = _GraphDatabase
    _install_stub("neo4j", neo4j_mod, stubs)

    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "pmoves/services/hi-rag-gateway-v2/app.py"
    module_name = "hirag_gateway_v2_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    sys.modules.setdefault("pmoves.services.hi_rag_gateway_v2.app", module)
    spec.loader.exec_module(module)

    def _cleanup() -> None:
        sys.modules.pop(module_name, None)
        sys.modules.pop("pmoves.services.hi_rag_gateway_v2.app", None)
        for name, original in stubs.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    return module, _cleanup


class _FakeSession:
    def __init__(self, records):
        self._records = records

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def run(self, *args, **kwargs):
        query = args[0] if args else ""
        if "return count(*) as total" in str(query).lower():
            return [{"total": len(self._records)}]
        if "coalesce(p.modality" in str(query).lower():
            counts: dict[str, int] = {}
            for record in self._records:
                modality = (
                    record.get("point", {}).get("modality")
                    or record.get("media", {}).get("modality")
                    or "unknown"
                ).lower()
                counts[modality] = counts.get(modality, 0) + 1
            return [{"modality": mod, "count": count} for mod, count in counts.items()]
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(self._records)) or len(self._records))
        end = offset + limit
        slice_records = self._records[offset:end]
        return slice_records


class _FakeDriver:
    def __init__(self, records):
        self._records = records

    def session(self):
        return _FakeSession(self._records)


@pytest.fixture()
def gateway_module(monkeypatch: pytest.MonkeyPatch):
    module, cleanup = _load_gateway_module(monkeypatch)
    try:
        yield module
    finally:
        cleanup()


def test_mindmap_route_returns_items(gateway_module, monkeypatch):
    records = [
        {
            "point": {"id": "p1", "proj": 0.9, "text": "alpha", "modality": "text"},
            "media": {"uid": "m1", "modality": "video", "ref_id": "yt_demo", "t_start": 42.3},
        },
        {
            "point": {"id": "p2", "proj": 0.8, "text": "beta", "modality": "text"},
            "media": {"uid": "m2", "modality": "text"},
        },
    ]
    monkeypatch.setattr(gateway_module, "driver", _FakeDriver(records))
    client = TestClient(gateway_module.app)
    resp = client.get(
        "/mindmap/demo",
        params={"modalities": "text,video", "limit": 1, "offset": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["offset"] == 1
    assert body["limit"] == 1
    assert body["returned"] == 1
    assert body["has_more"] is False
    assert body["total"] == 2
    assert body["remaining"] == 0
    assert body["stats"]["per_modality"]["text"] == 2
    item = body["items"][0]
    assert item["point"]["id"] == "p2"
    assert "media_url" in item
    assert item["notebook"]["constellation_id"] == "demo"


def test_mindmap_route_handles_missing_driver(gateway_module, monkeypatch):
    monkeypatch.setattr(gateway_module, "driver", None)
    client = TestClient(gateway_module.app)
    resp = client.get("/mindmap/demo")
    assert resp.status_code == 503
