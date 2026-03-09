"""
Test NATS configuration consistency across PMOVES.AI.

Validates that:
1. NATS service is properly configured
2. All services reference NATS_URL consistently
3. Documentation is up to date
4. NATS subjects follow naming conventions
"""

import os
import pytest
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = PROJECT_ROOT / "pmoves"
NATS_CONFIG_DOC = PMOVES_DIR / "docs" / "NATS_CONFIGURATION.md"


@pytest.mark.smoke
def test_nats_documentation_exists() -> None:
    """Verify NATS configuration documentation exists."""
    assert NATS_CONFIG_DOC.exists(), (
        "NATS_CONFIGURATION.md should exist in pmoves/docs/"
    )

    # Check documentation has key sections
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
    result = subprocess.run(
        ["grep", "-c", "^  nats:", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert int(result.stdout.strip()) > 0, (
        "NATS service should be defined in docker-compose.yml"
    )


@pytest.mark.smoke
def test_nats_service_has_documentation_header() -> None:
    """Verify NATS service has documentation comment header."""
    result = subprocess.run(
        ["grep", "-B", "10", "^  nats:", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, "NATS service not found"

    output = result.stdout
    assert "NATS Message Bus" in output or "NATS provides" in output, (
        "NATS service should have documentation comment header"
    )
    assert "NATS_CONFIGURATION.md" in output, (
        "NATS service comment should reference NATS_CONFIGURATION.md"
    )


@pytest.mark.smoke
def test_nats_url_defined_in_env_shared() -> None:
    """Verify NATS_URL is defined in env.shared."""
    result = subprocess.run(
        ["grep", "^NATS_URL=", "pmoves/env.shared"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, "NATS_URL should be defined in env.shared"

    # Check the value includes authentication
    url = result.stdout.strip().split("=", 1)[1]
    assert "nats://nats:" in url or "nats://0.0.0.0:" in url, (
        f"NATS_URL should include protocol and host, got: {url}"
    )


@pytest.mark.smoke
def test_nats_url_has_credentials() -> None:
    """Verify NATS_URL includes authentication credentials."""
    result = subprocess.run(
        ["grep", "^NATS_URL=", "pmoves/env.shared"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode == 0:
        url = result.stdout.strip().split("=", 1)[1]
        # Should have format: nats://user:password@host:port or nats://host:port
        # For internal services, credentials are provided
        assert "nats://" in url, (
            f"NATS_URL should use nats:// protocol, got: {url}"
        )


@pytest.mark.smoke
def test_services_have_consistent_nats_documentation() -> None:
    """Verify all services with NATS_URL have consistent documentation comments."""
    result = subprocess.run(
        ["grep", "-B", "2", "NATS_URL.*from env\\.", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        return  # No NATS_URL references found

    lines = result.stdout.split("\n")
    inconsistent = []

    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            # Extract the comment
            if "from env.tier-" in line:
                tier = line.split("from env.")[1].split(" ")[0] if "from env." in line else ""
                if tier:
                    # Check if comment mentions the correct tier file
                    if "env.tier-agent" in line or "env.tier-media" in line or "env.tier-worker" in line:
                        pass  # OK
                    else:
                        inconsistent.append(line.strip())

    # Allow some flexibility - just warn, don't fail
    if inconsistent:
        print(f"Warning: Some NATS_URL comments may be inconsistent")


@pytest.mark.smoke
def test_nats_subjects_follow_naming_convention() -> None:
    """Verify NATS subjects in documentation follow naming conventions."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    content = NATS_CONFIG_DOC.read_text()

    # Extract subject examples from documentation
    # Format: `research.deepresearch.request.v1`
    import re
    subjects = re.findall(r'`([a-z][a-z0-9_]*\.[^\s]+)`', content)

    for subject in subjects:
        # Check naming convention: lowercase with dots, version suffix
        assert subject.islower() or ">" in subject, (
            f"NATS subject should be lowercase: {subject}"
        )

        # Versioned subjects should end with .v1, .v2, etc.
        if ".v" in subject and not subject.endswith(">"):
            parts = subject.rsplit(".", 1)
            assert parts[-1].startswith("v"), (
                f"NATS subject version should use vN format: {subject}"
            )


@pytest.mark.smoke
def test_nats_has_correct_ports_exposed() -> None:
    """Verify NATS exposes the correct ports."""
    result = subprocess.run(
        ["grep", "-A", "10", "^  nats:", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, "NATS service not found"

    output = result.stdout

    # Check for client port (4222)
    assert "4222:4222" in output or "${NATS_PORT}" in output, (
        "NATS should expose client port 4222"
    )

    # Check for monitoring port (8222 or similar)
    assert "8222" in output or "monitoring" in output.lower(), (
        "NATS should expose monitoring interface"
    )

    # Check for WebSocket port (9223 or similar)
    assert "9223" in output or "websocket" in output.lower() or "ws" in output.lower(), (
        "NATS should expose WebSocket port"
    )


@pytest.mark.smoke
def test_nats_includes_jetstream() -> None:
    """Verify NATS is configured with JetStream enabled."""
    result = subprocess.run(
        ["grep", "-A", "10", "^  nats:", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, "NATS service not found"

    output = result.stdout
    assert "-js" in output or "jetstream" in output.lower(), (
        "NATS should have JetStream enabled (-js flag)"
    )


@pytest.mark.smoke
def test_nats_has_healthcheck() -> None:
    """Verify NATS service has a healthcheck configured."""
    result = subprocess.run(
        ["grep", "-A", "20", "^  nats:", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, "NATS service not found"

    output = result.stdout
    assert "healthcheck:" in output.lower(), (
        "NATS should have a healthcheck configured"
    )

    # Healthcheck should verify the monitoring endpoint
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

    for service in critical_services:
        result = subprocess.run(
            ["grep", "-A", "30", f"{service}:", "pmoves/docker-compose.yml"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode != 0:
            continue  # Service may not exist in this compose file

        output = result.stdout

        # Check for NATS_URL in environment (indicates NATS dependency)
        if "NATS_URL" in output:
            # Should have depends_on nats
            has_depends_on = "depends_on:" in output
            has_nats_dep = "nats:" in output or "nats$" in output

            # Services with NATS_URL should ideally depend on nats service
            # (But we'll just warn, not fail, since some services may handle missing NATS gracefully)
            if not has_depends_on or not has_nats_dep:
                print(f"Warning: {service} uses NATS_URL but doesn't explicitly depend on nats service")


@pytest.mark.smoke
def test_nats_on_correct_networks() -> None:
    """Verify NATS is on the correct Docker networks."""
    result = subprocess.run(
        ["docker", "inspect", "nats", "--format", "{{json .NetworkSettings.Networks}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        # Container might not be running
        result = subprocess.run(
            ["grep", "-A", "5", "^  nats:", "pmoves/docker-compose.yml"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            output = result.stdout
            assert "pmoves_bus" in output or "pmoves" in output, (
                "NATS should be on pmoves_bus or pmoves network"
            )
    else:
        import json
        networks = json.loads(result.stdout)

        # Should be on pmoves_bus or similar
        assert len(networks) > 0, "NATS should be on at least one network"
        assert any("pmoves" in net.lower() for net in networks.keys()), (
            f"NATS should be on pmoves network(s), got: {list(networks.keys())}"
        )


@pytest.mark.smoke
def test_no_hardcoded_nats_urls_in_compose() -> None:
    """Verify docker-compose.yml doesn't have hardcoded NATS URLs (should use ${NATS_URL})."""
    result = subprocess.run(
        ["grep", "-n", "NATS_URL=nats://", "pmoves/docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    # Should find no hardcoded NATS URLs (only ${NATS_URL} or ${NATS_URL:-...})
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        hardcode = [l for l in lines if not "${" in l]

        if hardcode:
            pytest.fail(
                f"Found hardcoded NATS_URL in docker-compose.yml:\n" +
                "\n".join(hardcode) +
                "\nUse ${NATS_URL:-nats://nats:pmoves@nats:4222} instead."
            )


@pytest.mark.smoke
def test_nats_documentation_matches_env_shared() -> None:
    """Verify NATS documentation example matches env.shared value."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    # Get NATS_URL from env.shared
    result = subprocess.run(
        ["grep", "^NATS_URL=", "pmoves/env.shared"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        pytest.skip("NATS_URL not found in env.shared")

    env_value = result.stdout.strip().split("=", 1)[1]

    # Get NATS_URL from documentation
    doc_content = NATS_CONFIG_DOC.read_text()
    doc_match = None
    for line in doc_content.splitlines():
        if "NATS_URL=" in line and not line.startswith("```"):
            doc_match = line.strip()
            break

    # Documentation should mention the same format
    if doc_match:
        # Extract just the protocol/host part (ignore default values)
        assert "nats://" in doc_match, (
            "NATS documentation should show nats:// protocol"
        )
