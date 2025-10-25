import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import numpy as np
from fastapi import HTTPException

# Disable Tailscale IP restrictions for all tests in this file
os.environ["TAILSCALE_ONLY"] = "false"
os.environ["TAILSCALE_ADMIN_ONLY"] = "false"

# The following imports are structured to match the existing test file's approach
# of stubbing modules to isolate the gateway logic for testing.
import importlib.util
import sys
import types
from pathlib import Path

@pytest.fixture(scope="module")
def gateway_module():
    # This fixture reuses the stubbing logic from the existing `test_trusted_proxies.py`
    # to ensure a consistent and isolated testing environment. It mocks out heavy
    # dependencies like Qdrant, SentenceTransformers, Neo4j, etc.
    stubs: dict[str, types.ModuleType | None] = {}
    root_path = Path(__file__).resolve().parents[4]
    added_root = False
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
        added_root = True

    def _install_stub(name: str, module: types.ModuleType, registry):
        registry[name] = sys.modules.get(name)
        sys.modules[name] = module

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
        def __init__(self, *args, **kwargs): pass
    class _FieldCondition:
        def __init__(self, *args, **kwargs): pass
    class _MatchValue:
        def __init__(self, *args, **kwargs): pass
    qdrant_http_models.Filter = _Filter
    qdrant_http_models.FieldCondition = _FieldCondition
    qdrant_http_models.MatchValue = _MatchValue
    qdrant_http.models = qdrant_http_models
    qdrant_module.http = qdrant_http
    _install_stub("qdrant_client.http", qdrant_http, stubs)
    _install_stub("qdrant_client.http.models", qdrant_http_models, stubs)

    # Sentence transformer stub
    st_module = types.ModuleType("sentence_transformers")
    class _SentenceTransformer:
        def __init__(self, *args, **kwargs): pass
        def encode(self, texts, normalize_embeddings=True): return np.array([[0.1, 0.2, 0.3]])
    st_module.SentenceTransformer = _SentenceTransformer
    _install_stub("sentence_transformers", st_module, stubs)

    # CrossEncoder stub
    class _CrossEncoder:
        def __init__(self, *args, **kwargs): pass
        def predict(self, pairs): return [0.9 for _ in pairs]
    st_module.CrossEncoder = _CrossEncoder


    # Rapidfuzz stub
    rapidfuzz_module = types.ModuleType("rapidfuzz")
    rapidfuzz_module.fuzz = types.SimpleNamespace(token_set_ratio=lambda q, t: 90.0)
    _install_stub("rapidfuzz", rapidfuzz_module, stubs)

    # Neo4j stub
    neo4j_module = types.ModuleType("neo4j")
    class _GraphDatabase:
        @staticmethod
        def driver(*args, **kwargs): return None
    neo4j_module.GraphDatabase = _GraphDatabase
    _install_stub("neo4j", neo4j_module, stubs)

    # Common services stubs
    common_module = types.ModuleType("services.common.geometry_params")
    common_module.get_decoder_pack = lambda: None
    _install_stub("services.common.geometry_params", common_module, stubs)

    hrm_module = types.ModuleType("services.common.hrm_sidecar")
    class _HrmDecoderController:
        def __init__(self, *args, **kwargs): pass
    hrm_module.HrmDecoderController = _HrmDecoderController
    _install_stub("services.common.hrm_sidecar", hrm_module, stubs)


    # Load the actual gateway module
    module_path = root_path / "pmoves/services/hi-rag-gateway/gateway.py"
    spec = importlib.util.spec_from_file_location("gateway", module_path)
    gateway = importlib.util.module_from_spec(spec)
    sys.modules["gateway"] = gateway
    spec.loader.exec_module(gateway)

    try:
        yield gateway
    finally:
        # Teardown: remove stubs and modules
        sys.modules.pop("gateway", None)
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


@pytest.fixture
def client(gateway_module):
    # Fixture to create a TestClient for the FastAPI app, ensuring tests run in a
    # clean, isolated environment.
    with patch.dict(os.environ, {"TAILSCALE_ONLY": "false"}):
        yield TestClient(gateway_module.app)


def test_query_endpoint_success(client, gateway_module):
    """
    Tests a successful call to the /hirag/query endpoint.
    It mocks the underlying `run_query` function to isolate the test to the HTTP layer,
    verifying that a valid request receives a 200 OK response and the expected JSON structure.
    """
    with patch.object(gateway_module, 'run_query', return_value=[{"text": "result1"}]) as mock_run_query:
        response = client.post("/hirag/query", json={"query": "test", "namespace": "default", "k": 5})
        assert response.status_code == 200
        assert response.json() == {"query": "test", "results": [{"text": "result1"}]}
        mock_run_query.assert_called_once()


