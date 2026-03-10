"""
Test NATS configuration consistency across PMOVES.AI.

Validates that:
1. NATS service is properly configured
2. All services reference NATS_URL consistently
3. Documentation is up to date
4. NATS subjects follow naming conventions
"""

import re
import pytest
from pathlib import Path

from _smoke_helpers import grep_file, grep_count, grep_context, PROJECT_ROOT, PMOVES_DIR


NATS_CONFIG_DOC = PMOVES_DIR / "docs" / "NATS_CONFIGURATION.md"
COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"


@pytest.mark.smoke
def test_nats_documentation_exists() -> None:
    """Verify NATS configuration documentation exists."""
    assert NATS_CONFIG_DOC.exists(), (
        "NATS_CONFIGURATION.md should exist in pmoves/docs/"
    )

    content = NATS_CONFIG_DOC.read_text()
    required_sections = [
        "## Overview",
        "## Standard Configuration",
        "## Environment Variable Sources",
        "## Common Subjects",
        "## Debugging",
    ]

    for section in required_sections:
        assert section in content, (
            f"NATS_CONFIGURATION.md should have section: {section}"
        )


@pytest.mark.smoke
def test_nats_service_exists() -> None:
    """Verify NATS service is defined in docker-compose.yml."""
    count = grep_count(COMPOSE_FILE, r"^  nats:")
    assert count > 0, "NATS service should be defined in docker-compose.yml"


@pytest.mark.smoke
def test_nats_service_has_documentation_header() -> None:
    """Verify NATS service has documentation comment header."""
    # Check for comment header above the nats service definition.
    # The comment may be several lines above the service key, so search
    # with enough context (up to 15 lines before the service definition).
    output = grep_context(COMPOSE_FILE, r"^  nats:", before=15)
    assert output, "NATS service not found"

    assert "NATS Message Bus" in output or "NATS provides" in output, (
        "NATS service should have documentation comment header"
    )


@pytest.mark.smoke
def test_nats_url_defined_in_tier_files() -> None:
    """Verify NATS_URL is defined in tier env files (not env.shared)."""
    tier_agent = PMOVES_DIR / "env.tier-agent"
    tier_worker = PMOVES_DIR / "env.tier-worker"

    agent_matches = grep_file(tier_agent, r"^NATS_URL=") if tier_agent.exists() else []
    worker_matches = grep_file(tier_worker, r"^NATS_URL=") if tier_worker.exists() else []

    assert agent_matches or worker_matches, (
        "NATS_URL should be defined in env.tier-agent and/or env.tier-worker"
    )


@pytest.mark.smoke
def test_nats_url_has_credentials() -> None:
    """Verify NATS_URL includes authentication credentials in tier files."""
    for tier_file in ["env.tier-agent", "env.tier-worker", "env.tier-ui"]:
        path = PMOVES_DIR / tier_file
        if not path.exists():
            continue
        matches = grep_file(path, r"^NATS_URL=")
        if matches:
            url = matches[0].split("=", 1)[1]
            assert "nats://" in url, (
                f"NATS_URL in {tier_file} should use nats:// protocol, got: {url}"
            )
            assert "@" in url, (
                f"NATS_URL in {tier_file} should include credentials (user:pass@host), got: {url}"
            )


@pytest.mark.smoke
def test_services_have_consistent_nats_documentation() -> None:
    """Verify all services with NATS_URL have consistent documentation comments."""
    matches = grep_file(COMPOSE_FILE, r"NATS_URL.*from env\.")
    if not matches:
        pytest.skip("No NATS_URL references with env documentation found")

    inconsistent = []
    for line in matches:
        if line.strip() and not line.strip().startswith("#"):
            if "from env.tier-" in line:
                tier = line.split("from env.")[1].split(" ")[0] if "from env." in line else ""
                if tier:
                    if "env.tier-agent" not in line and "env.tier-media" not in line and "env.tier-worker" not in line:
                        inconsistent.append(line.strip())

    assert not inconsistent, (
        f"Some NATS_URL comments may reference incorrect tier files: {inconsistent}"
    )


