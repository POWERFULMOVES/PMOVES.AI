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
