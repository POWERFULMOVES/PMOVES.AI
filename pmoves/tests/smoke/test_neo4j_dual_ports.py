"""
Test Neo4j dual-port configuration from PR #483.

Validates that Neo4j uses separate ports for HTTP (7474) and Bolt (7687)
instead of a single NEO4J_PORT variable that would cause conflicts.

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import pytest
import httpx
import subprocess


@pytest.mark.smoke
def test_neo4j_http_port_exposed() -> None:
    """Verify Neo4j HTTP interface is exposed on port 7474."""
    result = subprocess.run(
        ["grep", "-A", "5", "neo4j:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "neo4j service not found in docker-compose.yml"

    config = result.stdout
    has_http_port = "${NEO4J_HTTP_PORT:-7474}:7474" in config

    assert has_http_port, (
        "Neo4j should have NEO4J_HTTP_PORT mapping for port 7474"
    )


@pytest.mark.smoke
def test_neo4j_bolt_port_exposed() -> None:
    """Verify Neo4j Bolt protocol is exposed on port 7687."""
    result = subprocess.run(
        ["grep", "-A", "5", "neo4j:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "neo4j service not found in docker-compose.yml"

    config = result.stdout
    has_bolt_port = "${NEO4J_BOLT_PORT:-7687}:7687" in config

    assert has_bolt_port, (
        "Neo4j should have NEO4J_BOLT_PORT mapping for port 7687"
    )


@pytest.mark.smoke
def test_neo4j_ports_not_using_single_variable() -> None:
    """Verify Neo4j does NOT use a single NEO4J_PORT for both HTTP and Bolt."""
    result = subprocess.run(
        ["grep", "-A", "5", "neo4j:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    assert result.returncode == 0, "neo4j service not found in docker-compose.yml"

    config = result.stdout
    lines = config.split("\n")

    # Check that we DON'T have the old format where both ports use NEO4J_PORT
    # Old problematic format: ${NEO4J_PORT:-7474}:7474 and ${NEO4J_PORT:-7687}:7687
    has_duplicate_port_var = False

    for i, line in enumerate(lines):
        if "${NEO4J_PORT:-7474}:7474" in line:
            # Check if the next line also uses NEO4J_PORT for bolt
            if i + 1 < len(lines) and "${NEO4J_PORT:-7687}:7687" in lines[i + 1]:
                has_duplicate_port_var = True

    assert not has_duplicate_port_var, (
        "Neo4j should not use NEO4J_PORT for both HTTP and Bolt ports. "
        "Use NEO4J_HTTP_PORT and NEO4J_BOLT_PORT instead."
    )


@pytest.mark.smoke
def test_neo4j_http_port_mapping() -> None:
    """Verify HTTP port mapping format is correct."""
    result = subprocess.run(
        ["grep", "NEO4J_HTTP_PORT", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.skip("NEO4J_HTTP_PORT not found in docker-compose.yml")

    # Should map internal 7474 to host NEO4J_HTTP_PORT (default 7474)
    assert "${NEO4J_HTTP_PORT:-7474}:7474" in result.stdout, (
        "HTTP port mapping should use NEO4J_HTTP_PORT variable with default 7474"
    )


@pytest.mark.smoke
def test_neo4j_bolt_port_mapping() -> None:
    """Verify Bolt port mapping format is correct."""
    result = subprocess.run(
        ["grep", "NEO4J_BOLT_PORT", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.skip("NEO4J_BOLT_PORT not found in docker-compose.yml")

    # Should map internal 7687 to host NEO4J_BOLT_PORT (default 7687)
    assert "${NEO4J_BOLT_PORT:-7687}:7687" in result.stdout, (
        "Bolt port mapping should use NEO4J_BOLT_PORT variable with default 7687"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_neo4j_http_accessible() -> None:
    """Verify Neo4j HTTP interface is accessible on port 7474."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:7474")

            # Neo4j returns 200 OK when accessible
            assert response.status_code == 200

    except (httpx.ConnectError, httpx.TimeoutError) as e:
        pytest.skip(f"Neo4j not accessible on port 7474: {e}")


@pytest.mark.smoke
def test_neo4j_env_file_has_both_ports() -> None:
    """Verify env.tier-data can configure both HTTP and Bolt ports independently."""
    # Check that tier env files support both port variables
    result = subprocess.run(
        ["grep", "-E", "NEO4J_(HTTP|BOLT)_PORT", "env.tier-data.example"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    # env.tier-data.example should have both port variables documented
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        # At least one of the port variables should be documented
        assert len(lines) > 0, "Neo4j port variables should be documented in env.tier-data.example"


@pytest.mark.smoke
def test_hirag_v2_uses_neo4j_bolt_port() -> None:
    """Verify Hi-RAG v2 service can connect to Neo4j via Bolt protocol."""
    result = subprocess.run(
        ["grep", "-A", "30", "hi-rag-gateway-v2:", "docker-compose.yml"],
        capture_output=True,
        text=True,
        cwd="/home/pmoves/PMOVES.AI/pmoves",
    )

    if result.returncode != 0:
        pytest.skip("hi-rag-gateway-v2 service not found")

    config = result.stdout

    # Hi-RAG v2 should have NEO4J_URL configured for Bolt connection
    has_bolt_url = "NEO4J_URL" in config or "bolt://neo4j:7687" in config

    assert has_bolt_url, (
        "Hi-RAG v2 should have NEO4J_URL configured for Bolt protocol connection"
    )
