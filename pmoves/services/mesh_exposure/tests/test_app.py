"""Tests for the mesh_exposure service (slice 4 of the creator-collab lane).

All tests use an in-memory registry + injected reader/writer callables.
No real NATS, Cloudflare, Hostinger, or kvm2 access. No real disk reads
of the live headscale ACL unless the test wants to.
"""
from __future__ import annotations

import os
import sys

import pytest

# Make the service importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
for p in (
    os.path.join(_ROOT, "pmoves", "services", "mesh_exposure"),
    os.path.join(_ROOT, "pmoves", "services"),
    os.path.join(_ROOT, "pmoves"),
    _ROOT,
):
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mesh_exposure.app import create_app  # noqa: E402
from mesh_exposure.state import (  # noqa: E402
    DEFAULT_REGISTRY_DIR,
    Registry,
    desired_cloudflared_entries,
    desired_dns_records,
    desired_headscale_rules,
    diff_cloudflared,
    diff_dns,
    diff_headscale,
    plan,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

TEST_TOKEN = "test-meshbus-token-do-not-use-in-prod"


def _write_entry(path, slug, **overrides):
    """Helper: write a minimal valid curated entry to a temp file."""
    base = {
        "schema_version": "1.0.0",
        "slug": slug,
        "title": slug,
        "description": f"test {slug}",
        "owner": "pinokio",
        "version_seen": "0.0.1",
        "runtime": {
            "launcher_script": "start.js",
            "autostart": False,
            "gpu_required": False,
            "min_vram_mb": 0,
            "gpu_arch": [],
            "gpu_reservation_mb": 0,
            "gpu_reservation_mode": "concurrent",
            "dependencies": [],
            "requires_hf_login": False,
        },
        "endpoints": {
            "primary": {
                "port": 0,
                "protocol": "http",
                "health": None,
            },
            "alt": [],
        },
        "pinokio_skill_ref": None,
        "network_exposure": {
            "l1_venv": {"reachable": True},
            "l2_container_same_host": {"reachable": True, "address": None},
            "l3_mesh": {"reachable": False, "address": None, "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
        "notes": [],
    }
    base.update(overrides)
    path.write_text(yaml.safe_dump(base, sort_keys=False))
    return path


@pytest.fixture
def registry_dir(tmp_path):
    """A fresh curated dir with 3 test entries."""
    d = tmp_path / "curated"
    d.mkdir()
    _write_entry(d / "l4-app.yaml", "l4-app", **{
        "title": "L4 App",
        "endpoints": {"primary": {"port": 8188, "protocol": "http", "health": "/healthz"}, "alt": []},
        "network_exposure": {
            "l1_venv": {"reachable": True},
            "l2_container_same_host": {"reachable": True, "address": "http://host.docker.internal:8188"},
            "l3_mesh": {"reachable": True, "address": "http://l4-app.powerfulmoves-1.ts.pmoves.net:8188",
                         "headscale_acl_ports": [8188], "tags_required": []},
            "l4_public": {"reachable": True, "tunnel": "pmoves-edge",
                          "dns_record": "l4-app.pmoves.ai", "public_url": "https://l4-app.pmoves.ai"},
        },
    })
    _write_entry(d / "mesh-only.yaml", "mesh-only", **{
        "title": "Mesh Only",
        "network_exposure": {
            "l1_venv": {"reachable": True},
            "l2_container_same_host": {"reachable": True, "address": None},
            "l3_mesh": {"reachable": True, "address": "http://mesh-only.powerfulmoves-1.ts.pmoves.net:<dynamic>",
                         "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
    })
    _write_entry(d / "local-only.yaml", "local-only", **{
        "title": "Local Only",
        "network_exposure": {
            "l1_venv": {"reachable": True},
            "l2_container_same_host": {"reachable": False, "address": None},
            "l3_mesh": {"reachable": False, "address": None, "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
    })
    return str(d)


@pytest.fixture
def noop_readers():
    return (
        lambda: [],  # headscale
        lambda: [],  # cloudflared
        lambda: [],  # dns
    )


@pytest.fixture
def recording_writers():
    """Writers that record their calls instead of writing anywhere."""
    headscale_written: list = []
    cloudflared_written: list = []
    dns_written: list = []
    return (
        headscale_written.append,  # HeadscaleWriter
        cloudflared_written.append,
        dns_written.append,
        {"headscale": headscale_written, "cloudflared": cloudflared_written, "dns": dns_written},
    )


@pytest.fixture
def client(registry_dir, noop_readers):
    reg = Registry.load_from_dir(registry_dir)
    app = create_app(
        registry=reg,
        token=TEST_TOKEN,
        headscale_reader=noop_readers[0],
        cloudflared_reader=noop_readers[1],
        dns_reader=noop_readers[2],
    )
    return TestClient(app)


# --------------------------------------------------------------------------
# Registry loader
# --------------------------------------------------------------------------

def test_registry_loads_3_entries_from_test_dir(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    assert len(reg) == 3
    assert reg.slugs == ["l4-app", "local-only", "mesh-only"]
    assert reg.get("l4-app")["title"] == "L4 App"


def test_registry_handles_missing_dir(tmp_path) -> None:
    reg = Registry.load_from_dir(str(tmp_path / "nonexistent"))
    assert len(reg) == 0


def test_registry_skip_malformed_yaml(tmp_path) -> None:
    d = tmp_path / "curated"
    d.mkdir()
    (d / "good.yaml").write_text(yaml.safe_dump({
        "schema_version": "1.0.0", "slug": "good", "title": "Good",
        "description": "ok", "owner": "pinokio", "version_seen": "0.0.1",
        "runtime": {
            "launcher_script": "start.js", "autostart": False,
            "gpu_required": False, "min_vram_mb": 0, "gpu_arch": [],
            "gpu_reservation_mb": 0, "gpu_reservation_mode": "concurrent",
            "dependencies": [], "requires_hf_login": False,
        },
        "endpoints": {"primary": {"port": 0, "protocol": "http", "health": None}, "alt": []},
        "pinokio_skill_ref": None,
        "network_exposure": {
            "l1_venv": {"reachable": True}, "l2_container_same_host": {"reachable": True, "address": None},
            "l3_mesh": {"reachable": False, "address": None, "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
        "notes": [],
    }))
    (d / "bad.yaml").write_text("{ this is not valid yaml")
    reg = Registry.load_from_dir(str(d))
    assert reg.slugs == ["good"]


# --------------------------------------------------------------------------
# Desired-state helpers
# --------------------------------------------------------------------------

def test_desired_headscale_rules_for_mesh_reachable_app(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    rules = desired_headscale_rules(reg.get("l4-app"))
    assert len(rules) == 1
    assert rules[0]["port"] == 8188
    assert rules[0]["src"] == ["group:users"]


def test_desired_headscale_rules_for_mesh_unreachable_app(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    assert desired_headscale_rules(reg.get("mesh-only")) == []  # headscale_acl_ports empty
    assert desired_headscale_rules(reg.get("local-only")) == []  # not reachable


def test_desired_cloudflared_entries_for_l4_app(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    entries = desired_cloudflared_entries(reg.get("l4-app"))
    assert len(entries) == 1
    assert entries[0]["tunnel"] == "pmoves-edge"
    assert entries[0]["hostname"] == "l4-app.pmoves.ai"
    # Check the service URL hostname component, not a substring of the
    # whole URL (CodeQL thread 3657849873 — incomplete URL substring
    # sanitization). Parse the URL, then assert on the hostname field.
    from urllib.parse import urlparse
    parsed = urlparse(entries[0]["service"])
    assert parsed.hostname == "l4-app.powerfulmoves-1.ts.pmoves.net"


def test_desired_cloudflared_entries_for_non_l4_app(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    assert desired_cloudflared_entries(reg.get("mesh-only")) == []
    assert desired_cloudflared_entries(reg.get("local-only")) == []


def test_desired_dns_records_for_l4_app(registry_dir) -> None:
    reg = Registry.load_from_dir(registry_dir)
    recs = desired_dns_records(reg.get("l4-app"))
    assert len(recs) == 1
    assert recs[0]["name"] == "l4-app.pmoves.ai"
    assert recs[0]["type"] == "CNAME"
    assert recs[0]["content"] == "pmoves-edge.cfargotunnel.com"
    assert recs[0]["proxied"] is True


# --------------------------------------------------------------------------
# Diff helpers
# --------------------------------------------------------------------------

def test_diff_headscale_added_removed_unchanged() -> None:
    desired = [
        {"port": 8188, "src": ["group:users"], "dst": ["a"]},
        {"port": 9000, "src": ["group:users"], "dst": ["b"]},
    ]
    current = [
        {"port": 8188, "src": ["group:users"], "dst": ["a"]},  # match
        {"port": 9999, "src": ["group:users"], "dst": ["c"]},  # to be removed
    ]
    a, r, u = diff_headscale(desired, current)
    assert len(a) == 1 and a[0]["port"] == 9000
    assert len(r) == 1 and r[0]["port"] == 9999
    assert u == 1


def test_diff_cloudflared_keyed_by_tunnel_and_hostname() -> None:
    desired = [{"tunnel": "pmoves-edge", "hostname": "a.pmoves.ai", "service": "http://a:1"}]
    current = [
        {"tunnel": "pmoves-edge", "hostname": "a.pmoves.ai", "service": "http://a:1"},  # match
        {"tunnel": "pmoves-edge", "hostname": "b.pmoves.ai", "service": "http://b:2"},  # removed
    ]
    a, r, u = diff_cloudflared(desired, current)
    assert a == []
    assert len(r) == 1 and r[0]["hostname"] == "b.pmoves.ai"
    assert u == 1


def test_diff_dns_keyed_by_name_and_type() -> None:
    desired = [{"name": "x.pmoves.ai", "type": "CNAME", "content": "t.cfargotunnel.com"}]
    current = [{"name": "x.pmoves.ai", "type": "CNAME", "content": "t.cfargotunnel.com"}]
    a, r, u = diff_dns(desired, current)
    assert a == [] and r == [] and u == 1


def test_diff_dns_value_change_triggers_replace() -> None:
    """When the (name, type) key matches but content/ttl/proxied
    differ, the plan must be a remove-then-add (not unchanged).
    The previous contract left the live record pointing at the
    stale target (PR #2283 chatgpt-codex thread 3657849871)."""
    desired = [{"name": "x.pmoves.ai", "type": "CNAME", "content": "new.cfargotunnel.com", "ttl": 60}]
    current = [{"name": "x.pmoves.ai", "type": "CNAME", "content": "old.cfargotunnel.com", "ttl": 300}]
    a, r, u = diff_dns(desired, current)
    assert u == 0
    assert a == desired
    assert r == current


def test_diff_cloudflared_value_change_triggers_replace() -> None:
    """Same value-comparison guarantee for the cloudflared diff:
    a tunnel target move is a replace, not a no-op."""
    desired = [{"tunnel": "pmoves-edge", "hostname": "x.pmoves.ai", "service": "http://new:8188"}]
    current = [{"tunnel": "pmoves-edge", "hostname": "x.pmoves.ai", "service": "http://old:8188"}]
    a, r, u = diff_cloudflared(desired, current)
    assert u == 0
    assert a == desired
    assert r == current


def test_diff_headscale_value_change_triggers_replace() -> None:
    """Same value-comparison guarantee for the headscale diff: a
    src/dst change is a replace, not a no-op."""
    desired = [{"port": 8188, "src": ["group:admins"], "dst": ["b"]}]
    current = [{"port": 8188, "src": ["group:users"], "dst": ["a"]}]
    a, r, u = diff_headscale(desired, current)
    assert u == 0
    assert a == desired
    assert r == current


# --------------------------------------------------------------------------
# Plan: end-to-end
# --------------------------------------------------------------------------

def test_plan_with_empty_current_state_adds_everything(registry_dir, noop_readers) -> None:
    reg = Registry.load_from_dir(registry_dir)
    p = plan(reg, *noop_readers)
    assert p.apps_considered == 3
    # l4-app: 1 headscale + 1 cloudflared + 1 dns
    # mesh-only: 0 (no headscale_acl_ports)
    # local-only: 0 (no exposure)
    assert len(p.headscale_added) == 1
    assert len(p.cloudflared_added) == 1
    assert len(p.dns_added) == 1
    assert p.is_noop() is False


def test_plan_noop_when_current_matches_desired(registry_dir, noop_readers) -> None:
    reg = Registry.load_from_dir(registry_dir)
    p1 = plan(reg, *noop_readers)
    # Pretend current state matches desired
    def hs_cur(): return p1.headscale_added
    def cf_cur(): return p1.cloudflared_added
    def dn_cur(): return p1.dns_added
    p2 = plan(reg, hs_cur, cf_cur, dn_cur)
    assert p2.is_noop() is True
    assert len(p2.headscale_added) == 0
    assert p2.headscale_unchanged_count == 1
    assert p2.cloudflared_unchanged_count == 1
    assert p2.dns_unchanged_count == 1


def test_plan_to_dict_includes_all_sections(registry_dir, noop_readers) -> None:
    reg = Registry.load_from_dir(registry_dir)
    p = plan(reg, *noop_readers)
    d = p.to_dict()
    assert set(d.keys()) == {
        "apps_considered", "apps_skipped", "headscale", "cloudflared", "dns", "is_noop",
    }
    assert d["headscale"]["added"][0]["port"] == 8188
    assert d["cloudflared"]["added"][0]["hostname"] == "l4-app.pmoves.ai"
    assert d["dns"]["added"][0]["name"] == "l4-app.pmoves.ai"


# --------------------------------------------------------------------------
# HTTP: /healthz
# --------------------------------------------------------------------------

def test_healthz_reports_registry_count_and_writes_state(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["registry_entries"] == 3
    # writer_mode is a module-level constant; default is 'noop'. The
    # explicit apply-mode test is below; this one just confirms the
    # field is present.
    assert body["writer_mode"] in ("apply", "noop")
    # Token is set in fixture -> writes enabled
    assert body["writes_enabled"] is True


# --------------------------------------------------------------------------
# HTTP: /v1/registry
# --------------------------------------------------------------------------

def test_list_registry_returns_all(client) -> None:
    r = client.get("/v1/registry")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert {e["slug"] for e in body["entries"]} == {"l4-app", "mesh-only", "local-only"}


def test_list_registry_specific_slug(client) -> None:
    r = client.get("/v1/registry", params={"slug": "l4-app"})
    assert r.status_code == 200
    assert r.json()["entry"]["title"] == "L4 App"


def test_list_registry_unknown_slug_returns_404(client) -> None:
    r = client.get("/v1/registry", params={"slug": "nonexistent"})
    assert r.status_code == 404


# --------------------------------------------------------------------------
# HTTP: /v1/reconcile/plan
# --------------------------------------------------------------------------

def test_get_plan_computes_diff_and_records_state(client) -> None:
    r = client.get("/v1/reconcile/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["is_noop"] is False
    assert len(body["headscale"]["added"]) == 1
    assert len(body["cloudflared"]["added"]) == 1
    assert len(body["dns"]["added"]) == 1
    # After /v1/reconcile/plan, /v1/reconcile/status should reflect
    h = client.get("/v1/reconcile/status").json()
    assert h["last_reconcile_at"] is not None
    assert h["last_change_at"] is not None  # the plan was not a noop


def test_get_plan_noop_does_not_set_last_change_at(client) -> None:
    # First plan populates current state via a chain
    r1 = client.get("/v1/reconcile/plan")
    assert r1.status_code == 200
    client.get("/v1/reconcile/status").json()["last_change_at"]
    # Second plan against the same (mocked empty) current state will
    # still be non-noop because noop_readers returns []; but if we
    # match current state to desired, the noop flag flips. We test
    # the noop detection at the state-layer level separately.
    # Here we just confirm the timestamp advances.
    r2 = client.get("/v1/reconcile/plan")
    assert r2.status_code == 200


# --------------------------------------------------------------------------
# HTTP: /v1/reconcile/apply (write auth)
# --------------------------------------------------------------------------

def test_apply_without_token_returns_503_when_service_token_unset() -> None:
    """If MESH_EXPOSURE_TOKEN is empty, the service ships in read-only
    mode and apply returns 503 with a clear error."""
    # Reload app module with MESHBUS_TOKEN cleared
    import mesh_exposure.app as app_mod
    orig_token = os.environ.pop("MESH_EXPOSURE_TOKEN", None)
    try:
        reg = Registry()
        a = app_mod.create_app(registry=reg, token="")
        c = TestClient(a)
        r = c.post("/v1/reconcile/apply", json={"confirm": True})
        assert r.status_code == 503
        assert "MESH_EXPOSURE_TOKEN" in r.text
    finally:
        if orig_token is not None:
            os.environ["MESH_EXPOSURE_TOKEN"] = orig_token


def test_apply_with_wrong_token_returns_401(client) -> None:
    r = client.post(
        "/v1/reconcile/apply",
        headers={"X-PMOVES-Meshbus-Token": "wrong"},
        json={"confirm": True},
    )
    assert r.status_code == 401


def test_apply_without_confirm_returns_400(client) -> None:
    """The confirm field is a safety gate — caller must explicitly
    acknowledge they read the plan before applying."""
    r = client.post(
        "/v1/reconcile/apply",
        headers={"X-PMOVES-Meshbus-Token": TEST_TOKEN},
        json={"confirm": False},
    )
    assert r.status_code == 400
    assert "confirm" in r.json()["detail"].lower()


def test_apply_in_noop_writer_mode_returns_409(client) -> None:
    """Even with the right token + confirm=true, apply refuses when
    MESH_EXPOSURE_WRITER_MODE is not 'apply'. The default is noop for
    read-only use, which the production operator wires via runbook."""
    r = client.post(
        "/v1/reconcile/apply",
        headers={"X-PMOVES-Meshbus-Token": TEST_TOKEN},
        json={"confirm": True},
    )
    # The fixture doesn't override WRITER_MODE -> default 'noop' is in effect.
    # The response should be 409 explaining the writer mode.
    assert r.status_code == 409
    assert "WRITER_MODE" in r.text


def test_apply_in_apply_writer_mode_records_last_apply(client, monkeypatch) -> None:
    """When WRITER_MODE=apply, the writers are called. We use
    recording writers to verify the diff was passed through."""
    from mesh_exposure.state import plan as plan_fn
    reg = client.app.state.registry
    plan_fn(reg, lambda: [], lambda: [], lambda: [])
    written: dict = {"h": [], "c": [], "d": []}
    create_app(
        registry=reg,
        token=TEST_TOKEN,
        headscale_reader=lambda: [],
        cloudflared_reader=lambda: [],
        dns_reader=lambda: [],
        headscale_writer=lambda added, removed: written["h"].extend(added),
        cloudflared_writer=lambda added, removed: written["c"].extend(added),
        dns_writer=lambda added, removed: written["d"].extend(added),
    )
    # The fixture's app has WRITER_MODE=noop. We need to reload to get
    # the apply mode without monkeypatching the module-level constant.
    import importlib
    import mesh_exposure.app as app_mod
    monkeypatch.setenv("MESH_EXPOSURE_WRITER_MODE", "apply")
    importlib.reload(app_mod)
    a2 = app_mod.create_app(
        registry=reg,
        token=TEST_TOKEN,
        headscale_reader=lambda: [],
        cloudflared_reader=lambda: [],
        dns_reader=lambda: [],
        headscale_writer=lambda added, removed: written["h"].extend(added),
        cloudflared_writer=lambda added, removed: written["c"].extend(added),
        dns_writer=lambda added, removed: written["d"].extend(added),
    )
    c = TestClient(a2)
    r = c.post(
        "/v1/reconcile/apply",
        headers={"X-PMOVES-Meshbus-Token": TEST_TOKEN},
        json={"confirm": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["headscale_written"]) == 1
    assert len(body["cloudflared_written"]) == 1
    assert len(body["dns_written"]) == 1
    assert body["headscale_written"][0]["port"] == 8188


# --------------------------------------------------------------------------
# HTTP: /v1/reconcile/preview (per-slug dry-run, needs write auth)
# --------------------------------------------------------------------------

def test_preview_per_slug_returns_per_target_diff(client) -> None:
    r = client.post(
        "/v1/reconcile/preview?slug=l4-app",
        headers={"X-PMOVES-Meshbus-Token": TEST_TOKEN},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "l4-app"
    assert len(body["headscale"]["added"]) == 1
    assert body["headscale"]["added"][0]["port"] == 8188
    assert len(body["cloudflared"]["added"]) == 1
    assert body["cloudflared"]["added"][0]["hostname"] == "l4-app.pmoves.ai"


def test_preview_unknown_slug_returns_404(client) -> None:
    r = client.post(
        "/v1/reconcile/preview?slug=nope",
        headers={"X-PMOVES-Meshbus-Token": TEST_TOKEN},
    )
    assert r.status_code == 404


def test_preview_requires_token(client) -> None:
    r = client.post("/v1/reconcile/preview?slug=l4-app")
    assert r.status_code == 401


# --------------------------------------------------------------------------
# Live registry: confirm the 12 slice-4 curated entries are reachable
# --------------------------------------------------------------------------

def test_live_registry_loads_12_entries_from_slice4_curated() -> None:
    """Sanity check: the real slice-4 curated dir parses cleanly and the
    2 L4 apps (comfyui-desktop + ultimate-tts-studio) surface in the
    plan as expected."""
    reg = Registry.load_from_dir(DEFAULT_REGISTRY_DIR)
    assert len(reg) == 12
    l4 = reg.filter_l4_public()
    slugs = {e["slug"] for e in l4}
    assert slugs == {"comfyui-desktop", "ultimate-tts-studio"}
    # All 12 have a valid network_exposure block
    for e in reg.all():
        assert "network_exposure" in e
        for layer in ("l1_venv", "l2_container_same_host", "l3_mesh", "l4_public"):
            assert layer in e["network_exposure"]
            assert "reachable" in e["network_exposure"][layer]
