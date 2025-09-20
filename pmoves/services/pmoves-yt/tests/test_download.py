from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from .conftest import yt


class DownloadYDL:
    def __init__(self, opts: Dict[str, Any]):
        self.opts = opts

    def __enter__(self) -> "DownloadYDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def extract_info(self, url: str, download: bool) -> Dict[str, Any]:
        return {
            "id": "abc123",
            "title": "Video",
            "requested_downloads": [{"_filename": "/tmp/abc123.mp4"}],
        }


@pytest.fixture(autouse=True)
def _patch_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", DownloadYDL)


def test_download_uploads_and_emits() -> None:
    upload = MagicMock(return_value="http://s3/abc123.mp4")
    supa = MagicMock()
    publisher = MagicMock()

    yt.upload_to_s3 = upload
    yt.supa_insert = supa
    yt._publish_event = publisher

    client = TestClient(yt.app)
    response = client.post(
        "/yt/download",
        json={"url": "https://youtu.be/abc123", "bucket": "bkt", "namespace": "ns"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == "abc123"
    assert body["s3_url"] == "http://s3/abc123.mp4"

    upload.assert_called_once_with("/tmp/abc123.mp4", "bkt", "yt/abc123/raw.mp4")

    assert supa.call_count == 2
    supa.assert_any_call(
        "studio_board",
        {
            "title": "Video",
            "namespace": "ns",
            "content_url": "http://s3/abc123.mp4",
            "status": "submitted",
            "meta": {
                "source": "youtube",
                "original_url": "https://youtu.be/abc123",
                "thumb": None,
            },
        },
    )

    supa.assert_any_call(
        "videos",
        {
            "video_id": "abc123",
            "namespace": "ns",
            "title": "Video",
            "source_url": "https://youtu.be/abc123",
            "s3_base_prefix": "s3://bkt/yt/abc123",
            "meta": {"thumb": None},
        },
    )

    publisher.assert_called_once()
    args, kwargs = publisher.call_args
    assert args[0] == "ingest.file.added.v1"
    assert args[1] == {
        "bucket": "bkt",
        "key": "yt/abc123/raw.mp4",
        "namespace": "ns",
        "title": "Video",
        "source": "youtube",
        "video_id": "abc123",
    }
