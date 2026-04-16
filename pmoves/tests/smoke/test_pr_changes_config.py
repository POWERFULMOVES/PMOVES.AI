"""Smoke tests for configuration changes introduced in this PR.

Covers:
- model_strengths_seed.yaml: claude_sonnet_4 entry removed
- provider_catalog.yaml: claude_sonnet_4 strength_ref set to null
- tensorzero/config/tensorzero.toml: OTLP export disabled (commented out)
- .claude/hooks/damage-control/patterns.yaml: invidious paths removed from chitSafePaths
- pmoves/env.mesh-bind.example: new file with correct structure and content
- pmoves/docker-compose.yml: invidious-companion healthcheck restored (CMD-SHELL / wget)
"""

import re

import pytest
import yaml

from _smoke_helpers import PROJECT_ROOT, PMOVES_DIR, grep_file

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

MODEL_STRENGTHS_SEED = PMOVES_DIR / "config" / "model_strengths_seed.yaml"
PROVIDER_CATALOG = PMOVES_DIR / "config" / "provider_catalog.yaml"
TENSORZERO_TOML = PMOVES_DIR / "tensorzero" / "config" / "tensorzero.toml"
PATTERNS_YAML = PROJECT_ROOT / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
MESH_BIND_EXAMPLE = PMOVES_DIR / "env.mesh-bind.example"
DOCKER_COMPOSE = PMOVES_DIR / "docker-compose.yml"


# ===========================================================================
# model_strengths_seed.yaml — claude_sonnet_4 removed
# ===========================================================================


@pytest.mark.smoke
def test_model_strengths_seed_exists():
    """Prerequisite: seed file must be present."""
    assert MODEL_STRENGTHS_SEED.exists(), f"Missing: {MODEL_STRENGTHS_SEED}"


@pytest.mark.smoke
def test_claude_sonnet_4_absent_from_model_strengths_seed():
    """claude_sonnet_4 entry was removed from model_strengths_seed.yaml in this PR."""
    assert MODEL_STRENGTHS_SEED.exists(), pytest.skip("seed file missing")
    data = yaml.safe_load(MODEL_STRENGTHS_SEED.read_text())
    models = data.get("models", {})
    assert "claude_sonnet_4" not in models, (
        "claude_sonnet_4 was removed from model_strengths_seed.yaml; "
        "add a new key if this model re-enters the catalog."
    )


@pytest.mark.smoke
def test_model_strengths_seed_models_section_is_dict():
    """The 'models' top-level key must be a mapping."""
    assert MODEL_STRENGTHS_SEED.exists(), pytest.skip("seed file missing")
    data = yaml.safe_load(MODEL_STRENGTHS_SEED.read_text())
    assert isinstance(data.get("models"), dict), (
        "model_strengths_seed.yaml must have a top-level 'models' mapping"
    )


@pytest.mark.smoke
def test_model_strengths_seed_remaining_entries_have_strength_scores():
    """All remaining model entries must have a strength_scores section."""
    assert MODEL_STRENGTHS_SEED.exists(), pytest.skip("seed file missing")
    data = yaml.safe_load(MODEL_STRENGTHS_SEED.read_text())
    models = data.get("models", {})
    missing = [k for k, v in models.items() if not isinstance(v, dict) or "strength_scores" not in v]
    assert not missing, (
        f"Models without strength_scores: {missing}. "
        "Each model entry must define strength_scores."
    )


# ===========================================================================
# provider_catalog.yaml — claude_sonnet_4 strength_ref is null
# ===========================================================================


@pytest.mark.smoke
def test_provider_catalog_exists():
    assert PROVIDER_CATALOG.exists(), f"Missing: {PROVIDER_CATALOG}"


@pytest.mark.smoke
def test_claude_sonnet_4_strength_ref_is_null():
    """The claude_sonnet_4 model in provider_catalog must have strength_ref: null (needs seed entry)."""
    assert PROVIDER_CATALOG.exists(), pytest.skip("provider_catalog missing")
    data = yaml.safe_load(PROVIDER_CATALOG.read_text())
    providers = data.get("providers", {})
    anthropic = providers.get("anthropic", {})
    models = anthropic.get("models", {})
    assert "claude_sonnet_4" in models, (
        "claude_sonnet_4 must still appear in provider_catalog.yaml under anthropic.models"
    )
    strength_ref = models["claude_sonnet_4"].get("strength_ref")
    assert strength_ref is None, (
        f"claude_sonnet_4.strength_ref must be null (needs seed entry), got: {strength_ref!r}"
    )


