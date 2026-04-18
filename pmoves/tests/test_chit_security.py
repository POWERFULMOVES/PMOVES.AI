"""Tests for CHIT cryptographic functions.

Covers: canon(), sign_cgp(), verify_cgp(), encrypt_anchors(), decrypt_anchors(),
       _pack_floats(), _unpack_floats(), CGPValidator, edge cases.

Coverage target: >80% for chit_security.py and chit_common.py
"""

import struct
import pytest
from pmoves.tools.chit_common import canon


class TestCanon:
    """Test canonical JSON serialization."""

    def test_sorted_keys(self):
        result = canon({"z": 1, "a": 2})
        assert result == b'{"a":2,"z":1}'

    def test_no_whitespace(self):
        result = canon({"key": "value"})
        assert b" " not in result
        assert b"\n" not in result

    def test_deterministic(self):
        obj = {"b": [3, 1, 2], "a": {"y": 2, "x": 1}}
        assert canon(obj) == canon(obj)

    def test_returns_bytes(self):
        assert isinstance(canon({}), bytes)

    def test_empty_dict(self):
        assert canon({}) == b"{}"

    def test_nested_structures(self):
        obj = {"a": [{"b": 1}, {"c": 2}]}
        result = canon(obj)
        assert b"[{" in result or b'[{"' in result

    def test_unicode_escaped(self):
        """json.dumps escapes non-ASCII by default."""
        result = canon({"key": "\u65e5\u672c\u8a9e"})
        assert isinstance(result, bytes)
        assert b"\\u65e5" in result

    def test_special_chars(self):
        result = canon({"key": "a\nb\tc"})
        assert isinstance(result, bytes)


class TestPackUnpackFloats:
    """Test float32 packing/unpacking (mirrors chit_security internals)."""

    def _pack(self, floats):
        """Pack list of floats to binary float32 with 4-byte length prefix."""
        import numpy as np
        a = np.asarray(floats, dtype="float32").tobytes()
        return struct.pack(">I", len(floats)) + a

    def _unpack(self, data):
        """Unpack binary float32 with 4-byte length prefix."""
        import numpy as np
        n = struct.unpack(">I", data[:4])[0]
        a = np.frombuffer(data[4:], dtype="float32", count=n)
        return a.astype(float).tolist()

    def test_round_trip(self):
        original = [0.1, 0.5, 0.9, 1.0, -0.3]
        packed = self._pack(original)
        unpacked = self._unpack(packed)
        assert len(unpacked) == len(original)
        for o, u in zip(original, unpacked):
            assert abs(o - u) < 1e-6

    def test_empty_array(self):
        packed = self._pack([])
        assert packed == struct.pack(">I", 0)
        assert self._unpack(packed) == []

    def test_single_value(self):
        packed = self._pack([42.0])
        assert len(packed) == 8  # 4 bytes length + 4 bytes float
        assert abs(self._unpack(packed)[0] - 42.0) < 1e-6

    def test_negative_values(self):
        original = [-1.0, -0.5, -100.0]
        unpacked = self._unpack(self._pack(original))
        for o, u in zip(original, unpacked):
            assert abs(o - u) < 1e-6

    def test_zero(self):
        unpacked = self._unpack(self._pack([0.0]))
        assert abs(unpacked[0]) < 1e-6


