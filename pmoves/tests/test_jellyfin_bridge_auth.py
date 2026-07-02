"""Tests for jellyfin-bridge's branded MediaBrowser auth header.

The bridge must use the official Jellyfin auth scheme — Authorization: MediaBrowser
Client="…" … Token="…" (the declared securityScheme is X-Emby-Authorization; this
is its recommended standard form) — branded with JELLYFIN_CLIENT_NAME (PMOVES.AI),
and must NOT use the deprecated X-Emby-Token header or api_key query param.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[1] / "services" / "jellyfin-bridge" / "main.py"
pytest.importorskip("httpx")
pytest.importorskip("fastapi")
pytest.importorskip("prometheus_client")

sys.path.insert(0, str(_MOD.parent))  # service dir — main.py imports sibling 'tac_tree'
_spec = importlib.util.spec_from_file_location("jellyfin_bridge_main_under_test", _MOD)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)


def test_auth_header_is_branded_mediabrowser(monkeypatch):
    monkeypatch.setattr(m, "JELLYFIN_API_KEY", "tok123")
    monkeypatch.setattr(m, "JELLYFIN_CLIENT_NAME", "PMOVES.AI")
    h = m._jellyfin_auth_headers()
    auth = h["Authorization"]
    assert auth.startswith("MediaBrowser ")
    assert 'Client="PMOVES.AI"' in auth and 'Device="PMOVES.AI"' in auth
    assert 'Token="tok123"' in auth
    assert "X-Emby-Token" not in h  # deprecated form must be gone
    assert h["Accept"] == "application/json"


def test_auth_header_merges_extra_headers(monkeypatch):
    monkeypatch.setattr(m, "JELLYFIN_API_KEY", "t")
    h = m._jellyfin_auth_headers({"Content-Type": "application/json"})
    assert h["Content-Type"] == "application/json"
    assert h["Authorization"].startswith("MediaBrowser ")


def test_client_name_is_configurable(monkeypatch):
    monkeypatch.setattr(m, "JELLYFIN_API_KEY", "t")
    monkeypatch.setattr(m, "JELLYFIN_CLIENT_NAME", "Custom Brand")
    auth = m._jellyfin_auth_headers()["Authorization"]
    assert 'Client="Custom Brand"' in auth
