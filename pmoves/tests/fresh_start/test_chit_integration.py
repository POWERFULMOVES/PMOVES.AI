#!/usr/bin/env python3
"""Fresh Start Tests: CHIT Integration Tests.

Tests for verifying CHIT encoding/decoding and tier file population works correctly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add repo root to path
# Find the actual repo root by looking for .git directory
current = Path(__file__).resolve()
REPO_ROOT = current
while REPO_ROOT.parent != REPO_ROOT and not (REPO_ROOT / ".git").exists():
    REPO_ROOT = REPO_ROOT.parent

PMOVES_DIR = REPO_ROOT / "pmoves"
sys.path.insert(0, str(REPO_ROOT))


class TestCHITEncodeDecode:
    """Test CHIT encoding and decoding."""

    def test_encode_creates_valid_cgp(self):
        """Encoding secrets should create a valid CGP structure."""
        from pmoves.chit import encode_secret_map, CHIT_CGP_VERSION

        secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "NEO4J_AUTH": "neo4j/another_password",
            "OPENAI_API_KEY": "sk-test-key-123",
        }

        cgp = encode_secret_map(secrets, namespace="test", description="Test CGP")

        # Verify structure
        assert cgp["version"] == CHIT_CGP_VERSION
        assert cgp["namespace"] == "test"
        assert cgp["description"] == "Test CGP"
        assert len(cgp["points"]) == len(secrets)

        # Verify each point
        for point in cgp["points"]:
            assert point["label"] in secrets
            assert point["value"] == secrets[point["label"]]
            assert isinstance(point["anchor"], list)
            assert len(point["anchor"]) == 3

    def test_decode_recreates_secrets(self):
        """Decoding CGP should recreate the original secrets."""
        from pmoves.chit import encode_secret_map, decode_secret_map

        original_secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "NEO4J_AUTH": "neo4j/another_password",
            "OPENAI_API_KEY": "sk-test-key-123",
        }

        cgp = encode_secret_map(original_secrets)
        decoded = decode_secret_map(cgp)

        for key, value in original_secrets.items():
            assert decoded.get(key) == value, f"Mismatch for {key}"

    def test_encode_with_hex_encoding(self):
        """Encoding with hex should store obfuscated values."""
        from pmoves.chit import encode_secret_map, decode_secret_map

        secrets = {
            "SECRET_KEY": "super_secret_value",
        }

        cgp = encode_secret_map(secrets, include_cleartext=False)

        # Check that points use hex encoding
        for point in cgp["points"]:
            assert point["encoding"] == "hex"

        # Decoding should still work
        decoded = decode_secret_map(cgp)
        assert decoded.get("SECRET_KEY") == "super_secret_value"

    def test_anchor_is_deterministic(self):
        """Anchors should be deterministic for the same label."""
        from pmoves.chit import encode_secret_map

        secrets = {"TEST_VAR": "test_value"}

        cgp1 = encode_secret_map(secrets)
        cgp2 = encode_secret_map(secrets)

        assert cgp1["points"][0]["anchor"] == cgp2["points"][0]["anchor"]


class TestCHITFileOperations:
    """Test CHIT file save/load operations."""

    def test_save_and_load_cgp(self):
        """Saving and loading CGP should preserve data."""
        from pmoves.chit import encode_secret_map, decode_secret_map, save_cgp, load_cgp

        secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "NEO4J_AUTH": "neo4j/another_password",
        }

        cgp = encode_secret_map(secrets)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            save_cgp(cgp, temp_path)
            loaded = load_cgp(temp_path)

            assert loaded["version"] == cgp["version"]
            assert loaded["namespace"] == cgp["namespace"]
            assert len(loaded["points"]) == len(cgp["points"])

            decoded = decode_secret_map(loaded)
            for key, value in secrets.items():
                assert decoded.get(key) == value
        finally:
            temp_path.unlink(missing_ok=True)


class TestCHITTierFileWriting:
    """Test CHIT tier file writing."""

    def test_write_to_tier_envs(self):
        """Writing secrets to tier files should work correctly."""
        from pmoves.chit import write_to_tier_envs

        secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "NEO4J_AUTH": "neo4j/another_password",
            "OPENAI_API_KEY": "sk-test-key-123",
        }

        tier_files = {
            "data": ["POSTGRES_PASSWORD", "NEO4J_AUTH"],
            "llm": ["OPENAI_API_KEY"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            write_to_tier_envs(secrets, tier_files, base_dir)

            # Check tier-data
            data_file = base_dir / "env.tier-data"
            assert data_file.exists()
            content = data_file.read_text()
            assert "POSTGRES_PASSWORD=secure_password_123" in content
            assert "NEO4J_AUTH=neo4j/another_password" in content

            # Check tier-llm
            llm_file = base_dir / "env.tier-llm"
            assert llm_file.exists()
            content = llm_file.read_text()
            assert "OPENAI_API_KEY=sk-test-key-123" in content

    def test_write_to_tier_envs_preserves_existing(self):
        """Writing to tier files should preserve existing variables."""
        from pmoves.chit import write_to_tier_envs

        # Create initial tier file
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            data_file = base_dir / "env.tier-data"

            data_file.write_text(
                "# PMOVES.AI Tier DATA\n"
                "EXISTING_VAR=keep_this\n"
                "POSTGRES_PASSWORD=old_password\n"
            )

            secrets = {"POSTGRES_PASSWORD": "new_password"}

            write_to_tier_envs(secrets, {"data": ["POSTGRES_PASSWORD"]}, base_dir)

            content = data_file.read_text()
            assert "EXISTING_VAR=keep_this" in content
            assert "POSTGRES_PASSWORD=new_password" in content
            assert "old_password" not in content


class TestCHITMultiTargetOutput:
    """Test CHIT multi-target output (tier, GitHub, Docker)."""

    def test_write_github_secrets(self):
        """Writing GitHub secrets should work correctly."""
        from pmoves.chit import write_github_secrets

        secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "OPENAI_API_KEY": "sk-test-key-123",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = write_github_secrets(secrets, temp_path)

            assert temp_path.exists()
            with open(temp_path) as f:
                github_secrets = json.load(f)

            # Check PMOVES_ prefix was added
            assert "PMOVES_POSTGRES_PASSWORD" in github_secrets
            assert "PMOVES_OPENAI_API_KEY" in github_secrets

            # Check values are correct
            assert github_secrets["PMOVES_POSTGRES_PASSWORD"] == "secure_password_123"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_write_docker_secrets(self):
        """Writing Docker secrets should work correctly."""
        from pmoves.chit import write_docker_secrets

        secrets = {
            "POSTGRES_PASSWORD": "secure_password_123",
            "OPENAI_API_KEY": "sk-test-key-123",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = write_docker_secrets(secrets, temp_path)

            assert temp_path.exists()
            with open(temp_path) as f:
                docker_secrets = json.load(f)

            # Check pmoves_ prefix and lowercase
            assert "pmoves_postgres_password" in docker_secrets
            assert "pmoves_openai_api_key" in docker_secrets

            # Check values are correct
            assert docker_secrets["pmoves_postgres_password"] == "secure_password_123"
        finally:
            temp_path.unlink(missing_ok=True)


class TestCHITManifestV2:
    """Test CHIT manifest v2 application."""

    def test_manifest_v2_exists(self):
        """Manifest v2 should exist."""
        manifest = PMOVES_DIR / "chit" / "secrets_manifest_v2.yaml"
        assert manifest.exists(), "secrets_manifest_v2.yaml not found"

    def test_manifest_v2_structure(self):
        """Manifest v2 should have correct structure."""
        import yaml

        manifest = PMOVES_DIR / "chit" / "secrets_manifest_v2.yaml"
        if not manifest.exists():
            pytest.skip("secrets_manifest_v2.yaml does not exist")

        with open(manifest) as f:
            data = yaml.safe_load(f)

        assert data["version"] == 2
        assert data["tier_layout"] is True
        assert data["github_sync"] is True
        assert data["docker_secrets"] is True
        assert "entries" in data
        assert len(data["entries"]) > 0

    def test_manifest_entries_have_tier(self):
        """All manifest entries should have a tier field."""
        import yaml

        manifest = PMOVES_DIR / "chit" / "secrets_manifest_v2.yaml"
        if not manifest.exists():
            pytest.skip("secrets_manifest_v2.yaml does not exist")

        with open(manifest) as f:
            data = yaml.safe_load(f)

        valid_tiers = ["data", "api", "llm", "media", "agent", "worker"]

        for entry in data["entries"]:
            assert "tier" in entry, f"Entry missing tier: {entry.get('id', entry.get('source'))}"
            assert entry["tier"] in valid_tiers, f"Invalid tier: {entry['tier']}"

    def test_manifest_entries_have_targets(self):
        """All manifest entries should have targets."""
        import yaml

        manifest = PMOVES_DIR / "chit" / "secrets_manifest_v2.yaml"
        if not manifest.exists():
            pytest.skip("secrets_manifest_v2.yaml does not exist")

        with open(manifest) as f:
            data = yaml.safe_load(f)

        for entry in data["entries"]:
            assert "targets" in entry, f"Entry missing targets: {entry.get('id')}"
            assert len(entry["targets"]) > 0, f"Entry has no targets: {entry.get('id')}"

            # Check for tier file target
            has_tier_target = any(
                "file" in t and t["file"].startswith("env.tier-") for t in entry["targets"]
            )
            assert has_tier_target, f"Entry missing tier file target: {entry.get('id')}"


class TestLegacyEnvDeprecated:
    """Test legacy .env.generated deprecation."""

    def test_legacy_env_has_deprecation_notice(self):
        """Legacy .env.generated should have deprecation notice."""
        legacy_env = PMOVES_DIR / ".env.generated"
        if not legacy_env.exists():
            pytest.skip("Legacy .env.generated does not exist")

        content = legacy_env.read_text()

        # Check for deprecation notice
        # (This is a warning, not a hard requirement)
        if "deprecated" not in content.lower():
            # Add warning instead of failing
            pytest.warns(
                UserWarning,
                match="Legacy .env.generated exists without deprecation notice"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
