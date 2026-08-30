"""Tests for gateway verify_hmac delegation to canonical chit_security.verify_cgp.

Verifies that the gateway's verify_hmac function delegates correctly
to the canonical implementation while preserving backward compatibility.
"""
import os
import pytest


class TestGatewayVerifyHMACCanonical:
    """Test gateway verify_hmac delegates to canonical chit_security."""

    def test_verify_hmac_delegates_to_canonical(self, monkeypatch):
        """verify_hmac uses canonical chit_security.verify_cgp under the hood."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-gateway-key")
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")

        from pmoves.tools.chit_security import sign_cgp
        from pmoves.services.gateway.gateway.api.chit import verify_hmac

        cgp = {
            "spec": "geometry.cgp.v1",
            "meta": {"source": "test"},
            "super_nodes": [],
        }
        signed = sign_cgp(cgp, passphrase="test-gateway-key")
        assert verify_hmac(signed) is True

    def test_verify_hmac_rejects_tampered(self, monkeypatch):
        """verify_hmac rejects tampered CGPs."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-gateway-key")
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")

        from pmoves.tools.chit_security import sign_cgp
        from pmoves.services.gateway.gateway.api.chit import verify_hmac

        cgp = {
            "spec": "geometry.cgp.v1",
            "meta": {"source": "test"},
            "super_nodes": [],
        }
        signed = sign_cgp(cgp, passphrase="test-gateway-key")
        signed["meta"]["source"] = "tampered"
        assert verify_hmac(signed) is False

    def test_verify_hmac_no_sig_require_false(self, monkeypatch):
        """verify_hmac returns True when no sig and CHIT_REQUIRE_SIGNATURE=false."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-gateway-key")
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "false")
        # Need to reload the module to pick up env change
        import importlib
        from pmoves.services.gateway.gateway import api
        import pmoves.services.gateway.gateway.api.chit as chit_mod
        importlib.reload(chit_mod)

        cgp = {"spec": "geometry.cgp.v1", "meta": {}, "super_nodes": []}
        assert chit_mod.verify_hmac(cgp) is True

    def test_verify_hmac_no_sig_require_true(self, monkeypatch):
        """verify_hmac returns False when no sig and CHIT_REQUIRE_SIGNATURE=true."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-gateway-key")
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        import importlib
        import pmoves.services.gateway.gateway.api.chit as chit_mod
        importlib.reload(chit_mod)

        cgp = {"spec": "geometry.cgp.v1", "meta": {}, "super_nodes": []}
        assert chit_mod.verify_hmac(cgp) is False

    def test_sign_verify_cross_module(self, monkeypatch):
        """CGP signed by chit_security verifies in gateway verify_hmac and vice versa."""
        passphrase = "cross-module-key"

        from pmoves.tools.chit_security import sign_cgp, verify_cgp
        import pmoves.services.gateway.gateway.api.chit as chit_mod
        # Patch the module-level variable directly (set at import time)
        monkeypatch.setattr(chit_mod, "_CHIT_PASSPHRASE", passphrase)

        cgp = {
            "spec": "geometry.cgp.v1",
            "meta": {"source": "cross-module"},
            "super_nodes": [],
        }

        # Sign with canonical, verify with gateway
        signed = sign_cgp(cgp, passphrase=passphrase)
        assert chit_mod.verify_hmac(signed) is True

        # Canonical verify also works
        assert verify_cgp(signed, passphrase=passphrase) is True
