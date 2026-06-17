from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Callable, Dict

import pytest
import pytest_asyncio
import yaml as _yaml


def _compose_override_tag(loader, node):
    """Tolerate Docker Compose custom merge tags (!override, !reset) under PyYAML.

    docker-compose.hardened.yml uses `!override` (Compose 2.24+ replace-don't-append
    semantics) on list fields. PyYAML's SafeLoader/FullLoader otherwise raise a
    constructor error on these tags, breaking tests that yaml.safe_load the compose
    files (e.g. tests/hardening, tests/smoke). Construct the underlying value so the
    parsed structure matches the post-merge intent.
    """
    if isinstance(node, _yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, _yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)


for _compose_tag in ("!override", "!reset"):
    _yaml.SafeLoader.add_constructor(_compose_tag, _compose_override_tag)
    _yaml.FullLoader.add_constructor(_compose_tag, _compose_override_tag)


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
            is_connected = True

            async def connect(self, *args, **kwargs):  # pragma: no cover - trivial
                return self

            async def publish(self, *args, **kwargs):  # pragma: no cover - trivial
                return None

            async def close(self):  # pragma: no cover - trivial
                return None

        client_module.Client = _FakeNATS  # type: ignore[attr-defined]
        _install_module("nats", nats_module)
        _install_module("nats.aio", aio_module)
        _install_module("nats.aio.client", client_module)


@pytest.fixture(scope="session")
def nats_url() -> str:
    """Return the canonical authenticated NATS URL.

    Prefers the NATS_URL environment variable (useful for CI overrides);
    otherwise falls back to the production-authenticated default used
    throughout PMOVES.AI (``nats://nats:pmoves@nats:4222``).
    """
    return os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")


@pytest.fixture(scope="session")
def nats_available() -> bool:
    """Return True when a NATS broker is reachable on localhost:4222."""
    try:
        with socket.create_connection(("127.0.0.1", 4222), timeout=1.0):
            return True
    except OSError:
        return False


@pytest_asyncio.fixture(scope="function")
async def nats_client(nats_url: str, nats_available: bool):
    """Yield an authenticated NATS client or skip when broker is unavailable.

    The session-wide ``stub_external_modules`` fixture installs a lightweight
    fake ``nats`` module so unit tests can import ``nats`` without the real
    dependency. This fixture bypasses that stub and loads the real
    ``nats-py`` package (installed in CI when a broker is running).
    """
    if not nats_available:
        pytest.skip("NATS not reachable on localhost:4222")
    import importlib

    for mod_name in ("nats", "nats.aio", "nats.aio.client"):
        sys.modules.pop(mod_name, None)
    try:
        nats_real = importlib.import_module("nats")
    except ImportError:
        pytest.skip("nats-py not installed")
    nc = await nats_real.connect(nats_url)
    try:
        yield nc
    finally:
        try:
            await nc.close()
        except Exception:
            pass


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
