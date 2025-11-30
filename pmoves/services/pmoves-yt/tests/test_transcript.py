from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from .conftest import yt


class DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload

    @property
    def ok(self) -> bool:  # pragma: no cover - property used implicitly
        return True

    def raise_for_status(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "language": "en",
        "text": "hello",
        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
        "s3_uri": "s3://bucket/audio.m4a",
    }
    monkeypatch.setattr(yt.requests, "post", lambda *args, **kwargs: DummyResponse(payload))


def test_transcript_inserts_and_emits() -> None:
    supa = MagicMock()
    publisher = MagicMock()

    yt.supa_insert = supa
    yt._publish_event = publisher

    client = TestClient(yt.app)
    response = client.post(
        "/yt/transcript",
        json={"video_id": "abc123", "bucket": "bkt", "namespace": "ns"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en"
    assert body["s3_uri"] == "s3://bucket/audio.m4a"

    supa.assert_called_once_with(
        "transcripts",
        {
            "video_id": "abc123",
            "language": "en",
            "text": "hello",
            "s3_uri": "s3://bucket/audio.m4a",
            "meta": {
                "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
                "namespace": "ns",
                "language": "en",
                "s3_uri": "s3://bucket/audio.m4a",
            },
        },
    )

    publisher.assert_called_once()
    args, kwargs = publisher.call_args
    assert args[0] == "ingest.transcript.ready.v1"
    assert args[1] == {
        "video_id": "abc123",
        "namespace": "ns",
        "bucket": "bkt",
        "key": "yt/abc123/audio.m4a",
    }
