"""Tests for shape-attestation-bridge — shaped→attested→HiRAG gate."""
import pathlib
import importlib.util
import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_SVC_DIR = _HERE / "../../../services/shape-attestation-bridge"


@pytest.fixture(scope="module")
def main_mod():
    """Load the service main.py as a unique module, deferred to test time."""
    mod_path = _SVC_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("sab_main", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chit_attest_adds_signature(main_mod):
    payload = {"id": "shaped-1", "content": "test"}
    attested = main_mod._chit_attest(payload.copy(), "test_pass")
    assert "attestation" in attested
    assert attested["attestation"]["agent"] == "shape-attestation-bridge"
    assert attested["attestation"]["sig"]["alg"] == "HMAC-SHA256"
    assert len(attested["attestation"]["sig"]["hmac"]) == 64

def test_chit_attest_same_payload_same_struct(main_mod):
    payload = {"id": "shaped-1"}
    a1 = main_mod._chit_attest(payload.copy(), "pass")
    a2 = main_mod._chit_attest(payload.copy(), "pass")
    assert a1["attestation"]["agent"] == a2["attestation"]["agent"]
    assert a1["attestation"]["sig"]["alg"] == a2["attestation"]["sig"]["alg"]

def test_chit_attest_different_passphrase(main_mod):
    payload = {"id": "shaped-1"}
    a1 = main_mod._chit_attest(payload.copy(), "pass1")
    a2 = main_mod._chit_attest(payload.copy(), "pass2")
    assert a1["attestation"]["sig"]["hmac"] != a2["attestation"]["sig"]["hmac"]

def test_build_accepted_packet_has_required_fields(main_mod):
    attested = {
        "id": "shaped-1",
        "content": {"text": "hello"},
        "lexicon": {"terms": ["hello"]},
        "attestation": {"id": "att-123", "sig": {"hmac": "abc"}},
    }
    accepted = main_mod._build_accepted_packet(attested)
    assert accepted["status"] == "accepted"
    assert accepted["hirag_namespace"] == "default"
    assert accepted["content"] == {"text": "hello"}
    assert accepted["attestation"]["id"] == "att-123"

def test_load_secret_env(main_mod, monkeypatch):
    monkeypatch.setenv("TEST_SAB", "val")
    assert main_mod._load_secret("TEST_SAB") == "val"

def test_load_secret_default(main_mod, monkeypatch):
    monkeypatch.delenv("TEST_SAB", raising=False)
    assert main_mod._load_secret("TEST_SAB", "def") == "def"

def test_redact_url_with_creds(main_mod):
    url = "nats://nats:secret@nats:4222"
    assert "secret" not in main_mod._redact_url(url)

def test_redact_url_no_creds(main_mod):
    url = "nats://nats:4222"
    assert main_mod._redact_url(url) == url
