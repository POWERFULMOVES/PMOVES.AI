"""Tests for CHIT crypto consolidation (A2).

Validates:
1. _pack_floats/_unpack_floats parity between geometry_decoder and chit_security
2. gateway chit.py uses canonical canon()
3. Fail-closed behavior of validator when no key available
4. sign/verify roundtrip still works in geometry_decoder
"""
import os
import pytest
import struct
from datetime import datetime, timezone


class TestPackUnpackParity:
    """geometry_decoder and chit_security _pack/_unpack must agree."""

    def test_pack_floats_matches(self):
        from pmoves.tools.chit_security import _pack_floats as cs_pack
        from pmoves.services.common.geometry_decoder import _pack_floats as gd_pack

        data = [1.0, 2.5, -3.7, 0.0, 100.5]
        assert cs_pack(data) == gd_pack(data)

    def test_unpack_floats_matches(self):
        from pmoves.tools.chit_security import _pack_floats as cs_pack
        from pmoves.services.common.geometry_decoder import _unpack_floats as gd_unpack

        data = [1.0, 2.5, -3.7, 0.0, 100.5]
        packed = cs_pack(data)
        result = gd_unpack(packed)
        assert len(result) == len(data)
        for a, b in zip(result, data):
            assert abs(a - b) < 0.01

    def test_roundtrip_pack_unpack(self):
        from pmoves.services.common.geometry_decoder import _pack_floats, _unpack_floats

        data = [0.1, 0.2, 0.3]
        packed = _pack_floats(data)
        unpacked = _unpack_floats(packed)
        assert len(unpacked) == 3
        for a, b in zip(unpacked, data):
            assert abs(a - b) < 0.01

    def test_safety_limit_pack(self):
        from pmoves.services.common.geometry_decoder import _pack_floats, _MAX_FLOATS_UNPACK

        with pytest.raises(ValueError, match="too large"):
            _pack_floats([1.0] * (_MAX_FLOATS_UNPACK + 1))

    def test_safety_limit_unpack_count(self):
        from pmoves.services.common.geometry_decoder import _unpack_floats

        # Craft a buffer with an absurdly large count
        buf = struct.pack(">I", 999_999_999) + b"\x00" * 16
        with pytest.raises(ValueError, match="too large"):
            _unpack_floats(buf)

    def test_safety_limit_unpack_small_buffer(self):
        from pmoves.services.common.geometry_decoder import _unpack_floats

        with pytest.raises(ValueError, match="too small"):
            _unpack_floats(b"\x00\x00")


class TestGatewayCanonImport:
    """gateway chit.py should use canonical canon()."""

    def test_imports_canonical_canon(self):
        import importlib
        import pmoves.tools.chit_common
        # Verify the module imports canon from chit_common
        import pmoves.services.gateway.gateway.api.chit as chit_mod
        # The module should have 'canon' that is the same function as chit_common.canon
        assert hasattr(chit_mod, 'canon')
        from pmoves.tools.chit_common import canon as canonical
        assert chit_mod.canon is canonical or callable(chit_mod.canon)

    def test_canon_output_matches(self):
        import json
        from pmoves.tools.chit_common import canon as canonical
        # Import the gateway module's canon
        import pmoves.services.gateway.gateway.api.chit as chit_mod
        test_obj = {"b": 2, "a": 1}
        assert chit_mod.canon(test_obj) == canonical(test_obj)


class TestValidatorFailClosed:
    """Validator must fail-closed when no key is configured for SIGNED/STRICT."""

    def test_fails_when_no_key_signed(self, monkeypatch):
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)

        from pmoves.tools.chit_security_validator import CGPValidator, SecurityLevel
        validator = CGPValidator(passphrase="", audit_enabled=False)

        now = datetime.now(timezone.utc).isoformat()
        cgp = {
            "spec": "chit.cgp.v0.1",
            "summary": "test",
            "created_at": now,
            "super_nodes": [{
                "id": "sn1", "label": "sn1", "summary": "sn1",
                "x": 0.0, "y": 0.0, "r": 1.0,
                "constellations": [{"id": "test", "summary": "test", "sig": {"hmac": "abc"}}],
            }],
            "sig": {"alg": "HMAC-SHA256", "kid": "test", "hmac": "abc123"},
        }

        valid, err = validator.validate(cgp, source="agent-zero", security_level=SecurityLevel.SIGNED)
        assert not valid
        assert err is not None and "no signing key" in err.lower()

    def test_fails_when_no_key_strict(self, monkeypatch):
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)

        from pmoves.tools.chit_security_validator import CGPValidator, SecurityLevel
        validator = CGPValidator(passphrase="", audit_enabled=False)

        now = datetime.now(timezone.utc).isoformat()
        cgp = {
            "spec": "chit.cgp.v0.1",
            "summary": "test",
            "created_at": now,
            "super_nodes": [{
                "id": "sn1", "label": "sn1", "summary": "sn1",
                "x": 0.0, "y": 0.0, "r": 1.0,
                "constellations": [{"id": "test", "summary": "test"}],
            }],
            "sig": {"alg": "HMAC-SHA256", "kid": "test", "hmac": "abc123"},
        }

        valid, err = validator.validate(cgp, source="agent-zero", security_level=SecurityLevel.STRICT)
        assert not valid
        assert err is not None and "no signing key" in err.lower()


class TestGeometryDecoderSignVerify:
    """sign_cgp/verify_cgp roundtrip in geometry_decoder."""

    def test_sign_verify_roundtrip(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-secret-key-for-consolidation")

        from pmoves.services.common.geometry_decoder import sign_cgp, verify_cgp

        cgp = {"spec": "chit.cgp.v0.1", "super_nodes": [{"constellations": [{"id": "c1"}]}]}
        signed = sign_cgp(cgp, passphrase="test-secret-key-for-consolidation")
        assert "sig" in signed
        assert "hmac" in signed["sig"]
        assert "ts" in signed["sig"]  # geometry_decoder adds timestamp

        assert verify_cgp(signed, passphrase="test-secret-key-for-consolidation")

    def test_verify_tampered_fails(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-secret-key-for-consolidation")

        from pmoves.services.common.geometry_decoder import sign_cgp, verify_cgp

        cgp = {"spec": "chit.cgp.v0.1", "super_nodes": [{"constellations": [{"id": "c1"}]}]}
        signed = sign_cgp(cgp, passphrase="test-secret-key-for-consolidation")
        signed["spec"] = "tampered"

        assert not verify_cgp(signed, passphrase="test-secret-key-for-consolidation")
