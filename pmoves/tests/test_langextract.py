from fastapi.testclient import TestClient


def test_extract_text_smoke(load_service_module, monkeypatch):
    api = load_service_module("langextract_api", "services/langextract/api.py")

    published = []
    monkeypatch.setattr(api, "_maybe_publish", lambda payload: published.append(payload))

    client = TestClient(api.app)
    resp = client.post(
        "/extract/text",
        json={"text": "Hello world?\n\nAnother paragraph.", "namespace": "demo", "doc_id": "doc-42"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert body["chunks"][0]["namespace"] == "demo"
    assert published and published[0]["count"] == body["count"]
