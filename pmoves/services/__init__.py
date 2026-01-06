"""
Compatibility shims for the service directory.

Historically many services lived in kebab-case folders (e.g. `publisher-discord`)
or nested paths without `__init__.py`. The smoke tests and CI now import them as
`pmoves.services.<service>`, so we preload the underlying modules here while also
supporting legacy `services.*` imports.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict

__all__ = [
    "publisher",
    "publisher_discord",
    "pmoves_yt",
    "common",
]

# Import common package directly since it's a real package with __init__.py
from . import common  # noqa: E402, F401

_BASE = Path(__file__).resolve().parent
_ROOT = _BASE.parent
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)

# Register legacy top-level alias before dependent modules import `services.*`.
sys.modules.setdefault("services", sys.modules[__name__])

_ALIASES: Dict[str, Path] = {
    "publisher": _BASE / "publisher" / "publisher.py",
    "publisher_discord": _BASE / "publisher-discord" / "main.py",
    "pmoves_yt": _BASE / "pmoves-yt" / "yt.py",
}


def _load(name: str, path: Path) -> ModuleType:
    module_name = f"{__name__}.{name}"
    legacy_name = f"services.{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    if not path.exists():
        raise ModuleNotFoundError(
            f"Expected module for alias '{module_name}' at {path}, but it does not exist."
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load spec for {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    sys.modules.setdefault(legacy_name, module)
    spec.loader.exec_module(module)
    return module


def __getattr__(name: str) -> ModuleType:
    if name in _ALIASES:
        module = _load(name, _ALIASES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
