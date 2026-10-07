"""Pin the Archon 0.6.0+ health surface across every readiness probe.

Archon 0.6.0 (TypeScript/Bun) serves API and UI from one container port, 3090,
published on host 8091 (API alias) and 3737 (UI alias). Its only health route is
``/api/health`` (JSON). The pre-0.6.0 ``/healthz`` and ``/mcp/describe`` routes are
gone and there is no MCP transport (#2943).

The trap these tests guard: Archon's SPA catch-all answers **200 HTML** for any
unknown path, so a probe of a dead route still passes on status code alone. Each
probe below must (a) target ``/api/health`` and (b) reject a 200 that is not a JSON
health body. Four probes carry their own copy of the Archon row:

- pmoves/tools/flight_check_retro.py         (ENDPOINTS / CRITICAL_NAMES)
- pmoves/tools/flightcheck/retro_flightcheck.py (HTTP_HEALTH; run by bringup-showtime --strict)
- pmoves/services/showtime-api/health_probe.py (SERVICE_CATALOG, a hand-kept copy)
- pmoves/tools/topology_chit_gate.py + configs/topology_policy_manifest.json

All tests are offline: every network seam is stubbed (the directory conftest
denies outbound connects).
"""
from __future__ import annotations

import asyncio
import http.client
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[2]

LIVE_HEALTH_BODY = json.dumps({"status": "ok", "adapter": "web", "version": "0.8.0"})
SPA_HTML = "<!doctype html><html><head><title>Archon</title></head><body></body></html>"
OTHER_HTML = "<!doctype html><html><head><title>Some Other App</title></head><body></body></html>"
DEAD_ROUTES = ("/healthz", "/mcp/describe")


