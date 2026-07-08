"""Tests for shape-attestation-bridge — shaped→attested→HiRAG gate."""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/shape-attestation-bridge'))
from main import _chit_attest, _build_accepted_packet, _load_secret, _redact_url


def test_chit_attest_adds_signature():
    payload = {"id": "shaped-1", "content": "test"}
    attested = _chit_attest(payload.copy(), "test_pass")
    assert "attestation" in attested
    assert attested["attestation"]["agent"] == "shape-attestation-bridge"
    assert attested["attestation"]["sig"]["alg"] == "HMAC-SHA256"
    assert len(attested["attestation"]["sig"]["hmac"]) == 64

def test_chit_attest_same_payload_same_struct():
    payload = {"id": "shaped-1"}
    a1 = _chit_attest(payload.copy(), "pass")
    a2 = _chit_attest(payload.copy(), "pass")
    # Timestamps differ but structure should match
    assert a1["attestation"]["agent"] == a2["attestation"]["agent"]
    assert a1["attestation"]["sig"]["alg"] == a2["attestation"]["sig"]["alg"]

def test_chit_attest_different_passphrase():
    payload = {"id": "shaped-1"}
    a1 = _chit_attest(payload.copy(), "pass1")
    a2 = _chit_attest(payload.copy(), "pass2")
    assert a1["attestation"]["sig"]["hmac"] != a2["attestation"]["sig"]["hmac"]

def test_build_accepted_packet_has_required_fields():
    attested = {
        "id": "shaped-1",
        "content": {"text": "hello"},
        "lexicon": {"terms": ["hello"]},
        "attestation": {"id": "att-123", "sig": {"hmac": "abc"}},
    }
    accepted = _build_accepted_packet(attested)
    assert accepted["status"] == "accepted"
    assert accepted["hirag_namespace"] == "default"
    assert accepted["content"] == {"text": "hello"}
    assert accepted["attestation"]["id"] == "att-123"

def test_load_secret_env(monkeypatch):
    monkeypatch.setenv("TEST_SAB", "val")
    assert _load_secret("TEST_SAB") == "val"

def test_load_secret_default(monkeypatch):
    monkeypatch.delenv("TEST_SAB", raising=False)
    assert _load_secret("TEST_SAB", "def") == "def"

def test_redact_url_with_creds():
    url = "nats://nats:secret@nats:4222"
    assert "secret" not in _redact_url(url)

def test_redact_url_no_creds():
    url = "nats://nats:4222"
    assert _redact_url(url) == url
