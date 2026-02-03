import importlib.util
import sys
import types
from pathlib import Path
from typing import Callable

import pytest


def _load_sidecar_class():
    path = Path(__file__).resolve().parents[1] / "sidecars" / "gan_checker.py"
    spec = importlib.util.spec_from_file_location("hirag_gan_checker_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules.setdefault("hirag_gan_checker_test", module)
    spec.loader.exec_module(module)
    return module.GanSidecar


def _install_stub(name: str, module: types.ModuleType, registry: dict[str, types.ModuleType | None]) -> None:
    registry[name] = sys.modules.get(name)
    sys.modules[name] = module


def _load_gateway_v2(monkeypatch: pytest.MonkeyPatch, **env) -> tuple[types.ModuleType, Callable[[], None]]:
    stubs: dict[str, types.ModuleType | None] = {}
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

        def upsert(self, *args, **kwargs):  # pragma: no cover - compatibility
            return None

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

    st_module = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, normalize_embeddings=True, convert_to_numpy=False):
            if convert_to_numpy:
                return [[0.0] for _ in texts]
            return [[0.0] for _ in texts]

    st_module.SentenceTransformer = _SentenceTransformer
    _install_stub("sentence_transformers", st_module, stubs)

    rapidfuzz_module = types.ModuleType("rapidfuzz")
    rapidfuzz_module.fuzz = types.SimpleNamespace(token_set_ratio=lambda a, b: 42)
    _install_stub("rapidfuzz", rapidfuzz_module, stubs)

    neo4j_module = types.ModuleType("neo4j")

    class _GraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            raise RuntimeError("neo4j unavailable in tests")

    neo4j_module.GraphDatabase = _GraphDatabase
    _install_stub("neo4j", neo4j_module, stubs)

    flag_module = types.ModuleType("FlagEmbedding")

    class _FlagReranker:
        def __init__(self, *args, **kwargs):
            pass

        def compute_score(self, pairs, normalize=True):
            return [0.0 for _ in pairs]

    flag_module.FlagReranker = _FlagReranker
    _install_stub("FlagEmbedding", flag_module, stubs)

    nats_module = types.ModuleType("nats")
    _install_stub("nats", nats_module, stubs)

    psycopg_module = types.ModuleType("psycopg")

    def _connect(*args, **kwargs):  # pragma: no cover - not used in tests
        raise RuntimeError("psycopg disabled for tests")

    psycopg_module.connect = _connect
    _install_stub("psycopg", psycopg_module, stubs)

    fastapi_module = types.ModuleType("fastapi")

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str | None = None):
            self.status_code = status_code
            self.detail = detail or ""
            super().__init__(self.detail)

    class _Request:
        def __init__(self, client: tuple[str, int] | None = None, headers: dict[str, str] | None = None):
            self.client = client
            self.headers = headers or {}

    class _Depends:
        def __init__(self, dependency=None):
            self.dependency = dependency

    class _FastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = {}

        def post(self, path: str, **kwargs):
            def decorator(func):
                self.routes[(path, "POST")] = func
                return func
            return decorator

        def get(self, path: str, **kwargs):
            def decorator(func):
                self.routes[(path, "GET")] = func
                return func
            return decorator

        def mount(self, *args, **kwargs):
            return None

        def on_event(self, event: str):  # pragma: no cover - placeholder
            def decorator(func):
                return func
            return decorator

        def websocket(self, path: str, **kwargs):  # pragma: no cover - placeholder
            def decorator(func):
                self.routes[(path, "WEBSOCKET")] = func
                return func
            return decorator

    class _WebSocket:  # pragma: no cover - placeholder
        pass

    class _WebSocketDisconnect(Exception):
        pass

    class _UploadFile:  # pragma: no cover - placeholder
        def __init__(self, *args, **kwargs):
            pass

    def _body(default=..., **kwargs):
        return default

    def _depends(callable=None):
        return callable

    fastapi_module.FastAPI = _FastAPI
    fastapi_module.Body = _body
    fastapi_module.Depends = _depends
    fastapi_module.HTTPException = _HTTPException
    fastapi_module.Request = _Request
    fastapi_module.WebSocket = _WebSocket
    fastapi_module.WebSocketDisconnect = _WebSocketDisconnect
    fastapi_module.UploadFile = _UploadFile

    staticfiles_module = types.ModuleType("fastapi.staticfiles")

    class _StaticFiles:  # pragma: no cover - placeholder
        def __init__(self, *args, **kwargs):
            pass

    staticfiles_module.StaticFiles = _StaticFiles

    _install_stub("fastapi", fastapi_module, stubs)
    _install_stub("fastapi.staticfiles", staticfiles_module, stubs)

    pydantic_module = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self):  # pragma: no cover - minimal helper
            return dict(self.__dict__)

    def _field(default=None, **kwargs):
        return default

    pydantic_module.BaseModel = _BaseModel
    pydantic_module.Field = _field
    _install_stub("pydantic", pydantic_module, stubs)

    requests_module = types.ModuleType("requests")

    class _Response:  # pragma: no cover - placeholder
        def __init__(self, content: bytes = b""):
            self.content = content

        def raise_for_status(self):
            return None

    def _get(*args, **kwargs):
        return _Response()

    requests_module.get = _get
    _install_stub("requests", requests_module, stubs)

    libs_module = types.ModuleType("libs")
    providers_module = types.ModuleType("libs.providers")
    embedding_module = types.ModuleType("libs.providers.embedding")

    def _embed_text(text: str):  # pragma: no cover - placeholder
        return [0.0]

    embedding_module.embed_text = _embed_text
    providers_module.embedding = embedding_module
    libs_module.providers = providers_module

    _install_stub("libs", libs_module, stubs)
    _install_stub("libs.providers", providers_module, stubs)
    _install_stub("libs.providers.embedding", embedding_module, stubs)

    monkeypatch.setenv("CHIT_DECODE_TEXT", "true")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    module_path = root_path / "pmoves/services/hi-rag-gateway-v2/app.py"
    module_name = env.get("_module_name", "hirag_gateway_v2_test")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    sys.modules.setdefault("pmoves.services.hi_rag_gateway_v2.app", module)

    def _cleanup() -> None:
        sys.modules.pop(module_name, None)
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

    return module, _cleanup


