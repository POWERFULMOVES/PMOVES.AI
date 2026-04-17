"""Comprehensive tests for CHIT security: signing, verification, encryption, validation.

Target: >80% coverage of chit_security.py, chit_common.py, chit_security_validator.py
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock httpx so chit_security_validator can import without the real package
if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

import json
import os
import struct
import pytest

from pmoves.tools.chit_common import canon
from pmoves.tools.chit_security import (
    sign_cgp,
    verify_cgp,
    encrypt_anchors,
    decrypt_anchors,
    _pack_floats,
    _unpack_floats,
    _get_signing_key,
    _get_encryption_key,
)
from pmoves.tools.chit_security_validator import (
    CGPValidator,
    CGPValidationError,
    ValidationErrorType,
    validate_cgp,
    SecurityLevel,
)

PASSPHRASE = "test-passphrase-123"
ALT_PASSPHRASE = "different-passphrase-456"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_cgp():
    """Minimal valid CGP with v1.0 spec."""
    return {
        "spec": "chit.cgp.v1.0",
        "summary": "test packet",
        "created_at": "2026-04-17T00:00:00+00:00",
        "super_nodes": [],
    }


@pytest.fixture
def cgp_with_anchor():
    """CGP with one super_node containing a constellation with anchor."""
    return {
        "spec": "chit.cgp.v1.0",
        "summary": "test packet with anchor",
        "created_at": "2026-04-17T00:00:00+00:00",
        "super_nodes": [
            {
                "id": "sn-1",
                "label": "Node 1",
                "summary": "Test node",
                "x": 0.5,
                "y": 0.5,
                "r": 0.25,
                "constellations": [
                    {
                        "id": "const-1",
                        "summary": "Test constellation",
                        "anchor": [0.1, 0.2, 0.3],
                        "spectrum": [0.5, 0.5],
                        "points": [],
                    }
                ],
            }
        ],
    }


@pytest.fixture
def cgp_multi_anchor():
    """CGP with multiple anchors."""
    return {
        "spec": "chit.cgp.v1.0",
        "summary": "multi anchor test",
        "created_at": "2026-04-17T00:00:00+00:00",
        "super_nodes": [
            {
                "id": "sn-1",
                "label": "Node 1",
                "summary": "N1",
                "x": 0.0, "y": 0.0, "r": 0.5,
                "constellations": [
                    {"id": "c1", "summary": "C1", "anchor": [1.0, 2.0, 3.0], "spectrum": [], "points": []},
                    {"id": "c2", "summary": "C2", "anchor": [4.0, 5.0, 6.0], "spectrum": [], "points": []},
                ],
            },
            {
                "id": "sn-2",
                "label": "Node 2",
                "summary": "N2",
                "x": 1.0, "y": 1.0, "r": 0.5,
                "constellations": [
                    {"id": "c3", "summary": "C3", "anchor": [7.0, 8.0, 9.0], "spectrum": [], "points": []},
                ],
            },
        ],
    }


@pytest.fixture
def signed_cgp(minimal_cgp):
    """Pre-signed minimal CGP."""
    return sign_cgp(minimal_cgp, passphrase=PASSPHRASE)


# ===========================================================================
# 1. canon() tests
# ===========================================================================

class TestCanon:
    def test_returns_bytes(self):
        result = canon({"a": 1})
        assert isinstance(result, bytes)

    def test_sorted_keys(self):
        result = canon({"z": 1, "a": 2, "m": 3}).decode()
        assert result.index("a") < result.index("m") < result.index("z")

    def test_no_whitespace(self):
        result = canon({"a": 1, "b": {"c": 2}}).decode()
        assert " " not in result
        assert "\n" not in result
        assert "\t" not in result

    def test_deterministic_output(self):
        obj = {"z": [3, 1, 2], "a": {"n": 1, "m": 2}, "b": None}
        assert canon(obj) == canon(obj)

    def test_empty_dict(self):
        result = canon({})
        assert result == b"{}"

    def test_nested_dict(self):
        obj = {"outer": {"inner": "value"}}
        result = canon(obj).decode()
        assert result == '{"outer":{"inner":"value"}}'

    def test_unicode_values(self):
        obj = {"emoji": "😀", "accent": "é"}
        result = canon(obj)
        assert isinstance(result, bytes)
        # Unicode chars get utf-8 encoded in JSON output
        assert len(result) > 0

    def test_special_chars_in_keys(self):
        obj = {"key-with-dash": 1, "key.with.dot": 2, "key_with_underscore": 3}
        result = canon(obj)
        assert isinstance(result, bytes)
        assert b"key-with-dash" in result

    def test_numeric_values(self):
        obj = {"int": 42, "float": 3.14, "neg": -1}
        result = canon(obj).decode()
        assert '"int":42' in result
        assert '"float":3.14' in result

# ===========================================================================
# 2. sign_cgp() tests
# ===========================================================================

class TestSignCgp:
    def test_sig_present(self, minimal_cgp):
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert "sig" in signed

    def test_sig_has_kid(self, minimal_cgp):
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert "kid" in signed["sig"]
        assert len(signed["sig"]["kid"]) == 16

    def test_sig_has_hmac(self, minimal_cgp):
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert "hmac" in signed["sig"]
        assert isinstance(signed["sig"]["hmac"], str)

    def test_sig_has_alg(self, minimal_cgp):
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert signed["sig"]["alg"] == "HMAC-SHA256"

    def test_custom_kid(self, minimal_cgp):
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE, kid="my-custom-kid")
        assert signed["sig"]["kid"] == "my-custom-kid"

    def test_does_not_mutate_input(self, minimal_cgp):
        original = json.dumps(minimal_cgp)
        sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert json.dumps(minimal_cgp) == original

    def test_deterministic_signature(self, minimal_cgp):
        s1 = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        s2 = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert s1["sig"]["hmac"] == s2["sig"]["hmac"]

    def test_different_passphrase_different_sig(self, minimal_cgp):
        s1 = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        s2 = sign_cgp(minimal_cgp, passphrase=ALT_PASSPHRASE)
        assert s1["sig"]["hmac"] != s2["sig"]["hmac"]

    def test_removes_old_sig_before_signing(self, signed_cgp, minimal_cgp):
        """Re-signing a signed CGP should produce a fresh signature."""
        old_hmac = signed_cgp["sig"]["hmac"]
        # Modify CGP slightly
        modified = json.loads(json.dumps(signed_cgp))
        modified["summary"] = "modified"
        re_signed = sign_cgp(modified, passphrase=PASSPHRASE)
        assert re_signed["sig"]["hmac"] != old_hmac

# ===========================================================================
# 3. verify_cgp() tests
# ===========================================================================

class TestVerifyCgp:
    def test_valid_signature(self, signed_cgp):
        assert verify_cgp(signed_cgp, passphrase=PASSPHRASE) is True

    def test_tampered_cgp_fails(self, signed_cgp):
        tampered = json.loads(json.dumps(signed_cgp))
        tampered["summary"] = "tampered"
        assert verify_cgp(tampered, passphrase=PASSPHRASE) is False

    def test_missing_sig_fails(self, minimal_cgp):
        assert verify_cgp(minimal_cgp, passphrase=PASSPHRASE) is False

    def test_wrong_passphrase_fails(self, signed_cgp):
        assert verify_cgp(signed_cgp, passphrase=ALT_PASSPHRASE) is False

    def test_corrupted_hmac_fails(self, signed_cgp):
        corrupted = json.loads(json.dumps(signed_cgp))
        corrupted["sig"]["hmac"] = "not-base64!!!"
        assert verify_cgp(corrupted, passphrase=PASSPHRASE) is False

    def test_empty_hmac_fails(self, signed_cgp):
        corrupted = json.loads(json.dumps(signed_cgp))
        corrupted["sig"]["hmac"] = ""
        assert verify_cgp(corrupted, passphrase=PASSPHRASE) is False

    def test_missing_hmac_key_fails(self, signed_cgp):
        corrupted = json.loads(json.dumps(signed_cgp))
        del corrupted["sig"]["hmac"]
        assert verify_cgp(corrupted, passphrase=PASSPHRASE) is False

    def test_extra_field_in_sig_changes_canon_and_fails(self):
        """Adding extra fields to sig changes canonical form — verification fails."""
        modified = json.loads(json.dumps(signed_cgp))
        modified["sig"]["extra"] = "field"
        # Extra field changes the canonical JSON, so HMAC no longer matches
        assert verify_cgp(modified, passphrase=PASSPHRASE) is False

# ===========================================================================
# 4. encrypt_anchors() tests
# ===========================================================================

class TestEncryptAnchors:
    def test_anchor_enc_present(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        const = encrypted["super_nodes"][0]["constellations"][0]
        assert "anchor_enc" in const
        assert "anchor" not in const

    def test_anchor_enc_has_required_fields(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        enc = encrypted["super_nodes"][0]["constellations"][0]["anchor_enc"]
        assert "alg" in enc
        assert "iv" in enc
        assert "salt" in enc
        assert "ct" in enc
        assert enc["alg"] == "AES-GCM"

    def test_ciphertext_differs_from_plaintext(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        enc = encrypted["super_nodes"][0]["constellations"][0]["anchor_enc"]
        # ct is base64 of encrypted binary — cannot equal the original anchor values
        assert enc["ct"] != "[0.1, 0.2, 0.3]"

    def test_different_passphrase_different_ciphertext(self, cgp_with_anchor):
        e1 = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        e2 = encrypt_anchors(cgp_with_anchor, passphrase=ALT_PASSPHRASE)
        ct1 = e1["super_nodes"][0]["constellations"][0]["anchor_enc"]["ct"]
        ct2 = e2["super_nodes"][0]["constellations"][0]["anchor_enc"]["ct"]
        assert ct1 != ct2

    def test_different_salt_per_call(self, cgp_with_anchor):
        """Each encrypt call should use a random salt."""
        e1 = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        e2 = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        salt1 = e1["super_nodes"][0]["constellations"][0]["anchor_enc"]["salt"]
        salt2 = e2["super_nodes"][0]["constellations"][0]["anchor_enc"]["salt"]
        assert salt1 != salt2

    def test_also_signs_result(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        assert "sig" in encrypted
        assert verify_cgp(encrypted, passphrase=PASSPHRASE) is True

    def test_no_anchor_no_change(self, minimal_cgp):
        """CGP without anchors should still be signed but no anchor_enc added."""
        encrypted = encrypt_anchors(minimal_cgp, passphrase=PASSPHRASE)
        assert "sig" in encrypted
        assert not any(
            const.get("anchor_enc")
            for s in encrypted.get("super_nodes", []) or []
            for const in s.get("constellations", []) or []
        )

    def test_multiple_anchors_all_encrypted(self, cgp_multi_anchor):
        encrypted = encrypt_anchors(cgp_multi_anchor, passphrase=PASSPHRASE)
        encrypted_count = sum(
            1
            for s in encrypted["super_nodes"]
            for const in s["constellations"]
            if const.get("anchor_enc")
        )
        assert encrypted_count == 3

    def test_constellation_without_anchor_skipped(self, minimal_cgp):
        """Constellation without anchor field should not get anchor_enc."""
        cgp = {
            "spec": "chit.cgp.v1.0",
            "summary": "no anchor",
            "created_at": "2026-04-17T00:00:00+00:00",
            "super_nodes": [{
                "id": "sn-1", "label": "N", "summary": "S",
                "x": 0, "y": 0, "r": 0.5,
                "constellations": [{"id": "c1", "summary": "C1", "spectrum": [], "points": []}],
            }],
        }
        encrypted = encrypt_anchors(cgp, passphrase=PASSPHRASE)
        assert "anchor_enc" not in encrypted["super_nodes"][0]["constellations"][0]

    def test_does_not_mutate_input(self, cgp_with_anchor):
        original = json.dumps(cgp_with_anchor)
        encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        assert json.dumps(cgp_with_anchor) == original

# ===========================================================================
# 5. decrypt_anchors() tests
# ===========================================================================

class TestDecryptAnchors:
    def test_round_trip_preserves_anchors(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        decrypted = decrypt_anchors(encrypted, passphrase=PASSPHRASE)
        original_anchor = cgp_with_anchor["super_nodes"][0]["constellations"][0]["anchor"]
        restored_anchor = decrypted["super_nodes"][0]["constellations"][0]["anchor"]
        # float32 precision loss expected
        for orig, rest in zip(original_anchor, restored_anchor):
            assert abs(orig - rest) < 1e-6

    def test_wrong_passphrase_fails(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        with pytest.raises(Exception):
            decrypt_anchors(encrypted, passphrase=ALT_PASSPHRASE)

    def test_no_encrypted_anchors_returns_copy(self, minimal_cgp):
        result = decrypt_anchors(minimal_cgp, passphrase=PASSPHRASE)
        assert result == minimal_cgp
        # Ensure it's a copy
        result["summary"] = "modified"
        assert minimal_cgp["summary"] != "modified"

    def test_anchor_enc_removed_after_decrypt(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        decrypted = decrypt_anchors(encrypted, passphrase=PASSPHRASE)
        const = decrypted["super_nodes"][0]["constellations"][0]
        assert "anchor_enc" not in const
        assert "anchor" in const

    def test_multi_anchor_round_trip(self, cgp_multi_anchor):
        encrypted = encrypt_anchors(cgp_multi_anchor, passphrase=PASSPHRASE)
        decrypted = decrypt_anchors(encrypted, passphrase=PASSPHRASE)
        for sn_orig, sn_dec in zip(cgp_multi_anchor["super_nodes"], decrypted["super_nodes"]):
            for c_orig, c_dec in zip(sn_orig["constellations"], sn_dec["constellations"]):
                for orig_v, dec_v in zip(c_orig["anchor"], c_dec["anchor"]):
                    assert abs(orig_v - dec_v) < 1e-6

    def test_tampered_ciphertext_fails(self, cgp_with_anchor):
        encrypted = encrypt_anchors(cgp_with_anchor, passphrase=PASSPHRASE)
        tampered = json.loads(json.dumps(encrypted))
        enc = tampered["super_nodes"][0]["constellations"][0]["anchor_enc"]
        enc["ct"] = enc["ct"][:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt_anchors(tampered, passphrase=PASSPHRASE)

# ===========================================================================
# 6. _pack_floats / _unpack_floats tests
# ===========================================================================

class TestPackUnpackFloats:
    def test_round_trip(self):
        values = [0.1, 0.2, 0.3, -1.5, 100.0]
        packed = _pack_floats(values)
        unpacked = _unpack_floats(packed)
        for orig, rest in zip(values, unpacked):
            assert abs(orig - rest) < 1e-6

    def test_empty_array(self):
        packed = _pack_floats([])
        assert len(packed) == 4  # just the count header
        unpacked = _unpack_floats(packed)
        assert unpacked == []

    def test_single_value(self):
        packed = _pack_floats([42.0])
        unpacked = _unpack_floats(packed)
        assert len(unpacked) == 1
        assert abs(unpacked[0] - 42.0) < 1e-6

    def test_header_format(self):
        """First 4 bytes are big-endian uint32 count."""
        packed = _pack_floats([1.0, 2.0, 3.0])
        count = struct.unpack(">I", packed[:4])[0]
        assert count == 3

    def test_float32_precision_loss(self):
        """Very precise floats lose precision in float32."""
        value = 0.123456789012345
        unpacked = _unpack_floats(_pack_floats([value]))
        assert abs(unpacked[0] - value) < 1e-6  # float32 has ~7 decimal digits

    def test_large_array(self):
        values = list(range(1000))
        packed = _pack_floats(values)
        unpacked = _unpack_floats(packed)
        assert len(unpacked) == 1000
        for i, v in enumerate(unpacked):
            assert abs(v - float(i)) < 1e-6

    def test_negative_values(self):
        values = [-1.0, -100.0, -0.001]
        unpacked = _unpack_floats(_pack_floats(values))
        for orig, rest in zip(values, unpacked):
            assert abs(orig - rest) < 1e-6

    def test_zero_values(self):
        values = [0.0, 0.0, 0.0]
        unpacked = _unpack_floats(_pack_floats(values))
        assert all(v == 0.0 for v in unpacked)

    def test_unpack_requires_minimum_header(self):
        """Buffer shorter than 4 bytes should raise."""
        with pytest.raises(Exception):
            _unpack_floats(b"\x00\x01")

# ===========================================================================
# 7. CGPValidator tests
# ===========================================================================

class TestCGPValidator:
    def test_valid_cgp_passes(self, signed_cgp):
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(signed_cgp, source="agent-zero")
        assert is_valid is True
        assert error is None

    def test_missing_spec_fails(self):
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate({"summary": "no spec"}, source="")
        assert is_valid is False
        assert "spec" in error.lower() or "structure" in error.lower()

    def test_invalid_version_rejected(self):
        cgp = {
            "spec": "chit.cgp.v99.0",
            "summary": "bad version",
            "created_at": "2026-04-17T00:00:00+00:00",
        }
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(cgp, source="")
        assert is_valid is False
        assert "version" in error.lower()

    def test_missing_signature_for_signed_level(self, minimal_cgp):
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(minimal_cgp, source="agent-zero")
        assert is_valid is False
        assert "signature" in error.lower()

    def test_invalid_signature_fails(self, minimal_cgp):
        minimal_cgp["sig"] = {"alg": "HMAC-SHA256", "kid": "fake", "hmac": "ZmFrZWhhY2s="}
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(minimal_cgp, source="agent-zero")
        assert is_valid is False
        assert "signature" in error.lower()

    def test_access_denied_for_untrusted_source(self, signed_cgp):
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(signed_cgp, source="external")
        assert is_valid is False
        assert "access denied" in error.lower()

    def test_public_level_skips_signature(self, minimal_cgp):
        """PUBLIC security level should not require signature."""
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(
            minimal_cgp, source="", security_level=SecurityLevel.PUBLIC
        )
        assert is_valid is True

    def test_empty_source_allowed(self, signed_cgp):
        v = CGPValidator(passphrase=PASSPHRASE, audit_enabled=False)
        is_valid, error = v.validate(signed_cgp, source="")
        assert is_valid is True

    def test_validate_cgp_convenience_raises_on_failure(self, minimal_cgp):
        with pytest.raises(CGPValidationError):
            validate_cgp(minimal_cgp, source="agent-zero", passphrase=PASSPHRASE)

    def test_validate_cgp_convenience_returns_true_on_success(self, signed_cgp):
        result = validate_cgp(signed_cgp, source="agent-zero", passphrase=PASSPHRASE)
        assert result is True

    def test_expired_signature_detected(self):
        """CGP with old created_at should fail expiration check."""
        cgp = {
            "spec": "chit.cgp.v1.0",
            "summary": "old",
            "created_at": "2020-01-01T00:00:00+00:00",
            "super_nodes": [],
        }
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        v = CGPValidator(passphrase=PASSPHRASE, max_signature_age_hours=1, audit_enabled=False)
        is_valid, error = v.validate(signed, source="agent-zero")
        assert is_valid is False
        assert "expired" in error.lower()

# ===========================================================================
# 8. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_empty_cgp_sign_verify(self):
        """Minimal empty CGP can be signed and verified."""
        cgp = {"spec": "chit.cgp.v1.0", "summary": "", "created_at": "2026-04-17T00:00:00+00:00"}
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_very_long_string_in_cgp(self):
        long_str = "x" * 100_000
        cgp = {"spec": "chit.cgp.v1.0", "summary": long_str, "created_at": "2026-04-17T00:00:00+00:00"}
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_unicode_in_cgp(self):
        cgp = {
            "spec": "chit.cgp.v1.0",
            "summary": "üñíçø☃😀",
            "created_at": "2026-04-17T00:00:00+00:00",
        }
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_special_chars_in_keys(self):
        cgp = {
            "spec": "chit.cgp.v1.0",
            "created_at": "2026-04-17T00:00:00+00:00",
            "key-with-dash": "value",
            "key.with.dots": "value2",
            "key_with_underscore": "value3",
        }
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_none_values_in_cgp(self):
        cgp = {
            "spec": "chit.cgp.v1.0",
            "summary": None,
            "created_at": "2026-04-17T00:00:00+00:00",
            "meta": {"optional": None},
        }
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_numeric_keys_in_cgp(self):
        """JSON allows numeric keys — canon should handle them."""
        cgp = {"spec": "chit.cgp.v1.0", "created_at": "2026-04-17T00:00:00+00:00", 42: "answer"}
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_deeply_nested_cgp(self):
        cgp = {
            "spec": "chit.cgp.v1.0",
            "created_at": "2026-04-17T00:00:00+00:00",
            "meta": {"l1": {"l2": {"l3": {"l4": "deep"}}}},
        }
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

# ===========================================================================
# 9. Key separation tests (_get_signing_key / _get_encryption_key)
# ===========================================================================

class TestKeySeparation:
    def test_signing_key_from_dedicated_env(self, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "sign-key")
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        assert _get_signing_key() == "sign-key"

    def test_signing_key_fallback_to_passphrase(self, monkeypatch):
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.setenv("CHIT_PASSPHRASE", "shared-key")
        assert _get_signing_key() == "shared-key"

    def test_signing_key_priority_over_passphrase(self, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "sign-key")
        monkeypatch.setenv("CHIT_PASSPHRASE", "shared-key")
        assert _get_signing_key() == "sign-key"

    def test_signing_key_missing_raises(self, monkeypatch):
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        with pytest.raises(RuntimeError, match="CHIT_SIGNING_KEY or CHIT_PASSPHRASE"):
            _get_signing_key()

    def test_encryption_key_from_dedicated_env(self, monkeypatch):
        monkeypatch.setenv("CHIT_ENCRYPTION_KEY", "enc-key")
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        assert _get_encryption_key() == "enc-key"

    def test_encryption_key_fallback_to_passphrase(self, monkeypatch):
        monkeypatch.delenv("CHIT_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("CHIT_PASSPHRASE", "shared-key")
        assert _get_encryption_key() == "shared-key"

    def test_encryption_key_missing_raises(self, monkeypatch):
        monkeypatch.delenv("CHIT_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        with pytest.raises(RuntimeError, match="CHIT_ENCRYPTION_KEY or CHIT_PASSPHRASE"):
            _get_encryption_key()

    def test_sign_without_passphrase_uses_env(self, minimal_cgp, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "env-sign-key")
        signed = sign_cgp(minimal_cgp)  # no passphrase
        assert "sig" in signed
        assert verify_cgp(signed) is True  # verify also reads from env

    def test_encrypt_without_passphrase_uses_env(self, cgp_with_anchor, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "env-sign-key")
        monkeypatch.setenv("CHIT_ENCRYPTION_KEY", "env-enc-key")
        encrypted = encrypt_anchors(cgp_with_anchor)  # no passphrase
        assert "anchor_enc" in encrypted["super_nodes"][0]["constellations"][0]
        decrypted = decrypt_anchors(encrypted)
        assert "anchor" in decrypted["super_nodes"][0]["constellations"][0]

    def test_passphrase_overrides_env(self, minimal_cgp, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "env-key")
        signed = sign_cgp(minimal_cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True
        assert verify_cgp(signed) is False  # env key differs
