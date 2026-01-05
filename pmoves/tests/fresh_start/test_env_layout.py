#!/usr/bin/env python3
"""Fresh Start Tests: Environment Layout Validation.

Tests for verifying the 6-tier environment layout is correctly configured.
Ensures tier env files exist and Docker Compose uses correct anchors.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Add repo root to path
# Find the actual repo root by looking for .git directory
current = Path(__file__).resolve()
REPO_ROOT = current
while REPO_ROOT.parent != REPO_ROOT and not (REPO_ROOT / ".git").exists():
    REPO_ROOT = REPO_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))

from pmoves.tools.env_validator import TIER_DEFINITIONS


class TestTierFilesExist:
    """Test that all 6 tier env files exist."""

    @pytest.mark.parametrize("tier", list(TIER_DEFINITIONS.keys()))
    def test_tier_file_exists(self, tier):
        """Each tier env file should exist."""
        tier_file = REPO_ROOT / "pmoves" / TIER_DEFINITIONS[tier]["file"]
        assert tier_file.exists(), f"Tier file not found: {tier_file}"

    def test_all_tier_files_exist(self):
        """All 6 tier env files should exist."""
        missing = []
        for tier, tier_def in TIER_DEFINITIONS.items():
            tier_file = REPO_ROOT / "pmoves" / tier_def["file"]
            if not tier_file.exists():
                missing.append(tier)
        assert not missing, f"Missing tier files: {', '.join(missing)}"


class TestTierFileHeaders:
    """Test that tier env files have proper headers."""

    @pytest.mark.parametrize("tier", list(TIER_DEFINITIONS.keys()))
    def test_tier_file_has_header(self, tier):
        """Each tier file should have a descriptive header comment."""
        tier_file = REPO_ROOT / "pmoves" / TIER_DEFINITIONS[tier]["file"]
        if not tier_file.exists():
            pytest.skip(f"Tier file does not exist: {tier_file}")

        content = tier_file.read_text()
        assert content.startswith("#"), f"{tier_file} should start with # comment"

        # Should mention "PMOVES" and "Tier"
        assert "PMOVES" in content or "pmoves" in content.lower()
        assert tier.upper() in content or tier in content


class TestTierFileValidation:
    """Test tier file content validation."""

    def test_data_tier_has_postgres(self):
        """Data tier should have PostgreSQL credentials."""
        from pmoves.tools.env_validator import validate_tier

        report = validate_tier("data", REPO_ROOT)
        if report.errors:
            # Check if POSTGRES_PASSWORD is set (ignore other errors for now)
            for error in report.errors:
                if error.variable == "POSTGRES_PASSWORD":
                    pytest.fail(f"POSTGRES_PASSWORD validation failed: {error.message}")

    def test_api_tier_has_supabase(self):
        """API tier should have Supabase credentials."""
        from pmoves.tools.env_validator import validate_tier

        report = validate_tier("api", REPO_ROOT)
        if report.errors:
            for error in report.errors:
                if error.variable == "SUPABASE_JWT_SECRET":
                    pytest.fail(f"SUPABASE_JWT_SECRET validation failed: {error.message}")

    def test_agent_tier_has_nats(self):
        """Agent tier should have NATS URL."""
        from pmoves.tools.env_validator import validate_tier

        report = validate_tier("agent", REPO_ROOT)
        if report.errors:
            for error in report.errors:
                if error.variable == "NATS_URL":
                    pytest.fail(f"NATS_URL validation failed: {error.message}")


class TestNoPlaceholderValues:
    """Test that tier files don't contain placeholder values."""

    PLACEHOLDER_PATTERNS = [
        "changeme",
        "your_.*_here",
        "placeholder",
        "xxx+",
        "TODO",
        "<.*>",
    ]

    @pytest.mark.parametrize("tier", list(TIER_DEFINITIONS.keys()))
    def test_tier_no_placeholders(self, tier):
        """Tier files should not contain placeholder values."""
        import re

        tier_file = REPO_ROOT / "pmoves" / TIER_DEFINITIONS[tier]["file"]
        if not tier_file.exists():
            pytest.skip(f"Tier file does not exist: {tier_file}")

        content = tier_file.read_text()
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()

                for pattern in self.PLACEHOLDER_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        pytest.fail(
                            f"Placeholder value found in {tier_file}: "
                            f"{key}={value} (matches pattern: {pattern})"
                        )


