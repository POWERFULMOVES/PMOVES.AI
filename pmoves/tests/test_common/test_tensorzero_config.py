import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.tensorzero import (
    sync_openai_compat_env,
    tensorzero_openai_base,
)


def test_tensorzero_openai_base_from_env(monkeypatch):
    """When TENSORZERO_BASE_URL is set, it is used directly."""
    monkeypatch.delenv("TENSORZERO_BASE_URL", raising=False)
    monkeypatch.delenv("TENSORZERO_URL", raising=False)
    monkeypatch.delenv("DOCKED_MODE", raising=False)
    monkeypatch.setenv("TENSORZERO_BASE_URL", "http://my-tz:3030")
    result = tensorzero_openai_base()
    assert "my-tz:3030" in result
    assert result.endswith("/openai/v1")


def test_tensorzero_openai_base_from_tensorzero_url(monkeypatch):
    """When TENSORZERO_URL is set (no TENSORZERO_BASE_URL), derive the base."""
    monkeypatch.delenv("TENSORZERO_BASE_URL", raising=False)
    monkeypatch.delenv("DOCKED_MODE", raising=False)
    monkeypatch.setenv("TENSORZERO_URL", "http://parent-tz:3000")
    result = tensorzero_openai_base()
    assert "parent-tz:3000" in result
    assert result.endswith("/openai/v1")


def test_sync_openai_compat_env_sets_vars(monkeypatch):
    """sync_openai_compat_env sets OPENAI_API_KEY from TENSORZERO_API_KEY."""
    monkeypatch.delenv("OPENAI_COMPATIBLE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.setenv("TENSORZERO_BASE_URL", "http://tz:3030")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_secret(key):
        # OPENAI_API_KEY is not set -> return empty to trigger TZ fallback
        if key == "OPENAI_API_KEY":
            return ""
        if key == "TENSORZERO_API_KEY":
            return "test-tz-key"
        return ""

    sync_openai_compat_env(get_secret=fake_secret)

    # OPENAI_API_KEY should have been derived from TENSORZERO_API_KEY
    assert os.environ.get("OPENAI_API_KEY") == "test-tz-key"


def test_check_connectivity_timeout(monkeypatch):
    """When TensorZero is unreachable, tensorzero_openai_base returns empty."""
    monkeypatch.delenv("TENSORZERO_BASE_URL", raising=False)
    monkeypatch.delenv("TENSORZERO_URL", raising=False)
    monkeypatch.delenv("DOCKED_MODE", raising=False)
    # With DOCKED_MODE not set, it defaults to host.docker.internal
    with patch(
        "services.common.tensorzero._check_tensorzero_sync", return_value=False
    ):
        result = tensorzero_openai_base(check_connectivity=True)
        assert result == ""
