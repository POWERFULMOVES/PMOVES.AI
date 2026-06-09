from fastapi.testclient import TestClient
from app import create_app


def test_healthz_ok():
    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["service"] == "creator-operator"


def test_metrics_present():
    client = TestClient(create_app())
    assert client.get("/metrics").status_code == 200
