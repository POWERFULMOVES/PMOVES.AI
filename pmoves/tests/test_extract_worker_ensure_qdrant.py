"""extract-worker `_ensure_qdrant`: create-if-absent without dropping data or 500ing a race.

worker.py imports fastapi / sentence-transformers at module load, which the
unit-test environment does not carry, so the function is lifted out of the
source with `ast` and run against a fake Qdrant client.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

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