def test_query_endpoint_invalid_k(client):
    """
    Tests the /hirag/query endpoint with an invalid value for 'k' (negative integer).
    This test ensures that the endpoint correctly validates input parameters and returns a
    400 Bad Request status code with a descriptive error message, preventing invalid
    requests from being processed.
    """
    response = client.post("/hirag/query", json={"query": "test", "k": -1})
    assert response.status_code == 400
    assert "Invalid payload" in response.json()["detail"]


def test_query_endpoint_qdrant_error(client, gateway_module):
    """
    Tests the error handling of the /hirag/query endpoint when the Qdrant search call fails.
    By mocking `run_query` to raise an exception, this test verifies that the endpoint
    gracefully catches the error and returns a 503 Service Unavailable status code,
    ensuring the gateway remains stable even if its dependencies fail.
    """
    with patch.object(gateway_module, 'run_query', side_effect=HTTPException(status_code=503, detail="Qdrant search error")):
        response = client.post("/hirag/query", json={"query": "test"})
        assert response.status_code == 503
        assert "Qdrant search error" in response.json()["detail"]

def test_run_query_logic(gateway_module):
    """
    Tests the core logic of the `run_query` function with dependencies mocked.
    This test simulates a Qdrant search result and verifies that the function correctly
    processes the results, calculates a hybrid score, and returns the data in the
    expected format. This confirms the fundamental query processing path works as intended.
    """
    mock_point = MagicMock()
    mock_point.score = 0.8
    mock_point.payload = {"text": "some text", "chunk_id": "c1"}

    with patch.object(gateway_module.qdrant, 'search', return_value=[mock_point]) as mock_search:
        results = gateway_module.run_query("test query", "default", k=1)
        assert len(results) == 1
        assert results[0]["text"] == "some text"
        assert "score" in results[0]
        # With fuzz.token_set_ratio mocked to 90.0 -> 0.9, and alpha=0.7:
        # expected_score = 0.7 * 0.8 (vec) + 0.3 * 0.9 (lex) = 0.56 + 0.27 = 0.83
        assert abs(results[0]["score"] - 0.83) < 1e-9
        mock_search.assert_called_once()

def test_run_query_with_rerank(gateway_module, monkeypatch):
    """
    Tests the `run_query` function's reranking logic.
    This test enables reranking via a monkeypatch, simulates Qdrant results, and
    verifies that the CrossEncoder is called and that the results are resorted
    based on the rerank scores. This ensures the optional reranking path is functional.
    """
    monkeypatch.setattr(gateway_module, "RERANK_ENABLE", True)

    points = []
    for i in range(3):
        mock_point = MagicMock()
        mock_point.score = 0.8 - i * 0.1 # 0.8, 0.7, 0.6
        mock_point.payload = {"text": f"text {i}", "chunk_id": f"c{i}"}
        points.append(mock_point)

    with patch.object(gateway_module.qdrant, 'search', return_value=points):
        with patch.object(gateway_module, '_get_cross_encoder') as mock_get_ce:
            mock_encoder = MagicMock()
            # Reranker returns scores in reverse order of initial scores
            mock_encoder.predict.return_value = [0.1, 0.5, 0.9]
            mock_get_ce.return_value = mock_encoder

            results = gateway_module.run_query("test query", "default", k=3)

            assert len(results) == 3
            # The last result from Qdrant should now be first due to reranking
            assert results[0]["text"] == "text 2"
            assert results[0]["rerank_score"] == 0.9
            mock_encoder.predict.assert_called_once()

def test_admin_stats_endpoint(client):
    """
    Tests the /hirag/admin/stats endpoint for basic functionality.
    This test ensures the admin stats endpoint is accessible and returns a 200 OK
    response with the expected JSON structure, confirming that monitoring and
    administrative functions are operational.
    """
    response = client.get("/hirag/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "entity_cache" in data
    assert "warm_dictionary" in data
    assert "config" in data

def test_admin_refresh_endpoint(client, gateway_module):
    """
    Tests the /hirag/admin/refresh endpoint.
    This test calls the refresh endpoint and verifies it returns a 200 OK response.
    It also mocks the underlying `refresh_warm_dictionary` function to ensure it is
    called, confirming the endpoint correctly triggers the dictionary refresh logic.
    """
    with patch.object(gateway_module, 'refresh_warm_dictionary') as mock_refresh:
        response = client.post("/hirag/admin/refresh")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_refresh.assert_called_once()

def test_admin_cache_clear_endpoint(client, gateway_module):
    """
    Tests the /hirag/admin/cache/clear endpoint.
    This test ensures the cache clear endpoint is functional, returns a 200 OK response,
    and correctly clears the internal cache dictionaries, which is crucial for
    administrative control over the gateway's state.
    """
    # Pre-populate the cache to verify it gets cleared
    gateway_module._cache_entities['test'] = (123, 'value')
    gateway_module._cache_order.append('test')

    response = client.post("/hirag/admin/cache/clear")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(gateway_module._cache_entities) == 0
    assert len(gateway_module._cache_order) == 0
