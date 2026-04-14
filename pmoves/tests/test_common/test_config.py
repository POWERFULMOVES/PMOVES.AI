import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.config import BaseServiceSettings, TensorZeroSettings, env_bool


def test_env_bool_truthy_values():
    """env_bool returns True for truthy strings."""
    for val in ("1", "true", "yes", "on"):
        with patch.dict(os.environ, {"TEST_BOOL": val}):
            assert env_bool("TEST_BOOL") is True
    # Also test case insensitivity
    for val in ("TRUE", "True", "YES", "ON"):
        with patch.dict(os.environ, {"TEST_BOOL": val}):
            assert env_bool("TEST_BOOL") is True


def test_env_bool_falsy_values():
    """env_bool returns False for falsy strings."""
    for val in ("0", "false", "no", "off", ""):
        with patch.dict(os.environ, {"TEST_BOOL": val}):
            assert env_bool("TEST_BOOL") is False


def test_env_bool_default():
    """env_bool returns default when env var is unset."""
    os.environ.pop("TEST_BOOL_UNSET", None)
    assert env_bool("TEST_BOOL_UNSET", default=False) is False
    assert env_bool("TEST_BOOL_UNSET", default=True) is True


def test_base_service_settings_from_env(monkeypatch):
    """BaseServiceSettings loads from environment variables."""
    monkeypatch.setenv("NATS_URL", "nats://test:4222")
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DOCKED_MODE", "true")
    monkeypatch.setenv("DEBUG", "1")
    settings = BaseServiceSettings()
    assert settings.nats_url == "nats://test:4222"
    assert settings.port == 9090
    assert settings.log_level == "DEBUG"
    assert settings.docked_mode is True
    assert settings.debug is True
