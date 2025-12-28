"""
Parametrized health endpoint tests for all PMOVES.AI services.

Tests all 53 services in parallel with specialized handlers for different
health check types (HTTP, Gradio, databases, TCP sockets).

Target execution time: <30s for all services (with pytest-xdist parallel execution)
"""

import asyncio
import socket
import subprocess
from typing import AsyncGenerator
import pytest
import httpx
from pmoves.tests.utils.service_catalog import (
    SERVICES,
    GPU_SERVICES,
    ServiceDefinition,
    HealthCheckType,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Shared HTTP client for all tests."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client


# ============================================================================
# HEALTH CHECK HELPERS
# ============================================================================

async def check_http_health(
    service: ServiceDefinition,
    client: httpx.AsyncClient,
) -> tuple[bool, str, dict | None]:
    """
    Check HTTP service health.

    Returns:
        (is_healthy, message, response_json)
    """
    url = f"http://localhost:{service.port}{service.health_path}"

    try:
        response = await client.get(
            url,
            timeout=service.timeout,
            follow_redirects=True,
        )

        # Check status code
        if response.status_code != service.expected_status:
            return (
                False,
                f"Unexpected status: {response.status_code} (expected {service.expected_status})",
                None,
            )

        # Validate expected fields
        if service.expected_fields:
            try:
                data = response.json()
                missing_fields = [
                    field for field in service.expected_fields
                    if field not in data
                ]
                if missing_fields:
                    return (
                        False,
                        f"Missing fields: {', '.join(missing_fields)}",
                        data,
                    )
                return True, "OK", data
            except Exception as e:
                return False, f"Invalid JSON: {e}", None

        return True, "OK", None

    except httpx.TimeoutException:
        return False, "Timeout", None
    except httpx.ConnectError:
        return False, "Connection refused", None
    except Exception as e:
        return False, f"Error: {e}", None


async def check_gradio_health(
    service: ServiceDefinition,
    client: httpx.AsyncClient,
) -> tuple[bool, str, dict | None]:
    """
    Check Gradio service health.

    Gradio returns 200 with JSON containing version/mode info.
    """
    url = f"http://localhost:{service.port}{service.health_path}"

    try:
        response = await client.get(url, timeout=service.timeout)

        if response.status_code != 200:
            return False, f"Status: {response.status_code}", None

        # Gradio info endpoint returns JSON
        try:
            data = response.json()

            # Check for expected Gradio fields
            if service.expected_fields:
                missing_fields = [
                    field for field in service.expected_fields
                    if field not in data
                ]
                if missing_fields:
                    return (
                        False,
                        f"Missing fields: {', '.join(missing_fields)}",
                        data,
                    )

            return True, "OK", data
        except Exception as e:
            return False, f"Invalid JSON: {e}", None

    except httpx.TimeoutException:
        return False, "Timeout", None
    except httpx.ConnectError:
        return False, "Connection refused", None
    except Exception as e:
        return False, f"Error: {e}", None


async def check_postgres_health(
    service: ServiceDefinition,
) -> tuple[bool, str, None]:
    """
    Check PostgreSQL health using pg_isready.

    Uses subprocess to run pg_isready command.
    """
    try:
        # Try to connect via pg_isready
        result = subprocess.run(
            ["pg_isready", "-h", "localhost", "-p", str(service.port)],
            capture_output=True,
            text=True,
            timeout=service.timeout,
        )

        if result.returncode == 0:
            return True, "OK", None
        else:
            return False, f"pg_isready: {result.stdout.strip()}", None

    except subprocess.TimeoutExpired:
        return False, "Timeout", None
    except FileNotFoundError:
        # pg_isready not in PATH, try TCP connection
        return await check_socket_health(service)
    except Exception as e:
        return False, f"Error: {e}", None


async def check_qdrant_health(
    service: ServiceDefinition,
    client: httpx.AsyncClient,
) -> tuple[bool, str, dict | None]:
    """
    Check Qdrant health using /readyz endpoint.

    Qdrant returns 200 when ready to accept requests.
    """
    url = f"http://localhost:{service.port}{service.health_path}"

    try:
        response = await client.get(url, timeout=service.timeout)

        if response.status_code == 200:
            # Try to parse response
            try:
                data = response.json()
                return True, "OK", data
            except Exception:
                # Qdrant might return plain text
                return True, "OK", None
        else:
            return False, f"Status: {response.status_code}", None

    except httpx.TimeoutException:
        return False, "Timeout", None
    except httpx.ConnectError:
        return False, "Connection refused", None
    except Exception as e:
        return False, f"Error: {e}", None


async def check_meilisearch_health(
    service: ServiceDefinition,
    client: httpx.AsyncClient,
) -> tuple[bool, str, dict | None]:
    """
    Check Meilisearch health using /health endpoint.

    Meilisearch returns 200 with {"status": "available"}.
    """
    url = f"http://localhost:{service.port}{service.health_path}"

    try:
        response = await client.get(url, timeout=service.timeout)

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("status") == "available":
                    return True, "OK", data
                else:
                    return False, f"Status: {data.get('status')}", data
            except Exception:
                return True, "OK", None
        else:
            return False, f"Status: {response.status_code}", None

    except httpx.TimeoutException:
        return False, "Timeout", None
    except httpx.ConnectError:
        return False, "Connection refused", None
    except Exception as e:
        return False, f"Error: {e}", None


async def check_nats_health(
    service: ServiceDefinition,
) -> tuple[bool, str, None]:
    """
    Check NATS health using TCP connection.

    NATS monitoring endpoint responds to TCP connection.
    """
    return await check_socket_health(service)


async def check_neo4j_health(
    service: ServiceDefinition,
    client: httpx.AsyncClient,
) -> tuple[bool, str, None]:
    """
    Check Neo4j health using HTTP UI.

    Neo4j browser UI responds with 200.
    """
    url = f"http://localhost:{service.port}{service.health_path}"

    try:
        response = await client.get(url, timeout=service.timeout)

        if response.status_code == 200:
            return True, "OK", None
        else:
            return False, f"Status: {response.status_code}", None

    except httpx.TimeoutException:
        return False, "Timeout", None
    except httpx.ConnectError:
        return False, "Connection refused", None
    except Exception as e:
        return False, f"Error: {e}", None


async def check_socket_health(
    service: ServiceDefinition,
) -> tuple[bool, str, None]:
    """
    Check service health using TCP socket connection.

    For services without HTTP endpoints (NATS, mesh-agent, etc.).
    """
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(service.timeout)

        # Try to connect
        result = sock.connect_ex(("localhost", service.port))
        sock.close()

        if result == 0:
            return True, "OK", None
        else:
            return False, "Connection refused", None

    except socket.timeout:
        return False, "Timeout", None
    except Exception as e:
        return False, f"Error: {e}", None


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.parametrize("service", SERVICES, ids=lambda s: s.name)
@pytest.mark.asyncio
async def test_service_health_endpoint(
    service: ServiceDefinition,
    http_client: httpx.AsyncClient,
):
    """
    Test that service health endpoint returns expected response.

    This parametrized test runs once for each service in the SERVICES list.
    Each test validates:
    1. Service is accessible on its port
    2. Health endpoint returns expected status code
    3. Response contains expected fields (if specified)

    Services are tested in parallel when using pytest-xdist:
        pytest pmoves/tests/smoke/test_health_endpoints.py -n auto

    Expected runtime: <30s for all services (with -n auto)
    """
    # Skip GPU services if GPU not available
    if service.gpu_required:
        # TODO: Add GPU detection logic
        pytest.skip("GPU required - skipping in non-GPU environment")

    # Check health based on service type
    match service.health_type:
        case HealthCheckType.STANDARD:
            is_healthy, message, _ = await check_http_health(service, http_client)
        case HealthCheckType.GRADIO:
            is_healthy, message, _ = await check_gradio_health(service, http_client)
        case HealthCheckType.QDRANT:
            is_healthy, message, _ = await check_qdrant_health(service, http_client)
        case HealthCheckType.MEILISEARCH:
            is_healthy, message, _ = await check_meilisearch_health(service, http_client)
        case HealthCheckType.POSTGRES:
            is_healthy, message, _ = await check_postgres_health(service)
        case HealthCheckType.NATS:
            is_healthy, message, _ = await check_nats_health(service)
        case HealthCheckType.NEO4J:
            is_healthy, message, _ = await check_neo4j_health(service, http_client)
        case HealthCheckType.CONNECTION:
            is_healthy, message, _ = await check_socket_health(service)
        case _:
            is_healthy, message = False, f"Unknown health type: {service.health_type}"

    # Assert result
    assert is_healthy, f"{service.name}:{service.port} - {message}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_gpu_services_can_be_skipped():
    """
    Test that GPU services are properly identified and can be skipped.

    This is a meta-test that validates our GPU service detection.
    """
    # Should have at least some GPU services
    assert len(GPU_SERVICES) > 0, "Expected to find GPU services"

    # All should have gpu_required=True
    for service in GPU_SERVICES:
        assert service.gpu_required, f"{service.name} should be marked as GPU-required"

    # Common GPU services in our catalog
    gpu_service_names = {s.name for s in GPU_SERVICES}
    expected_gpu_services = {
        "hi-rag-gateway-v2-gpu",
        "hi-rag-gateway-gpu",
        "ultimate-tts-studio",
        "ffmpeg-whisper",
        "media-video",
    }

    # At least some expected services should be present
    assert len(gpu_service_names & expected_gpu_services) > 0


# ============================================================================
# AGGREGATE TESTS
# ============================================================================

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_critical_services_minimum_health(http_client: httpx.AsyncClient):
    """
    Smoke test for critical services only.

    Tests a subset of critical services that must be healthy for
    the system to function. This is a faster subset of the full test.

    Critical services: postgres, nats, tensorzero-gateway, agent-zero, hirag-v2
    Expected runtime: <5s
    """
    from pmoves.tests.utils.service_catalog import CRITICAL_PATH

    critical_with_endpoints = [s for s in CRITICAL_PATH if s.port > 0]

    results = []
    for service in critical_with_endpoints:
        # Skip GPU services
        if service.gpu_required:
            continue

        match service.health_type:
            case HealthCheckType.STANDARD:
                is_healthy, message, _ = await check_http_health(service, http_client)
            case HealthCheckType.POSTGRES:
                is_healthy, message, _ = await check_postgres_health(service)
            case HealthCheckType.NATS:
                is_healthy, message, _ = await check_nats_health(service)
            case HealthCheckType.QDRANT:
                is_healthy, message, _ = await check_qdrant_health(service, http_client)
            case HealthCheckType.MEILISEARCH:
                is_healthy, message, _ = await check_meilisearch_health(service, http_client)
            case HealthCheckType.GRADIO:
                is_healthy, message, _ = await check_gradio_health(service, http_client)
            case _:
                is_healthy, message = False, "Not checked"

        results.append((service.name, is_healthy, message))

    # Report failures
    failures = [(name, msg) for name, healthy, msg in results if not healthy]
    if failures:
        failure_summary = "\n".join([f"  - {name}: {msg}" for name, msg in failures])
        pytest.fail(f"Critical services failed:\n{failure_summary}")

    # At least 50% of critical services should be healthy
    healthy_count = sum(1 for _, healthy, _ in results if healthy)
    assert healthy_count >= len(results) * 0.5, (
        f"Less than 50% of critical services healthy ({healthy_count}/{len(results)})"
    )
