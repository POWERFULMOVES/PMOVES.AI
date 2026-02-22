import importlib.util
from pathlib import Path
import sys

from fastapi.testclient import TestClient


def _load_yt_module():
    module_name = "pmoves_yt_service"
    if module_name in sys.modules:
        return sys.modules[module_name]
    yt_path = Path(__file__).resolve().parents[1] / "yt.py"
    spec = importlib.util.spec_from_file_location(module_name, yt_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


app_module = _load_yt_module()


def test_docs_catalog_endpoint_smoke():
    client = TestClient(app_module.app)
    resp = client.get("/yt/docs/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "meta" in data and "yt_dlp_version" in data["meta"]
    assert "counts" in data and data["counts"]["options"] >= 0
