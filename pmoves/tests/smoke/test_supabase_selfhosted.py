"""
Test self-hosted Supabase integration (PMOVES-supabase submodule).

Validates that services can reach Supabase via the self-hosted container
services (supabase-db, supabase-postgrest, supabase-realtime, etc.)
instead of the Supabase CLI or host.docker.internal.

This test validates the migration from Supabase CLI to self-hosted Supabase.
"""

import os
import pytest
import subprocess
import httpx
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = PROJECT_ROOT / "pmoves"
COMPOSE_FILE = str(PMOVES_DIR / "docker-compose.yml")
ENV_SHARED = str(PMOVES_DIR / "env.shared")
ENV_TIER_SUPABASE = str(PMOVES_DIR / "env.tier-supabase")


SUPABASE_POSTGREST_URL = os.getenv(
    "SUPABASE_POSTGREST_URL",
    "http://localhost:3010/rest/v1/"
)
SUPABASE_REALTIME_URL = os.getenv(
    "SUPABASE_REALTIME_URL",
    "ws://localhost:4000/socket/websocket"
)
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT", "5432")


@pytest.mark.smoke
def test_supabase_postgrest_container_running() -> None:
    """Verify self-hosted Supabase PostgREST container is running."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-postgrest", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should have at least one container with "Up" status
    assert result.returncode == 0, "Failed to query Docker containers"
    assert "Up" in result.stdout, "supabase-postgrest container should be running"


@pytest.mark.smoke
def test_supabase_db_container_running() -> None:
    """Verify self-hosted Supabase database container is running."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-db", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Failed to query Docker containers"
    assert "Up" in result.stdout, "supabase-db container should be running"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_postgrest_accessible() -> None:
    """Verify self-hosted Supabase PostgREST API is accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # PostgREST root endpoint returns OpenAPI spec
            response = await client.get(SUPABASE_POSTGREST_URL)

            assert response.status_code == 200, f"PostgREST should be accessible, got {response.status_code}"
            # OpenAPI spec should be in response
            assert "openapi" in response.text.lower(), "Response should contain OpenAPI spec"

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase PostgREST not accessible at {SUPABASE_POSTGREST_URL}: {e}")


@pytest.mark.smoke
def test_supabase_pg_isready() -> None:
    """Verify self-hosted Supabase database is ready for connections."""
    result = subprocess.run(
        ["docker", "exec", "supabase-db", "pg_isready", "-U", "pmoves"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # pg_isready returns 0 when accepting connections
    assert result.returncode == 0, f"Supabase DB should be ready: {result.stderr}"
    assert "accepting connections" in result.stdout, "DB should be accepting connections"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_realtime_accessible() -> None:
    """Verify self-hosted Supabase Realtime is accessible."""
    # Realtime WebSocket endpoint - we can't test WebSocket easily here,
    # but we can check if the port is accessible
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to connect to the Realtime endpoint (may return 404 or 426 for WebSocket upgrade)
            response = await client.get(SUPABASE_REALTIME_URL.replace("ws://", "http://"))

            # Any response (even error) means the service is up
            # We expect 426 Upgrade Required for WebSocket connections
            assert response.status_code in [200, 404, 426], (
                f"Realtime should respond, got {response.status_code}"
            )

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase Realtime not accessible at {SUPABASE_REALTIME_URL}: {e}")


@pytest.mark.smoke
def test_no_cli_references_in_compose() -> None:
    """Verify docker-compose files don't reference Supabase CLI ports."""
    result = subprocess.run(
        ["grep", "-r", "54321", str(PMOVES_DIR / "docker-compose*.yml")],
        capture_output=True,
        text=True,
    )

    # 54321 is the Supabase CLI port - should not appear in compose files
    if result.returncode == 0:
        pytest.fail(
            f"Found Supabase CLI port reference (54321) in docker-compose files: {result.stdout}"
        )