class TestDockerComposeAnchors:
    """Test that Docker Compose uses correct tier env file anchors."""

    def test_docker_compose_exists(self):
        """docker-compose.yml should exist."""
        compose_file = REPO_ROOT / "pmoves" / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml not found"

    def test_invidious_uses_tier_media_anchor(self):
        """Invidious service should use env.tier-media anchor."""
        import yaml

        compose_file = REPO_ROOT / "pmoves" / "docker-compose.yml"
        if not compose_file.exists():
            pytest.skip("docker-compose.yml does not exist")

        with open(compose_file) as f:
            compose = yaml.safe_load(f)

        invidious = compose["services"].get("invidious")
        if not invidious:
            pytest.skip("invidious service not found in docker-compose.yml")

        # Check that invidious uses the tier-media anchor
        env_files = invidious.get("env_file", [])
        if isinstance(env_files, str):
            env_files = [env_files]

        # Look for tier-media reference
        has_tier_media = any(
            "tier-media" in str(ef) or "id004" in str(ef) for ef in env_files
        )
        assert has_tier_media, "invidious should use env.tier-media anchor"

    def test_tensorzero_clickhouse_has_data_network(self):
        """TensorZero ClickHouse should have pmoves_data network."""
        import yaml

        compose_file = REPO_ROOT / "pmoves" / "docker-compose.yml"
        if not compose_file.exists():
            pytest.skip("docker-compose.yml does not exist")

        with open(compose_file) as f:
            compose = yaml.safe_load(f)

        tensorzero_ui = compose["services"].get("tensorzero-ui")
        if not tensorzero_ui:
            pytest.skip("tensorzero-ui service not found in docker-compose.yml")

        networks = tensorzero_ui.get("networks", [])
        has_data_network = "pmoves_data" in networks or "data" in str(networks)
        assert has_data_network, "tensorzero-ui should have pmoves_data network"


class TestNoLegacyEnvGenerated:
    """Test that services don't reference legacy .env.generated directly."""

    def test_no_services_use_legacy_env(self):
        """Services should not reference .env.generated directly."""
        import yaml

        compose_file = REPO_ROOT / "pmoves" / "docker-compose.yml"
        if not compose_file.exists():
            pytest.skip("docker-compose.yml does not exist")

        with open(compose_file) as f:
            content = f.read()

        # Check for any direct reference to .env.generated
        # (excluding comments)
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        legacy_refs = [
            line
            for line in lines
            if ".env.generated" in line and "env.tier-" not in line
        ]

        assert not legacy_refs, (
            f"Found {len(legacy_refs)} references to .env.generated "
            f"without tier migration: {legacy_refs[:3]}"
        )


class TestCHITManifestV2:
    """Test CHIT manifest v2 structure."""

    def test_manifest_v2_exists(self):
        """secrets_manifest_v2.yaml should exist."""
        manifest = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
        assert manifest.exists(), "secrets_manifest_v2.yaml not found"

    def test_manifest_v2_has_correct_version(self):
        """Manifest v2 should have version: 2."""
        import yaml

        manifest = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
        if not manifest.exists():
            pytest.skip("secrets_manifest_v2.yaml does not exist")

        with open(manifest) as f:
            data = yaml.safe_load(f)

        assert data.get("version") == 2, "Manifest version should be 2"
        assert data.get("tier_layout") is True, "Manifest should have tier_layout: true"
        assert data.get("github_sync") is True, "Manifest should have github_sync: true"
        assert data.get("docker_secrets") is True, "Manifest should have docker_secrets: true"

    def test_manifest_v2_entries_have_tier(self):
        """All manifest entries should have a tier field."""
        import yaml

        manifest = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
        if not manifest.exists():
            pytest.skip("secrets_manifest_v2.yaml does not exist")

        with open(manifest) as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        missing_tier = [
            e for e in entries if not e.get("tier") or e["tier"] not in TIER_DEFINITIONS
        ]

        assert not missing_tier, (
            f"{len(missing_tier)} entries missing valid tier field"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
