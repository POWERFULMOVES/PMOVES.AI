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
from pathlib import Path

from _smoke_helpers import grep_file, grep_context, PROJECT_ROOT, PMOVES_DIR


COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"
ENV_SHARED = PMOVES_DIR / "env.shared"
ENV_TIER_SUPABASE = PMOVES_DIR / "env.tier-supabase"

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
            response = await client.get(SUPABASE_POSTGREST_URL)

            assert response.status_code == 200, f"PostgREST should be accessible, got {response.status_code}"
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

    assert result.returncode == 0, f"Supabase DB should be ready: {result.stderr}"
    assert "accepting connections" in result.stdout, "DB should be accepting connections"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_realtime_accessible() -> None:
    """Verify self-hosted Supabase Realtime is accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(SUPABASE_REALTIME_URL.replace("ws://", "http://"))

            assert response.status_code in [200, 404, 426], (
                f"Realtime should respond, got {response.status_code}"
            )

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase Realtime not accessible at {SUPABASE_REALTIME_URL}: {e}")


@pytest.mark.smoke
def test_no_cli_references_in_compose() -> None:
    """Verify docker-compose files don't reference Supabase CLI ports."""
    compose_files = list(PMOVES_DIR.glob("docker-compose*.yml"))

    for compose_file in compose_files:
        matches = grep_file(compose_file, "54321", fixed=True)
        non_comment_matches = [m for m in matches if not m.strip().startswith("#")]
        if non_comment_matches:
            pytest.fail(
                f"Found Supabase CLI port reference (54321) in {compose_file.name}: "
                + "; ".join(m.strip() for m in non_comment_matches[:3])
            )


@pytest.mark.smoke
def test_env_uses_selfhosted_urls() -> None:
    """Verify environment files use self-hosted Supabase URLs."""
    matches = grep_file(ENV_SHARED, "SUPABASE_REST_URL", fixed=True)
    assert matches, "SUPABASE_REST_URL not found in env.shared"

    line = matches[0].strip()
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
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=5)

    if not output:
        pytest.skip("supabase-realtime service not found in docker-compose.yml")

    assert "localhost" in output or "TENANT" in output, (
        "Realtime should have tenant configuration for localhost"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_health_check() -> None:
    """Verify self-hosted Supabase stack health via container checks."""
    services = ["supabase-db", "supabase-postgrest", "supabase-realtime"]

    for service in services:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", service],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0 or "no such" in result.stderr.lower():
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
            )
            assert "Up" in result.stdout, f"{service} should be running"
        else:
            status = result.stdout.strip()
            assert status == "healthy", f"{service} health status: {status} (expected 'healthy')"


@pytest.mark.smoke
def test_env_shared_has_jwt_comment() -> None:
    """Verify env.shared documents that JWT secret is in env.tier-supabase."""
    matches = grep_context(ENV_SHARED, "SUPABASE_JWT_SECRET", after=2)
    assert matches, "JWT secret reference not found in env.shared"

    assert "env.tier-supabase" in matches or "tier isolation" in matches.lower(), (
        "env.shared should document that JWT secret is in env.tier-supabase"
    )


@pytest.mark.smoke
def test_no_duplicate_jwt_secrets() -> None:
    """Verify there are no duplicate SUPABASE_JWT_SECRET definitions in env.shared."""
    matches = grep_file(ENV_SHARED, r"^SUPABASE_JWT_SECRET=")
    non_comment = [line for line in matches if not line.strip().startswith("#")]

    assert len(non_comment) <= 1, (
        f"env.shared should not have duplicate SUPABASE_JWT_SECRET definitions. "
        f"Found {len(non_comment)}: {non_comment}"
    )


@pytest.mark.smoke
def test_supabase_env_file_exists() -> None:
    """Verify env.tier-supabase exists and has required variables."""
    if not ENV_TIER_SUPABASE.exists():
        pytest.skip("env.tier-supabase not found (may be gitignored)")

    from _smoke_helpers import grep_file as _grep
    required_vars = ["SUPABASE_JWT_SECRET", "SUPABASE_DB_PASSWORD", "SUPABASE_ANON_KEY"]
    for var in required_vars:
        matches = _grep(ENV_TIER_SUPABASE, rf"^{var}=")
        assert matches, f"{var} should be defined in env.tier-supabase"
        value = matches[0].split("=", 1)[1] if "=" in matches[0] else ""
        assert not value.startswith("your_") and not value.startswith("PLACEHOLDER"), (
            f"{var} should have a real value, not placeholder: {value}"
        )
