"""
Pytest configuration for PMOVES integration tests.
"""

import os
import pytest

# Load environment from env.shared if available
ENV_SHARED_PATH = "/home/pmoves/PMOVES.AI/pmoves/env.shared"

def load_env_shared():
    """Load environment variables from env.shared."""
    if os.path.exists(ENV_SHARED_PATH):
        with open(ENV_SHARED_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    # Don't override existing env vars
                    if key not in os.environ:
                        os.environ[key] = value


# Load on import
load_env_shared()


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "health: mark test as health check"
    )
    config.addinivalue_line(
        "markers", "wealth: mark test as wealth/finance integration"
    )


@pytest.fixture(scope="session")
def env_vars():
    """Provide access to loaded environment variables."""
    return {
        "JELLYFIN_URL": os.getenv("JELLYFIN_URL", "http://localhost:8096"),
        "JELLYFIN_API_KEY": os.getenv("JELLYFIN_API_KEY", ""),
        "FIREFLY_URL": os.getenv("FIREFLY_URL", "http://localhost:8082"),
        "FIREFLY_ACCESS_TOKEN": os.getenv("FIREFLY_ACCESS_TOKEN", ""),
        "WGER_URL": os.getenv("WGER_URL", "http://localhost:8002"),
        "WGER_API_TOKEN": os.getenv("WGER_API_TOKEN", ""),
        "OPEN_NOTEBOOK_URL": os.getenv("OPEN_NOTEBOOK_URL", "http://localhost:5055"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL", "http://localhost:65421"),
        "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    }
