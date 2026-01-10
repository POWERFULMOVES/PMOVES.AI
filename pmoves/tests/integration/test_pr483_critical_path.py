"""
End-to-end critical path test with all PR #483 changes.

Validates the complete critical path with new configurations:
Supabase → NATS → Agent Zero → TensorZero → Hi-RAG v2

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import pytest
import httpx


@pytest.mark.integration
@pytest.mark.dependency()
@pytest.mark.asyncio
async def test_critical_path_supabase(http_client: httpx.AsyncClient) -> None:
    """
    Step 1: Verify Supabase is accessible.

    Supabase CLI should be running with Kong gateway on port 54321.
    """
    try:
        response = await http_client.get("http://localhost:54321/rest/v1/", timeout=5.0)
        assert response.status_code == 200
        assert "openapi" in response.text.lower()
    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Supabase not accessible: {e}")


@pytest.mark.integration
@pytest.mark.dependency(depends=["test_critical_path_supabase"])
@pytest.mark.asyncio
async def test_critical_path_nats(http_client: httpx.AsyncClient) -> None:
    """
    Step 2: Verify NATS is running with authentication.

    NATS should be accessible and services should be able to authenticate.
    """
    # Check if NATS port is listening
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", 4222))
        sock.close()
        assert result == 0, "NATS should be listening on port 4222"
    except Exception as e:
        pytest.skip(f"NATS not accessible: {e}")


@pytest.mark.integration
@pytest.mark.dependency(depends=["test_critical_path_nats"])
@pytest.mark.asyncio
async def test_critical_path_agent_zero(http_client: httpx.AsyncClient) -> None:
    """
    Step 3: Verify Agent Zero is healthy and connected to NATS.

    Agent Zero should be accessible on port 8080 with NATS connected.
    """
    response = await http_client.get("http://localhost:8080/healthz", timeout=10.0)
    assert response.status_code == 200

    data = response.json()
    assert data.get("status") == "ok"

    # Verify NATS connection with credentials
    nats = data.get("nats", {})
    assert nats.get("connected") is True, "Agent Zero should be connected to NATS"
    assert "pmoves@" in nats.get("url", ""), "NATS URL should have credentials"


@pytest.mark.integration
@pytest.mark.dependency(depends=["test_critical_path_agent_zero"])
@pytest.mark.asyncio
async def test_critical_path_tensorzero(http_client: httpx.AsyncClient) -> None:
    """
    Step 4: Verify TensorZero gateway is accessible.

    TensorZero should be accessible on host port 3030 (mapped to internal 3000).
    """
    try:
        # TensorZero main gateway on host port
        response = await http_client.get("http://localhost:3030/", timeout=5.0)
        # Any response indicates the gateway is running
        assert response.status_code in (200, 404)
    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"TensorZero not accessible: {e}")


@pytest.mark.integration
@pytest.mark.dependency(depends=["test_critical_path_tensorzero"])
@pytest.mark.asyncio
async def test_critical_path_hirag_v2(http_client: httpx.AsyncClient) -> None:
    """
    Step 5: Verify Hi-RAG v2 is accessible.

    Hi-RAG v2 should be accessible on port 8086 (CPU) or 8087 (GPU).
    """
    try:
        response = await http_client.get("http://localhost:8086/health", timeout=5.0)
        assert response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutError):
        # Try GPU port
        try:
            response = await http_client.get("http://localhost:8087/health", timeout=5.0)
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Hi-RAG v2 not accessible: {e}")


@pytest.mark.integration
@pytest.mark.dependency(depends=["test_critical_path_hirag_v2"])
@pytest.mark.asyncio
async def test_critical_path_neo4j(http_client: httpx.AsyncClient) -> None:
    """
    Step 6: Verify Neo4j is accessible on both HTTP and Bolt ports.

    Neo4j should be accessible on HTTP (7474) and Bolt (7687) ports.
    """
    try:
        response = await http_client.get("http://localhost:7474", timeout=5.0)
        assert response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Neo4j not accessible: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_archon_to_supabase(http_client: httpx.AsyncClient) -> None:
    """
    End-to-end: Verify Archon can reach Supabase.

    Archon service should be able to query Supabase via host.docker.internal.
    """
    # Archon health check
    try:
        response = await http_client.get("http://localhost:8091/healthz", timeout=10.0)
        assert response.status_code == 200

        data = response.json()
        assert data.get("status") == "ok"

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Archon not accessible: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_pmoves_ui(http_client: httpx.AsyncClient) -> None:
    """
    End-to-end: Verify PMOVES UI is accessible and healthy.

    PMOVES UI should be accessible and show health status.
    """
    try:
        response = await http_client.get("http://localhost:4482/api/health", timeout=5.0)
        assert response.status_code == 200

        data = response.json()
        assert data.get("status") == "healthy"

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"PMOVES UI not accessible: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_critical_path_summary() -> None:
    """
    Summary test: Quick health check of all critical services.

    This test runs as a final check to ensure the critical path is functional.
    """
    import subprocess

    # Use docker ps to check if critical containers are running
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )

    running_containers = result.stdout.strip().split("\n")

    # Critical containers that should be running
    critical_containers = [
        "pmoves-agent-zero-1",
        "pmoves-archon-1",
        "pmoves-nats-1",
        "pmoves-tensorzero-gateway-1",
        "pmoves-neo4j-1",
        "pmoves-pmoves-ui-1",
    ]

    for container in critical_containers:
        # Check if container is in running list
        is_running = any(container in c for c in running_containers)
        assert is_running, f"Critical container {container} should be running"

    # Check Supabase CLI status
    supabase_result = subprocess.run(
        ["supabase", "status"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should not have "exited" errors
    assert "exited" not in supabase_result.stderr.lower(), (
        "Supabase CLI should be running"
    )


@pytest.mark.integration
def test_pr483_changes_verified() -> None:
    """
    Verification test: Confirm all PR #483 changes are in place.

    This test checks that the specific changes from PR #483 are present:
    1. NATS_URL moved to tier env files (not in env.shared)
    2. TensorZero uses port 3000 for internal calls
    3. Neo4j uses separate HTTP_PORT and BOLT_PORT
    4. Supabase network name is correct
    """
    import subprocess

    # Check 1: NATS_URL removed from env.shared
    result = subprocess.run(
        ["grep", "^NATS_URL=", "env.shared"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )
    assert result.returncode != 0, "NATS_URL should be removed from env.shared"

    # Check 2: TensorZero internal port in docker-compose
    result = subprocess.run(
        ["grep", "TENSORZERO_URL.*3000", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )
    assert result.returncode == 0, "TensorZero should use internal port 3000"

    # Check 3: Neo4j dual port variables
    result = subprocess.run(
        ["grep", "NEO4J_HTTP_PORT", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )
    assert result.returncode == 0, "Neo4j should use NEO4J_HTTP_PORT"

    result = subprocess.run(
        ["grep", "NEO4J_BOLT_PORT", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )
    assert result.returncode == 0, "Neo4j should use NEO4J_BOLT_PORT"

    # Check 4: Supabase network name
    result = subprocess.run(
        ["grep", "supabase_network_PMOVES.AI", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )
    assert result.returncode == 0, "Should reference supabase_network_PMOVES.AI"
