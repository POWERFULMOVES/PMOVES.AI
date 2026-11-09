"""Tests for cf_dns_token_provision — no live Cloudflare calls (transport injected)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools import cf_dns_token_provision as mod

ZONE_ID = "eb78d65290b24279ba6f44721b3ea3c4"
ACCOUNT_ID = "aa11bb22cc33dd44ee55ff66aa77bb88"
DNS_EDIT_ID = "4755a26eedb94da69e1066d98aa820be"
ZONE_READ_ID = "c8fed203ed3043cba015a93ad1616f1f"


def _ok(result):
    return 200, {"success": True, "result": result, "errors": []}


def make_transport(*, zone_found=True, groups="both", token_value="cf-new-secret-value",
                   tokens_list=None, tokens_readable=True):
    """Build a fake CF transport keyed on (method, path). Records the POST body."""
    calls = {"created_policies": None, "post_count": 0}

    def transport(method, url, headers, body):
        path = url.replace(mod.CF_API_BASE, "")
        if method == "GET" and path.startswith("/zones"):
            return _ok([{"id": ZONE_ID, "name": "pmoves.ai",
                         "account": {"id": ACCOUNT_ID}}] if zone_found else [])
        if method == "GET" and path.startswith("/user/tokens/permission_groups"):
            g = []
            if groups in ("both", "edit_only"):
                g.append({"id": DNS_EDIT_ID, "name": "DNS Write", "scopes": ["com.cloudflare.api.account.zone"]})
            if groups in ("both", "read_only"):
                g.append({"id": ZONE_READ_ID, "name": "Zone Read", "scopes": ["com.cloudflare.api.account.zone"]})
            return _ok(g)
        if method == "GET" and path.startswith("/user/tokens"):
            if not tokens_readable:
                return 403, {"success": False, "result": None,
                             "errors": [{"message": "Authentication error"}]}
            return _ok([{"name": n} for n in (tokens_list or [])])
        if method == "POST" and path == "/user/tokens":
            calls["post_count"] += 1
            calls["created_policies"] = json.loads(body.decode("utf-8"))["policies"]
            return _ok({"id": "newtok123", "value": token_value})
        raise AssertionError(f"unexpected call {method} {path}")

    return transport, calls


def test_resolve_zone_and_plan_scopes_to_single_zone():
    transport, _ = make_transport()
    client = mod.CFClient(admin_token="admin", transport=transport)
    plan = mod.build_plan(client, "pmoves.ai", "pmoves-traefik-dns01-pmoves.ai")
    assert plan.zone.id == ZONE_ID and plan.zone.account_id == ACCOUNT_ID
    assert plan.dns_edit_group_id == DNS_EDIT_ID and plan.zone_read_group_id == ZONE_READ_ID
    pol = plan.policy()
    # Exactly one allow policy, scoped to ONLY the pmoves.ai zone, with both groups.
    assert len(pol) == 1 and pol[0]["effect"] == "allow"
    assert list(pol[0]["resources"]) == [f"com.cloudflare.api.account.zone.{ZONE_ID}"]
    assert {g["id"] for g in pol[0]["permission_groups"]} == {DNS_EDIT_ID, ZONE_READ_ID}


def test_resolve_zone_missing_raises():
    transport, _ = make_transport(zone_found=False)
    client = mod.CFClient(admin_token="admin", transport=transport)
    with pytest.raises(mod.CFApiError, match="not found"):
        mod.resolve_zone(client, "pmoves.ai")


def test_missing_permission_group_lists_available(capsys):
    transport, _ = make_transport(groups="read_only")  # DNS Write absent
    client = mod.CFClient(admin_token="admin", transport=transport)
    with pytest.raises(mod.CFApiError) as exc:
        mod.select_permission_groups(client)
    # The diagnostic lists zone-scoped group NAMES (never secret) to aid the operator.
    assert "Zone Read" in str(exc.value)


def test_create_token_without_value_raises():
    transport, _ = make_transport(token_value="")
    client = mod.CFClient(admin_token="admin", transport=transport)
    plan = mod.build_plan(client, "pmoves.ai", "t")
    with pytest.raises(mod.CFApiError, match="no value"):
        mod.create_token(client, plan)


def test_main_requires_admin_env(monkeypatch, capsys):
    monkeypatch.delenv("CF_ADMIN_API_TOKEN", raising=False)
    rc = mod.main([], transport=make_transport()[0])
    assert rc == 2
    assert "CF_ADMIN_API_TOKEN" in capsys.readouterr().err


def test_main_dry_run_mints_nothing(monkeypatch, capsys):
    monkeypatch.setenv("CF_ADMIN_API_TOKEN", "admin")
    transport, calls = make_transport()
    funneled = []
    rc = mod.main([], transport=transport, rotate_runner=lambda s: funneled.append(s))
    out = capsys.readouterr().out
    assert rc == 0
    assert calls["post_count"] == 0 and funneled == []      # nothing created, nothing funnelled
    assert "dry-run" in out.lower() and ZONE_ID in out


def test_main_apply_creates_and_funnels_secret_via_runner(monkeypatch, capsys):
    monkeypatch.setenv("CF_ADMIN_API_TOKEN", "admin")
    transport, calls = make_transport(token_value="the-real-secret")
    funneled = []
    rc = mod.main(["--apply"], transport=transport, rotate_runner=lambda s: funneled.append(s))
    out = capsys.readouterr().out
    assert rc == 0
    assert calls["post_count"] == 1
    # The secret reaches the funnel runner (which in prod injects it into the child
    # env for `make secrets-rotate`) and NEVER appears in stdout.
    assert funneled == ["the-real-secret"]
    assert "the-real-secret" not in out


def test_main_apply_reports_funnel_failure_without_leaking(monkeypatch, capsys):
    monkeypatch.setenv("CF_ADMIN_API_TOKEN", "admin")
    transport, _ = make_transport(token_value="leaky-secret")

    def _boom(_secret):
        raise RuntimeError("secrets-rotate failed: boom")

    rc = mod.main(["--apply"], transport=transport, rotate_runner=_boom)
    err = capsys.readouterr()
    assert rc == 1
    assert "funnel failed" in err.err
    assert "leaky-secret" not in (err.out + err.err)   # never leak the value on failure


def test_main_apply_warns_on_duplicate_token_name(monkeypatch, capsys):
    monkeypatch.setenv("CF_ADMIN_API_TOKEN", "admin")
    name = "pmoves-traefik-dns01-pmoves.ai"
    transport, _ = make_transport(tokens_list=[name])
    rc = mod.main([], transport=transport, rotate_runner=lambda s: None)  # dry-run still lists
    out = capsys.readouterr().out
    assert rc == 0 and "already exists" in out
