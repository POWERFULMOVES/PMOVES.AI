"""Smoke test conftest — ensures the smoke directory is importable."""

import subprocess
import sys
from pathlib import Path

import httpx
import pytest

# Add the smoke directory to sys.path so _smoke_helpers can be imported
_smoke_dir = str(Path(__file__).resolve().parent)
if _smoke_dir not in sys.path:
    sys.path.insert(0, _smoke_dir)


def is_docker_service_running(name: str) -> bool:
    """Check if a Docker service container is running (fast, no network I/O).

    Uses ``docker ps`` with a name filter. Returns False if docker CLI
    is not available or the command times out.
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name={name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def docker_available() -> bool:
    """Check if Docker CLI is available and responsive.

    Consolidates the duplicate ``_docker_available()`` helpers that were
    scattered across individual test modules.
    """
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


def container_running(name: str) -> bool:
    """Check if a Docker container is running by name.

    Uses ``docker ps`` with a name filter and checks for 'Up' in status.
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "Up" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_docker: test requires Docker CLI and daemon"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked requires_docker when Docker is unavailable."""
    if docker_available():
        return
    skip_docker = pytest.mark.skip(reason="Docker not available")
    for item in items:
        if "requires_docker" in item.keywords:
            item.add_marker(skip_docker)


@pytest.fixture(scope="session")
async def http_client():
    """Shared async HTTP client for smoke tests."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client
