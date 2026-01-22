"""Pytest configuration and shared fixtures for flute-gateway tests."""

import os
import sys

import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "functional: marks tests as functional (require live services, deselect with '-m \"not functional\"')"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# Environment defaults for tests
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("FLUTE_API_KEY", "test-api-key")
os.environ.setdefault("ULTIMATE_TTS_URL", "http://localhost:7861")
