import importlib
import os
import sys
import types
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[4]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.hrm_sidecar import HrmDecoderController, is_torch_available


def _install_stub_modules():
    # sentence_transformers stub
    st_mod = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, normalize_embeddings=True):
            return [[0.0, 0.0, 0.0] for _ in texts]

    st_mod.SentenceTransformer = _SentenceTransformer
    sys.modules["sentence_transformers"] = st_mod

    # FlagEmbedding stub
    flag_mod = types.ModuleType("FlagEmbedding")

    class _FlagReranker:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return [0.0]

    flag_mod.FlagReranker = _FlagReranker
    sys.modules["FlagEmbedding"] = flag_mod

    # qdrant_client stub with minimal API
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
    sys.modules["qdrant_client"] = qdrant_mod
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
    sys.modules["qdrant_client.http"] = http_mod
    sys.modules["qdrant_client.http.models"] = models_mod

    # rapidfuzz stub
    rapidfuzz_mod = types.ModuleType("rapidfuzz")

    class _Fuzz:
        @staticmethod
        def token_set_ratio(*args, **kwargs):
            return 100.0

    rapidfuzz_mod.fuzz = _Fuzz()
    sys.modules["rapidfuzz"] = rapidfuzz_mod

    # requests stub
    requests_mod = types.ModuleType("requests")

    class _Response:
        def __init__(self, ok: bool = True):
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
    sys.modules["requests"] = requests_mod

    # transformers pipeline stub
    transformers_mod = types.ModuleType("transformers")

    def _pipeline(task, model):
        assert task == "summarization"

        def _runner(text, max_length=128, min_length=32, do_sample=False):
            return [{"summary_text": "stub summary"}]

        return _runner

    transformers_mod.pipeline = _pipeline
    sys.modules["transformers"] = transformers_mod

    # neo4j stub
    neo4j_mod = types.ModuleType("neo4j")

    class _Driver:
        def session(self):
            return self

        def run(self, *args, **kwargs):
            return []

        def close(self):
            pass

    class _GraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            return _Driver()

    neo4j_mod.GraphDatabase = _GraphDatabase
    sys.modules["neo4j"] = neo4j_mod

    # Misc optional modules
    sys.modules["nats"] = types.ModuleType("nats")
    sys.modules["psycopg"] = types.ModuleType("psycopg")


def _prepare_env():
    os.environ.setdefault("RERANK_ENABLE", "false")
    os.environ.setdefault("CHIT_DECODE_TEXT", "true")
    os.environ.setdefault("CHIT_DECODE_IMAGE", "false")
    os.environ.setdefault("CHIT_DECODE_AUDIO", "false")
    os.environ.setdefault("SUPA_REST_URL", "")
    os.environ.setdefault("TAILSCALE_ONLY", "false")


@pytest.fixture(scope="module")
def hirag_module():
    module_names = [
        "sentence_transformers",
        "FlagEmbedding",
        "qdrant_client",
        "qdrant_client.http",
        "qdrant_client.http.models",
        "transformers",
        "neo4j",
        "nats",
        "psycopg",
        "rapidfuzz",
        "requests",
    ]
    originals = {name: sys.modules.get(name) for name in module_names}
    _install_stub_modules()
    _prepare_env()
    app_path = repo_root / "pmoves" / "services" / "hi-rag-gateway-v2" / "app.py"
    pkg_name = "pmoves.services.hi_rag_gateway_v2"
    if pkg_name not in sys.modules:
        pkg_module = types.ModuleType(pkg_name)
        pkg_module.__path__ = [str(app_path.parent)]
        sys.modules[pkg_name] = pkg_module
    spec = importlib.util.spec_from_file_location(f"{pkg_name}.app", app_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.app"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    yield module
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


@pytest.mark.skipif(not is_torch_available(), reason="torch not available")
def test_geometry_decode_text_hrm_disabled(hirag_module):
    hirag_module._hrm_controller = HrmDecoderController(lambda ns, mod: None)
    hirag_module._hrm_controller.clear_cache()
    hirag_module._load_codebook = lambda path: [{"text": "alpha"}]
    body = {"mode": "learned", "namespace": "pmoves"}
    result = hirag_module.geometry_decode_text(body)
    assert result["hrm"]["enabled"] is False
    assert result["namespace"] == "pmoves"


@pytest.mark.skipif(not is_torch_available(), reason="torch not available")
def test_geometry_decode_text_hrm_enabled(hirag_module):
    pack = {"id": "pack-hrm", "params": {"hrm_halt_thresh": 0.6, "hrm_mmax": 3, "hrm_mmin": 1}}
    hirag_module._hrm_controller = HrmDecoderController(lambda ns, mod: pack)
    hirag_module._hrm_controller.clear_cache()
    hirag_module._load_codebook = lambda path: [{"text": "alpha"}]
    body = {"mode": "learned", "namespace": "pmoves"}
    result = hirag_module.geometry_decode_text(body)
    assert result["hrm"]["enabled"] is True
    assert result["hrm"]["steps"] <= pack["params"]["hrm_mmax"]
    assert result["summary"] == "stub summary"
