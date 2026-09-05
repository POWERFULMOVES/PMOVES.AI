"""Tests for gh_app_token — the sanctioned local GitHub App token mint.

Covers the pieces that can be tested without network or secrets: the
scoping truth table (the GITHUB_APP.md rules), JWT construction shape,
permission parsing, and the secret-handoff file mode.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import time
from pathlib import Path

import jwt
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # .../PMOVES.AI-ghapp
TOOL = REPO_ROOT / "pmoves" / "tools" / "gh_app_token.py"

spec = importlib.util.spec_from_file_location("gh_app_token", TOOL)
mod = importlib.util.module_from_spec(spec)
sys.modules["gh_app_token"] = mod
spec.loader.exec_module(mod)


def test_scope_body_lists_repos_and_permissions():
    body = mod.build_scope_body(["PMOVES.AI"], {"contents": "read"})
    assert body == {"repositories": ["PMOVES.AI"], "permissions": {"contents": "read"}}


def test_scope_body_empty_is_installation_default():
    assert mod.build_scope_body([], {}) == {}


def test_parse_permissions_read_write_only():
    assert mod.parse_permissions("contents:read, pull_requests:write") == {
        "contents": "read",
        "pull_requests": "write",
    }
    with pytest.raises(SystemExit):
        mod.parse_permissions("contents:admin")
    with pytest.raises(SystemExit):
        mod.parse_permissions("contents")


def test_jwt_is_rs256_with_ten_minute_cap():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # test-only key
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    now = time.time()
    encoded = mod.build_app_jwt("123456", pem, now=now)
    claims = jwt.decode(encoded, public_pem, algorithms=["RS256"])
    assert claims["iss"] == "123456"
    assert claims["exp"] - claims["iat"] <= 600


def test_write_token_file_is_owner_only(tmp_path):
    target = tmp_path / "nested" / "token"
    mod.write_token_file(target, "ghs_example")
    assert target.read_text().strip() == "ghs_example"
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_dry_run_makes_no_network(monkeypatch, capsys):
    monkeypatch.setenv("GH_APP_ID", "123")
    monkeypatch.setenv("GH_APP_CLIENT_ID", "Iv1.test")
    monkeypatch.setenv("GH_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("GH_APP_SEC", "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    rc = mod.main(["--repositories", "PMOVES.AI", "--permissions", "contents:read", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no network call made" in out
    assert "PMOVES.AI" in out


def test_missing_repositories_refused(monkeypatch):
    monkeypatch.setenv("GH_APP_ID", "123")
    monkeypatch.setenv("GH_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("GH_APP_SEC", "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    with pytest.raises(SystemExit) as exc:
        mod.main([])
    assert exc.value.code == 3


def test_all_requires_yes(monkeypatch):
    monkeypatch.setenv("GH_APP_ID", "123")
    monkeypatch.setenv("GH_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("GH_APP_SEC", "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    with pytest.raises(SystemExit) as exc:
        mod.main(["--all"])
    assert exc.value.code == 3