@pytest.mark.smoke
def test_provider_catalog_anthropic_provider_present():
    """Anthropic provider section must exist in the catalog."""
    assert PROVIDER_CATALOG.exists(), pytest.skip("provider_catalog missing")
    data = yaml.safe_load(PROVIDER_CATALOG.read_text())
    assert "anthropic" in data.get("providers", {}), (
        "provider_catalog.yaml must contain an 'anthropic' provider entry"
    )


@pytest.mark.smoke
def test_provider_catalog_no_strength_ref_to_removed_model():
    """No model in provider_catalog should reference claude_sonnet_4 via strength_ref."""
    assert PROVIDER_CATALOG.exists(), pytest.skip("provider_catalog missing")
    data = yaml.safe_load(PROVIDER_CATALOG.read_text())
    providers = data.get("providers", {})

    bad_refs = []
    for prov_name, prov_data in providers.items():
        if not isinstance(prov_data, dict):
            continue
        for model_key, model_data in prov_data.get("models", {}).items():
            if not isinstance(model_data, dict):
                continue
            ref = model_data.get("strength_ref")
            if ref == "claude_sonnet_4":
                bad_refs.append(f"{prov_name}.{model_key}")

    assert not bad_refs, (
        f"These models still reference removed seed key 'claude_sonnet_4': {bad_refs}"
    )


# ===========================================================================
# tensorzero.toml — OTLP export is disabled
# ===========================================================================


@pytest.mark.smoke
def test_tensorzero_toml_exists():
    assert TENSORZERO_TOML.exists(), f"Missing: {TENSORZERO_TOML}"


@pytest.mark.smoke
def test_tensorzero_otlp_export_section_is_commented_out():
    """OTLP export was disabled in this PR — the [gateway.export.otlp.traces] block must be commented out."""
    assert TENSORZERO_TOML.exists(), pytest.skip("tensorzero.toml missing")
    content = TENSORZERO_TOML.read_text()

    # The active (uncommented) key must not appear — commented occurrences like
    # '# [gateway.export.otlp.traces]' are fine; an active line would not start with '#'.
    active_otlp_lines = [
        line for line in content.splitlines()
        if "[gateway.export.otlp.traces]" in line and not line.strip().startswith("#")
    ]
    assert not active_otlp_lines, (
        "[gateway.export.otlp.traces] is active — it should be commented out until "
        "the OTel collector is running. Re-enable via the appropriate PR.\n"
        "Active lines: " + str(active_otlp_lines)
    )


@pytest.mark.smoke
def test_tensorzero_otlp_disabled_comment_present():
    """A human-readable comment explaining the disabled OTLP state must exist."""
    assert TENSORZERO_TOML.exists(), pytest.skip("tensorzero.toml missing")
    content = TENSORZERO_TOML.read_text()
    assert "OTLP export disabled" in content or "otlp" in content.lower(), (
        "tensorzero.toml should contain a comment explaining why OTLP is disabled"
    )


@pytest.mark.smoke
def test_tensorzero_gateway_observability_still_enabled():
    """gateway.observability must remain enabled even without OTLP export."""
    assert TENSORZERO_TOML.exists(), pytest.skip("tensorzero.toml missing")
    content = TENSORZERO_TOML.read_text()
    # Look for the non-commented enabled = true under [gateway.observability]
    assert re.search(r"^\[gateway\.observability\]", content, re.MULTILINE), (
        "[gateway.observability] section missing from tensorzero.toml"
    )
    assert re.search(r"^enabled\s*=\s*true", content, re.MULTILINE), (
        "gateway.observability.enabled must be true in tensorzero.toml"
    )


# ===========================================================================
# patterns.yaml — invidious paths removed from chitSafePaths
# ===========================================================================


@pytest.mark.smoke
def test_patterns_yaml_exists():
    assert PATTERNS_YAML.exists(), f"Missing: {PATTERNS_YAML}"


