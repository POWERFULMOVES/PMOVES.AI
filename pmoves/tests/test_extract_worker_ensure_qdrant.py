"""extract-worker `_ensure_qdrant`: create-if-absent without dropping data or 500ing a race.

Also pins the QDRANT_API_KEY lookup order and the /ingest pre-embed reachability
gate (an unreachable Qdrant is a 503 and never spends an embedding).

worker.py imports fastapi / sentence-transformers at module load, which the
unit-test environment does not carry, so each function is lifted out of the
source with `ast` and run against fakes.
"""
from __future__ import annotations

import ast
import json
import os
import uuid
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

import pytest

WORKER = Path(__file__).resolve().parents[1] / "services" / "extract-worker" / "worker.py"


class _HTTPException(Exception):
    def __init__(self, status_code: int, detail: str = "") -> None:
        super().__init__(detail)
        self.status_code = status_code


class _Conflict(Exception):
    """Stands in for qdrant_client's UnexpectedResponse(409)."""


def _ensure_qdrant():
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_ensure_qdrant")
    ns = {"COLL": "chunks", "os": os, "HTTPException": _HTTPException,
          "VectorParams": lambda **kw: kw, "Distance": type("D", (), {"COSINE": "Cosine"}),
          "QdrantClient": object}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(WORKER), "exec"), ns)
    return ns["_ensure_qdrant"]


class _Client:
    """exists: successive collection_exists answers; create_error: raised by create."""

    def __init__(self, exists, create_error=None, dim=384):
        self.exists = list(exists)
        self.create_error = create_error
        self.dim = dim
        self.calls = []

    def collection_exists(self, name):
        self.calls.append("exists")
        answer = self.exists.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def create_collection(self, name, vectors_config):
        self.calls.append("create")
        if self.create_error:
            raise self.create_error

    def get_collection(self, name):
        self.calls.append("get")
        vectors = type("V", (), {"size": self.dim})
        params = type("P", (), {"vectors": vectors})
        return type("I", (), {"config": type("C", (), {"params": params})})

    def recreate_collection(self, *a, **kw):  # pragma: no cover - must never run here
        self.calls.append("RECREATE")


def test_absent_collection_is_created():
    c = _Client([False])
    _ensure_qdrant()(c, 384)
    assert c.calls == ["exists", "create"]


def test_losing_the_create_race_is_not_an_error():
    c = _Client([False, True], create_error=_Conflict("409 already exists"))
    _ensure_qdrant()(c, 384)
    assert c.calls == ["exists", "create", "exists", "get"]  # validated like any existing one


def test_race_winner_with_the_wrong_dimension_is_still_caught():
    c = _Client([False, True], create_error=_Conflict("409"), dim=768)
    with pytest.raises(_HTTPException) as e:
        _ensure_qdrant()(c, 384)
    assert e.value.status_code == 500 and "dim=768" in str(e.value)
    assert "RECREATE" not in c.calls


def test_a_create_failure_that_is_not_a_race_propagates():
    c = _Client([False, False], create_error=RuntimeError("500 from qdrant"))
    with pytest.raises(RuntimeError, match="500 from qdrant"):
        _ensure_qdrant()(c, 384)


def test_qdrant_down_during_the_recheck_propagates():
    c = _Client([False, ConnectionError("qdrant unreachable")], create_error=_Conflict("409"))
    with pytest.raises(ConnectionError):
        _ensure_qdrant()(c, 384)


def test_transient_error_never_drops_the_collection():
    c = _Client([TimeoutError("timed out")])
    with pytest.raises(TimeoutError):
        _ensure_qdrant()(c, 384)
    assert "RECREATE" not in c.calls and "create" not in c.calls


# ── QDRANT_API_KEY lookup order (worker.py module-level assignment) ─────────


