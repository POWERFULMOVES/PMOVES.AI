import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pmoves.services.gateway.gateway.api import mindmap as mindmap_module


class _FakeMindmapSession:
    def __init__(self, driver):
        self._driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query: str, **kwargs):
        self._driver.last_params = kwargs
        return list(self._driver.records)


class _FakeMindmapDriver:
    def __init__(self):
        self.records = [
            {
                "point": {"id": "p.demo", "modality": "text"},
                "media": {"uid": "doc|codebook|0-6"},
            }
        ]
        self.last_params = {}

    def session(self):  # pragma: no cover - exercised via FastAPI route
        return _FakeMindmapSession(self)


@pytest.fixture
def fake_mindmap_driver(monkeypatch):
    driver = _FakeMindmapDriver()
    monkeypatch.setattr(mindmap_module, "driver", driver)
    yield driver
    monkeypatch.setattr(mindmap_module, "driver", None)


@pytest.fixture
def client(fake_mindmap_driver):
    app = FastAPI()
    app.include_router(mindmap_module.router)
    return TestClient(app)


def test_mindmap_returns_records(client, fake_mindmap_driver):
    response = client.get(
        "/mindmap/demo-constellation",
        params={"modalities": "text,video", "limit": 5, "minProj": 0.7},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["point"]["id"] == "p.demo"
    assert fake_mindmap_driver.last_params["mods"] == ["text", "video"]
    assert fake_mindmap_driver.last_params["limit"] == 5
    assert pytest.approx(fake_mindmap_driver.last_params["minProj"], rel=1e-6) == 0.7


def test_mindmap_requires_modality(client):
    resp = client.get("/mindmap/demo-constellation", params={"modalities": " "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "At least one modality is required"
