"""Tests for decoded_consumer — geometry.packet.decoded.v1 subscriber."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from decoded_consumer import _validate_decoded_packet, _redact_url, _resolve_nats_url


def test_validate_valid_packet():
    payload = {"source_spec": "cgp_v0.2", "super_nodes": [], "control_plane": {}}
    assert _validate_decoded_packet(payload) is True

def test_validate_missing_source_spec():
    payload = {"super_nodes": [], "control_plane": {}}
    assert _validate_decoded_packet(payload) is False

def test_validate_missing_super_nodes():
    payload = {"source_spec": "cgp_v0.2", "control_plane": {}}
    assert _validate_decoded_packet(payload) is False

def test_validate_missing_control_plane():
    payload = {"source_spec": "cgp_v0.2", "super_nodes": []}
    assert _validate_decoded_packet(payload) is False

def test_redact_url_with_password():
    url = "nats://nats:secret123@nats:4222"
    redacted = _redact_url(url)
    assert "secret123" not in redacted
    assert "***" in redacted

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

def test_resolve_nats_url_from_env(monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://test:4222")
    assert _resolve_nats_url() == "nats://test:4222"

def test_resolve_nats_url_from_components(monkeypatch):
    monkeypatch.delenv("NATS_URL", raising=False)
    monkeypatch.setenv("NATS_HOST", "myhost")
    monkeypatch.setenv("NATS_PORT", "4223")
    monkeypatch.setenv("NATS_USER", "u")
    monkeypatch.setenv("NATS_PASSWORD", "p")
    assert _resolve_nats_url() == "nats://u:p@myhost:4223"


def test_resolve_nats_url_default(monkeypatch):
    monkeypatch.delenv("NATS_URL", raising=False)
    monkeypatch.delenv("NATS_HOST", raising=False)
    monkeypatch.delenv("NATS_PORT", raising=False)
    monkeypatch.delenv("NATS_USER", raising=False)
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    assert _resolve_nats_url() == "nats://nats:4222"