def _api_key_under(monkeypatch, env):
    """Evaluate worker.py's QDRANT_API_KEY assignment against ``env`` only."""
    for name in ("QDRANT_API_KEY", "QDRANT__API_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    assign = next(
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "QDRANT_API_KEY" for t in n.targets)
    )
    ns = {"os": os}
    exec(compile(ast.Module(body=[assign], type_ignores=[]), str(WORKER), "exec"), ns)
    return ns["QDRANT_API_KEY"]


def test_client_side_key_name_wins_over_the_gateway_name(monkeypatch):
    assert _api_key_under(monkeypatch, {"QDRANT_API_KEY": "client", "QDRANT__API_KEY": "gateway"}) == "client"


def test_gateway_key_name_is_used_when_the_client_name_is_unset(monkeypatch):
    assert _api_key_under(monkeypatch, {"QDRANT__API_KEY": "gateway"}) == "gateway"


def test_an_empty_client_key_falls_through_to_the_gateway_name(monkeypatch):
    # compose renders QDRANT_API_KEY=${QDRANT__API_KEY:-}, so "" must not mask a real key.
    assert _api_key_under(monkeypatch, {"QDRANT_API_KEY": "", "QDRANT__API_KEY": "gateway"}) == "gateway"


def test_no_key_at_all_gives_none_not_empty_string(monkeypatch):
    assert _api_key_under(monkeypatch, {}) is None
    assert _api_key_under(monkeypatch, {"QDRANT_API_KEY": "", "QDRANT__API_KEY": ""}) is None


# ── /ingest pre-embed reachability gate ─────────────────────────────────────


class _Vecs:
    """Minimal stand-in for the ndarray _embed returns (shape + row.tolist())."""

    def __init__(self, n, dim=384):
        self.shape = (n, dim)
        self._rows = [mock.Mock(tolist=mock.Mock(return_value=[0.0] * dim)) for _ in range(n)]

    def __iter__(self):
        return iter(self._rows)


def _ingest(qdrant_client, embed):
    """Lift ``ingest`` out of worker.py, undecorated, with its collaborators faked."""
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "ingest")
    fn.decorator_list = []
    metric = mock.MagicMock()
    metric.time.return_value = nullcontext()
    ns = {
        "Request": object, "Dict": dict, "Any": object, "List": list, "Body": lambda *a, **kw: None,
        "HTTPException": _HTTPException, "QdrantClient": mock.Mock(return_value=qdrant_client),
        "QDRANT_URL": "http://qdrant.invalid:6333", "QDRANT_API_KEY": "k", "COLL": "chunks",
        "_embed": embed, "_ensure_qdrant": mock.Mock(), "_meili": mock.Mock(),
        "PointStruct": lambda **kw: kw, "uuid": uuid, "json": json,
        "CGP_PUBLISH_ENABLED": False, "logger": mock.Mock(), "requests": mock.Mock(), "SUPA": "",
        "http_request_duration": metric, "http_requests_total": mock.MagicMock(),
        "qdrant_operations_total": mock.MagicMock(), "embeddings_processed_total": mock.MagicMock(),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(WORKER), "exec"), ns)
    return ns["ingest"]


def _request():
    return type("R", (), {"headers": {}})()


def test_unreachable_qdrant_is_a_503_and_never_embeds():
    qc = mock.Mock()
    qc.get_collections.side_effect = ConnectionError("401 / refused")
    embed = mock.Mock()
    with pytest.raises(_HTTPException) as e:
        _ingest(qc, embed)(_request(), {"chunks": [{"chunk_id": "a", "text": "hello"}]})
    assert e.value.status_code == 503
    embed.assert_not_called()
    qc.upsert.assert_not_called()


def test_reachable_qdrant_embeds_and_upserts():
    qc = mock.Mock()
    embed = mock.Mock(return_value=_Vecs(2))
    chunks = [{"chunk_id": "a", "text": "hello"}, {"chunk_id": "b", "text": "world"}]
    result = _ingest(qc, embed)(_request(), {"chunks": chunks})
    qc.get_collections.assert_called_once()
    embed.assert_called_once_with(["hello", "world"])
    qc.upsert.assert_called_once()
    assert result["ok"] is True and result["chunks"] == 2