@pytest.mark.smoke
def test_nats_subjects_follow_naming_convention() -> None:
    """Verify NATS subjects in documentation follow naming conventions."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    content = NATS_CONFIG_DOC.read_text()

    subjects = re.findall(r'`([a-z][a-z0-9_]*\.[^\s]+)`', content)

    for subject in subjects:
        assert subject.islower() or ">" in subject, (
            f"NATS subject should be lowercase: {subject}"
        )

        if ".v" in subject and not subject.endswith(">"):
            parts = subject.rsplit(".", 1)
            assert parts[-1].startswith("v"), (
                f"NATS subject version should use vN format: {subject}"
            )


@pytest.mark.smoke
def test_nats_has_correct_ports_exposed() -> None:
    """Verify NATS exposes the correct ports."""
    # Use a wider context window to capture ports section (may be
    # separated from the service key by anchor expansion).
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=25)
    assert output, "NATS service not found"

    assert "4222:4222" in output or "${NATS_PORT" in output, (
        "NATS should expose client port 4222"
    )


@pytest.mark.smoke
def test_nats_includes_jetstream() -> None:
    """Verify NATS is configured with JetStream enabled."""
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=10)
    assert output, "NATS service not found"

    assert "-js" in output or "jetstream" in output.lower(), (
        "NATS should have JetStream enabled (-js flag)"
    )


@pytest.mark.smoke
def test_nats_has_healthcheck() -> None:
    """Verify NATS service has a healthcheck configured.

    The healthcheck may be defined directly on the service block or
    inherited from a YAML anchor (e.g. *tier-data-hardened).  We search
    a wide window (30 lines after the service key) to capture both cases.
    """
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=35)
    assert output, "NATS service not found"

    has_healthcheck = "healthcheck:" in output.lower()

    # Also check if it might come from the anchor — look for the anchor
    # definition in the compose file
    if not has_healthcheck:
        anchor_output = grep_context(COMPOSE_FILE, r"tier-data-hardened", after=15)
        if anchor_output:
            has_healthcheck = "healthcheck:" in anchor_output.lower()

    assert has_healthcheck, (
        "NATS should have a healthcheck configured (directly or via anchor)"
    )

    assert "8222" in output or "varz" in output, (
        "NATS healthcheck should verify monitoring endpoint (8222/varz)"
    )


@pytest.mark.smoke
def test_critical_services_depend_on_nats() -> None:
    """Verify critical services that need NATS have proper depends_on."""
    critical_services = [
        "agent-zero",
        "deepresearch",
        "supaserch",
        "publisher-discord",
    ]

    missing_deps = []
    for service in critical_services:
        # Use a wide context window to capture depends_on from the
        # service block (may be after environment/volumes sections)
        output = grep_context(COMPOSE_FILE, rf"^  {service}:", after=50)
        if not output:
            continue  # Service may not exist in this compose file

        if "NATS_URL" in output or "NATS" in output:
            has_nats_dep = "nats:" in output and "depends_on:" in output
            # Also accept nats dependency via nats-init (implies nats)
            has_nats_init_dep = "nats-init:" in output
            if not has_nats_dep and not has_nats_init_dep:
                missing_deps.append(service)

    assert not missing_deps, (
        f"Services using NATS_URL but missing depends_on nats: {missing_deps}"
    )


@pytest.mark.smoke
def test_nats_on_correct_networks() -> None:
    """Verify NATS is on the correct Docker networks.

    Network assignment may come from a YAML anchor or be listed directly.
    Search a wide context window to capture both.
    """
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=25)

    if output:
        assert "pmoves_bus" in output or "pmoves" in output, (
            "NATS should be on pmoves_bus or pmoves network"
        )


@pytest.mark.smoke
def test_no_hardcoded_nats_urls_in_compose() -> None:
    """Verify docker-compose.yml doesn't have hardcoded NATS URLs (should use ${NATS_URL})."""
    matches = grep_file(COMPOSE_FILE, r"NATS_URL=nats://")

    if matches:
        hardcoded = [line for line in matches if "${" not in line]
        assert not hardcoded, (
            f"Found hardcoded NATS_URL in docker-compose.yml:\n"
            + "\n".join(hardcoded)
            + "\nUse ${NATS_URL:-nats://nats:pmoves@nats:4222} instead."
        )


@pytest.mark.smoke
def test_nats_documentation_matches_env_shared() -> None:
    """Verify NATS documentation references correct credential format."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    doc_content = NATS_CONFIG_DOC.read_text()

    # Documentation should reference the authenticated NATS URL format
    assert "nats://" in doc_content, (
        "NATS documentation should reference nats:// protocol"
    )
    assert "pmoves" in doc_content, (
        "NATS documentation should reference the pmoves credentials"
    )