@pytest.mark.smoke
def test_env_uses_selfhosted_urls() -> None:
    """Verify environment files use self-hosted Supabase URLs."""
    # Check env.shared for self-hosted Supabase references
    result = subprocess.run(
        ["grep", "SUPABASE_REST_URL", ENV_SHARED],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, "SUPABASE_REST_URL not found in env.shared"

    # Should reference supabase-postgrest container, not host.docker.internal:54321
    line = result.stdout.strip()
    assert "supabase-postgrest:3000" in line or "postgrest:3000" in line, (
        f"SUPABASE_REST_URL should use self-hosted postgrest, got: {line}"
    )
    assert "54321" not in line, (
        f"SUPABASE_REST_URL should not reference CLI port 54321, got: {line}"
    )


@pytest.mark.smoke
def test_supabase_network_exists() -> None:
    """Verify the Supabase container network exists."""
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=pmoves", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )

    assert "pmoves" in result.stdout or "pmoves_data" in result.stdout or "pmoves_app" in result.stdout, (
        "Supabase network (pmoves/pmoves_data/pmoves_app) should exist"
    )


@pytest.mark.smoke
def test_supabase_tenant_configured() -> None:
    """Verify Supabase Realtime tenants are configured for localhost."""
    # Check if docker-compose.yml has REALTIME tenant configuration
    result = subprocess.run(
        ["grep", "-A", "5", "supabase-realtime:", COMPOSE_FILE],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.skip("supabase-realtime service not found in docker-compose.yml")

    # Should have tenant configuration for localhost
    config = result.stdout
    # Realtime should be configured with proper tenant ID
    assert "localhost" in config or "TENANT" in config, (
        "Realtime should have tenant configuration for localhost"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_health_check() -> None:
    """Verify self-hosted Supabase stack health via container checks."""
    # Check multiple Supabase services
    services = ["supabase-db", "supabase-postgrest", "supabase-realtime"]

    for service in services:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", service],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # If no healthcheck, just check if running
        if result.returncode != 0 or "no such" in result.stderr.lower():
            # Fallback: check if container is running
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
            )
            assert "Up" in result.stdout, f"{service} should be running"
        else:
            # Has healthcheck - should be healthy
            status = result.stdout.strip()
            assert status in ["healthy", "starting"], f"{service} health status: {status}"


@pytest.mark.smoke
def test_env_shared_has_jwt_comment() -> None:
    """Verify env.shared documents that JWT secret is in env.tier-supabase."""
    result = subprocess.run(
        ["grep", "-A", "2", "SUPABASE_JWT_SECRET", ENV_SHARED],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, "JWT secret reference not found in env.shared"

    # Should have comment explaining tier isolation
    output = result.stdout
    assert "env.tier-supabase" in output or "tier isolation" in output.lower(), (
        "env.shared should document that JWT secret is in env.tier-supabase"
    )


@pytest.mark.smoke
def test_no_duplicate_jwt_secrets() -> None:
    """Verify there are no duplicate SUPABASE_JWT_SECRET definitions in env.shared."""
    result = subprocess.run(
        ["grep", "^SUPABASE_JWT_SECRET=", ENV_SHARED],
        capture_output=True,
        text=True,
    )

    # Should have 0 or 1 lines (not 2+)
    lines = [line for line in result.stdout.split("\n") if line and not line.strip().startswith("#")]
    assert len(lines) <= 1, (
        f"env.shared should not have duplicate SUPABASE_JWT_SECRET definitions. Found {len(lines)}: {lines}"
    )


@pytest.mark.smoke
def test_supabase_env_file_exists() -> None:
    """Verify env.tier-supabase exists and has required variables."""
    result = subprocess.run(
        ["test", "-f", ENV_TIER_SUPABASE],
        capture_output=True,
    )

    # env.tier-supabase may not exist in all environments (gitignored)
    if result.returncode != 0:
        pytest.skip("env.tier-supabase not found (may be gitignored)")

    # Check for required variables
    required_vars = ["SUPABASE_JWT_SECRET", "SUPABASE_DB_PASSWORD", "SUPABASE_ANON_KEY"]
    for var in required_vars:
        result = subprocess.run(
            ["grep", f"^{var}=", ENV_TIER_SUPABASE],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{var} should be defined in env.tier-supabase"
        # Should not be a placeholder
        value = result.stdout.strip().split("=", 1)[1] if "=" in result.stdout else ""
        assert not value.startswith("your_") and not value.startswith("PLACEHOLDER"), (
            f"{var} should have a real value, not placeholder: {value}"
        )