@pytest.fixture()
def gateway_factory(monkeypatch: pytest.MonkeyPatch):
    cleaners: list[Callable[[], None]] = []

    def _loader(**env):
        module, cleanup = _load_gateway_v2(monkeypatch, **env)
        cleaners.append(cleanup)
        return module

    try:
        yield _loader
    finally:
        while cleaners:
            cleaners.pop()()


def test_gan_sidecar_applies_edits():
    GanSidecar = _load_sidecar_class()
    sidecar = GanSidecar()
    candidates = [
        {"id": "c1", "text": "TODO clean summary for the agent."},
        {"id": "c2", "text": "Concise constellation summary with context and action."},
    ]
    review = sidecar.review_text_candidates(
        candidates,
        enabled=True,
        max_edits=1,
        accept_threshold=0.9,
    )
    assert review["selected"]["id"] == "c2"
    edited_candidate = review["candidates"][0]
    assert edited_candidate["original_text"].startswith("TODO")
    assert "TODO" not in edited_candidate["text"]
    assert edited_candidate["edits"] >= 1
    assert review["telemetry"]["decision"] in {"accepted", "escalated"}


def test_geometry_decode_swarm_disabled_bypasses(gateway_factory):
    module = gateway_factory(GAN_SIDECAR_ENABLED="false", _module_name="hirag_gateway_v2_disabled")
    assert module.shape_store is not None
    module.shape_store.put_cgp({
        "super_nodes": [
            {
                "constellations": [
                    {
                        "id": "const.test",
                        "points": [
                            {"id": "p1", "text": "Primary summary for evaluation.", "conf": 0.9, "proj": 0.5},
                            {"id": "p2", "text": "Backup summary content.", "conf": 0.8, "proj": 0.4},
                        ],
                    }
                ]
            }
        ]
    })
    data = module.geometry_decode_text({"mode": "swarm", "constellation_id": "const.test", "k": 2})
    assert data["telemetry"]["decision"] == "bypassed"
    assert data["selected"]["id"] == "p1"
    assert data["telemetry"]["enabled"] is False


def test_geometry_decode_swarm_enabled_scores_candidates(gateway_factory):
    module = gateway_factory(GAN_SIDECAR_ENABLED="true", _module_name="hirag_gateway_v2_enabled")
    assert module.shape_store is not None
    module.shape_store.put_cgp({
        "super_nodes": [
            {
                "constellations": [
                    {
                        "id": "const.live",
                        "summary": "Constellation summary for reference.",
                        "points": [
                            {"id": "bad", "text": "TODO fix this later.", "conf": 0.95, "proj": 0.6},
                            {"id": "good", "text": "Grounded constellation summary with actionable insight.", "conf": 0.85, "proj": 0.55},
                        ],
                    }
                ]
            }
        ]
    })
    data = module.geometry_decode_text(
        {
            "mode": "swarm",
            "constellation_id": "const.live",
            "k": 2,
            "accept_threshold": 0.9,
            "max_edits": 1,
        }
    )
    assert data["telemetry"]["enabled"] is True
    assert data["telemetry"]["decision"] in {"accepted", "escalated"}
    assert data["selected"]["id"] == "good"
    first_candidate = next(item for item in data["candidates"] if item["id"] == "bad")
    assert "TODO" not in first_candidate["text"]
    assert first_candidate["edits"] >= 1
