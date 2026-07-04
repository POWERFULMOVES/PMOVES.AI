"""CORS preflight tests for the BoTZ gateway.

Regression guard for the 5090 DL-3 review finding: the persona-adaptive preview
fetches ``/v1/agent/theme/*`` and ``/v1/agent/whoami`` cross-origin, which failed
silently with no CORS middleware. These assert the explicit allow-list works and
that unlisted origins are not echoed (no wildcard).
"""
import importlib

from fastapi.testclient import TestClient


def _client():
    main = importlib.import_module("main")
    return TestClient(main.app)


def test_preflight_allows_listed_origin():
    client = _client()
    resp = client.options(
        "/v1/agent/theme/agent-x",
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
        "/v1/agent/theme/agent-x",
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
        "/v1/agent/theme/agent-x",
        headers={"Origin": "http://localhost:3000"},
    )
    # Regardless of the route's own status, CORS must tag the response for a listed origin.
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
