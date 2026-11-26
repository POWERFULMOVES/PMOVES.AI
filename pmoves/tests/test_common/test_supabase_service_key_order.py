"""SUPABASE_SERVICE_ROLE_KEY is canonical; SUPABASE_KEY is a read-fallback only.

#3498 stopped shipping per-node Supabase keys from GitHub Prod, so every
resolver that read SUPABASE_KEY first (or only) now prefers the canonical
service-role name and keeps SUPABASE_KEY working alone. All values are fakes.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

from services.common import env as common_env

PMOVES = Path(__file__).resolve().parents[2]
_NAMES = (
    "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_KEY", "ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY_FILE", "SUPABASE_SERVICE_KEY_FILE", "SUPABASE_KEY_FILE",
    "ANON_KEY_FILE", "SUPABASE_REALTIME_KEY", "REALTIME_ANON_KEY", "SUPABASE_ANON_KEY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


# --- services/common/env.py (used by services/common/supabase.py) ---


def test_common_service_role_key_wins(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "role-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_KEY", "alias-key")
    assert common_env.supabase_service_key() == "role-key"


def test_common_supabase_key_alone_still_works(monkeypatch):
    monkeypatch.setenv("SUPABASE_KEY", "alias-key")
    assert common_env.supabase_service_key() == "alias-key"


def test_common_none_set_returns_default():
    assert common_env.supabase_service_key() is None
    assert common_env.supabase_service_key("") == ""


# --- flute-gateway persona_selector ---


def _persona_selector():
    pytest.importorskip("httpx")
    pytest.importorskip("yaml")
    return _load("persona_selector_under_test", PMOVES / "services" / "flute-gateway" / "persona_selector.py")


def test_persona_service_role_key_wins_over_alias_and_anon(monkeypatch):
    mod = _persona_selector()
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "role-key")
    monkeypatch.setenv("SUPABASE_KEY", "alias-key")
    monkeypatch.setenv("ANON_KEY", "anon-key")
    assert mod._resolve_supabase_key() == "role-key"


def test_persona_supabase_key_alone_still_works(monkeypatch):
    mod = _persona_selector()
    monkeypatch.setenv("SUPABASE_KEY", "alias-key")
    monkeypatch.setenv("ANON_KEY", "anon-key")
    assert mod._resolve_supabase_key() == "alias-key"


def test_persona_anon_fallback_is_logged(monkeypatch, caplog):
    mod = _persona_selector()
    monkeypatch.setenv("ANON_KEY", "anon-key")
    with caplog.at_level(logging.WARNING):
        assert mod._resolve_supabase_key() == "anon-key"
    assert "falling back to ANON_KEY" in caplog.text
    assert "anon-key" not in caplog.text


# --- hi-rag-gateway-v2 config (realtime JWT source) ---

_JWT_ROLE = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.cm9sZQ"
_JWT_ALIAS = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.YWxpYXM"


def _hirag_config():
    return _load("hirag_config_under_test", PMOVES / "services" / "hi-rag-gateway-v2" / "config.py")


def test_hirag_service_role_key_wins(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _JWT_ROLE)
    monkeypatch.setenv("SUPABASE_KEY", _JWT_ALIAS)
    cfg = _hirag_config()
    assert cfg._jwt_service_key == _JWT_ROLE
    assert cfg.SUPABASE_REALTIME_KEY == _JWT_ROLE


def test_hirag_supabase_key_alone_still_works(monkeypatch):
    monkeypatch.setenv("SUPABASE_KEY", _JWT_ALIAS)
    cfg = _hirag_config()
    assert cfg._jwt_service_key == _JWT_ALIAS
    assert cfg.SUPABASE_REALTIME_KEY == _JWT_ALIAS
