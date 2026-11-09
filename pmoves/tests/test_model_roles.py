"""The role vocabulary is a closed set, and superseded names resolve with a warning."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_role_resolves_without_warning():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("deep_debugging", roles)
    assert canonical == "deep_debugging"
    assert warning is None


def test_superseded_role_resolves_and_warns():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("debugging", roles)
    assert canonical == "deep_debugging", "a superseded name must still resolve"
    assert warning is not None and "superseded" in warning


def test_unknown_role_does_not_resolve():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("vibes_based_refactor", roles)
    assert canonical is None
    assert warning is not None


def test_wildcard_role_is_always_valid():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("*", roles)
    assert canonical == "*"
    assert warning is None
