from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from .conftest import yt


def test_summarize_updates_meta_and_emits(monkeypatch) -> None:
    monkeypatch.setattr(yt, "_get_transcript", lambda video_id: {"text": "hello world"})
    monkeypatch.setattr(yt, "_summarize_ollama", lambda text, style: "summary")

    merge_meta = MagicMock()
    publisher = MagicMock()

    yt._merge_video_meta = merge_meta
    yt._publish_event = publisher

    client = TestClient(yt.app)
    response = client.post("/yt/summarize", json={"video_id": "abc123"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "video_id": "abc123",
        "provider": "ollama",
        "style": "short",
        "summary": "summary",
    }

    merge_meta.assert_called_once_with("abc123", {"style": "short", "provider": "ollama", "summary": "summary"})

    publisher.assert_called_once()
    args, kwargs = publisher.call_args
    assert args[0] == "ingest.summary.ready.v1"
    assert args[1]["video_id"] == "abc123"
    assert args[1]["style"] == "short"
    assert args[1]["provider"] == "ollama"
    assert args[1]["summary"] == "summary"
