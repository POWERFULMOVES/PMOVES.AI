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
    }

    assert len(calls) == 2
    upsert_call = next(call for call in calls if "upsert-batch" in call[0])
    geometry_call = next(call for call in calls if "geometry/event" in call[0])

    assert upsert_call[1]["items"] == chunks
    assert upsert_call[1]["ensure_collection"] is True

    assert geometry_call[1]["type"] == "geometry.cgp.v1"
    assert geometry_call[1]["data"]["spec"] == "chit.cgp.v0.1"
