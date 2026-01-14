from __future__ import annotations

import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from .conftest import yt


def test_chapters_persists_and_emits(monkeypatch) -> None:
    monkeypatch.setattr(yt, "_get_transcript", lambda video_id: {"text": "hello"})

    chapters_json = json.dumps([
        {"title": "Intro", "blurb": "Opening"},
        {"title": "Main", "blurb": "Content"},
    ])
    monkeypatch.setattr(yt, "_summarize_ollama", lambda text, style: chapters_json)

    merge_meta = MagicMock()
    publisher = MagicMock()

    yt._merge_video_meta = merge_meta
    yt._publish_event = publisher

    client = TestClient(yt.app)
    response = client.post("/yt/chapters", json={"video_id": "abc123"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["video_id"] == "abc123"
    assert body["chapters"] == [
        {"title": "Intro", "blurb": "Opening"},
        {"title": "Main", "blurb": "Content"},
    ]

    merge_meta.assert_called_once_with(
        "abc123",
        {"chapters": [{"title": "Intro", "blurb": "Opening"}, {"title": "Main", "blurb": "Content"}]},
    )

    publisher.assert_called_once()
    args, kwargs = publisher.call_args
    assert args[0] == "ingest.chapters.ready.v1"
    assert args[1]["video_id"] == "abc123"
    assert args[1]["n"] == 2
    assert args[1]["chapters"] == [
        {"title": "Intro", "blurb": "Opening"},
        {"title": "Main", "blurb": "Content"},
    ]
