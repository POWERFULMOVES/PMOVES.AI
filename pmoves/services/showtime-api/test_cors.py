"""CORS preflight tests for the Showtime API.

Regression guard for DL-3.2: the Notebook UI (served on :4482) fetches Showtime
endpoints cross-origin. These assert the explicit allow-list echoes listed
origins (including the Notebook origin) and never echoes unlisted origins.
"""
import importlib
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

# Make the service module importable in isolation (mirrors botz-gateway/conftest.py).
sys.path.insert(0, str(Path(__file__).parent))

# ``app`` imports ``cgp_decoder`` (owned by a sibling task/module that may be absent
# in isolation). Provide a lightweight stub so the CORS wiring can be imported and
# exercised on its own. This has no bearing on the CORS behaviour under test.
if "cgp_decoder" not in sys.modules:
    try:  # pragma: no cover - prefer the real module when present
        importlib.import_module("cgp_decoder")
    except ModuleNotFoundError:
        _stub = types.ModuleType("cgp_decoder")

        class ValidationResult:  # minimal placeholder
            pass

        def validate_cgp(*args, **kwargs):  # noqa: D401 - placeholder
            raise NotImplementedError

        _stub.ValidationResult = ValidationResult
        _stub.validate_cgp = validate_cgp
        sys.modules["cgp_decoder"] = _stub


def _client():
    app_module = importlib.import_module("app")
    return TestClient(app_module.app)


def test_preflight_allows_listed_origin():
    client = _client()
    resp = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:9225",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:9225"


def test_preflight_rejects_unlisted_origin():
    client = _client()
    resp = client.options(
        "/healthz",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette does not echo an allow-origin header for a disallowed origin.
    assert resp.headers.get("access-control-allow-origin") != "http://evil.example"


def test_actual_get_carries_allow_origin_for_listed():
    client = _client()
    resp = client.get(
        "/healthz",
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_preflight_allows_notebook_origin_4482():
    # Notebook UI is served on :4482 and fetches Showtime cross-origin (DL-3.2).
    client = _client()
    resp = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:4482",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:4482"


def test_actual_get_carries_allow_origin_for_notebook_4482():
    client = _client()
    resp = client.get(
        "/healthz",
        headers={"Origin": "http://localhost:4482"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:4482"
