"""Tests for CHIT canonical HMAC signing in Tokenism Simulator CHITEncoder.

Tests sign_cgp_packet / verify_cgp_packet roundtrip, dev mode, and tamper detection.
These tests exercise the CHITEncoder signing methods which delegate to the
canonical pmoves.tools.chit_security.sign_cgp / verify_cgp.
"""
import os
import sys
import importlib
import pytest

# Add the tokenism-simulator service dir for model imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "tokenism-simulator"))

from models.simulation import CGPPacket
from pmoves.tools.chit_security import sign_cgp, verify_cgp


class TestTokenismCHITSigning:
    """Test CHIT signing roundtrip for CGPPacket objects."""

    def test_sign_cgp_packet_roundtrip(self):
        """Sign a CGP dict and verify it roundtrips via canonical sign_cgp/verify_cgp."""
        passphrase = "test-tokenism-signing-key"
        packet = CGPPacket(
            simulation_id="sign-test",
            geometry={"points": [[0, 1]], "edges": []},
            metadata={"test": True},
        )
        cgp_dict = packet.model_dump(mode="json")
        signed = sign_cgp(cgp_dict, passphrase=passphrase)
        assert "sig" in signed
        assert "hmac" in signed["sig"]
        assert verify_cgp(signed, passphrase=passphrase) is True

    def test_verify_tampered_cgp_fails(self):
        """Verification fails when signed CGP is tampered."""
        passphrase = "test-tokenism-signing-key"
        packet = CGPPacket(
            simulation_id="tamper-test",
            geometry={"points": [[0, 1]], "edges": []},
        )
        cgp_dict = packet.model_dump(mode="json")
        signed = sign_cgp(cgp_dict, passphrase=passphrase)
        # Tamper
        signed["simulation_id"] = "tampered"
        assert verify_cgp(signed, passphrase=passphrase) is False

    def test_unsigned_cgp_fails_verification(self):
        """Unsigned CGP fails verification when passphrase is provided."""
        passphrase = "test-tokenism-signing-key"
        cgp = {"simulation_id": "unsigned", "geometry": {}}
        assert verify_cgp(cgp, passphrase=passphrase) is False

    def test_sign_preserves_cgp_data(self):
        """Signing preserves all original CGP data fields."""
        passphrase = "test-tokenism-signing-key"
        packet = CGPPacket(
            simulation_id="preserve-test",
            geometry={"points": [[1.5, 2.3], [3.1, 4.0]], "edges": [[0, 1]]},
            metadata={"scenario": "baseline", "week": 10},
        )
        cgp_dict = packet.model_dump(mode="json")
        signed = sign_cgp(cgp_dict, passphrase=passphrase)
        # All original data preserved
        assert signed["simulation_id"] == "preserve-test"
        assert signed["geometry"]["points"] == [[1.5, 2.3], [3.1, 4.0]]
        assert signed["metadata"]["scenario"] == "baseline"
        # sig added
        assert "sig" in signed
