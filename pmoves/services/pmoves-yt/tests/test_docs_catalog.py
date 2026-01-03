from fastapi.testclient import TestClient
from services.pmoves_yt import docs_sync as _  # noqa: F401 ensure module importable
from services.pmoves_yt import yt as app_module


def test_docs_catalog_endpoint_smoke():
    client = TestClient(app_module.app)
    resp = client.get("/yt/docs/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "meta" in data and "yt_dlp_version" in data["meta"]
    assert "counts" in data and data["counts"]["options"] >= 0
