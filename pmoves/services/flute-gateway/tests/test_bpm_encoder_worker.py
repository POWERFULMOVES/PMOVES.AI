"""Tests for bpm_encoder_worker — mesh.gpu.inference.result.v1 → bpm.encoded.v1."""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from bpm_encoder_worker import _extract_text, _detect_boundaries, _encode_prosodic_profile, _build_cgp_packet, _redact_url


def test_extract_text_from_response():
    payload = {"result": {"response": "Hello world. How are you?"}}
    assert _extract_text(payload) == "Hello world. How are you?"

def test_extract_text_from_text_field():
    payload = {"result": {"text": "Some text here."}}
    assert _extract_text(payload) == "Some text here."

def test_extract_text_from_output():
    payload = {"result": {"output": "Output text."}}
    assert _extract_text(payload) == "Output text."

def test_extract_text_fallback():
    payload = {"result": "Direct string result."}
    assert _extract_text(payload) == "Direct string result."

def test_extract_text_empty():
    # An empty result dict has no response/text/output field, so extraction
    # yields empty text (NOT the literal "{}"): _detect_boundaries("") then
    # produces a single NONE boundary. Feeding "{}" downstream would encode
    # braces as if they were speech.
    payload = {"result": {}}
    assert _extract_text(payload) == ""

def test_detect_boundaries_sentences():
    text = "Hello world. How are you? I am fine!"
    boundaries = _detect_boundaries(text)
    assert len(boundaries) >= 2
    assert any(b["type"] == "SENTENCE" for b in boundaries)

def test_detect_boundaries_empty_text():
    boundaries = _detect_boundaries("")
    assert len(boundaries) == 1
    assert boundaries[0]["type"] == "NONE"

def test_encode_prosodic_profile_chunks():
    text = "Hello world. How are you?"
    profile = _encode_prosodic_profile(text)
    assert profile["total_chunks"] >= 1
    assert "avg_bpm" in profile
    assert "chunks" in profile

def test_encode_prosodic_profile_empty():
    profile = _encode_prosodic_profile("")
    assert profile["total_chunks"] == 0 or profile["total_chunks"] == 1

def test_build_cgp_packet_structure():
    profile = {"chunks": [{"text": "Hi", "boundary": "SENTENCE", "bpm": 60}], "avg_bpm": 60.0, "total_chunks": 1}
    source = {"model": "qwen2.5-coder:32b"}
    packet = _build_cgp_packet(profile, source)
    assert packet["spec"] == "chit.cgp.v0.2"
    assert "id" in packet
    assert "timestamp" in packet
    assert packet["source"]["agent"] == "bpm-encoder-worker"
    assert packet["source"]["inference_model"] == "qwen2.5-coder:32b"
    assert len(packet["super_nodes"]) == 1

def test_build_cgp_packet_with_attestation(monkeypatch):
    monkeypatch.setenv("BPM_ENCODER_SECRET", "test_secret")
    profile = {"chunks": [], "avg_bpm": 150.0, "total_chunks": 0}
    packet = _build_cgp_packet(profile, {})
    assert "attestation" in packet
    assert packet["attestation"]["algorithm"] == "HMAC-SHA256"


def test_build_cgp_packet_no_attestation(monkeypatch):
    monkeypatch.delenv("BPM_ENCODER_SECRET", raising=False)
    profile = {"chunks": [], "avg_bpm": 150.0, "total_chunks": 0}
    packet = _build_cgp_packet(profile, {})
    assert "attestation" not in packet

def test_redact_url_with_password():
    url = "nats://nats:secret@nats:4222"
    redacted = _redact_url(url)
    assert "secret" not in redacted

def test_redact_url_no_password():
    url = "nats://nats:4222"
    assert _redact_url(url) == url

def test_redact_url_token_only():
    # Token auth (nats://TOKEN@host) puts the secret in `username` with no
    # password — it must still be redacted.
    url = "nats://s3cr3t-token@nats:4222"
    redacted = _redact_url(url)
    assert "s3cr3t-token" not in redacted
    assert "nats:4222" in redacted

def test_redact_url_user_and_password():
    url = "nats://user:p4ss@nats:4222"
    redacted = _redact_url(url)
    assert "p4ss" not in redacted
    assert "user" not in redacted

def test_cgp_packet_validates_against_schema():
    # The emitted packet must satisfy contracts/schemas/geometry/cgp.v2.schema.json.
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "contracts", "schemas", "geometry", "cgp.v2.schema.json",
    )
    with open(schema_path) as fh:
        schema = json.load(fh)
    profile = _encode_prosodic_profile("Hello world. How are you today?")
    packet = _build_cgp_packet(profile, {"result": {"text": "Hello world."}})
    jsonschema.validate(packet, schema)