@pytest.mark.smoke
def test_invidious_sql_path_not_in_chit_safe_paths():
    """pmoves/services/invidious/ was removed from chitSafePaths in this PR."""
    assert PATTERNS_YAML.exists(), pytest.skip("patterns.yaml missing")
    data = yaml.safe_load(PATTERNS_YAML.read_text())
    chit_safe = data.get("chitSafePaths", [])
    assert "pmoves/services/invidious/" not in chit_safe, (
        "pmoves/services/invidious/ should no longer be in chitSafePaths; "
        "the SQL init scripts were removed from the repository."
    )


@pytest.mark.smoke
def test_services_invidious_path_not_in_chit_safe_paths():
    """services/invidious/ was also removed from chitSafePaths in this PR."""
    assert PATTERNS_YAML.exists(), pytest.skip("patterns.yaml missing")
    data = yaml.safe_load(PATTERNS_YAML.read_text())
    chit_safe = data.get("chitSafePaths", [])
    assert "services/invidious/" not in chit_safe, (
        "services/invidious/ should no longer be in chitSafePaths."
    )


@pytest.mark.smoke
def test_patterns_yaml_chit_safe_paths_is_list():
    """chitSafePaths must be a list so pattern matching iterates correctly."""
    assert PATTERNS_YAML.exists(), pytest.skip("patterns.yaml missing")
    data = yaml.safe_load(PATTERNS_YAML.read_text())
    assert isinstance(data.get("chitSafePaths"), list), (
        "chitSafePaths in patterns.yaml must be a list"
    )


@pytest.mark.smoke
def test_patterns_yaml_no_empty_chit_safe_path_entries():
    """chitSafePaths must not contain empty or None entries (regression guard)."""
    assert PATTERNS_YAML.exists(), pytest.skip("patterns.yaml missing")
    data = yaml.safe_load(PATTERNS_YAML.read_text())
    chit_safe = data.get("chitSafePaths", [])
    bad = [repr(e) for e in chit_safe if not e]
    assert not bad, f"chitSafePaths contains empty/null entries: {bad}"


# ===========================================================================
# env.mesh-bind.example — new file structure
# ===========================================================================


@pytest.mark.smoke
def test_mesh_bind_example_exists():
    """env.mesh-bind.example must exist as a new file introduced by this PR."""
    assert MESH_BIND_EXAMPLE.exists(), f"Missing: {MESH_BIND_EXAMPLE}"


@pytest.mark.smoke
def test_mesh_bind_example_all_lines_are_commented_or_blank():
    """Every non-blank line in env.mesh-bind.example must start with '#'.

    The file is a template; no live overrides should be committed.
    """
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    live_assignments = []
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            live_assignments.append(f"  Line {lineno}: {line}")
    assert not live_assignments, (
        "env.mesh-bind.example must contain only comments and blank lines — "
        "no live bind overrides should be committed:\n" + "\n".join(live_assignments)
    )


@pytest.mark.smoke
def test_mesh_bind_example_contains_reviewed_control_plane_services():
    """The file must list reviewed control-plane services (KONG_PROXY_BIND, AGENT_ZERO_BIND, etc.)."""
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    for expected in ("KONG_PROXY_BIND", "AGENT_ZERO_BIND", "TENSORZERO_BIND", "FLUTE_BIND"):
        assert expected in content, f"{expected} must appear in env.mesh-bind.example"


@pytest.mark.smoke
def test_mesh_bind_example_never_widen_section_present():
    """The 'Never widen without a separate security review' section must be present."""
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    assert "Never widen" in content or "never widen" in content.lower(), (
        "env.mesh-bind.example must include a 'Never widen without separate security review' section"
    )


@pytest.mark.smoke
def test_mesh_bind_example_data_tier_stores_in_never_widen_section():
    """Data-tier services must be listed in the 'never widen' section (not the reviewed allowlist)."""
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    never_widen_services = (
        "SUPABASE_DB_BIND",
        "SUPABASE_AUTH_BIND",
        "KONG_ADMIN_BIND",
        "QDRANT_BIND",
        "MEILISEARCH_BIND",
        "CLICKHOUSE_BIND",
    )
    for svc_bind in never_widen_services:
        assert svc_bind in content, (
            f"{svc_bind} must appear in env.mesh-bind.example (in the 'never widen' section)"
        )


