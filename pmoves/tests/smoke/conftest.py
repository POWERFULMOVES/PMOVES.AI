"""Smoke test conftest — ensures the smoke directory is importable."""

import subprocess
import sys
from pathlib import Path

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