def _load(name: str, rel: str, monkeypatch: pytest.MonkeyPatch):
    # flight_check_retro builds ENDPOINTS at import and would shell out to
    # `docker ps` to detect the Supabase runtime; pin it instead.
    monkeypatch.setenv("SUPABASE_RUNTIME", "compose")
    monkeypatch.delenv("SERVICE_ARCHON_URL", raising=False)
    spec = importlib.util.spec_from_file_location(name, PMOVES / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


class _FakeResp:
    def __init__(self, status: int, ctype: str, body: str):
        self.status = status
        self.headers = {"content-type": ctype}
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------- flight_check_retro


@pytest.fixture
def fcr(monkeypatch):
    return _load("flight_check_retro_t", "tools/flight_check_retro.py", monkeypatch)


def test_fcr_archon_api_targets_api_health(fcr):
    urls = dict(fcr.ENDPOINTS)
    assert urls["Archon API"] == "http://localhost:8091/api/health"
    assert urls["Archon UI"] == "http://localhost:3737"


def test_fcr_has_no_dead_archon_surfaces(fcr):
    names = {name for name, _ in fcr.ENDPOINTS}
    assert "Archon MCP" not in names
    for name, url in fcr.ENDPOINTS:
        if name.startswith("Archon"):
            assert not any(url.endswith(r) for r in DEAD_ROUTES), (name, url)


def test_fcr_archon_api_is_critical_and_json_checked(fcr):
    assert {"Archon API", "Archon UI"} <= fcr.CRITICAL_NAMES
    assert "Archon API" in fcr.JSON_HEALTH_NAMES
    # every critical name must exist as an endpoint, or strict silently skips it
    assert fcr.CRITICAL_NAMES - {n for n, _ in fcr.ENDPOINTS} == set()


def test_fcr_service_archon_url_is_a_base_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_RUNTIME", "compose")
    monkeypatch.setenv("SERVICE_ARCHON_URL", "http://archon.example:9999/")
    spec = importlib.util.spec_from_file_location("fcr_env_t", PMOVES / "tools/flight_check_retro.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "fcr_env_t", mod)
    spec.loader.exec_module(mod)
    assert dict(mod.ENDPOINTS)["Archon API"] == "http://archon.example:9999/api/health"


def test_fcr_check_rejects_spa_html_when_json_required(fcr, monkeypatch):
    monkeypatch.setattr(fcr, "urlopen", lambda url, timeout: _FakeResp(200, "text/html; charset=utf-8", SPA_HTML))
    status, code, _ = fcr.check("http://localhost:8091/healthz", require_json=True)
    assert (status, code) == ("error", 200)
    # without the JSON requirement, the same response is (falsely) ok
    assert fcr.check("http://localhost:8091/healthz")[0] == "ok"


def test_fcr_check_accepts_live_health_json(fcr, monkeypatch):
    monkeypatch.setattr(fcr, "urlopen", lambda url, timeout: _FakeResp(200, "application/json", LIVE_HEALTH_BODY))
    assert fcr.check("http://localhost:8091/api/health", require_json=True) == ("ok", 200, "")


def test_fcr_archon_ui_requires_archon_title(fcr, monkeypatch):
    assert fcr.HTML_TITLE_BY_NAME["Archon UI"] == "Archon"
    monkeypatch.setattr(fcr, "urlopen", lambda url, timeout: _FakeResp(200, "text/html", SPA_HTML))
    assert fcr.check("http://localhost:3737", expect_title="Archon")[0] == "ok"
    monkeypatch.setattr(fcr, "urlopen", lambda url, timeout: _FakeResp(200, "text/html", OTHER_HTML))
    assert fcr.check("http://localhost:3737", expect_title="Archon")[:2] == ("error", 200)
    monkeypatch.setattr(fcr, "urlopen", lambda url, timeout: _FakeResp(200, "application/json", LIVE_HEALTH_BODY))
    assert fcr.check("http://localhost:3737", expect_title="Archon")[0] == "error"


@pytest.mark.parametrize(
    "ctype,body,expected",
    [
        ("application/json", LIVE_HEALTH_BODY, True),
        ("application/json", '{"ok": true}', True),
        ("application/json", '{"status": "degraded"}', False),
        ("application/json", "[]", False),
        ("application/json", "not json", False),
        ("text/html", SPA_HTML, False),
        ("text/html", LIVE_HEALTH_BODY, False),
    ],
)
def test_json_health_validators_agree(fcr, monkeypatch, ctype, body, expected):
    # same optional-dep guards as the rfc/hp fixtures, so a missing dep SKIPs uniformly
    pytest.importorskip("rich")
    pytest.importorskip("httpx")
    rfc = _load("retro_flightcheck_t", "tools/flightcheck/retro_flightcheck.py", monkeypatch)
    hp = _load("health_probe_t", "services/showtime-api/health_probe.py", monkeypatch)
    assert fcr.json_health_ok(ctype, body) is expected
    assert rfc._json_status_ok(ctype, body) is expected
    assert hp._json_health_ok(ctype, body) is expected


# --------------------------------------------------------------- retro_flightcheck


@pytest.fixture
def rfc(monkeypatch):
    pytest.importorskip("rich")
    return _load("retro_flightcheck_t", "tools/flightcheck/retro_flightcheck.py", monkeypatch)


def test_rfc_archon_rows(rfc):
    rows = {e[0]: e for e in rfc.HTTP_HEALTH}
    assert rows["archon"][1] == "http://localhost:8091/api/health"
    assert rows["archon"][2] == "json_status_ok"
    assert rows["archon-ui"][1] == "http://localhost:3737"
    assert rows["archon-ui"][2] == "html_title:Archon"
    assert {"archon", "archon-ui"} <= rfc.CRITICAL_HTTP_NAMES
    for e in rfc.HTTP_HEALTH:
        if e[0].startswith("archon"):
            assert not any(e[1].endswith(r) for r in DEAD_ROUTES), e


def _run_check_http(rfc, monkeypatch, archon_resp, ui_resp=(200, "text/html; charset=utf-8", SPA_HTML)):
    """Model the live Archon: /api/health answers archon_resp, :3737 answers ui_resp,
    and EVERY other path on :8091 gets the SPA catch-all (200 HTML), exactly as the
    real container does. Pre-fix code (probing /healthz) must PASS here falsely."""

    def fake_get(url, timeout=4.0):
        if url == "http://localhost:8091/api/health":
            return archon_resp
        if url.startswith("http://localhost:3737"):
            return ui_resp
        if url.startswith("http://localhost:8091"):
            return 200, "text/html; charset=utf-8", SPA_HTML
        return None, "", "refused"

    monkeypatch.setattr(rfc, "_http_get", fake_get)
    rfc.console.quiet = True
    only_archon = [e for e in rfc.HTTP_HEALTH if e[0].startswith("archon")]
    monkeypatch.setattr(rfc, "HTTP_HEALTH", only_archon)
    return rfc.check_http()


def test_rfc_check_http_passes_live_archon(rfc, monkeypatch):
    assert _run_check_http(rfc, monkeypatch, (200, "application/json", LIVE_HEALTH_BODY)) == (0, 0)


def test_rfc_check_http_fails_spa_catch_all(rfc, monkeypatch):
    # /api/health missing (Archon not there / wrong service): every :8091 path is the
    # SPA catch-all. Pre-fix, the /healthz probe passed on that HTML (false PASS).
    assert _run_check_http(rfc, monkeypatch, (200, "text/html; charset=utf-8", SPA_HTML)) == (1, 1)


def test_rfc_check_http_fails_foreign_ui(rfc, monkeypatch):
    # some other app answering 200 on :3737 must not count as the Archon UI
    live = (200, "application/json", LIVE_HEALTH_BODY)
    assert _run_check_http(rfc, monkeypatch, live, ui_resp=(200, "text/html", OTHER_HTML)) == (1, 1)


# --------------------------------------------------------------- showtime-api health_probe


@pytest.fixture
def hp(monkeypatch):
    pytest.importorskip("httpx")
    return _load("health_probe_t", "services/showtime-api/health_probe.py", monkeypatch)


def test_hp_catalog_matches_flight_check_retro(hp, fcr):
    """SERVICE_CATALOG is a hand-kept copy of ENDPOINTS: the Archon rows must agree."""
    cat = {s["name"]: s for s in hp.SERVICE_CATALOG}
    fcr_urls = dict(fcr.ENDPOINTS)
    for name in ("Archon API", "Archon UI"):
        assert cat[name]["url"] == fcr_urls[name], name
    assert cat["Archon API"].get("expect_json") is True
    assert cat["Archon UI"].get("expect_title") == "Archon"
    assert "Archon MCP" not in cat


def _probe(hp, ctype: str, body: str, name: str = "Archon API"):
    import httpx

    transport = httpx.MockTransport(lambda req: httpx.Response(200, headers={"content-type": ctype}, text=body))
    svc = next(s for s in hp.SERVICE_CATALOG if s["name"] == name)

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            return await hp._probe_one(client, svc)

    return asyncio.run(go())


def test_hp_probe_rejects_spa_html(hp):
    r = _probe(hp, "text/html; charset=utf-8", SPA_HTML)
    assert r.ok is False and r.status_code == 200 and r.error


def test_hp_probe_accepts_live_health(hp):
    r = _probe(hp, "application/json", LIVE_HEALTH_BODY)
    assert r.ok is True and r.error == ""


def test_hp_probe_ui_requires_archon_title(hp):
    assert _probe(hp, "text/html; charset=utf-8", SPA_HTML, "Archon UI").ok is True
    r = _probe(hp, "text/html", OTHER_HTML, "Archon UI")
    assert r.ok is False and r.error


# --------------------------------------------------------------- topology_chit_gate


@pytest.fixture
def topo(monkeypatch):
    return _load("topology_chit_gate_t", "tools/topology_chit_gate.py", monkeypatch)


def _archon_inspection(bindings):
    return {
        "pmoves-archon-1": {
            "Config": {"Labels": {"com.docker.compose.service": "archon"}},
            "NetworkSettings": {"Ports": bindings},
        }
    }


LIVE_PORTS = {
    "3090/tcp": [
        {"HostIp": "127.0.0.1", "HostPort": "3090"},
        {"HostIp": "127.0.0.1", "HostPort": "8091"},
        {"HostIp": "127.0.0.1", "HostPort": "3737"},
    ]
}


def test_policy_requires_archon_container_port_3090():
    policy = json.loads((PMOVES / "configs/topology_policy_manifest.json").read_text(encoding="utf-8"))
    # policy entries are CONTAINER ports; 0.6.0 exposes only 3090 (8091/3737 are host aliases)
    assert policy["required_published_ports_by_service"]["archon"] == [3090]


def test_topo_archon_live_layout_passes(topo, monkeypatch):
    seen = []
    monkeypatch.setattr(
        topo, "_json_health_ok", lambda url, **kw: (seen.append((url, kw.get("expect_title"))) or True, "200")
    )
    warnings, errors = [], []
    topo._check_archon_topology(_archon_inspection(LIVE_PORTS), warnings=warnings, errors=errors)
    assert (warnings, errors) == ([], [])
    assert seen == [("http://localhost:8091/api/health", None), ("http://localhost:3737/", "Archon")]


def test_topo_archon_missing_publish_is_error(topo):
    warnings, errors = [], []
    topo._check_archon_topology(_archon_inspection({}), warnings=warnings, errors=errors)
    assert errors == ["pmoves-archon-1 is missing host publish for 3090/tcp"]


def test_topo_json_health_rejects_spa_html(topo, monkeypatch):
    monkeypatch.setattr(topo, "urlopen", lambda req, timeout: _FakeResp(200, "text/html", SPA_HTML))
    ok, detail = topo._json_health_ok("http://localhost:8091/healthz")
    assert ok is False and "non-JSON" in detail
    monkeypatch.setattr(topo, "urlopen", lambda req, timeout: _FakeResp(200, "application/json", LIVE_HEALTH_BODY))
    assert topo._json_health_ok("http://localhost:8091/api/health") == (True, "200")


def test_topo_ui_title_check(topo, monkeypatch):
    monkeypatch.setattr(topo, "urlopen", lambda req, timeout: _FakeResp(200, "text/html", SPA_HTML))
    assert topo._json_health_ok("http://localhost:3737/", expect_title="Archon") == (True, "200")
    monkeypatch.setattr(topo, "urlopen", lambda req, timeout: _FakeResp(200, "text/html", OTHER_HTML))
    ok, detail = topo._json_health_ok("http://localhost:3737/", expect_title="Archon")
    assert ok is False and "titled" in detail


@pytest.mark.parametrize(
    "exc",
    [ConnectionResetError("reset"), OSError("boom"), TimeoutError("slow"), http.client.IncompleteRead(b"")],
)
def test_topo_json_health_survives_socket_errors(topo, monkeypatch, exc):
    def boom(req, timeout):
        raise exc

    monkeypatch.setattr(topo, "urlopen", boom)
    assert topo._json_health_ok("http://localhost:8091/api/health") == (False, "0")
