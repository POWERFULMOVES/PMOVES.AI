"""CHIT signing tests for the consciousness service.

Mirrors pmoves/services/tokenism-simulator/tests/test_chit_encoder.py (the
CHIT-Full reference) and pmoves/tests/test_chit_security.py: canonical
round-trip, tamper detection, dev-mode unsigned, fail-closed enforcement,
publish-boundary signing in cgp_mapper, and fallback-signer parity.
"""

import builtins
import importlib
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import chr_algorithm
from chr_algorithm import (
    CHRResult,
    ConstellationResult,
    chr_result_to_cgp,
    get_chit_signing_key,
    sign_cgp,
    verify_cgp,
)

PASSPHRASE = "test-signing-key"


def make_result() -> CHRResult:
    return CHRResult(
        namespace="pmoves.test",
        K=1,
        mhep=0.5,
        Hg=0.1,
        Hs=0.2,
        constellations=[
            ConstellationResult(
                id="c0",
                anchor=[0.1, 0.2],
                spectrum=[0.5, 0.5],
                points=[{"id": "u0", "r": 0.3}],
                radial_minmax=(0.0, 1.0),
                summary="test constellation",
            )
        ],
        embeddings=np.zeros((1, 2)),
        anchors=np.zeros((1, 2)),
        labels=np.zeros(1, dtype=int),
        shape_id="deadbeef",
    )


@pytest.fixture(autouse=True)
def clean_chit_env(monkeypatch):
    for var in (
        "CHIT_SIGNING_KEY",
        "CHIT_PASSPHRASE",
        "CHIT_PROD_PASSPHRASE",
        "CHIT_SIGNING_KEY_ID",
        "CHIT_REQUIRE_SIGNATURE",
    ):
        monkeypatch.delenv(var, raising=False)


