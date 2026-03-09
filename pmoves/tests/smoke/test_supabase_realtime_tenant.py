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
import pytest
import subprocess
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


@pytest.mark.smoke
def test_supabase_realtime_container_running() -> None:
    """Verify Supabase Realtime container is running."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=supabase-realtime", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Failed to query Docker containers"
    assert "Up" in result.stdout, "supabase-realtime container should be running"


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
    """Verify SEED_SELF_HOST is enabled in docker-compose.yml."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=20)
    assert output, "supabase-realtime service not found in docker-compose.yml"

    assert "SEED_SELF_HOST=true" in output, (
        "SEED_SELF_HOST should be enabled for automatic tenant seeding"
    )


@pytest.mark.smoke
def test_realtime_jwt_secret_configured() -> None:
    """Verify Realtime JWT secret is configured."""
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=20)
    assert output, "supabase-realtime service not found in docker-compose.yml"

    assert "JWT_SECRET=${SUPABASE_JWT_SECRET}" in output, (
        "Realtime JWT_SECRET should reference SUPABASE_JWT_SECRET"
    )
    assert "API_JWT_SECRET=${SUPABASE_JWT_SECRET}" in output, (
        "Realtime API_JWT_SECRET should reference SUPABASE_JWT_SECRET"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_realtime_websocket_upgrade() -> None:
    """Verify Realtime accepts WebSocket upgrade requests."""
    try:
        import websockets

        ws_url = SUPABASE_REALTIME_URL.replace("ws://", "ws://localhost:4000/")

        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                await ws.ping()
                # If we get here, WebSocket is working

        except asyncio.TimeoutError:
            pytest.skip("WebSocket connection timed out (may require authentication)")

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code in [401, 403]:
                pass  # 401/403 expected if authentication required
            else:
                pytest.fail(f"Unexpected WebSocket status code: {e.status_code}")

    except ImportError:
        pytest.skip("websockets library not installed")
    except (ConnectionRefusedError, OSError) as e:
        pytest.skip(f"WebSocket connection failed: {e}")


@pytest.mark.smoke
def test_realtime_database_schema_exists() -> None:
    """Verify _realtime schema exists in Supabase database."""
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
    """Verify Hi-RAG v2 service has SUPABASE_REALTIME_URL configured."""
    output = grep_context(COMPOSE_FILE, r"hirag-v2:", after=10)

    if not output:
        output = grep_context(COMPOSE_FILE, r"hi-rag-gateway-v2:", after=10)

    if not output:
        pytest.skip("Hi-RAG v2 service not found in docker-compose.yml")

    assert "SUPABASE_REALTIME_URL" in output, (
        "Hi-RAG v2 should have SUPABASE_REALTIME_URL configured"
    )
    assert "supabase-realtime:4000" in output or "realtime:4000" in output, (
        "SUPABASE_REALTIME_URL should point to supabase-realtime container"
    )


@pytest.mark.smoke
def test_realtime_on_correct_networks() -> None:
    """Verify Realtime is on the correct Docker networks."""
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
    output = grep_context(COMPOSE_FILE, r"supabase-realtime:", after=25)
    assert output, "supabase-realtime service not found"

    assert "DB_HOST=supabase-db" in output, "Should have DB_HOST configured"
    assert "DB_NAME=${SUPABASE_DB_NAME}" in output, "Should have DB_NAME configured"
    assert "DB_USER=${SUPABASE_DB_USER}" in output, "Should have DB_USER configured"
    assert "DB_PASSWORD=${SUPABASE_DB_PASSWORD}" in output, "Should have DB_PASSWORD configured"

    assert "search_path TO _realtime" in output, (
        "Should set search_path to _realtime schema"
    )
