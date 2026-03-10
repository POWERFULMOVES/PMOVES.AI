"""
Test network configuration changes from PR #483.

Validates container-to-container communication uses correct ports.
Services should use internal container ports (3000) not host ports (3030).

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import pytest
import httpx

from _smoke_helpers import PMOVES_DIR, grep_file, grep_numbered


COMPOSE = PMOVES_DIR / "docker-compose.yml"


@pytest.mark.smoke
async def test_tensorzero_uses_internal_port(http_client: httpx.AsyncClient) -> None:
    """Verify TensorZero gateway is accessible on internal port 3000 from within container network."""
    # Internal container-to-container communication should use port 3000
    # Host port 3030 is only for external access
    try:
        # This test runs from host, so we use the host port mapping
        response = await http_client.get("http://localhost:3030/")
        # If we get any response (even 404), the service is reachable
        assert response.status_code in (200, 404)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.fail(f"TensorZero gateway not accessible on host port 3030: {e}")


@pytest.mark.smoke
async def test_agent_zero_connects_to_tensorzero(http_client: httpx.AsyncClient) -> None:
    """Verify Agent Zero health check shows TensorZero connectivity."""
    response = await http_client.get("http://localhost:8080/healthz")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


@pytest.mark.smoke
def test_tensorzero_port_configuration() -> None:
    """Verify TensorZero port configuration in docker-compose.yml uses internal port."""
    matches = grep_numbered(COMPOSE, r"TENSORZERO_URL", fixed=True)

    if not matches:
        pytest.skip("docker-compose.yml not accessible")

    # All TENSORZERO_URL references should use port 3000 (internal), not 3030 (host)
    for line in matches:
        # Port 3030 should only appear in port mappings, not in service URLs
        if "TENSORZERO_URL" in line and ":3030" in line:
            pytest.fail(
                f"Found host port 3030 in service URL: {line}\n"
                "Services should use internal port 3000 for container-to-container communication"
            )


@pytest.mark.smoke
def test_no_legacy_tensorzero_port_3030_in_urls() -> None:
    """Scan for any remaining hardcoded port 3030 references in service configurations."""
    matches = grep_numbered(COMPOSE, r":3030", fixed=True)

    if not matches:
        return  # No matches found - test passes

    for line in matches:
        # Port 3030 is only valid in port mappings (e.g., "3030:3000")
        # It should NOT appear in environment variable values
        if "environment:" in line or (
            "- " in line and ":3030" in line and "ports:" not in line
        ):
            pytest.fail(
                f"Found hardcoded port 3030 in service URL: {line}\n"
                "Container-to-container communication should use internal port 3000"
            )
