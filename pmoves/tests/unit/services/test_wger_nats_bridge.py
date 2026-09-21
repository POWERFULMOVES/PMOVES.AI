"""Tests for wger-nats-bridge CHIT signing and event building."""
import pathlib
import importlib.util
import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_SVC_DIR = _HERE / "../../../services/wger-nats-bridge"


@pytest.fixture(scope="module")
def main_mod():
    """Load the service main.py as a unique module, deferred to test time."""
    mod_path = _SVC_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("wger_main", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chit_sign_adds_sig_block(main_mod):
    payload = {"id": "test-1", "data": "value"}
    signed = main_mod._chit_sign(payload.copy(), "test_passphrase")
    assert "sig" in signed
    assert signed["sig"]["alg"] == "HMAC-SHA256"
    assert signed["sig"]["kid"] == "wger-nats-bridge"
    assert len(signed["sig"]["hmac"]) == 64

def test_chit_sign_deterministic(main_mod):
    payload = {"id": "test-1", "data": "value"}
    s1 = main_mod._chit_sign(payload.copy(), "pass")
    s2 = main_mod._chit_sign(payload.copy(), "pass")
    assert s1["sig"]["hmac"] == s2["sig"]["hmac"]

def test_chit_sign_different_passphrase_different_sig(main_mod):
    payload = {"id": "test-1"}
    s1 = main_mod._chit_sign(payload.copy(), "pass1")
    s2 = main_mod._chit_sign(payload.copy(), "pass2")
    assert s1["sig"]["hmac"] != s2["sig"]["hmac"]

def test_load_secret_from_env(main_mod, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "env_value")
    assert main_mod._load_secret("TEST_KEY") == "env_value"

def test_load_secret_default(main_mod, monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    monkeypatch.delenv("TEST_KEY_FILE", raising=False)
    assert main_mod._load_secret("TEST_KEY", "default") == "default"

def test_redact_url_with_password(main_mod):
    url = "nats://nats:secret@nats:4222"
    redacted = main_mod._redact_url(url)
    assert "secret" not in redacted
    assert "***" in redacted

def test_redact_url_no_password(main_mod):
    url = "nats://nats:4222"
    assert main_mod._redact_url(url) == url