class TestSignVerify:
    """Test CGP signing and verification via chit_security."""

    @pytest.fixture
    def test_cgp(self):
        return {
            "schema_version": "1.0",
            "contributor": "test-agent",
            "anchors": [0.1, 0.2, 0.3],
            "metadata": {"source": "test"},
        }

    @pytest.fixture
    def passphrase(self):
        return "test-passphrase-123"

    def test_sign_produces_sig(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp
        result = sign_cgp(test_cgp, passphrase)
        assert "sig" in result
        assert "hmac" in result["sig"]  # Key is 'hmac', not 'mac'
        assert "kid" in result["sig"]
        assert "alg" in result["sig"]
        assert result["sig"]["alg"] == "HMAC-SHA256"

    def test_verify_valid_signature(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        signed = sign_cgp(test_cgp, passphrase)
        assert verify_cgp(signed, passphrase) is True

    def test_verify_wrong_passphrase(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        signed = sign_cgp(test_cgp, passphrase)
        assert verify_cgp(signed, "wrong-passphrase") is False

    def test_verify_tampered_cgp(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        signed = sign_cgp(test_cgp, passphrase)
        signed["contributor"] = "tampered"
        assert verify_cgp(signed, passphrase) is False

    def test_verify_missing_sig(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import verify_cgp
        assert verify_cgp(test_cgp, passphrase) is False

    def test_sign_preserves_cgp_fields(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp
        result = sign_cgp(test_cgp, passphrase)
        assert result["schema_version"] == "1.0"
        assert result["contributor"] == "test-agent"
        assert result["anchors"] == [0.1, 0.2, 0.3]

    def test_sign_custom_kid(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp
        result = sign_cgp(test_cgp, passphrase, kid="custom-kid-123")
        assert result["sig"]["kid"] == "custom-kid-123"

    def test_verify_bad_hmac_b64(self, test_cgp, passphrase):
        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        signed = sign_cgp(test_cgp, passphrase)
        signed["sig"]["hmac"] = "not-valid-base64!!!"
        assert verify_cgp(signed, passphrase) is False


class TestEncryptDecryptAnchors:
    """Test CGP anchor encryption/decryption using super_nodes structure."""

    @pytest.fixture
    def encrypted_cgp(self):
        """A CGP with super_nodes/constellations/anchor structure."""
        return {
            "schema_version": "1.0",
            "contributor": "test-agent",
            "super_nodes": [
                {
                    "id": "sn-1",
                    "constellations": [
                        {
                            "id": "const-1",
                            "anchor": [0.1, 0.5, 0.9, -0.3, 42.0],
                        },
                        {
                            "id": "const-2",
                            "anchor": [0.25, 0.75],
                        },
                    ],
                }
            ],
        }

    @pytest.fixture
    def passphrase(self):
        return "test-passphrase-123"

    def test_encrypt_produces_anchor_enc(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors
        result = encrypt_anchors(encrypted_cgp, passphrase)
        const = result["super_nodes"][0]["constellations"][0]
        assert "anchor_enc" in const
        assert "anchor" not in const

    def test_encrypt_anchor_enc_has_required_fields(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors
        result = encrypt_anchors(encrypted_cgp, passphrase)
        enc = result["super_nodes"][0]["constellations"][0]["anchor_enc"]
        assert enc["alg"] == "AES-GCM"
        assert "iv" in enc
        assert "salt" in enc
        assert "ct" in enc

    def test_encrypt_also_signs(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors, verify_cgp
        result = encrypt_anchors(encrypted_cgp, passphrase)
        assert verify_cgp(result, passphrase) is True

    def test_round_trip(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors, decrypt_anchors
        encrypted = encrypt_anchors(encrypted_cgp, passphrase)
        decrypted = decrypt_anchors(encrypted, passphrase)
        const = decrypted["super_nodes"][0]["constellations"][0]
        assert "anchor" in const
        assert "anchor_enc" not in const
        original = encrypted_cgp["super_nodes"][0]["constellations"][0]["anchor"]
        for orig, dec in zip(original, const["anchor"]):
            assert abs(orig - dec) < 1e-6

    def test_round_trip_multiple_constellations(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors, decrypt_anchors
        encrypted = encrypt_anchors(encrypted_cgp, passphrase)
        decrypted = decrypt_anchors(encrypted, passphrase)
        for i, orig_const in enumerate(encrypted_cgp["super_nodes"][0]["constellations"]):
            dec_const = decrypted["super_nodes"][0]["constellations"][i]
            for orig, dec in zip(orig_const["anchor"], dec_const["anchor"]):
                assert abs(orig - dec) < 1e-6

    def test_decrypt_wrong_passphrase_raises(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors, decrypt_anchors
        encrypted = encrypt_anchors(encrypted_cgp, passphrase)
        with pytest.raises(Exception):
            decrypt_anchors(encrypted, "wrong-passphrase")

    def test_different_passphrase_different_ciphertext(self, encrypted_cgp):
        from pmoves.tools.chit_security import encrypt_anchors
        e1 = encrypt_anchors(encrypted_cgp, "passphrase-a")
        e2 = encrypt_anchors(encrypted_cgp, "passphrase-b")
        enc1 = e1["super_nodes"][0]["constellations"][0]["anchor_enc"]["ct"]
        enc2 = e2["super_nodes"][0]["constellations"][0]["anchor_enc"]["ct"]
        assert enc1 != enc2

    def test_decrypt_no_encrypted_anchors_returns_doc(self, encrypted_cgp, passphrase):
        from pmoves.tools.chit_security import decrypt_anchors
        result = decrypt_anchors(encrypted_cgp, passphrase)
        assert result["super_nodes"][0]["constellations"][0]["anchor"] == [0.1, 0.5, 0.9, -0.3, 42.0]

    def test_encrypt_empty_super_nodes(self, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors
        cgp = {"schema_version": "1.0", "super_nodes": []}
        result = encrypt_anchors(cgp, passphrase)
        assert "sig" in result  # Still signs even with no anchors

    def test_encrypt_no_super_nodes_key(self, passphrase):
        from pmoves.tools.chit_security import encrypt_anchors
        cgp = {"schema_version": "1.0"}
        result = encrypt_anchors(cgp, passphrase)
        assert "sig" in result


class TestCGPValidator:
    """Test CGP schema validation."""

    def test_validator_instantiates(self):
        from pmoves.tools.chit_security_validator import CGPDocument
        # CGPDocument is the Pydantic model
        assert CGPDocument is not None

    def test_validate_method_exists(self):
        from pmoves.tools.chit_security_validator import CGPValidator
        validator = CGPValidator(passphrase="test")
        assert hasattr(validator, "validate")

    def test_validate_callable(self):
        from pmoves.tools.chit_security_validator import validate_cgp
        # Standalone validate_cgp function exists at module level
        assert callable(validate_cgp)


class TestDeriveKey:
    """Test key derivation function."""

    def test_derive_key_produces_32_bytes(self):
        from pmoves.tools.chit_security import _derive_key
        key = _derive_key("test-passphrase", salt=b"0123456789abcdef", length=32)
        assert len(key) == 32

    def test_derive_key_deterministic(self):
        from pmoves.tools.chit_security import _derive_key
        k1 = _derive_key("test-passphrase", salt=b"0123456789abcdef")
        k2 = _derive_key("test-passphrase", salt=b"0123456789abcdef")
        assert k1 == k2

    def test_derive_key_different_salt(self):
        from pmoves.tools.chit_security import _derive_key
        k1 = _derive_key("test-passphrase", salt=b"0123456789abcdef")
        k2 = _derive_key("test-passphrase", salt=b"abcdef0123456789")
        assert k1 != k2

    def test_derive_key_different_passphrase(self):
        from pmoves.tools.chit_security import _derive_key
        k1 = _derive_key("passphrase-a", salt=b"0123456789abcdef")
        k2 = _derive_key("passphrase-b", salt=b"0123456789abcdef")
        assert k1 != k2

    def test_derive_key_custom_length(self):
        from pmoves.tools.chit_security import _derive_key
        key = _derive_key("test", salt=b"0123456789abcdef", length=16)
        assert len(key) == 16


class TestEdgeCases:
    """Edge case tests."""

    def test_very_long_string(self):
        result = canon({"key": "x" * 10000})
        assert len(result) > 10000

    def test_special_json_chars(self):
        result = canon({"key": '"\\\n\t'})
        assert isinstance(result, bytes)

    def test_nested_deep(self):
        obj = {"a": {"b": {"c": {"d": {"e": 1}}}}}
        result = canon(obj)
        assert b"e" in result

    def test_list_values(self):
        result = canon({"items": [3, 1, 2]})
        assert b"[3,1,2]" in result

    def test_numeric_keys_coerced(self):
        result = canon({"1": "a", "2": "b"})
        assert b'{"1"' in result

    def test_sign_empty_cgp(self):
        from pmoves.tools.chit_security import sign_cgp
        result = sign_cgp({}, "test")
        assert "sig" in result

    def test_verify_empty_cgp_no_sig(self):
        from pmoves.tools.chit_security import verify_cgp
        assert verify_cgp({}, "test") is False

    def test_sign_cgp_with_existing_sig_replaced(self):
        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        cgp = {"data": "test", "sig": {"hmac": "old", "kid": "old", "alg": "old"}}
        result = sign_cgp(cgp, "test")
        assert verify_cgp(result, "test") is True
        assert result["sig"]["hmac"] != "old"
