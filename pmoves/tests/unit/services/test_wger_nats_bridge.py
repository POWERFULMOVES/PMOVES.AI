"""Tests for wger-nats-bridge CHIT signing and event building."""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/wger-nats-bridge'))


def test_chit_sign_adds_sig_block():
    from main import _chit_sign
    payload = {"id": "test-1", "data": "value"}
    signed = _chit_sign(payload.copy(), "test_passphrase")
    assert "sig" in signed
    assert signed["sig"]["alg"] == "HMAC-SHA256"
    assert signed["sig"]["kid"] == "wger-nats-bridge"
    assert len(signed["sig"]["hmac"]) == 64

def test_chit_sign_deterministic():
    from main import _chit_sign
    payload = {"id": "test-1", "data": "value"}
    s1 = _chit_sign(payload.copy(), "pass")
    s2 = _chit_sign(payload.copy(), "pass")
    assert s1["sig"]["hmac"] == s2["sig"]["hmac"]

def test_chit_sign_different_passphrase_different_sig():
    from main import _chit_sign
    payload = {"id": "test-1"}
    s1 = _chit_sign(payload.copy(), "pass1")
    s2 = _chit_sign(payload.copy(), "pass2")
    assert s1["sig"]["hmac"] != s2["sig"]["hmac"]

def test_load_secret_from_env(monkeypatch):
    from main import _load_secret
    monkeypatch.setenv("TEST_KEY", "env_value")
    assert _load_secret("TEST_KEY") == "env_value"

def test_load_secret_default(monkeypatch):
    from main import _load_secret
    monkeypatch.delenv("TEST_KEY", raising=False)
    monkeypatch.delenv("TEST_KEY_FILE", raising=False)
    assert _load_secret("TEST_KEY", "default") == "default"

def test_redact_url_with_password():
    from main import _redact_url
    url = "nats://nats:secret@nats:4222"
    redacted = _redact_url(url)
    assert "secret" not in redacted
    assert "***" in redacted

def test_redact_url_no_password():
    from main import _redact_url
    url = "nats://nats:4222"
    assert _redact_url(url) == url
