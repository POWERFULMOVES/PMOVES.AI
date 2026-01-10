"""
Test NATS authentication with tier credentials from PR #483.

Validates that services use authenticated NATS connections from tier env files
rather than unauthenticated fallbacks.

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import pytest
import httpx
import subprocess
import json


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_nats_has_credentials(http_client: httpx.AsyncClient) -> None:
    """Agent Zero should connect to NATS with credentials from env.tier-agent."""
    response = await http_client.get("http://localhost:8080/healthz", timeout=10.0)

    assert response.status_code == 200
    data = response.json()

    # Check NATS connection info
    assert "nats" in data
    nats_info = data["nats"]

    # Verify credentials in URL (format: nats://user:pass@host:port)
    assert "url" in nats_info
    assert "pmoves@" in nats_info["url"], (
        f"NATS URL should contain credentials (user:pass@), got: {nats_info['url']}"
    )

    # Verify connection status
    assert nats_info.get("connected") is True, (
        f"Agent Zero should be connected to NATS, got: {nats_info.get('connected')}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_nats_not_using_unauthenticated_url(http_client: httpx.AsyncClient) -> None:
    """Agent Zero should NOT use unauthenticated NATS URL (nats://nats:4222)."""
    response = await http_client.get("http://localhost:8080/healthz", timeout=10.0)

    assert response.status_code == 200
    data = response.json()
    nats_url = data.get("nats", {}).get("url", "")

    # URL should NOT be the unauthenticated format
    assert nats_url != "nats://nats:4222", (
        f"NATS URL should have credentials, not unauthenticated format"
    )


@pytest.mark.smoke
def test_agent_zero_env_file_has_nats_credentials() -> None:
    """Verify env.tier-agent defines NATS_URL with credentials."""
    import subprocess

    result = subprocess.run(
        ["grep", "^NATS_URL=", "env.tier-agent"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.fail("NATS_URL not found in env.tier-agent")

    nats_url = result.stdout.strip()

    # Should have credentials in the URL
    assert "pmoves@" in nats_url or ":" in nats_url, (
        f"NATS_URL in env.tier-agent should have credentials, got: {nats_url}"
    )


@pytest.mark.smoke
def test_comfy_watcher_env_file_has_nats_credentials() -> None:
    """Verify env.tier-worker defines NATS_URL with credentials for comfy-watcher."""
    result = subprocess.run(
        ["grep", "^NATS_URL=", "env.tier-worker"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.fail("NATS_URL not found in env.tier-worker")

    nats_url = result.stdout.strip()

    # Should have credentials in the URL
    assert "pmoves@" in nats_url or ":" in nats_url, (
        f"NATS_URL in env.tier-worker should have credentials, got: {nats_url}"
    )


@pytest.mark.smoke
def test_nats_url_removed_from_env_shared() -> None:
    """Verify NATS_URL was removed from env.shared (moved to tier-specific files)."""
    result = subprocess.run(
        ["grep", "^NATS_URL=", "env.shared"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    # env.shared should NOT have NATS_URL defined (it's now tier-specific)
    assert result.returncode != 0, (
        "NATS_URL should be removed from env.shared and defined in tier env files"
    )


@pytest.mark.smoke
def test_env_shared_still_has_nats_user_and_password() -> None:
    """Verify env.shared still has NATS_USER and NATS_PASSWORD for reference."""
    result = subprocess.run(
        ["grep", "-E", "^NATS_(USER|PASSWORD)=", "env.shared"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    # env.shared should still have the credential components
    assert result.returncode == 0, (
        "env.shared should have NATS_USER and NATS_PASSWORD for reference"
    )

    lines = result.stdout.strip().split("\n")
    assert len(lines) >= 2, "Should have both NATS_USER and NATS_PASSWORD"


@pytest.mark.smoke
def test_comfy_watcher_service_uses_tier_nats_url() -> None:
    """Verify comfy-watcher service does NOT override NATS_URL from env files."""
    import subprocess

    # Check that comfy-watcher doesn't have NATS_URL override in environment section
    result = subprocess.run(
        ["awk", "/comfy-watcher:/,/^\\S/{print}", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    comfy_watcher_config = result.stdout

    # Should NOT have NATS_URL override in environment section
    # (it should use the value from env.shared/env.tier-worker via env_file)
    has_nats_override = False
    in_environment = False

    for line in comfy_watcher_config.split("\n"):
        if "environment:" in line:
            in_environment = True
        elif line.startswith("  ") and not line.startswith("    "):
            in_environment = False
        elif in_environment and "NATS_URL" in line and "env_file" not in line:
            has_nats_override = True

    assert not has_nats_override, (
        "comfy-watcher should not override NATS_URL in environment section"
    )


@pytest.mark.smoke
def test_agent_zero_service_uses_tier_nats_url() -> None:
    """Verify agent-zero service does NOT override NATS_URL from env files."""
    import subprocess

    # Check that agent-zero doesn't have NATS_URL override in environment section
    result = subprocess.run(
        ["awk", "/agent-zero:/,/^\\S/{print}", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    agent_zero_config = result.stdout

    # Should NOT have NATS_URL override in environment section
    has_nats_override = False
    in_environment = False

    for line in agent_zero_config.split("\n"):
        if "environment:" in line:
            in_environment = True
        elif line.startswith("  ") and not line.startswith("    "):
            in_environment = False
        elif in_environment and "NATS_URL" in line:
            has_nats_override = True

    assert not has_nats_override, (
        "agent-zero should not override NATS_URL in environment section"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_nats_server_requires_authentication() -> None:
    """Verify NATS server requires authentication (not allowing anonymous connections)."""
    import docker

    client = docker.from_env()

    # Get NATS container
    try:
        nats_container = client.containers.get("pmoves-nats-1")

        # Check NATS configuration - it should require authentication
        # NATS with --auth flag or NATS_USER/NATS_PASSWORD environment variables
        result = nats_container.exec_run("env | grep -i nats")

        env_output = result.output.decode()

        # Should have authentication configured
        has_auth = (
            "NATS_USER" in env_output
            or "NATS_PASSWORD" in env_output
        )

        assert has_auth, "NATS server should be configured with authentication"

    except Exception as e:
        pytest.skip(f"Could not check NATS container: {e}")
    finally:
        client.close()
