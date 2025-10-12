"""
Compatibility shims for the service directory.

Historically many services lived in kebab-case folders (e.g. `publisher-discord`)
or nested paths without `__init__.py`.  The smoke tests and CI now import them as
`pmoves.services.<service>` as well as the legacy `services.<service>` form.
This module keeps both entry points working without forcing a directory
restructure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict

__all__ = ["publisher", "publisher_discord", "pmoves_yt"]

_BASE = Path(__file__).resolve().parent
_ROOT = _BASE.parent
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)

_ALIASES: Dict[str, Path] = {
    "publisher": _BASE / "publisher" / "publisher.py",
    "publisher_discord": _BASE / "publisher-discord" / "main.py",
    "pmoves_yt": _BASE / "pmoves-yt" / "yt.py",
}

# Register legacy top-level alias before any dynamic imports fire.
sys.modules.setdefault("services", sys.modules[__name__])


def _load(name: str, path: Path) -> ModuleType:
    module_name = f"{__name__}.{name}"
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
    spec.loader.exec_module(module)
    return module


def __getattr__(name: str) -> ModuleType:
    if name in _ALIASES:
        module = _load(name, _ALIASES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(list(globals().keys()) + list(__all__)))
