"""CHIT signature-gate tests for the A2UI NATS bridge (consumer edge).

The bridge is the last hop before geometry reaches the frontend: with a key,
tampered packets must never be forwarded; unsigned packets forward in dev
mode and are rejected fail-closed under CHIT_REQUIRE_SIGNATURE.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "bridge.py"
SPEC = importlib.util.spec_from_file_location("pmoves.services.a2ui_nats_bridge.bridge", MODULE_PATH)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
sys.modules["pmoves.services.a2ui_nats_bridge.bridge"] = bridge
SPEC.loader.exec_module(bridge)

from pmoves.tools.chit_security import sign_cgp  # noqa: E402

PASSPHRASE = "a2ui-test-key"


@pytest.fixture(autouse=True)
def clean_chit_env(monkeypatch):
    for var in ("CHIT_SIGNING_KEY", "CHIT_PASSPHRASE", "CHIT_REQUIRE_SIGNATURE"):
        monkeypatch.delenv(var, raising=False)


class TestSignatureGateWithKey:
    def test_valid_signature_forwarded(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        signed = sign_cgp({"spec": "chit.cgp.v0.2", "n": 1}, passphrase=PASSPHRASE)
        assert bridge.cgp_passes_signature_gate(signed) == (True, "")

    def test_tampered_always_rejected(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        tampered = sign_cgp({"spec": "chit.cgp.v0.2", "n": 1}, passphrase=PASSPHRASE)
        tampered["n"] = 2
        passes, reason = bridge.cgp_passes_signature_gate(tampered)
        assert passes is False
        assert reason == "invalid"

    def test_unsigned_forwarded_in_dev_mode(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        passes, reason = bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"})
        assert passes is True
        assert reason == "unsigned"

    def test_unsigned_rejected_fail_closed(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"}) == (False, "unsigned")


class TestSignatureGateWithoutKey:
    def test_dev_mode_passthrough(self):
        passes, _ = bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"})
        assert passes is True

    def test_fail_closed_rejects_unverifiable(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "1")
        assert bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"}) == (False, "unverifiable")


class TestSignatureGateWithFile:
    def test_valid_signature_forwarded_from_file(self, monkeypatch, tmp_path):
        secret_file = tmp_path / "chit-passphrase"
        secret_file.write_text(PASSPHRASE)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.setenv("CHIT_PASSPHRASE_FILE", str(secret_file))
        signed = sign_cgp({"spec": "chit.cgp.v0.2", "n": 1}, passphrase=PASSPHRASE)
        assert bridge.cgp_passes_signature_gate(signed) == (True, "")


class TestSignatureGateNonDict:
    def test_non_dict_payload_passes_in_dev_mode(self):
        assert bridge.cgp_passes_signature_gate([1, 2, 3]) == (True, "non-dict")
        assert bridge.cgp_passes_signature_gate("raw") == (True, "non-dict")

    def test_non_dict_payload_rejected_fail_closed(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert bridge.cgp_passes_signature_gate([1, 2, 3]) == (False, "non-dict")
