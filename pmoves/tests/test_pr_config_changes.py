"""Tests validating the PR config-file changes.

Covers:
- env.mesh-bind.example — new reviewed override file
- .claude/hooks/damage-control/patterns.yaml — invidious paths removed
- pmoves/config/provider_catalog.yaml — claude_sonnet_4 strength_ref → null
- pmoves/config/model_strengths_seed.yaml — claude_sonnet_4 entry removed
- pmoves/tensorzero/config/tensorzero.toml — OTLP export disabled

All tests use plain file I/O; no external service calls required.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]  # /home/jailuser/git
_PMOVES = _REPO / "pmoves"

ENV_MESH_BIND = _PMOVES / "env.mesh-bind.example"
PATTERNS_YAML = _REPO / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
PROVIDER_CATALOG = _PMOVES / "config" / "provider_catalog.yaml"
MODEL_STRENGTHS = _PMOVES / "config" / "model_strengths_seed.yaml"
TENSORZERO_TOML = _PMOVES / "tensorzero" / "config" / "tensorzero.toml"


# ===========================================================================
# env.mesh-bind.example
# ===========================================================================


class TestEnvMeshBindExample:
    """Validate structure of the new env.mesh-bind.example file."""

    def test_file_exists(self) -> None:
        """The reviewed mesh-bind file must exist after the PR."""
        assert ENV_MESH_BIND.exists(), f"{ENV_MESH_BIND} not found"

    def test_no_active_bind_overrides(self) -> None:
        """All VAR=0.0.0.0 override lines must be commented out.

        The file is intentionally a template; no live overrides should be
        committed into the repo.
        """
        active_bind_pattern = re.compile(r"^\s*\w+_BIND\s*=\s*0\.0\.0\.0", re.MULTILINE)
        content = ENV_MESH_BIND.read_text()
        matches = active_bind_pattern.findall(content)
        assert matches == [], (
            f"Active (uncommented) 0.0.0.0 bind overrides found: {matches}"
        )

    def test_control_plane_services_present_as_commented_entries(self) -> None:
        """Core control-plane services must appear (commented) in the file."""
        content = ENV_MESH_BIND.read_text()
        for service_var in (
            "KONG_PROXY_BIND",
            "AGENT_ZERO_BIND",
            "TENSORZERO_BIND",
            "FLUTE_BIND",
        ):
            assert service_var in content, f"{service_var} missing from {ENV_MESH_BIND.name}"

    def test_never_widen_services_present_but_not_activated(self) -> None:
        """High-risk services appear in comments but MUST NOT have active entries."""
        never_widen = [
            "SUPABASE_DB_BIND",
            "SUPABASE_AUTH_BIND",
            "KONG_ADMIN_BIND",
            "QDRANT_BIND",
            "MEILISEARCH_BIND",
            "NEO4J_BIND",
            "MINIO_BIND",
            "CLICKHOUSE_BIND",
        ]
        content = ENV_MESH_BIND.read_text()
        for var in never_widen:
            # Must appear somewhere in the file (as a documentation reference)
            assert var in content, f"{var} not documented in {ENV_MESH_BIND.name}"
            # Must NOT appear as an active assignment
            active_pattern = re.compile(rf"^\s*{re.escape(var)}\s*=", re.MULTILINE)
            assert not active_pattern.search(content), (
                f"{var} has an active (non-commented) assignment in {ENV_MESH_BIND.name}"
            )

    def test_mesh_default_services_documented(self) -> None:
        """Services already mesh-default in base compose must be listed."""
        content = ENV_MESH_BIND.read_text()
        for var in ("NATS_BIND", "BOTZ_BIND", "PUBLISHER_DISCORD_BIND", "PMOVES_UI_BIND"):
            assert var in content, f"{var} not documented in {ENV_MESH_BIND.name}"

    def test_file_contains_never_widen_section_header(self) -> None:
        """The 'Never widen' advisory section must be present."""
        content = ENV_MESH_BIND.read_text()
        assert "Never widen" in content or "never widen" in content.lower()

    def test_no_active_assignments_at_all(self) -> None:
        """No line in the file should be an active KEY=VALUE assignment.

        Every override must remain commented out (# prefix).
        """
        for line in ENV_MESH_BIND.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                pytest.fail(
                    f"Unexpected active (non-comment) line in {ENV_MESH_BIND.name!r}: {line!r}"
                )


# ===========================================================================
# patterns.yaml — invidious paths removed
# ===========================================================================


class TestPatternsYamlInvidiousRemoval:
    """Verify that invidious service paths were removed from chitSafePaths."""

    def test_patterns_file_exists(self) -> None:
        assert PATTERNS_YAML.exists(), f"{PATTERNS_YAML} not found"

    def test_invidious_service_path_not_in_chit_safe_paths(self) -> None:
        """pmoves/services/invidious/ must not appear in chitSafePaths after PR."""
        content = PATTERNS_YAML.read_text()
        # Find the chitSafePaths block and ensure the invidious path is gone
        assert "pmoves/services/invidious/" not in content, (
            "pmoves/services/invidious/ still present in patterns.yaml chitSafePaths"
        )

    def test_invidious_unscoped_path_not_in_chit_safe_paths(self) -> None:
        """The bare services/invidious/ path must not appear either."""
        content = PATTERNS_YAML.read_text()
        # The PR removed both `pmoves/services/invidious/` and `services/invidious/`
        assert "services/invidious/" not in content, (
            "services/invidious/ still present in patterns.yaml"
        )

    def test_docker_compose_still_in_chit_safe_paths(self) -> None:
        """docker-compose.yml must still be present (sanity: file not truncated)."""
        content = PATTERNS_YAML.read_text()
        assert "docker-compose.yml" in content

    def test_pr_kits_still_in_chit_safe_paths(self) -> None:
        """pr-kits entry must survive the invidious removal."""
        content = PATTERNS_YAML.read_text()
        assert "pr-kits" in content


# ===========================================================================
# provider_catalog.yaml — strength_ref changed to null
# ===========================================================================


class TestProviderCatalogStrengthRef:
    """Validate the claude_sonnet_4 strength_ref change."""

    def test_provider_catalog_exists(self) -> None:
        assert PROVIDER_CATALOG.exists(), f"{PROVIDER_CATALOG} not found"

    def test_claude_sonnet_4_strength_ref_is_null(self) -> None:
        """After the PR, claude_sonnet_4 model entry must have strength_ref: null."""
        import re as _re
        content = PROVIDER_CATALOG.read_text()

        # Locate the claude_sonnet_4 model block and find its strength_ref line
        # Pattern: find 'strength_ref:' within a reasonable proximity of 'claude_sonnet_4:'
        block_match = _re.search(
            r"claude_sonnet_4:\s*\n(?:.*\n){0,20}?\s*strength_ref:\s*(\S+)",
            content,
        )
        assert block_match is not None, (
            "Could not find claude_sonnet_4 → strength_ref in provider_catalog.yaml"
        )
        strength_ref_value = block_match.group(1).rstrip("#").strip()
        assert strength_ref_value == "null", (
            f"claude_sonnet_4 strength_ref expected 'null', got {strength_ref_value!r}"
        )

    def test_claude_sonnet_4_model_block_still_exists(self) -> None:
        """The model entry itself (claude_sonnet_4:) must still exist in catalog."""
        content = PROVIDER_CATALOG.read_text()
        assert "claude_sonnet_4:" in content, (
            "claude_sonnet_4 model block missing from provider_catalog.yaml"
        )

    def test_strength_ref_not_pointing_to_removed_seed_entry(self) -> None:
        """strength_ref must not reference the now-absent model_strengths_seed entry."""
        content = PROVIDER_CATALOG.read_text()
        # The removed value was 'claude_sonnet_4' as a seed reference
        # Ensure the strength_ref line specifically does NOT say 'claude_sonnet_4'
        # while being a non-null value (it should be null now)
        bad_pattern = re.compile(
            r"strength_ref:\s*claude_sonnet_4(?!\w)"  # claude_sonnet_4 as a bare value
        )
        assert not bad_pattern.search(content), (
            "strength_ref still points to the removed claude_sonnet_4 seed entry"
        )


# ===========================================================================
# model_strengths_seed.yaml — claude_sonnet_4 removed
# ===========================================================================


class TestModelStrengthsSeedRemoval:
    """Verify claude_sonnet_4 was removed from the strengths seed file."""

    def test_model_strengths_file_exists(self) -> None:
        assert MODEL_STRENGTHS.exists(), f"{MODEL_STRENGTHS} not found"

    def test_claude_sonnet_4_not_in_model_strengths(self) -> None:
        """The claude_sonnet_4 top-level key must not exist after the PR."""
        content = MODEL_STRENGTHS.read_text()
        # Look for 'claude_sonnet_4:' as a top-level YAML key (indented under models:)
        assert "claude_sonnet_4:" not in content, (
            "claude_sonnet_4 still present in model_strengths_seed.yaml"
        )

    def test_model_strengths_still_has_other_entries(self) -> None:
        """Sanity: other model entries must still be present (file not truncated)."""
        content = MODEL_STRENGTHS.read_text()
        assert "models:" in content
        # A known surviving entry from the file
        assert "pmoves-chit-text-7b:" in content

    def test_removed_entry_notes_not_present(self) -> None:
        """The craftsman notes string that belonged to claude_sonnet_4 must be gone."""
        content = MODEL_STRENGTHS.read_text()
        assert "The craftsman" not in content, (
            "claude_sonnet_4 'craftsman' notes still found in model_strengths_seed.yaml"
        )

    def test_strength_scores_for_claude_sonnet_4_not_present(self) -> None:
        """Specific score values unique to the removed entry must be absent.

        The removed entry had cost_efficiency_score: 5.5 and preferred_functions
        that included coding_claude_fallback — used to validate uniqueness.
        """
        content = MODEL_STRENGTHS.read_text()
        # 'coding_claude_fallback' was in the preferred_functions of claude_sonnet_4
        # Verify it's not still appearing in a strengths context
        # (Note: it may still appear in provider_catalog — we only check this file)
        # Use the unique combination of cost_efficiency_score: 5.5 near claude_sonnet_4
        # Check that the unique note is gone as the best signal
        assert "The craftsman — Anthropic's balanced powerhouse" not in content


# ===========================================================================
# tensorzero.toml — OTLP export disabled
# ===========================================================================


class TestTensorzeroOtlpDisabled:
    """Verify OTLP export was commented out in tensorzero.toml."""

    def test_tensorzero_toml_exists(self) -> None:
        assert TENSORZERO_TOML.exists(), f"{TENSORZERO_TOML} not found"

    def test_otlp_traces_section_is_not_active(self) -> None:
        """[gateway.export.otlp.traces] must not be an active TOML section."""
        content = TENSORZERO_TOML.read_text()
        # Active section header (not commented)
        active_pattern = re.compile(r"^\s*\[gateway\.export\.otlp\.traces\]", re.MULTILINE)
        assert not active_pattern.search(content), (
            "[gateway.export.otlp.traces] is still an active section in tensorzero.toml"
        )

    def test_otlp_traces_section_present_as_comment(self) -> None:
        """The OTLP config must still exist as a comment (easy re-enable path)."""
        content = TENSORZERO_TOML.read_text()
        # Should appear as a commented-out line
        commented_pattern = re.compile(r"#\s*\[gateway\.export\.otlp\.traces\]")
        assert commented_pattern.search(content), (
            "Commented [gateway.export.otlp.traces] line not found in tensorzero.toml"
        )

    def test_otlp_disabled_comment_present(self) -> None:
        """An explanatory comment about the disabled status must exist."""
        content = TENSORZERO_TOML.read_text()
        # PR added: "# OTLP export disabled — re-enable when OTel collector is running"
        assert "OTLP export disabled" in content, (
            "Explanatory OTLP disabled comment not found in tensorzero.toml"
        )

    def test_gateway_observability_still_enabled(self) -> None:
        """Core observability (ClickHouse async writes) must remain enabled."""
        content = TENSORZERO_TOML.read_text()
        # The [gateway.observability] section with enabled = true must still be active
        assert "[gateway.observability]" in content
        # enabled = true must appear as an active (non-commented) line
        active_enabled = re.compile(r"^\s*enabled\s*=\s*true", re.MULTILINE)
        assert active_enabled.search(content), (
            "gateway.observability enabled = true not found (may have been commented out)"
        )

    def test_no_active_otlp_enabled_line(self) -> None:
        """'enabled = true' must not appear inside an active OTLP export block."""
        content = TENSORZERO_TOML.read_text()
        lines = content.splitlines()
        in_otlp_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped == "[gateway.export.otlp.traces]":
                in_otlp_block = True
            elif stripped.startswith("[") and in_otlp_block:
                in_otlp_block = False
            if in_otlp_block and re.match(r"enabled\s*=\s*true", stripped):
                pytest.fail(
                    "Found 'enabled = true' inside an active [gateway.export.otlp.traces] block"
                )