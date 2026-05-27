"""Tests for CHIT signing module for graph-linker Neo4j writes.

Tests chit_signer.sign_neo4j_node / verify_neo4j_node roundtrip,
CHIT_SIGN_NEO4J gating, and dev mode graceful handling.

Located in pmoves/tests/ to avoid pydantic_settings dependency
in the graph-linker service conftest.
"""
import os
import sys
import importlib
import pytest

# Add graph-linker dir for chit_signer import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "graph-linker"))


class TestNeo4jCHITSigner:
    """Test CHIT signing for Neo4j node data."""

    def test_sign_verify_roundtrip(self, monkeypatch):
        """Signing and verifying a node data dict roundtrips."""
        monkeypatch.setenv("CHIT_SIGN_NEO4J", "true")
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-neo4j-signing-key")
        import chit_signer as cs
        importlib.reload(cs)

        node_data = {
            "id": "asset-001",
            "uri": "s3://bucket/key",
            "label": "Image",
        }
        signed = cs.sign_neo4j_node(node_data)
        assert "sig" in signed
        assert "hmac" in signed["sig"]
        assert cs.verify_neo4j_node(signed) is True

    def test_sign_disabled_returns_original(self, monkeypatch):
        """When CHIT_SIGN_NEO4J is not set, node data passes through."""
        monkeypatch.delenv("CHIT_SIGN_NEO4J", raising=False)
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
        import chit_signer as cs
        importlib.reload(cs)

        node_data = {"id": "node-1", "label": "Test"}
        result = cs.sign_neo4j_node(node_data)
        assert result == node_data  # Unchanged
        assert "sig" not in result

    def test_sign_no_passphrase_dev_mode(self, monkeypatch):
        """When CHIT_SIGN_NEO4J=true but no passphrase, returns unsigned."""
        monkeypatch.setenv("CHIT_SIGN_NEO4J", "true")
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        import chit_signer as cs
        importlib.reload(cs)

        node_data = {"id": "node-2", "label": "Test"}
        result = cs.sign_neo4j_node(node_data)
        assert "sig" not in result
        # Verify returns True in dev mode
        assert cs.verify_neo4j_node(result) is True

    def test_verify_tampered_node_fails(self, monkeypatch):
        """Verification fails when node data is tampered."""
        monkeypatch.setenv("CHIT_SIGN_NEO4J", "true")
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-neo4j-signing-key")
        import chit_signer as cs
        importlib.reload(cs)

        node_data = {"id": "node-3", "label": "Original"}
        signed = cs.sign_neo4j_node(node_data)
        # Tamper
        signed["label"] = "Tampered"
        assert cs.verify_neo4j_node(signed) is False

    def test_verify_disabled_always_passes(self, monkeypatch):
        """When CHIT_SIGN_NEO4J is false, verification always passes."""
        monkeypatch.delenv("CHIT_SIGN_NEO4J", raising=False)
        import chit_signer as cs
        importlib.reload(cs)

        assert cs.verify_neo4j_node({"id": "x"}) is True
        assert cs.verify_neo4j_node({}) is True
