"""
Shared utilities for PMOVES services.

The directory historically lacked an ``__init__`` making it a namespace package,
but explicit packaging helps downstream tooling and CI imports such as
``services.common.telemetry`` work reliably.
"""

from .telemetry import *  # noqa: F401,F403
