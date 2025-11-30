import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _install_stub(name: str, module: types.ModuleType, registry: dict[str, types.ModuleType | None]) -> None:
    registry[name] = sys.modules.get(name)
    sys.modules[name] = module


@pytest.fixture()
def gateway_v2_module():
    root_path = Path(__file__).resolve().parents[4]
    added_root = False
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
        added_root = True

    stubs: dict[str, types.ModuleType | None] = {}

    try:
        # fastapi stub (service module expects FastAPI primitives)
        fastapi_module = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str | None = None):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        class Depends:  # pragma: no cover - structure only
            def __init__(self, dependency):
                self.dependency = dependency

        class Body:  # pragma: no cover - structure only
            def __init__(self, default=None, **kwargs):
                self.default = default

        class Request:  # pragma: no cover - structure only
            def __init__(self, client=None, headers=None):
                self.client = client
                self.headers = headers or {}

        class WebSocket:  # pragma: no cover - structure only
            def __init__(self):
                self.client = types.SimpleNamespace(host="127.0.0.1")

            async def accept(self):
                return None

            async def receive_json(self):
                return {}

            async def send_json(self, msg):
                return None

            async def close(self, *args, **kwargs):  # pragma: no cover
                return None

        class WebSocketDisconnect(Exception):
            pass

        class UploadFile:  # pragma: no cover - structure only
            def __init__(self, filename: str = "", file=None):
                self.filename = filename
                self.file = file

        class FastAPI:
            def __init__(self, *args, **kwargs):
                pass

            def on_event(self, _event):
                def decorator(func):
                    return func

                return decorator

            def get(self, *_args, **_kwargs):
                def decorator(func):
                    return func

                return decorator

            def post(self, *_args, **_kwargs):
                def decorator(func):
                    return func

                return decorator

            def websocket(self, *_args, **_kwargs):
                def decorator(func):
                    return func

                return decorator

            def mount(self, *_args, **_kwargs):
                return None

        fastapi_module.FastAPI = FastAPI
        fastapi_module.Body = Body
        fastapi_module.HTTPException = HTTPException
        fastapi_module.Request = Request
        fastapi_module.Depends = Depends
        fastapi_module.WebSocket = WebSocket
        fastapi_module.WebSocketDisconnect = WebSocketDisconnect
        fastapi_module.UploadFile = UploadFile
        _install_stub("fastapi", fastapi_module, stubs)

        staticfiles_module = types.ModuleType("fastapi.staticfiles")

        class StaticFiles:  # pragma: no cover - structure only
            def __init__(self, *args, **kwargs):
                pass

        staticfiles_module.StaticFiles = StaticFiles
        _install_stub("fastapi.staticfiles", staticfiles_module, stubs)

        pydantic_module = types.ModuleType("pydantic")

        class BaseModel:
            def __init__(self, **data):
                for key, value in data.items():
                    setattr(self, key, value)

            def model_dump(self):  # pragma: no cover - helper only
                return self.__dict__.copy()

        def Field(default=None, **kwargs):  # pragma: no cover - structure only
            return default

        pydantic_module.BaseModel = BaseModel
        pydantic_module.Field = Field
        _install_stub("pydantic", pydantic_module, stubs)

        requests_module = types.ModuleType("requests")

        class _Response:
            def __init__(self):
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):  # pragma: no cover - structure only
                return []

            @property
            def content(self):  # pragma: no cover - structure only
                return b""

        def _request(*args, **kwargs):  # pragma: no cover - structure only
            return _Response()

        requests_module.get = _request  # type: ignore[attr-defined]
        requests_module.post = _request  # type: ignore[attr-defined]
        _install_stub("requests", requests_module, stubs)

        providers_module = types.ModuleType("libs.providers")
        embedding_module = types.ModuleType("libs.providers.embedding")

        def _embed_text(_text):  # pragma: no cover - structure only
            return [0.0]

        embedding_module.embed_text = _embed_text
        providers_module.embedding = embedding_module
        _install_stub("libs", types.ModuleType("libs"), stubs)
        sys.modules["libs.providers"] = providers_module
        sys.modules["libs.providers.embedding"] = embedding_module

        # Minimal qdrant client stub
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

        class _Filter:
            pass

        class _FieldCondition:
            def __init__(self, *args, **kwargs):
                pass

        class _MatchValue:
            def __init__(self, *args, **kwargs):
                pass

        class _Distance:
            COSINE = "cosine"

        class _VectorParams:
            def __init__(self, *args, **kwargs):
                pass

        class _PointStruct:
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

        # sentence_transformers stub
        st_module = types.ModuleType("sentence_transformers")

        class _SentenceTransformer:
            def __init__(self, *args, **kwargs):
                pass

            def encode(self, texts, normalize_embeddings=True, convert_to_numpy=False):
                return [[0.0] for _ in texts]

        st_module.SentenceTransformer = _SentenceTransformer
        _install_stub("sentence_transformers", st_module, stubs)

        # FlagEmbedding stub
        flag_module = types.ModuleType("FlagEmbedding")

        class _FlagReranker:
            def __init__(self, *args, **kwargs):
                pass

            def compute_score(self, pairs, normalize=True):
                return [0.0 for _ in pairs]

        flag_module.FlagReranker = _FlagReranker
        _install_stub("FlagEmbedding", flag_module, stubs)

        # rapidfuzz stub
        rapidfuzz_module = types.ModuleType("rapidfuzz")
        rapidfuzz_module.fuzz = types.SimpleNamespace(token_set_ratio=lambda *args, **kwargs: 0)
        _install_stub("rapidfuzz", rapidfuzz_module, stubs)

        # neo4j stub to avoid connection attempts
        neo4j_module = types.ModuleType("neo4j")

        class _GraphDatabase:
            @staticmethod
            def driver(*args, **kwargs):
                raise RuntimeError("neo4j unavailable in tests")

        neo4j_module.GraphDatabase = _GraphDatabase
        _install_stub("neo4j", neo4j_module, stubs)

        # nats stub (used for optional background listener)
        nats_module = types.ModuleType("nats")

        async def _connect(*args, **kwargs):  # pragma: no cover - not exercised
            raise RuntimeError("nats not available")

        nats_module.connect = _connect  # type: ignore[attr-defined]
        _install_stub("nats", nats_module, stubs)

        # psycopg stub
        psycopg_module = types.ModuleType("psycopg")
        _install_stub("psycopg", psycopg_module, stubs)

        spec = importlib.util.spec_from_file_location(
            "hirag_gateway_v2_test", root_path / "pmoves/services/hi-rag-gateway-v2/app.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules["hirag_gateway_v2_test"] = module
        spec.loader.exec_module(module)

        yield module
    finally:
        sys.modules.pop("hirag_gateway_v2_test", None)
        for name, original in stubs.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        sys.modules.pop("libs.providers", None)
        sys.modules.pop("libs.providers.embedding", None)
        if added_root:
            try:
                sys.path.remove(str(root_path))
            except ValueError:
                pass


def _sample_cgp(namespace: str = "pmoves", modality: str = "text") -> dict:
    return {
        "spec": "geometry.cgp.v1",
        "meta": {"namespace": namespace, "modality": modality},
        "super_nodes": [
            {
                "constellations": [
                    {
                        "id": "const-1",
                        "summary": "example",
                        "points": [
                            {
                                "id": "point-1",
                                "modality": modality,
                                "ref_id": "ref-1",
                                "text": "hello",
                                "proj": 0.5,
                                "conf": 0.9,
                            }
                        ],
                    }
                ]
            }
        ],
    }


def test_swarm_meta_updates_builder_pack(monkeypatch, gateway_v2_module):
    module = gateway_v2_module
    module.shape_store = module.ShapeStore(capacity=128)
    module._active_builder_packs.clear()

    module.shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": _sample_cgp()})

    fetch_payloads = {
        "pack-1": {"id": "pack-1", "params": {"alpha": 0.1}},
        "pack-2": {"id": "pack-2", "params": {"alpha": 0.2}},
    }

    async def _fake_fetch(pack_id: str, **kwargs):
        return fetch_payloads.get(pack_id)

    monkeypatch.setattr(module, "_fetch_geometry_pack", _fake_fetch)

    clear_calls: list[bool] = []

    def _clear_cache():
        clear_calls.append(True)

    monkeypatch.setattr(module.geometry_params, "clear_cache", _clear_cache)

    payload_one = {
        "namespace": "pmoves",
        "modality": "text",
        "pack_id": "pack-1",
        "status": "active",
        "version": "v1",
    }

    asyncio.run(module._apply_swarm_meta(payload_one))

    pack = module._get_active_builder_pack("pmoves", "text")
    assert pack is not None
    assert pack["pack_id"] == "pack-1"

    const = module.shape_store.get_constellation("const-1")
    assert const
    assert const.get("meta", {}).get("builder_pack", {}).get("pack_id") == "pack-1"

    payload_two = {
        "namespace": "pmoves",
        "modality": "text",
        "pack_id": "pack-2",
        "status": "active",
    }

    asyncio.run(module._apply_swarm_meta(payload_two))

    pack = module._get_active_builder_pack("pmoves", "text")
    assert pack is not None
    assert pack["pack_id"] == "pack-2"

    const = module.shape_store.get_constellation("const-1")
    assert const
    assert const.get("meta", {}).get("builder_pack", {}).get("pack_id") == "pack-2"

    assert len(clear_calls) == 2


def test_geometry_decode_includes_builder_pack(gateway_v2_module):
    module = gateway_v2_module
    module.shape_store = module.ShapeStore(capacity=128)
    module._active_builder_packs.clear()
    module.CHIT_DECODE_TEXT = True

    module.shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": _sample_cgp()})

    module._set_active_builder_pack(
        "pmoves",
        "text",
        {
            "pack_id": "pack-9",
            "status": "active",
            "namespace": "pmoves",
            "modality": "text",
            "params": {"alpha": 0.9},
        },
    )

    result = module.geometry_decode_text({"constellation_id": "const-1"})
    assert result["builder_pack"]["pack_id"] == "pack-9"
    assert result["namespace"] == "pmoves"
    assert result["modality"].lower() == "text"

    const = module.shape_store.get_constellation("const-1")
    assert const
    assert const.get("meta", {}).get("builder_pack", {}).get("pack_id") == "pack-9"
