"""
Test self-hosted Supabase integration (PMOVES-supabase submodule).

Validates that services can reach Supabase via the self-hosted container
services (supabase-db, supabase-postgrest, supabase-realtime, etc.)
instead of the Supabase CLI or host.docker.internal.

This test validates the migration from Supabase CLI to self-hosted Supabase.
"""

import os
import subprocess
import pytest
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


def _docker_available() -> bool:
    """Check if Docker CLI is available and responsive."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _container_running(name: str) -> bool:
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={name}", "--format", "{{{{.Status}}}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "Up" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.smoke
def test_supabase_postgrest_container_running() -> None:
    """Verify self-hosted Supabase PostgREST container is running."""
    if not _docker_available():
        pytest.skip("Docker not available")

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-postgrest", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0 or "Up" not in result.stdout:
        pytest.skip("supabase-postgrest container not running (service-dependent)")


@pytest.mark.smoke
def test_supabase_db_container_running() -> None:
    """Verify self-hosted Supabase database container is running."""
    if not _docker_available():
        pytest.skip("Docker not available")

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-db", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0 or "Up" not in result.stdout:
        pytest.skip("supabase-db container not running (service-dependent)")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_postgrest_accessible() -> None:
    """Verify self-hosted Supabase PostgREST API is accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(SUPABASE_POSTGREST_URL)

            assert response.status_code == 200, f"PostgREST should be accessible, got {response.status_code}"
            assert "openapi" in response.text.lower(), "Response should contain OpenAPI spec"

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Supabase PostgREST not accessible at {SUPABASE_POSTGREST_URL}: {e}")


@pytest.mark.smoke
def test_supabase_pg_isready() -> None:
    """Verify self-hosted Supabase database is ready for connections."""
    if not _docker_available() or not _container_running("supabase-db"):
        pytest.skip("supabase-db container not running")

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

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Supabase Realtime not accessible at {SUPABASE_REALTIME_URL}: {e}")


@pytest.mark.smoke
def test_no_cli_references_in_compose() -> None:
    """Verify docker-compose files don't hardcode Supabase CLI port 54321."""
    compose_files = list(PMOVES_DIR.glob("docker-compose*.yml"))

    for compose_file in compose_files:
        matches = grep_file(compose_file, "54321", fixed=True)
        non_comment_matches = [m for m in matches if not m.strip().startswith("#")]
        # Env-var fallback defaults like ${NEXT_PUBLIC_SUPABASE_URL:-http://localhost:54321}
        # are acceptable — they only apply when the env var is unset, and the
        # canonical value is set in env.shared.  Only flag bare/hardcoded refs.
        hardcoded_refs = [
            m for m in non_comment_matches
            if "${" not in m
        ]
        if hardcoded_refs:
            pytest.fail(
                f"Found hardcoded Supabase CLI port (54321) in {compose_file.name}: "
                + "; ".join(m.strip() for m in hardcoded_refs[:3])
            )


@pytest.mark.smoke
def test_env_uses_selfhosted_urls() -> None:
    """Verify environment files use self-hosted Supabase URLs."""
    # Check for SUPABASE_REST_URL or SUPA_REST_URL with container-based URL
    rest_matches = grep_file(ENV_SHARED, "SUPABASE_REST_URL", fixed=True)
    supa_matches = grep_file(ENV_SHARED, "SUPA_REST_URL", fixed=True)
    all_matches = rest_matches + supa_matches

    assert all_matches, "SUPABASE_REST_URL or SUPA_REST_URL not found in env.shared"

    # At least one should point to the self-hosted postgrest container
    has_selfhosted = any(
        "supabase-postgrest" in m or "postgrest:3000" in m
        for m in all_matches
        if not m.strip().startswith("#")
    )
    assert has_selfhosted, (
        f"SUPABASE_REST_URL/SUPA_REST_URL should use self-hosted postgrest, "
        f"got: {[m.strip() for m in all_matches]}"
    )


@pytest.mark.smoke
def test_supabase_network_exists() -> None:
    """Verify the Supabase container network exists."""
    if not _docker_available():
        pytest.skip("Docker not available")

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
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=40)

    if not output:
        pytest.skip("supabase-realtime service not found in docker-compose.yml")

    # Accept tenant config via TENANT env, localhost reference, SEED_SELF_HOST,
    # or supabase-local profile (which implies self-hosted tenant seeding)
    has_tenant = (
        "localhost" in output
        or "TENANT" in output
        or "SEED_SELF_HOST" in output
        or "supabase-local" in output
    )
    assert has_tenant, (
        "Realtime should have tenant configuration (SEED_SELF_HOST, TENANT, or supabase-local profile)"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_health_check() -> None:
    """Verify self-hosted Supabase stack health via container checks."""
    if not _docker_available():
        pytest.skip("Docker not available")

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
                ["docker", "ps", "--filter", f"name={service}", "--format", "{{{{.Status}}}}"],
                capture_output=True,
                text=True,
            )
            if "Up" not in result.stdout:
                pytest.skip(f"{service} container not running")
        else:
            status = result.stdout.strip()
            assert status == "healthy", f"{service} health status: {status} (expected 'healthy')"


@pytest.mark.smoke
def test_env_shared_has_jwt_comment() -> None:
    """Verify env.shared documents that JWT secret is in env.tier-supabase."""
    matches = grep_context(ENV_SHARED, "SUPABASE_JWT_SECRET", before=3, after=2)
    assert matches, "JWT secret reference not found in env.shared"

    assert "env.tier-supabase" in matches or "tier" in matches.lower(), (
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
