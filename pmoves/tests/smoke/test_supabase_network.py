"""
Test Supabase network connectivity fix from PR #483.

Validates that services can reach Supabase via the correct container network
instead of relying on host.docker.internal.

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import subprocess

import pytest
import httpx

from _smoke_helpers import PMOVES_DIR, grep_context, grep_file
from conftest import docker_available


COMPOSE = PMOVES_DIR / "docker-compose.yml"


@pytest.mark.smoke
def test_supabase_network_name_correct_in_compose() -> None:
    """Verify Supabase services and consumers share a reachable network."""
    content = COMPOSE.read_text()

    network_names = ["supabase_net", "pmoves_data", "pmoves_external", "pmoves_app", "pmoves_api"]

    # Find which networks exist in compose
    present = [n for n in network_names if n in content]
    assert present, (
        "docker-compose.yml should define a Supabase-accessible network "
        "(supabase_net, pmoves_data, pmoves_external, pmoves_app, or pmoves_api)"
    )

    # Verify supabase-postgrest is on at least one of these shared networks
    postgrest_block = grep_context(COMPOSE, r"supabase-postgrest:", after=40)
    if postgrest_block:
        postgrest_networks = [n for n in present if n in postgrest_block]
        assert postgrest_networks, (
            f"supabase-postgrest should be on a shared network ({present})"
        )


@pytest.mark.smoke
def test_pmoves_ui_on_supabase_network() -> None:
    """Verify pmoves-ui service is connected to a Supabase-accessible network."""
    config = grep_context(COMPOSE, r"pmoves-ui:", after=55)

    if not config:
        pytest.skip("pmoves-ui service not found in docker-compose.yml")

    has_network = (
        "supabase_net" in config
        or "pmoves_api" in config
        or "pmoves_data" in config
        or "pmoves_app" in config
        or "pmoves_external" in config
    )

    assert has_network, (
        "pmoves-ui should be on a Supabase-accessible network "
        "(supabase_net, pmoves_api, pmoves_data, pmoves_app, or pmoves_external)"
    )


@pytest.mark.smoke
def test_supabase_network_is_external() -> None:
    """Verify supabase_net is defined as external network (if used)."""
    config = grep_context(COMPOSE, r"supabase_net:", before=2, after=2)

    if not config:
        pytest.skip("supabase_net network not used in this compose configuration")

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

    except (httpx.ConnectError, httpx.TimeoutException) as e:
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

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Supabase Studio not accessible on host port 65433: {e}")


@pytest.mark.smoke
def test_supabase_cli_running() -> None:
    """Verify Supabase CLI is running and containers are healthy."""
    try:
        result = subprocess.run(
            ["supabase", "status"],
            capture_output=True,
            text=True,
            cwd=str(PMOVES_DIR.parent),
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("Supabase CLI timed out")
        return
    except FileNotFoundError:
        pytest.skip("supabase CLI not found")
        return

    # Should not have errors about containers not running
    assert "exited" not in result.stderr.lower(), (
        f"Supabase CLI should be running: {result.stderr}"
    )


@pytest.mark.smoke
def test_archon_uses_host_dot_internal_for_supabase() -> None:
    """Verify Archon service uses host.docker.internal for Supabase (cross-network)."""
    config = grep_context(COMPOSE, r"archon:", after=30)

    if not config:
        pytest.skip("archon service not found in docker-compose.yml")

    # Archon should use host.docker.internal for Supabase access
    # since it may be on different networks.
    # Accept either host.docker.internal or direct container references.
    has_supabase_ref = (
        ("host.docker.internal" in config and "SUPABASE" in config)
        or ("supabase-postgrest" in config)
        or ("SUPA_REST_URL" in config)
    )

    assert has_supabase_ref, (
        "Archon should reference Supabase (host.docker.internal or container URL)"
    )

    # When SUPA_REST_URL is used, validate it points to the right host
    for line in config.split("\n"):
        if "SUPA_REST_URL" in line and "=" in line:
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            # Skip variable references (${...}) — only validate literal values
            if value and "${" not in value:
                assert "supabase-postgrest" in value or "host.docker.internal" in value, (
                    f"SUPA_REST_URL should point to supabase-postgrest or "
                    f"host.docker.internal, got: {value}"
                )


@pytest.mark.smoke
def test_no_legacy_supabase_net_in_url_defaults() -> None:
    """Verify no services use old incorrect Supabase network in URLs."""
    matches = grep_file(COMPOSE, r"supabase_net", fixed=True)

    if not matches:
        return  # No supabase_net references found - test passes

    for line in matches:
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
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get("http://localhost:4482/api/health")

            # Accept 200 (healthy) or 307 (redirect, common for Next.js)
            assert response.status_code in [200, 307], (
                f"pmoves-ui should respond, got {response.status_code}"
            )

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"pmoves-ui not accessible on port 4482: {e}")


@pytest.mark.smoke
def test_supabase_network_exists() -> None:
    """Verify a Supabase-accessible Docker network exists."""
    if not docker_available():
        pytest.skip("Docker not available")

    try:
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=pmoves", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("docker CLI not available")
        return

    networks = result.stdout.strip().splitlines()
    expected_prefixes = ("pmoves_data", "pmoves_api", "pmoves_app", "pmoves_bus", "pmoves_external")
    has_network = any(
        net.startswith(prefix) for net in networks for prefix in expected_prefixes
    )

    assert has_network, (
        f"A Supabase-accessible Docker network should exist "
        f"(one of {expected_prefixes}), got: {networks}"
    )
