from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_multiagent_video_to_search_pipeline(load_service_module, monkeypatch):
    yt = load_service_module("pmoves_yt_multiagent", "services/pmoves-yt/yt.py")

    uploads: list[tuple[str, str, str]] = []
    published: list[tuple[str, dict]] = []
    inserts: list[tuple[str, dict]] = []

    def fake_upload(path: str, bucket: str, key: str) -> str:
        uploads.append((Path(path).name, bucket, key))
        return f"https://local/{bucket}/{key}"

    def fake_publish(topic: str, payload):
        published.append((topic, payload))

    def fake_insert(table: str, row):
        inserts.append((table, row))
        return [{"id": f"{table}-row"}]

    monkeypatch.setattr(yt, "upload_to_s3", fake_upload)
    monkeypatch.setattr(yt, "_publish_event", fake_publish)
    monkeypatch.setattr(yt, "supa_insert", fake_insert)
    monkeypatch.setattr(yt, "supa_upsert", lambda *args, **kwargs: None)
    monkeypatch.setattr(yt, "supa_update", lambda *args, **kwargs: None)

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts
            self._filename: str | None = None

        def __enter__(self):  # pragma: no cover - trivial context
            return self

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - trivial context
            return False

        def extract_info(self, url, download):
            outtmpl = self.opts["outtmpl"]
            video_path = Path(outtmpl.replace("%(id)s", "abc123").replace("%(ext)s", "mp4"))
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"demo")
            thumb_path = video_path.with_suffix(".jpg")
            thumb_path.write_bytes(b"thumb")
            self._filename = str(video_path)
            return {
                "id": "abc123",
                "title": "Demo Title",
                "requested_downloads": [{"_filename": self._filename}],
            }

        def prepare_filename(self, info):  # pragma: no cover - fallback path
            return self._filename or ""

    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", DummyYDL)

    with TestClient(yt.app) as yt_client:
        yt_response = yt_client.post(
            "/yt/download",
            json={"url": "https://youtu.be/example", "bucket": "assets", "namespace": "demo"},
        )
    assert yt_response.status_code == 200
    video_payload = yt_response.json()

    assert video_payload["video_id"] == "abc123"
    assert uploads and uploads[0][1:] == ("assets", "yt/abc123/raw.mp4")
    assert any(topic == "ingest.file.added.v1" for topic, _ in published)
    assert {table for table, _ in inserts} == {"studio_board", "videos"}

    lang = load_service_module("langextract_multiagent", "services/langextract/api.py")
    extracted: list[dict] = []
    monkeypatch.setattr(lang, "_maybe_publish", lambda payload: extracted.append(payload))

    with TestClient(lang.app) as lang_client:
        extract_response = lang_client.post(
            "/extract/text",
            json={
                "text": "Hello world?\n\nAdditional context for retrieval.",
                "namespace": "demo",
                "doc_id": video_payload["video_id"],
            },
        )
    assert extract_response.status_code == 200
    chunk_payload = extract_response.json()
    assert chunk_payload["count"] >= 1
    first_chunk = chunk_payload["chunks"][0]
    assert first_chunk["doc_id"] == video_payload["video_id"]
    assert first_chunk["namespace"] == "demo"

    gateway = load_service_module("hirag_gateway_multiagent", "services/hi-rag-gateway/gateway.py")
    monkeypatch.setattr(gateway, "TAILSCALE_ONLY", False)
    monkeypatch.setattr(gateway, "require_tailscale", lambda request, admin_only=False: None)
    monkeypatch.setattr(gateway, "driver", None)
    monkeypatch.setattr(gateway, "embed_query", lambda query: [0.1, 0.2, 0.3])

    class FakePoint:
        def __init__(self, payload, score):
            self.payload = payload
            self.score = score

    qdrant_calls: list[dict] = []

    class FakeQdrant:
        def search(self, collection, query_vector, limit, query_filter, with_payload, with_vectors):
            qdrant_calls.append(
                {
                    "collection": collection,
                    "query_vector": query_vector,
                    "limit": limit,
                    "query_filter": query_filter,
                }
            )
            return [FakePoint(dict(first_chunk), 0.87)]

    monkeypatch.setattr(gateway, "qdrant", FakeQdrant())
    monkeypatch.setattr(gateway, "USE_MEILI", False)

    with TestClient(gateway.app) as gateway_client:
        hirag_response = gateway_client.post(
            "/hirag/query",
            json={
                "query": first_chunk["text"],
                "namespace": first_chunk["namespace"],
                "k": 1,
                "alpha": 0.3,
            },
        )
    assert hirag_response.status_code == 200
    hirag_payload = hirag_response.json()
    assert hirag_payload["query"] == first_chunk["text"]
    assert hirag_payload["results"]
    assert hirag_payload["results"][0]["doc_id"] == video_payload["video_id"]

    assert qdrant_calls, "qdrant.search should be invoked"
    query_filter = qdrant_calls[0]["query_filter"]
    namespace_condition = query_filter.must[0]
    assert getattr(namespace_condition, "key", None) == "namespace"
    match_obj = getattr(namespace_condition, "match", None)
    match_value = None
    if match_obj is not None:
        match_value = getattr(match_obj, "value", None)
        if match_value is None and hasattr(match_obj, "model_dump"):
            match_value = match_obj.model_dump().get("value")
    assert match_value == "demo"

    assert extracted and extracted[0]["chunks"][0]["doc_id"] == video_payload["video_id"]
