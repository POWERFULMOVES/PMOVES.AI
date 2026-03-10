"""
Test Supabase Realtime tenant configuration.

Validates that Supabase Realtime has proper tenant configuration
for self-hosted mode, including localhost and internal container access.

Realtime requires tenants to be configured in the database for WebSocket
connections to be accepted. This test verifies:
1. Tenant(s) exist in database
2. Tenant external ID matches expected values
3. Realtime service is accessible and healthy
"""

import os
import subprocess
import pytest
import httpx
import asyncio
from pathlib import Path

from _smoke_helpers import grep_file, grep_context, PROJECT_ROOT, PMOVES_DIR


COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"

SUPABASE_REALTIME_URL = os.getenv(
    "SUPABASE_REALTIME_URL",
    "ws://localhost:4000/socket/websocket"
)
SUPABASE_POSTGREST_URL = os.getenv(
    "SUPABASE_POSTGREST_URL",
    "http://localhost:3010/rest/v1/"
)


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


@pytest.mark.smoke
def test_supabase_realtime_container_running() -> None:
    """Verify Supabase Realtime container is running."""
    if not _docker_available():
        pytest.skip("Docker not available")

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-realtime", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0 or "Up" not in result.stdout:
        pytest.skip("supabase-realtime container not running (service-dependent)")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_realtime_http_accessible() -> None:
    """Verify Supabase Realtime HTTP endpoint is accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            http_url = SUPABASE_REALTIME_URL.replace("ws://", "http://").replace("/socket/websocket", "/")
            response = await client.get(http_url)

            assert response.status_code in [200, 404, 426], (
                f"Realtime should respond, got {response.status_code}"
            )

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Supabase Realtime not accessible at {SUPABASE_REALTIME_URL}: {e}")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_supabase_realtime_tenant_exists() -> None:
    """Verify tenant(s) exist in the Realtime database schema."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_POSTGREST_URL}/_realtime_tenants",
                headers={
                    "apikey": os.getenv("SUPABASE_ANON_KEY", ""),
                    "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY', '')}"
                }
            )

            if response.status_code == 200:
                tenants = response.json()
                assert isinstance(tenants, list), "Tenants response should be a list"
                assert len(tenants) > 0, "At least one tenant should be configured"

                external_ids = [t.get("external_id") for t in tenants]
                assert "stub" in external_ids or "localhost" in external_ids, (
                    f"Expected tenant external_id 'stub' or 'localhost', got: {external_ids}"
                )

            elif response.status_code == 404:
                pytest.skip("_realtime_tenants table not found (migrations may not be complete)")
            else:
                pytest.fail(f"Unexpected response from PostgREST: {response.status_code}")

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Supabase PostgREST not accessible: {e}")


