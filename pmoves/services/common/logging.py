"""Shared structlog configuration for PMOVES services.

Consolidates the identical structlog setup previously duplicated across
gpu-orchestrator, node-registry, and other services.

Usage::

    from services.common.logging import configure_structlog, get_logger

    configure_structlog()
    logger = get_logger(__name__)
    logger.info("service started", port=8080)

Or for immediate setup on import::

    from services.common.logging import setup_logging
    # calls configure_structlog() and returns a logger
"""

from __future__ import annotations

import logging
import os
from typing import Any


def configure_structlog(
    *,
    log_level: str | None = None,
    json_output: bool = True,
    timestamp_format: str = "iso",
    wrapper_class: Any = None,
    context_class: Any = None,
    cache_logger: bool = True,
) -> None:
    """Configure structlog with standard PMOVES processors.

    This sets up both structlog and the stdlib logging bridge so that
    all log output goes through the same structured pipeline.

    Args:
        log_level: Root logger level (``"DEBUG"``, ``"INFO"``, etc.).
            Defaults to ``LOG_LEVEL`` env var or ``"INFO"``.
        json_output: Use JSON renderer (True) or console renderer (False).
        timestamp_format: Timestamp format string passed to TimeStamper.
        wrapper_class: Custom structlog wrapper class.
        context_class: Custom structlog context class.
        cache_logger: Enable structlog logger caching.
    """
    try:
        import structlog
    except ImportError:
        # structlog not available; fall back to basic stdlib logging
        level = log_level or os.getenv("LOG_LEVEL", "INFO")
        logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
        return

    level = log_level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))

    processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt=timestamp_format),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        try:
            processors.append(structlog.dev.ConsoleRenderer())
        except AttributeError:
            processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=wrapper_class or structlog.stdlib.BoundLogger,
        context_class=context_class or dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=cache_logger,
    )


def get_logger(name: str) -> Any:
    """Return a structlog-backed logger for the given module name.

    Falls back to a standard ``logging.Logger`` if structlog is not
    available.

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A structlog BoundLogger or stdlib Logger.
    """
    try:
        import structlog
        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)


def setup_logging(
    name: str,
    *,
    log_level: str | None = None,
    json_output: bool = True,
) -> Any:
    """One-shot logging setup: configure structlog and return a logger.

    Usage::

        logger = setup_logging(__name__)
        logger.info("started")

    Args:
        name: Logger name, typically ``__name__``.
        log_level: Override for ``LOG_LEVEL`` env var.
        json_output: Use JSON output (default True).

    Returns:
        A configured logger instance.
    """
    configure_structlog(log_level=log_level, json_output=json_output)
    return get_logger(name)


__all__ = [
    "configure_structlog",
    "get_logger",
    "setup_logging",
]
