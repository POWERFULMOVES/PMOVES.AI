from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict

import pytest


@pytest.fixture(scope="session")
def load_service_module() -> Callable[[str, str], ModuleType]:
    """Import service modules by relative path and cache per test session."""
    cache: Dict[str, ModuleType] = {}
    base = Path(__file__).resolve().parents[3]

    def _load(name: str, relative_path: str) -> ModuleType:
        if name in cache:
            return cache[name]
        module_path = base / relative_path
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {name} from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cache[name] = module
        return module

    return _load
