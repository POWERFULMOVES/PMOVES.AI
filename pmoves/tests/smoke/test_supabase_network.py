"""
Test Supabase network connectivity fix from PR #483.

Validates that services can reach Supabase via the correct container network
(supabase_network_PMOVES.AI) instead of relying on host.docker.internal.

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import pytest
import subprocess
import httpx


@pytest.mark.smoke
def test_supabase_network_name_correct_in_compose() -> None:
    """Verify docker-compose.yml references correct Supabase network name."""
    result = subprocess.run(
        ["grep", "-A", "2", "supabase_net:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "supabase_net network not found in docker-compose.yml"

    config = result.stdout
    # Should reference the actual network created by Supabase CLI
    has_correct_name = "supabase_network_PMOVES.AI" in config

    assert has_correct_name, (
        f"supabase_net should reference 'supabase_network_PMOVES.AI', got: {config}"
    )


@pytest.mark.smoke
def test_pmoves_ui_on_supabase_network() -> None:
    """Verify pmoves-ui service is connected to Supabase container network."""
    result = subprocess.run(
        ["grep", "-A", "15", "pmoves-ui:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "pmoves-ui service not found in docker-compose.yml"

    config = result.stdout
    has_supabase_network = "supabase_net" in config

    assert has_supabase_network, (
        "pmoves-ui should be on supabase_net network for container-to-container communication"
    )


@pytest.mark.smoke
def test_supabase_network_is_external() -> None:
    """Verify supabase_net is defined as external network (created by Supabase CLI)."""
    result = subprocess.run(
        ["grep", "-B", "2", "-A", "2", "supabase_net:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "supabase_net network not found in docker-compose.yml"

    config = result.stdout
    is_external = "external: true" in config

    assert is_external, (
        "supabase_net should be marked as external network (managed by Supabase CLI)"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_kong_accessible_via_host() -> None:
    """Verify Supabase Kong gateway is accessible from host (for external access)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Supabase CLI maps Kong to host port 54321
            response = await client.get("http://localhost:54321/rest/v1/")

            # Should get OpenAPI spec even if no tables exist
            assert response.status_code == 200
            assert "openapi" in response.text.lower()

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase Kong not accessible on host port 54321: {e}")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_studio_accessible_via_host() -> None:
    """Verify Supabase Studio is accessible from host."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:65433/")

            # Studio should return HTML
            assert response.status_code == 200
            assert "html" in response.headers.get("content-type", "").lower()

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase Studio not accessible on host port 65433: {e}")


@pytest.mark.smoke
def test_supabase_cli_running() -> None:
    """Verify Supabase CLI is running and containers are healthy."""
    result = subprocess.run(
        ["supabase", "status"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI",
        timeout=10,
    )

    # Should not have errors about containers not running
    assert "exited" not in result.stderr.lower(), (
        f"Supabase CLI should be running: {result.stderr}"
    )


@pytest.mark.smoke
def test_archon_uses_host_dot_internal_for_supabase() -> None:
    """Verify Archon service uses host.docker.internal for Supabase (cross-network)."""
    result = subprocess.run(
        ["grep", "-A", "20", "archon:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.skip("archon service not found in docker-compose.yml")

    config = result.stdout

    # Archon should use host.docker.internal for Supabase access
    # since it may be on different networks
    has_host_internal = (
        "host.docker.internal" in config
        and "SUPABASE" in config
    )

    assert has_host_internal, (
        "Archon should use host.docker.internal for cross-network Supabase access"
    )


@pytest.mark.smoke
def test_no_legacy_supabase_net_in_url_defaults() -> None:
    """Verify no services use old incorrect Supabase network in URLs."""
    result = subprocess.run(
        ["grep", "supabase_net", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        return  # No supabase_net references found - test passes

    for line in result.stdout.split("\n"):
        # supabase_net in network definitions is OK
        # But should NOT appear in URL values like http://supabase_net:...
        if "http://" in line and "supabase_net" in line:
            pytest.fail(
                f"Found supabase_net in URL (should use service name or host.docker.internal): {line}"
            )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_pmoves_ui_accessible() -> None:
    """Verify pmoves-ui is accessible and can check health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:4482/api/health")

            assert response.status_code == 200

            data = response.json()
            assert data.get("status") == "healthy"

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"pmoves-ui not accessible on port 4482: {e}")


@pytest.mark.smoke
def test_supabase_network_exists() -> None:
    """Verify the supabase_network_PMOVES.AI network exists."""
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=supabase"],
        capture_output=True,
        text=True,
    )

    assert "supabase_network_PMOVES.AI" in result.stdout, (
        "supabase_network_PMOVES.AI network should exist (created by Supabase CLI)"
    )
