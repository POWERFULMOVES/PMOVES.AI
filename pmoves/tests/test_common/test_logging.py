import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.logging import configure_structlog, get_logger, setup_logging


def test_configure_structlog_default():
    """configure_structlog with defaults does not raise."""
    configure_structlog()
    # If structlog is available, it was configured; if not, basicConfig was called.
    # Either way, no exception.


def test_configure_structlog_custom_level():
    """configure_structlog accepts custom log_level."""
    configure_structlog(log_level="DEBUG")
    # No exception raised


def test_get_logger_returns_logger():
    """get_logger returns a logger-like object."""
    logger = get_logger("test.module")
    assert logger is not None
    assert callable(getattr(logger, "info", None)) or callable(getattr(logger, "debug", None))


def test_setup_logging_returns_logger():
    """setup_logging configures structlog and returns a logger."""
    logger = setup_logging("test.setup", log_level="INFO")
    assert logger is not None
    assert callable(getattr(logger, "info", None)) or callable(getattr(logger, "debug", None))