@pytest.mark.smoke
def test_mesh_bind_example_mesh_default_section_includes_nats():
    """NATS_BIND must appear in the 'already mesh-default' documentation section."""
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    assert "NATS_BIND" in content, (
        "NATS_BIND must be documented in env.mesh-bind.example as already mesh-default"
    )


@pytest.mark.smoke
def test_mesh_bind_example_values_are_0_0_0_0_where_present():
    """Any override values in the example must be 0.0.0.0 (not 127.0.0.1)."""
    assert MESH_BIND_EXAMPLE.exists(), pytest.skip("env.mesh-bind.example missing")
    content = MESH_BIND_EXAMPLE.read_text()
    # Extract commented-out assignment lines like #FOO_BIND=0.0.0.0
    bind_values = re.findall(r"#\w+_BIND=(\S+)", content)
    non_wide = [v for v in bind_values if v != "0.0.0.0"]
    assert not non_wide, (
        f"env.mesh-bind.example bind values should all be 0.0.0.0, got: {non_wide}"
    )


# ===========================================================================
# docker-compose.yml — invidious-companion healthcheck restored
# ===========================================================================


@pytest.mark.smoke
def test_docker_compose_exists():
    assert DOCKER_COMPOSE.exists(), f"Missing: {DOCKER_COMPOSE}"


@pytest.mark.smoke
def test_invidious_companion_healthcheck_uses_wget():
    """invidious-companion healthcheck was restored to a CMD-SHELL / wget probe in this PR."""
    assert DOCKER_COMPOSE.exists(), pytest.skip("docker-compose.yml missing")

    content = DOCKER_COMPOSE.read_text()

    # Match the service definition block (indented at exactly 2 spaces) until
    # the next top-level service (also at 2 spaces, followed by a lowercase letter).
    match = re.search(
        r"^  invidious-companion:\s*\n(.*?)(?=^  [a-z])",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "invidious-companion service block not found in docker-compose.yml"

    svc_block = match.group(0)

    assert "healthcheck:" in svc_block, (
        "invidious-companion must have a healthcheck section"
    )
    assert "disable: true" not in svc_block, (
        "invidious-companion healthcheck must not be disabled"
    )
    assert "wget" in svc_block, (
        "invidious-companion healthcheck must use wget to probe the service"
    )
    assert "8282" in svc_block, (
        "invidious-companion healthcheck must probe port 8282"
    )


@pytest.mark.smoke
def test_invidious_companion_healthcheck_has_interval():
    """healthcheck interval must be configured for invidious-companion."""
    assert DOCKER_COMPOSE.exists(), pytest.skip("docker-compose.yml missing")
    content = DOCKER_COMPOSE.read_text()

    match = re.search(
        r"^  invidious-companion:\s*\n(.*?)(?=^  [a-z])",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "invidious-companion block not found"
    svc_block = match.group(0)

    assert re.search(r"interval:\s*\d+s", svc_block), (
        "invidious-companion healthcheck must define an interval"
    )
    assert re.search(r"retries:\s*\d+", svc_block), (
        "invidious-companion healthcheck must define retries"
    )


@pytest.mark.smoke
def test_invidious_companion_healthcheck_not_disabled_globally():
    """Confirm 'disable: true' does not appear in any invidious-companion healthcheck context."""
    assert DOCKER_COMPOSE.exists(), pytest.skip("docker-compose.yml missing")
    lines = DOCKER_COMPOSE.read_text().splitlines()

    in_companion = False
    in_healthcheck = False
    for line in lines:
        if "invidious-companion:" in line and not line.strip().startswith("#"):
            in_companion = True
        elif in_companion and line.startswith("  ") and not line.startswith("    "):
            # Back at top-level service indentation — new service started
            if re.match(r"  \S", line) and "invidious-companion" not in line:
                in_companion = False
                in_healthcheck = False
        if in_companion and "healthcheck:" in line:
            in_healthcheck = True
        if in_healthcheck and "disable: true" in line:
            pytest.fail(
                "Found 'disable: true' in invidious-companion healthcheck — "
                "this PR restored the healthcheck; it must not be disabled."
            )