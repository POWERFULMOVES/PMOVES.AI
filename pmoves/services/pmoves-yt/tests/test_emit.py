from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient

from .conftest import yt


class DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def test_emit_segments_transcript_and_calls_hirag(monkeypatch) -> None:
    segments = [{"start": 0.0, "end": 1.0, "text": "hello"}]
    chunks = [
        {
            "doc_id": "yt:abc123",
            "section_id": None,
            "chunk_id": "yt:abc123:0",
            "text": "hello",
            "namespace": "pmoves",
            "payload": {},
        }
    ]

    monkeypatch.setattr(yt, "_get_transcript", lambda video_id: {"text": "hello", "segments": segments})
    monkeypatch.setattr(yt, "YT_SEG_AUTOTUNE", False)
    monkeypatch.setattr(
        yt,
        "_segment_from_whisper_segments",
        lambda segs, doc_id, namespace, **kwargs: chunks,
    )

    def fake_supa_get(table: str, match: Dict[str, Any]):
        if table == "videos":
            return [{"title": "Video"}]
        return []

    monkeypatch.setattr(yt, "supa_get", fake_supa_get)

    calls: List[Tuple[str, Dict[str, Any]]] = []

    def fake_post(url: str, *args, **kwargs):
        payload = json.loads(kwargs.get("data", "{}"))
        calls.append((url, payload))
        if "upsert-batch" in url:
            return DummyResponse({"upserted": 1, "lexical_indexed": True})
        return DummyResponse({})

    monkeypatch.setattr(yt.requests, "post", fake_post)

    client = TestClient(yt.app)
    response = client.post("/yt/emit", json={"video_id": "abc123", "namespace": "pmoves"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "video_id": "abc123",
        "chunks": 1,
        "upserted": 1,
        "lexical_indexed": True,
        "profile": None,
        "lexical_auto_disabled": False,
    }

    assert len(calls) == 2
    upsert_call = next(call for call in calls if "upsert-batch" in call[0])
    geometry_call = next(call for call in calls if "geometry/event" in call[0])

    assert upsert_call[1]["items"] == chunks
    assert upsert_call[1]["ensure_collection"] is True

    assert geometry_call[1]["type"] == "geometry.cgp.v1"
    assert geometry_call[1]["data"]["spec"] == "chit.cgp.v0.1"


def test_emit_async_enqueues_job(monkeypatch) -> None:
    segments = [{"start": 0.0, "end": 1.0, "text": "hello"}]
    chunk = {
        "doc_id": "yt:async",
        "section_id": None,
        "chunk_id": "yt:async:0",
        "text": "hello",
        "namespace": "pmoves",
        "payload": {},
    }

    monkeypatch.setattr(yt, "YT_ASYNC_UPSERT_ENABLED", True)
    monkeypatch.setattr(yt, "YT_ASYNC_UPSERT_MIN_CHUNKS", 1)
    monkeypatch.setattr(yt, "YT_INDEX_LEXICAL_DISABLE_THRESHOLD", 0)
    monkeypatch.setattr(yt, "YT_INDEX_LEXICAL", True)
    monkeypatch.setattr(yt, "YT_SEG_AUTOTUNE", False)
    monkeypatch.setattr(yt, "_get_transcript", lambda video_id: {"text": "hello", "segments": segments})
    monkeypatch.setattr(yt, "_segment_from_whisper_segments", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(yt, "supa_get", lambda table, match: [{"title": "Video"}] if table == "videos" else [])

    yt._clear_emit_jobs()

    def fake_async(job_id, video_id, namespace, title, tuned, chunks, lexical, batch_size):
        yt._update_emit_job(
            job_id,
            status="completed",
            finished_at="now",
            upserted=42,
            lexical_indexed=lexical,
        )

    monkeypatch.setattr(yt, "_emit_async_job", fake_async)

    client = TestClient(yt.app)
    response = client.post("/yt/emit", json={"video_id": "async", "namespace": "pmoves"})
    assert response.status_code == 200
    body = response.json()
    assert body["async"] is True
    job_id = body["job_id"]
    assert job_id

    status_resp = client.get(f"/yt/emit/status/{job_id}")
    assert status_resp.status_code == 200
    job = status_resp.json()["job"]
    assert job["status"] == "completed"
    assert job["upserted"] == 42
    assert job["lexical_indexed"] is True


def test_emit_auto_disables_lexical_when_threshold_hit(monkeypatch) -> None:
    segments = [{"start": 0.0, "end": 1.0, "text": "hello"}]
    chunk = {
        "doc_id": "yt:disable",
        "section_id": None,
        "chunk_id": "yt:disable:0",
        "text": "hello",
        "namespace": "pmoves",
        "payload": {},
    }

    monkeypatch.setattr(yt, "YT_ASYNC_UPSERT_ENABLED", False)
    monkeypatch.setattr(yt, "YT_INDEX_LEXICAL", True)
    monkeypatch.setattr(yt, "YT_INDEX_LEXICAL_DISABLE_THRESHOLD", 1)
    monkeypatch.setattr(yt, "YT_SEG_AUTOTUNE", False)
    monkeypatch.setattr(yt, "_get_transcript", lambda video_id: {"text": "hello", "segments": segments})
    monkeypatch.setattr(yt, "_segment_from_whisper_segments", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(yt, "supa_get", lambda table, match: [{"title": "Video"}] if table == "videos" else [])

    monkeypatch.setattr(yt, "_upsert_chunks_to_hirag", lambda chunks, lexical, batch_size: {"upserted": len(chunks), "lexical_indexed": lexical})
    monkeypatch.setattr(yt, "_emit_geometry_event", lambda *args, **kwargs: None)

    client = TestClient(yt.app)
    response = client.post("/yt/emit", json={"video_id": "disable", "namespace": "pmoves"})
    assert response.status_code == 200
    body = response.json()
    assert body["lexical_indexed"] is False
    assert body["lexical_auto_disabled"] is True

def test_cgp_build_uses_pack(monkeypatch) -> None:
    client = TestClient(yt.app)

    pack = {
        "id": "pack-123",
        "status": "active",
        "generation": 3,
        "population_id": "pop",
        "fitness": 0.91,
        "params": {"bins": 10, "K": 2, "tau": 0.7, "beta": 1.1, "spectrum_mode": "histogram"},
    }

    monkeypatch.setattr(yt, "get_builder_pack", lambda namespace, modality: pack)

    response = client.post(
        "/yt/cgp-build",
        json={
            "video_id": "abc123",
            "namespace": "pmoves",
            "title": "Demo",
            "chunks": [
                {"text": "alpha beta gamma", "payload": {"t_start": 0.0, "t_end": 3.2}},
                {"text": "delta epsilon", "payload": {"t_start": 3.2, "t_end": 6.4}},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["cgp"]["meta"]["pack_id"] == "pack-123"
    assert data["cgp"]["meta"]["builder_pack"]["params"]["bins"] == 10


def test_smoke_seed_pack_inserts_and_clears_cache(monkeypatch) -> None:
    client = TestClient(yt.app)

    captured: list = []

    def fake_post(url: str, headers=None, data=None, timeout=None):
        captured.append((url, headers, data))
        payload = json.loads(data)
        return DummyResponse([payload])

    monkeypatch.setattr(yt.requests, "post", fake_post)

    cleared = {"called": False}

    def fake_clear() -> None:
        cleared["called"] = True

    monkeypatch.setattr(yt, "clear_cache", fake_clear)

    response = client.post(
        "/yt/smoke/seed-pack",
        json={"namespace": "pmoves", "pack_id": "pack-smoke", "params": {"bins": 12, "K": 1, "tau": 1.0, "beta": 1.0}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["pack"]["id"] == "pack-smoke"
    assert cleared["called"] is True
    assert captured
