"""Unit tests for graph-linker's fail-closed CHIT signer.

The previous signer failed OPEN: no key returned the dict unsigned and
`verify` returned True, and the tests here enshrined that. These replace them.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chit_signer as cs  # noqa: E402
from pmoves.tools.chit_security import SignatureStatus  # noqa: E402


def _failures(reason: str) -> float:
    return cs.CHIT_SIGN_FAILURES.labels(reason=reason)._value.get()


PARAMS = {"evt_id": "evt-001", "uri": "s3://bucket/obj.png", "source": "comfyui-agent"}


class TestSignWrite:
    def test_adds_three_flat_fields_and_keeps_params(self):
        out = cs.sign_write(dict(PARAMS))
        for field in cs.CHIT_FIELDS:
            assert isinstance(out[field], str) and out[field]
        assert {k: out[k] for k in PARAMS} == PARAMS
        # No nested map: Neo4j property values cannot be maps.
        assert "sig" not in out

    def test_roundtrip_verifies_unpinned(self):
        # Deployment-wide key: attribution, not per-writer authentication.
        result = cs.verify_write(cs.sign_write(dict(PARAMS)))
        assert result.status is SignatureStatus.OK_UNPINNED

    def test_tampered_param_is_mismatch(self):
        signed = cs.sign_write(dict(PARAMS))
        signed["uri"] = "s3://bucket/other.png"
        assert cs.verify_write(signed).status is SignatureStatus.MISMATCH

    def test_tampered_timestamp_is_mismatch(self):
        signed = cs.sign_write(dict(PARAMS))
        signed["chit_signed_at"] = "1970-01-01T00:00:00+00:00"
        assert cs.verify_write(signed).status is SignatureStatus.MISMATCH

    def test_unsigned_is_no_signature_not_ok(self):
        assert cs.verify_write(dict(PARAMS)).status is SignatureStatus.NO_SIGNATURE

    def test_kid_follows_signing_key_id(self, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY_ID", "b850-claude")
        assert cs.sign_write(dict(PARAMS))["chit_kid"] == "b850-claude"


class TestFailClosed:
    def test_no_key_raises_and_counts(self, clear_chit_key):
        before = _failures("no_key")
        with pytest.raises(cs.ChitSigningError) as exc:
            cs.sign_write(dict(PARAMS))
        assert exc.value.reason == "no_key"
        assert _failures("no_key") == before + 1

    def test_error_never_carries_key_material(self, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "secret-material-xyz")
        with pytest.raises(cs.ChitSigningError) as exc:
            cs.sign_write({"bad": object()})
        assert "secret-material-xyz" not in str(exc.value)

    def test_unserializable_params_raise_and_count(self):
        before = _failures("unserializable")
        with pytest.raises(cs.ChitSigningError) as exc:
            cs.sign_write({"bad": object()})
        assert exc.value.reason == "unserializable"
        assert _failures("unserializable") == before + 1

    def test_signing_status(self, clear_chit_key, monkeypatch):
        assert cs.signing_status() == (False, "no_key")
        monkeypatch.setenv("CHIT_SIGNING_KEY", "k")
        assert cs.signing_status() == (True, "ok")
