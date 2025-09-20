from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from .conftest import yt


class DummyYDL:
    def __init__(self, opts: Dict[str, Any]):
        self.opts = opts

    def __enter__(self) -> "DummyYDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def extract_info(self, url: str, download: bool) -> Dict[str, Any]:
        return {
            "id": "abc123",
            "title": "Video",
            "uploader": "Uploader",
            "duration": 10,
            "webpage_url": url,
        }


@pytest.fixture(autouse=True)
def _patch_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", DummyYDL)


def test_info_returns_expected_payload() -> None:
    client = TestClient(yt.app)
    response = client.post("/yt/info", json={"url": "https://youtu.be/abc123"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["info"] == {
        "id": "abc123",
        "title": "Video",
        "uploader": "Uploader",
        "duration": 10,
        "webpage_url": "https://youtu.be/abc123",
    }