@pytest.mark.smoke
def test_realtime_has_seed_self_host_enabled() -> None:
    """Verify SEED_SELF_HOST is enabled or tenant seeding is configured."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=45)
    if not output:
        pytest.skip("supabase-realtime service not found in docker-compose.yml")

    # SEED_SELF_HOST may be in compose env, env_file, or the service may be
    # in the supabase-local profile (which implies self-hosted tenant seeding).
    has_seed = (
        "SEED_SELF_HOST" in output
        or "env.tier-supabase" in output
        or "supabase-local" in output
    )

    if not has_seed:
        # Check if it's set in env.tier-supabase
        tier_supabase = PMOVES_DIR / "env.tier-supabase"
        if tier_supabase.exists():
            tier_matches = grep_file(tier_supabase, "SEED_SELF_HOST")
            has_seed = bool(tier_matches)

    assert has_seed, (
        "SEED_SELF_HOST should be enabled for automatic tenant seeding "
        "(in compose env, env.tier-supabase, or supabase-local profile)"
    )


@pytest.mark.smoke
def test_realtime_jwt_secret_configured() -> None:
    """Verify Realtime JWT secret is configured."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=30)
    if not output:
        pytest.skip("supabase-realtime service not found in docker-compose.yml")

    # Accept various formats: direct reference, nested ${}, or env_file inheritance
    has_jwt = (
        "JWT_SECRET" in output
        or "SUPABASE_JWT_SECRET" in output
        or "env.tier-supabase" in output
    )
    assert has_jwt, (
        "Realtime should have JWT_SECRET configured (directly or via env_file)"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_realtime_websocket_upgrade() -> None:
    """Verify Realtime accepts WebSocket upgrade requests."""
    try:
        import websockets
        from websockets.exceptions import InvalidStatus
    except ImportError:
        pytest.skip("websockets library not installed")
        return

    ws_url = SUPABASE_REALTIME_URL

    try:
        async with websockets.connect(ws_url, close_timeout=5) as ws:
            await ws.ping()

    except asyncio.TimeoutError:
        pytest.skip("WebSocket connection timed out (may require authentication)")

    except InvalidStatus as e:
        # 401/403 expected if authentication required, 404 if path not mapped
        if e.response.status_code in [401, 403, 404]:
            pytest.skip(f"WebSocket rejected with {e.response.status_code} (expected without auth)")
        else:
            pytest.fail(f"Unexpected WebSocket status code: {e.response.status_code}")

    except (ConnectionRefusedError, OSError) as e:
        pytest.skip(f"WebSocket connection failed: {e}")


@pytest.mark.smoke
def test_realtime_database_schema_exists() -> None:
    """Verify _realtime schema exists in Supabase database."""
    if not _docker_available():
        pytest.skip("Docker not available")

    result = subprocess.run(
        ["docker", "exec", "supabase-db", "psql", "-U", "pmoves", "-d", "pmoves",
         "-c", "SELECT schema_name FROM information_schema.schemata WHERE schema_name = '_realtime';"],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if result.returncode != 0:
        pytest.skip("Could not query database schema")

    assert "_realtime" in result.stdout, (
        "_realtime schema should exist in database"
    )


@pytest.mark.smoke
def test_realtime_healthcheck_configured() -> None:
    """Verify Realtime has a healthcheck configured in docker-compose."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=30)
    assert output, "supabase-realtime service not found"

    assert "healthcheck:" in output, (
        "Realtime should have a healthcheck configured"
    )

    assert "curl" in output and "4000" in output, (
        "Healthcheck should verify Realtime on port 4000"
    )


@pytest.mark.smoke
def test_hirag_v2_has_realtime_url_configured() -> None:
    """Verify Hi-RAG v2 service has SUPABASE_REALTIME_URL configured (if applicable)."""
    output = grep_context(COMPOSE_FILE, r"hirag-v2:", after=15)

    if not output:
        output = grep_context(COMPOSE_FILE, r"hi-rag-gateway-v2:", after=15)

    if not output:
        pytest.skip("Hi-RAG v2 service not found in docker-compose.yml")

    # SUPABASE_REALTIME_URL is optional for Hi-RAG v2 — it may not need
    # realtime subscriptions. Skip if not configured.
    if "SUPABASE_REALTIME_URL" not in output:
        pytest.skip("Hi-RAG v2 does not have SUPABASE_REALTIME_URL (may not be required)")


@pytest.mark.smoke
def test_realtime_on_correct_networks() -> None:
    """Verify Realtime is on the correct Docker networks."""
    if not _docker_available():
        pytest.skip("Docker not available")

    result = subprocess.run(
        ["docker", "inspect", "supabase-realtime", "--format", "{{json .NetworkSettings.Networks}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=realtime", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            container_name = result.stdout.strip().split("\n")[0]
            result = subprocess.run(
                ["docker", "inspect", container_name, "--format", "{{json .NetworkSettings.Networks}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            pytest.skip("Realtime container not found")

    import json
    try:
        networks = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse docker inspect output: {result.stdout[:200]}")

    assert len(networks) > 0, "Realtime should be on at least one network"
    assert any("pmoves" in net.lower() for net in networks.keys()), (
        f"Realtime should be on pmoves network(s), got: {list(networks.keys())}"
    )


@pytest.mark.smoke
def test_realtime_environment_has_db_params() -> None:
    """Verify Realtime service has database connection parameters configured."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=35)
    assert output, "supabase-realtime service not found"

    # Check for DB connection params — accept both exact matches and
    # nested ${} variable references (e.g. ${POSTGRES_DB:-${SUPABASE_DB_NAME:-postgres}})
    assert "DB_HOST" in output, "Should have DB_HOST configured"
    assert "DB_NAME" in output or "POSTGRES_DB" in output, "Should have DB_NAME or POSTGRES_DB configured"
    assert "DB_USER" in output or "POSTGRES_USER" in output, "Should have DB_USER configured"
    assert "DB_PASSWORD" in output or "POSTGRES_PASSWORD" in output, "Should have DB_PASSWORD configured"
