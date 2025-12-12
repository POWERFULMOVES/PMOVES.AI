from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Callable, Dict

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_repo_on_path() -> None:
    """Ensure the repository root is importable during tests."""
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _install_module(name: str, module: ModuleType) -> None:
    sys.modules.setdefault(name, module)


@pytest.fixture(scope="session", autouse=True)
def stub_external_modules() -> None:
    """Provide lightweight stand-ins for optional heavy dependencies."""
    # qdrant client + http models
    if "qdrant_client" not in sys.modules:
        qdrant_module = ModuleType("qdrant_client")

        class _FakeQdrantClient:
            def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
                self.args = args
                self.kwargs = kwargs

        qdrant_module.QdrantClient = _FakeQdrantClient  # type: ignore[attr-defined]
        _install_module("qdrant_client", qdrant_module)

        models_module = ModuleType("qdrant_client.http.models")

        class _FakeFilter:
            def __init__(self, *args, must=None, **kwargs) -> None:  # pragma: no cover - trivial
                self.args = args
                self.must = must or []
                self.kwargs = kwargs

        class _FakeFieldCondition(_FakeFilter):
            def __init__(self, key=None, match=None, *args, **kwargs) -> None:  # pragma: no cover
                super().__init__(*args, **kwargs)
                self.key = key
                self.match = match

        class _FakeMatchValue:
            def __init__(self, value=None, **kwargs) -> None:  # pragma: no cover
                self.value = value
                self.kwargs = kwargs

            def model_dump(self):  # pragma: no cover
                return {"value": self.value}

        models_module.Filter = _FakeFilter  # type: ignore[attr-defined]
        models_module.FieldCondition = _FakeFieldCondition  # type: ignore[attr-defined]
        models_module.MatchValue = _FakeMatchValue  # type: ignore[attr-defined]
        http_module = ModuleType("qdrant_client.http")
        http_module.models = models_module  # type: ignore[attr-defined]
        _install_module("qdrant_client.http", http_module)
        _install_module("qdrant_client.http.models", models_module)

    # sentence-transformers
    if "sentence_transformers" not in sys.modules:
        st_module = ModuleType("sentence_transformers")

        class _FakeSentenceTransformer:
            def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
                self.args = args
                self.kwargs = kwargs

            def encode(self, texts, normalize_embeddings: bool = True):  # pragma: no cover - trivial
                return [[0.0, 0.0, 0.0] for _ in texts]

        st_module.SentenceTransformer = _FakeSentenceTransformer  # type: ignore[attr-defined]
        _install_module("sentence_transformers", st_module)

    # rapidfuzz
    if "rapidfuzz" not in sys.modules:
        rapidfuzz_module = ModuleType("rapidfuzz")
        rapidfuzz_module.fuzz = SimpleNamespace(token_set_ratio=lambda a, b: 100.0)  # type: ignore[attr-defined]
        _install_module("rapidfuzz", rapidfuzz_module)

    # neo4j
    if "neo4j" not in sys.modules:
        neo4j_module = ModuleType("neo4j")

        class _FakeGraphDatabase:
            @staticmethod
            def driver(*args, **kwargs):  # pragma: no cover - trivial
                raise RuntimeError("neo4j driver unavailable in tests")

        neo4j_module.GraphDatabase = _FakeGraphDatabase  # type: ignore[attr-defined]
        _install_module("neo4j", neo4j_module)

    # yt_dlp (overridden per-test with richer behaviour)
    if "yt_dlp" not in sys.modules:
        yt_module = ModuleType("yt_dlp")

        class _PlaceholderYDL:  # pragma: no cover - simple stub
            def __init__(self, *args, **kwargs) -> None:
                raise RuntimeError("yt_dlp stub used without monkeypatch")

        yt_module.YoutubeDL = _PlaceholderYDL  # type: ignore[attr-defined]
        _install_module("yt_dlp", yt_module)

    if "yaml" not in sys.modules:
        yaml_module = ModuleType("yaml")

        def _yaml_stub(*args, **kwargs):  # pragma: no cover - simple stub
            raise RuntimeError("yaml stub used without dependency")

        yaml_module.safe_load = _yaml_stub  # type: ignore[attr-defined]
        yaml_module.safe_dump = _yaml_stub  # type: ignore[attr-defined]
        _install_module("yaml", yaml_module)

    # boto3 client stub; upload_file is patched in tests
    if "boto3" not in sys.modules:
        boto3_module = ModuleType("boto3")

        class _FakeS3Client:
            def upload_file(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
                return None

        def _fake_client(*args, **kwargs):  # pragma: no cover - trivial
            return _FakeS3Client()

        boto3_module.client = _fake_client  # type: ignore[attr-defined]
        _install_module("boto3", boto3_module)

    # nats-py
    if "nats" not in sys.modules:
        nats_module = ModuleType("nats")
        aio_module = ModuleType("nats.aio")
        client_module = ModuleType("nats.aio.client")

        class _FakeNATS:
            async def connect(self, *args, **kwargs):  # pragma: no cover - trivial
                return None

            async def publish(self, *args, **kwargs):  # pragma: no cover - trivial
                return None

            async def close(self):  # pragma: no cover - trivial
                return None

        client_module.Client = _FakeNATS  # type: ignore[attr-defined]
        _install_module("nats", nats_module)
        _install_module("nats.aio", aio_module)
        _install_module("nats.aio.client", client_module)


@pytest.fixture(scope="session")
def load_service_module() -> Callable[[str, str], ModuleType]:
    """Helper to import service modules by file path once per session."""
    cache: Dict[str, ModuleType] = {}
    base = Path(__file__).resolve().parents[1]

    def _load(name: str, relative_path: str) -> ModuleType:
        if name in cache:
            return cache[name]
        module_path = base / relative_path
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {name} from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cache[name] = module
        return module

    return _load