class TestCanonicalSignVerify:
    def test_round_trip(self):
        cgp = {"spec": "chit.cgp.v0.1", "summary": "x"}
        signed = sign_cgp(cgp, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_signature_shape_is_canonical(self):
        signed = sign_cgp({"a": 1}, passphrase=PASSPHRASE)
        sig = signed["sig"]
        assert sig["alg"] == "HMAC-SHA256"
        assert sig["kid"] == "chit-signing-v01"
        assert "hmac" in sig
        # The old inline signer added a non-canonical `ts` field.
        assert "ts" not in sig

    def test_tamper_detection(self):
        signed = sign_cgp({"a": 1}, passphrase=PASSPHRASE)
        signed["a"] = 2
        assert verify_cgp(signed, passphrase=PASSPHRASE) is False

    def test_wrong_key_rejected(self):
        signed = sign_cgp({"a": 1}, passphrase=PASSPHRASE)
        assert verify_cgp(signed, passphrase="other-key") is False

    def test_unsigned_doc_fails_verification(self):
        assert verify_cgp({"a": 1}, passphrase=PASSPHRASE) is False


class TestKeySourcing:
    def test_canonical_chain_preferred(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", "canonical")
        monkeypatch.setenv("CHIT_PROD_PASSPHRASE", "legacy")
        assert get_chit_signing_key() == "canonical"

    def test_signing_key_wins_over_passphrase(self, monkeypatch):
        monkeypatch.setenv("CHIT_SIGNING_KEY", "dedicated")
        monkeypatch.setenv("CHIT_PASSPHRASE", "shared")
        assert get_chit_signing_key() == "dedicated"

    def test_legacy_prod_passphrase_still_honored(self, monkeypatch):
        monkeypatch.setenv("CHIT_PROD_PASSPHRASE", "legacy")
        assert get_chit_signing_key() == "legacy"

    def test_empty_when_unset(self):
        assert get_chit_signing_key() == ""


class TestCHRResultToCGP:
    def test_signed_when_key_present(self):
        cgp = chr_result_to_cgp(make_result(), passphrase=PASSPHRASE)
        assert "sig" in cgp
        assert verify_cgp(cgp, passphrase=PASSPHRASE) is True

    def test_unsigned_dev_mode_when_no_key(self, caplog):
        cgp = chr_result_to_cgp(make_result(), passphrase="")
        assert "sig" not in cgp
        assert any("unsigned" in r.message for r in caplog.records)

    def test_fail_closed_when_signature_required(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        with pytest.raises(RuntimeError, match="CHIT_REQUIRE_SIGNATURE"):
            chr_result_to_cgp(make_result(), passphrase="")


class TestMapperPublishBoundary:
    @pytest.fixture
    def mapper(self):
        from cgp_mapper import CGPMapper

        return CGPMapper()

    @pytest.mark.asyncio
    async def test_publish_signs_packet(self, mapper, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        posted = {}

        async def fake_post(url, json=None, headers=None):
            posted["packet"] = json
            resp = mock.Mock()
            resp.raise_for_status = mock.Mock()
            resp.json = mock.Mock(return_value={"ok": True})
            return resp

        monkeypatch.setattr(mapper.client, "post", fake_post)
        packet = {"spec": "chit.cgp.v1.0", "super_nodes": [{"constellations": [{"id": "t0"}]}]}
        await mapper.publish_to_hirag(packet)
        assert "sig" in posted["packet"]
        assert verify_cgp(posted["packet"], passphrase=PASSPHRASE) is True

    @pytest.mark.asyncio
    async def test_publish_fail_closed_without_key(self, mapper, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "1")
        with pytest.raises(RuntimeError, match="CHIT_REQUIRE_SIGNATURE"):
            await mapper.publish_to_hirag(
                {"spec": "chit.cgp.v1.0", "super_nodes": [{"constellations": [{"id": "t0"}]}]}
            )

    @pytest.mark.asyncio
    async def test_publish_unsigned_dev_mode(self, mapper, monkeypatch, caplog):
        posted = {}

        async def fake_post(url, json=None, headers=None):
            posted["packet"] = json
            resp = mock.Mock()
            resp.raise_for_status = mock.Mock()
            resp.json = mock.Mock(return_value={"ok": True})
            return resp

        monkeypatch.setattr(mapper.client, "post", fake_post)
        await mapper.publish_to_hirag(
            {"spec": "chit.cgp.v1.0", "super_nodes": [{"constellations": [{"id": "t0"}]}]}
        )
        assert "sig" not in posted["packet"]


class TestFallbackParity:
    """The standalone fallback must produce byte-identical signatures to the
    canonical pmoves.tools.chit_security implementation — this is the drift
    the lane exists to eliminate."""

    @pytest.fixture
    def fallback_chr(self):
        canonical_available = chr_algorithm.CHIT_CANONICAL
        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name.startswith("pmoves.tools.chit_security") or (
                name == "pmoves.tools" and args and args[3] and "chit_security" in str(args[3])
            ):
                raise ImportError("blocked for fallback parity test")
            if name.startswith("pmoves"):
                raise ImportError("blocked for fallback parity test")
            return real_import(name, *args, **kwargs)

        with mock.patch.object(builtins, "__import__", side_effect=blocked_import):
            module = importlib.reload(chr_algorithm)
        assert module.CHIT_CANONICAL is False
        yield module
        restored = importlib.reload(chr_algorithm)
        assert restored.CHIT_CANONICAL is canonical_available

    def test_fallback_signature_matches_canonical(self, fallback_chr):
        from pmoves.tools.chit_security import sign_cgp as canonical_sign

        doc = {"spec": "chit.cgp.v0.1", "meta": {"n": 1}, "super_nodes": []}
        fallback_signed = fallback_chr.sign_cgp(doc, passphrase=PASSPHRASE)
        canonical_signed = canonical_sign(doc, passphrase=PASSPHRASE)
        assert fallback_signed["sig"] == canonical_signed["sig"]

    def test_fallback_verifies_canonical_signature(self, fallback_chr):
        from pmoves.tools.chit_security import sign_cgp as canonical_sign

        signed = canonical_sign({"a": 1}, passphrase=PASSPHRASE)
        assert fallback_chr.verify_cgp(signed, passphrase=PASSPHRASE) is True

    def test_fallback_requires_key(self, fallback_chr):
        with pytest.raises(RuntimeError):
            fallback_chr.sign_cgp({"a": 1})
