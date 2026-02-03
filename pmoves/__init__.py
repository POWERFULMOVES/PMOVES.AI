<<<<<<< HEAD
"""
Lightweight package initializer so project modules can be imported as
`pmoves.services.*` inside local tooling and CI contexts.

The directory tree predates a traditional Python package layout (service code
often lives in hyphenated folders).  Rather than forcing a large refactor, we
bootstrap a namespace package here and let `pmoves.services` take care of the
compatibility shims.
"""

import sys
from importlib import import_module as _import_module

__all__ = ["services"]

# Trigger import side-effects so compatibility loaders register.
_services_module = _import_module("pmoves.services")

# Provide legacy alias so imports like `services.common.telemetry` keep working.
sys.modules.setdefault("services", _services_module)
=======
"""PMOVES.AI - Multi-Agent Orchestration Platform.

This package provides the core services and utilities for the PMOVES.AI
distributed computing platform.
"""

__version__ = "0.1.0"
>>>>>>> origin/main
