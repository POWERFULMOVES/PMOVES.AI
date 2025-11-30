import importlib
import importlib.util
import ipaddress
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _install_stub(name: str, module: types.ModuleType, registry):
    registry[name] = sys.modules.get(name)
    sys.modules[name] = module


@pytest.fixture(scope="module")
def gateway_modules():
    stubs: dict[str, types.ModuleType | None] = {}

    # Minimal qdrant client stub to satisfy imports.
    root_path = Path(__file__).resolve().parents[4]
    added_root = False
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
        added_root = True

    qdrant_module = types.ModuleType("qdrant_client")

    class _QdrantClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, *args, **kwargs):
            return []

    qdrant_module.QdrantClient = _QdrantClient
    _install_stub("qdrant_client", qdrant_module, stubs)

    qdrant_http = types.ModuleType("qdrant_client.http")
    qdrant_http_models = types.ModuleType("qdrant_client.http.models")

    class _Filter:  # pragma: no cover - structure only
        pass

    class _FieldCondition:  # pragma: no cover - structure only
        def __init__(self, *args, **kwargs):
            pass

    class _MatchValue:  # pragma: no cover - structure only
        def __init__(self, *args, **kwargs):
            pass

    class _Distance:  # pragma: no cover - structure only
        COSINE = "cosine"

    class _VectorParams:  # pragma: no cover - structure only
        def __init__(self, *args, **kwargs):
            pass

    class _PointStruct:  # pragma: no cover - structure only
        def __init__(self, *args, **kwargs):
            pass

    qdrant_http_models.Filter = _Filter
    qdrant_http_models.FieldCondition = _FieldCondition
    qdrant_http_models.MatchValue = _MatchValue
    qdrant_http_models.Distance = _Distance
    qdrant_http_models.VectorParams = _VectorParams
    qdrant_http_models.PointStruct = _PointStruct
    qdrant_http.models = qdrant_http_models
    qdrant_module.http = qdrant_http
    _install_stub("qdrant_client.http", qdrant_http, stubs)
    _install_stub("qdrant_client.http.models", qdrant_http_models, stubs)

    # Sentence transformer stub avoids heavy dependency loading.
    st_module = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, normalize_embeddings=True):
            return [[0.0]]

    st_module.SentenceTransformer = _SentenceTransformer
    _install_stub("sentence_transformers", st_module, stubs)

    # Rapidfuzz stub
    rapidfuzz_module = types.ModuleType("rapidfuzz")
    rapidfuzz_module.fuzz = types.SimpleNamespace()
    _install_stub("rapidfuzz", rapidfuzz_module, stubs)

    # Neo4j stub so driver creation gracefully fails.
    neo4j_module = types.ModuleType("neo4j")

    class _GraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            raise RuntimeError("neo4j unavailable for tests")

    neo4j_module.GraphDatabase = _GraphDatabase
    _install_stub("neo4j", neo4j_module, stubs)

    # FlagEmbedding stub used by v2 gateway reranker wiring.
    flag_module = types.ModuleType("FlagEmbedding")

    class _FlagReranker:
        def __init__(self, *args, **kwargs):
            pass

        def compute_score(self, pairs, normalize=True):
            return [0.0 for _ in pairs]

    flag_module.FlagReranker = _FlagReranker
    _install_stub("FlagEmbedding", flag_module, stubs)

    # Misc optional dependencies
    nats_module = types.ModuleType("nats")
    _install_stub("nats", nats_module, stubs)

    psycopg_module = types.ModuleType("psycopg")
    _install_stub("psycopg", psycopg_module, stubs)

    loaded = []

    def _load(name: str, relative: str):
        module_path = root_path / relative
        spec = importlib.util.spec_from_file_location(name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded.append(name)
        return module

    gateway_v1 = _load("hirag_gateway_v1", "pmoves/services/hi-rag-gateway/gateway.py")
    gateway_v2 = _load("hirag_gateway_v2", "pmoves/services/hi-rag-gateway-v2/app.py")

    sys.modules.setdefault("pmoves.services.hi_rag_gateway.gateway", gateway_v1)
    sys.modules.setdefault("pmoves.services.hi_rag_gateway_v2.app", gateway_v2)

    # Ensure the misnamed reranker sentinel exists for stats endpoint usage.
    setattr(gateway_v2, "reranker", None)

    try:
        yield gateway_v1, gateway_v2
    finally:
        for alias in loaded:
            sys.modules.pop(alias, None)
        sys.modules.pop("pmoves.services.hi_rag_gateway.gateway", None)
        sys.modules.pop("pmoves.services.hi_rag_gateway_v2.app", None)

        for name, original in stubs.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if added_root:
            try:
                sys.path.remove(str(root_path))
            except ValueError:
                pass


def test_v1_rejects_spoofed_forwarded_for(gateway_modules, monkeypatch):
    gateway_v1, _ = gateway_modules
    monkeypatch.setattr(gateway_v1, "TAILSCALE_ONLY", True)
    monkeypatch.setattr(gateway_v1, "_TRUSTED_PROXY_NETWORKS", [], raising=False)
    client = TestClient(gateway_v1.app, client=("198.51.100.10", 50000))

    response = client.get(
        "/hirag/admin/stats",
        headers={"X-Forwarded-For": "100.64.1.25"},
    )

    assert response.status_code == 403


def test_v1_allows_trusted_proxy_forwarded_for(gateway_modules, monkeypatch):
    gateway_v1, _ = gateway_modules
    network = ipaddress.ip_network("10.10.0.1/32")
    monkeypatch.setattr(gateway_v1, "TAILSCALE_ONLY", True)
    monkeypatch.setattr(gateway_v1, "_TRUSTED_PROXY_NETWORKS", [network], raising=False)
    client = TestClient(gateway_v1.app, client=("10.10.0.1", 50000))

    response = client.get(
        "/hirag/admin/stats",
        headers={"X-Forwarded-For": "100.64.2.1"},
    )

    assert response.status_code == 200


def test_v2_rejects_spoofed_forwarded_for(gateway_modules, monkeypatch):
    _, gateway_v2 = gateway_modules
    monkeypatch.setattr(gateway_v2, "TAILSCALE_ONLY", False)
    monkeypatch.setattr(gateway_v2, "TAILSCALE_ADMIN_ONLY", True)
    monkeypatch.setattr(gateway_v2, "_TRUSTED_PROXY_NETWORKS", [], raising=False)
    client = TestClient(gateway_v2.app, client=("198.51.100.20", 50000))

    response = client.get(
        "/hirag/admin/stats",
        headers={"X-Forwarded-For": "100.64.5.10"},
    )

    assert response.status_code == 403


def test_v2_allows_trusted_proxy_forwarded_for(gateway_modules, monkeypatch):
    _, gateway_v2 = gateway_modules
    network = ipaddress.ip_network("10.20.0.5/32")
    monkeypatch.setattr(gateway_v2, "TAILSCALE_ONLY", False)
    monkeypatch.setattr(gateway_v2, "TAILSCALE_ADMIN_ONLY", True)
    monkeypatch.setattr(gateway_v2, "_TRUSTED_PROXY_NETWORKS", [network], raising=False)
    client = TestClient(gateway_v2.app, client=("10.20.0.5", 50000))

    response = client.get(
        "/hirag/admin/stats",
        headers={"X-Forwarded-For": "100.64.6.10"},
    )

    assert response.status_code == 200
