"""Unit tests for pmoves/services/spark-shape-worker/main.py.

These tests exercise the pure transformation logic of the SPARK Shape Worker
without requiring a live NATS connection.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

# The shape worker imports nats at module load time. Stub it so tests run
# without requiring the real nats-py package in the test environment.
if "nats" not in sys.modules:
    nats_mod = ModuleType("nats")
    nats_aio_mod = ModuleType("nats.aio")
    nats_aio_client_mod = ModuleType("nats.aio.client")
    nats_aio_client_mod.Client = SimpleNamespace
    nats_aio_mod.client = nats_aio_client_mod
    nats_aio_mod.Client = SimpleNamespace
    nats_mod.aio = nats_aio_mod
    nats_mod.connect = lambda *args, **kwargs: None
    sys.modules["nats"] = nats_mod
    sys.modules["nats.aio"] = nats_aio_mod
    sys.modules["nats.aio.client"] = nats_aio_client_mod

# Load the shape worker module from its service directory (not a package).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_MODULE_PATH = _REPO_ROOT / "pmoves/services/spark-shape-worker/main.py"

def _load_module():
    spec = importlib.util.spec_from_file_location("spark_shape_worker_main", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def shape_mod():
    return _load_module()


@pytest.fixture
def worker(shape_mod):
    return shape_mod.ShapeWorker(
        nats_url="nats://nats:pmoves@nats:4222",
        shape_secret="shape-secret",
        mesh_passphrase="mesh-passphrase",
    )


def test_extract_text_prefers_result(worker):
    assert worker._extract_text({"result": "  hello world  "}) == "hello world"


def test_extract_text_falls_back_to_output(worker):
    assert worker._extract_text({"output": "output text"}) == "output text"


def test_extract_text_falls_back_to_prompt(worker):
    assert worker._extract_text({"prompt": "prompt text"}) == "prompt text"


def test_extract_terms_limits_and_filters(worker):
    text = "one two three four five six seven"
    terms = worker._extract_terms(text, limit=3)
    assert len(terms) == 3
    assert all(len(t) >= 3 for t in terms)
    assert "one" in terms


def test_shape_schema_compliance(worker):
    raw = {
        "request_id": "req-123",
        "model_id": "kimi-k2",
        "node_id": "node-4090",
        "result": "This is a test inference result for PMOVES.",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "duration_ms": 120,
    }
    shaped = worker._shape(raw)
    assert shaped["text"] == raw["result"]
    assert shaped["content_type"] == "gpu.inference.result.v1"
    assert shaped["source_ref"] == "mesh.gpu.inference.result.v1/req-123"
    assert isinstance(shaped["content_id"], str) and shaped["content_id"]
    assert isinstance(shaped["shape_id"], str) and shaped["shape_id"]
    assert isinstance(shaped["anchor_terms"], list)
    assert isinstance(shaped["semantic_weights"], list)
    assert 0 <= shaped["noise_score"] <= 1
    assert 0 <= shaped["semantic_density"] <= 1
    assert "pmoves" in shaped["anchor_terms"]
    assert "spark" in shaped["labels"]
    assert str(raw["model_id"]) in shaped["labels"]
    assert shaped["meta"]["source_model"] == str(raw["model_id"])
    assert shaped["meta"]["source_node"] == str(raw["node_id"])
    assert shaped["meta"]["signature"] != ""


def test_shape_coerces_non_string_model_and_node_ids(worker):
    raw = {"request_id": "r1", "model_id": 42, "node_id": 7, "result": "ok"}
    shaped = worker._shape(raw)
    assert shaped["meta"]["source_model"] == "42"
    assert shaped["meta"]["source_node"] == "7"
    assert "42" in shaped["labels"]


def test_validate_shaped_rejects_missing_field(worker):
    incomplete = {"content_id": "c1"}
    assert worker._validate_shaped(incomplete) is False


def test_validate_shaped_rejects_out_of_range_scores(worker):
    raw = {"request_id": "r1", "result": "ok"}
    shaped = worker._shape(raw)
    shaped["noise_score"] = 2.0
    assert worker._validate_shaped(shaped) is False


def test_handshake_contains_capsule(worker):
    raw = {"request_id": "r1", "result": "ok"}
    shaped = worker._shape(raw)
    handshake = worker._handshake(shaped)
    assert handshake["type"] == "shape-capsule"
    assert handshake["capsule"]["kind"] == "cgp"
    assert handshake["capsule"]["data"] == shaped
    assert handshake["capsule"]["sig"]["hmac"] != ""


def test_handshake_unsigned_when_no_passphrase(shape_mod):
    unsigned_worker = shape_mod.ShapeWorker(
        nats_url="nats://nats:4222",
        shape_secret="",
        mesh_passphrase="",
    )
    shaped = unsigned_worker._shape({"request_id": "r1", "result": "ok"})
    handshake = unsigned_worker._handshake(shaped)
    assert handshake["capsule"]["sig"]["hmac"] == ""
    assert shaped["meta"]["signature"] == ""


def test_attestation_deterministic(worker):
    raw = {"request_id": "r1", "result": "ok"}
    shaped = worker._shape(raw)
    sig1 = worker._attestation(shaped)
    sig2 = worker._attestation(shaped)
    assert sig1 == sig2
    assert len(sig1) == 64  # hex SHA-256
