import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from services.gateway.gateway.main import app
from services.gateway.gateway.api import mindmap as mindmap_module


def test_healthz_reports_dependency_state(monkeypatch):
    monkeypatch.setattr(mindmap_module, "driver", None)
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "gateway"
    assert body["neo4j"] == "unconfigured"
    assert body["nats"] in {"connected", "disconnected"}


def test_healthz_neo4j_configured_when_driver_exists(monkeypatch):
    monkeypatch.setattr(mindmap_module, "driver", object())
    assert TestClient(app).get("/healthz").json()["neo4j"] == "configured"
