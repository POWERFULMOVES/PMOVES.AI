from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException


def _load_security_module(monkeypatch: pytest.MonkeyPatch):
    config_mod = types.ModuleType("config")
    config_mod.TAILSCALE_ONLY = False
    config_mod.TAILSCALE_ADMIN_ONLY = False
    config_mod.TAILSCALE_CIDRS = []
    config_mod.TRUSTED_PROXY_SOURCES = []
    config_mod.CHIT_IMAGE_FETCH_ALLOW_PRIVATE = False
    config_mod.CHIT_IMAGE_FETCH_ALLOWED_HOSTS = {"cdn.example.com"}
    config_mod.logger = types.SimpleNamespace(warning=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "config", config_mod)

    module_name = "hirag_gateway_v2_security_test"
    sys.modules.pop(module_name, None)
    module_path = Path(__file__).resolve().parents[1] / "security.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sanitize_fetch_path_allows_safe_segments_and_query(monkeypatch: pytest.MonkeyPatch):
    module = _load_security_module(monkeypatch)

    result = module._sanitize_fetch_path(
        "/mindmap/frame-001.png",
        "token=abc123&sig=deadbeef",
    )

    assert result == "/mindmap/frame-001.png?token=abc123&sig=deadbeef"


def test_sanitize_fetch_path_rejects_absolute_form_segments(monkeypatch: pytest.MonkeyPatch):
    module = _load_security_module(monkeypatch)

    with pytest.raises(HTTPException, match="unsafe path segment"):
        module._sanitize_fetch_path("/mindmap/http:evil", "")


def test_sanitize_fetch_path_rejects_unsafe_query_values(monkeypatch: pytest.MonkeyPatch):
    module = _load_security_module(monkeypatch)

    with pytest.raises(HTTPException, match="unsafe query parameter"):
        module._sanitize_fetch_path("/mindmap/frame-001.png", "redirect=http://evil")


def test_validate_remote_image_url_blocks_non_allowlisted_hosts(monkeypatch: pytest.MonkeyPatch):
    module = _load_security_module(monkeypatch)

    with pytest.raises(HTTPException, match="image host not allowed"):
        module._validate_remote_image_url("https://evil.example.com/frame-001.png")
