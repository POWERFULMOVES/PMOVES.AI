from __future__ import annotations

from pathlib import Path
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
        base_dir = Path(yt.YT_TEMP_ROOT) / "abc123"
        base_dir.mkdir(parents=True, exist_ok=True)
        filename = str(base_dir / "abc123.mp4")
        return {
            "id": "abc123",
            "title": "Video",
            "requested_downloads": [{"_filename": filename}],
            "duration": 321,
            "uploader": "Channel Name",
            "uploader_id": "channel-xyz",
            "tags": ["tag1", "tag2"],
            "categories": ["Education"],
        }


@pytest.fixture(autouse=True)
def _patch_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", DownloadYDL)


@pytest.fixture(autouse=True)
def _patch_video_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt, "supa_get", MagicMock(return_value=[{"meta": {}}]))
    monkeypatch.setattr(yt, "supa_update", MagicMock())


def test_download_uploads_and_emits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upload = MagicMock(return_value="http://s3/abc123.mp4")
    supa = MagicMock()
    supa_upsert = MagicMock()
    publisher = MagicMock()

    yt.upload_to_s3 = upload
    yt.supa_insert = supa
    yt.supa_upsert = supa_upsert
    yt._publish_event = publisher
    monkeypatch.setenv("YT_TEMP_ROOT", str(tmp_path))
    yt.YT_TEMP_ROOT = tmp_path
    yt.YT_ARCHIVE_DIR = tmp_path
    yt.YT_DOWNLOAD_ARCHIVE = str(tmp_path / "download-archive.txt")

    client = TestClient(yt.app)
    response = client.post(
        "/yt/download",
        json={"url": "https://youtu.be/abc123", "bucket": "bkt", "namespace": "ns"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == "abc123"
    assert body["s3_url"] == "http://s3/abc123.mp4"

    upload.assert_called_once_with(str(tmp_path / "abc123" / "abc123.mp4"), "bkt", "yt/abc123/raw.mp4")

    supa.assert_called_once()
    supa_upsert.assert_called_once()
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
                "duration": 321,
                "channel": {"title": "Channel Name", "id": "channel-xyz"},
                "job_id": None,
            },
        },
    )

    supa_upsert.assert_called_once_with(
        "videos",
        {
            "video_id": "abc123",
            "namespace": "ns",
            "title": "Video",
            "source_url": "https://youtu.be/abc123",
            "s3_base_prefix": "s3://bkt/yt/abc123",
            "meta": {"thumb": None},
        },
        on_conflict="video_id",
    )

    yt.supa_update.assert_called_once()
    update_args, _ = yt.supa_update.call_args
    meta_payload = update_args[2]["meta"]
    assert meta_payload["duration"] == 321
    assert meta_payload["channel"]["title"] == "Channel Name"
    assert meta_payload["provenance"]["source"] == "youtube"

    publisher.assert_called_once()
    args, _ = publisher.call_args
    assert args[0] == "ingest.file.added.v1"
    event_payload = args[1]
    assert event_payload["bucket"] == "bkt"
    assert event_payload["key"] == "yt/abc123/raw.mp4"
    assert event_payload["duration"] == 321


def test_soundcloud_credentials_and_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upload = MagicMock(return_value="http://s3/abc123.mp3")
    supa_insert = MagicMock()
    supa_upsert = MagicMock()
    supa_update = MagicMock()
    publisher = MagicMock()
    captured_opts: Dict[str, Any] = {}

    class CaptureYDL(DownloadYDL):
        def __init__(self, opts: Dict[str, Any]):
            captured_opts.update(opts)
            super().__init__(opts)

    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", CaptureYDL)
    monkeypatch.setenv("YT_TEMP_ROOT", str(tmp_path))
    monkeypatch.setenv("SOUNDCLOUD_USERNAME", "user@example.com")
    monkeypatch.setenv("SOUNDCLOUD_PASS", "super-secret")
    yt.YT_TEMP_ROOT = tmp_path
    yt.YT_ARCHIVE_DIR = tmp_path
    yt.YT_DOWNLOAD_ARCHIVE = str(tmp_path / "download-archive.txt")
    yt.SOUNDCLOUD_USERNAME = "user@example.com"
    yt.SOUNDCLOUD_PASSWORD = "super-secret"
    yt.SOUNDCLOUD_COOKIEFILE = None
    yt.SOUNDCLOUD_COOKIES_FROM_BROWSER = None
    yt.upload_to_s3 = upload
    yt.supa_insert = supa_insert
    yt.supa_upsert = supa_upsert
    yt.supa_update = supa_update
    yt._publish_event = publisher

    client = TestClient(yt.app)
    response = client.post(
        "/yt/download",
        json={
            "url": "https://soundcloud.com/darkxside/sample-track",
            "bucket": "bkt",
            "namespace": "ns",
            "metadata": {"platform": "soundcloud"},
        },
    )

    assert response.status_code == 200
    assert captured_opts.get("username") == "user@example.com"
    assert captured_opts.get("password") == "super-secret"
    upload.assert_called_once_with(
        str(tmp_path / "abc123" / "abc123.mp4"), "bkt", "sc/abc123/raw.mp4"
    )
    supa_insert.assert_any_call(
        "studio_board",
        {
            "title": "Video",
            "namespace": "ns",
            "content_url": "http://s3/abc123.mp3",
            "status": "submitted",
            "meta": {
                "source": "soundcloud",
                "original_url": "https://soundcloud.com/darkxside/sample-track",
                "thumb": None,
                "duration": 321,
                "channel": {"title": "Channel Name", "id": "channel-xyz"},
                "job_id": None,
            },
        },
    )
    publisher.assert_called_once()
    event_payload = publisher.call_args[0][1]
    assert event_payload["source"] == "soundcloud"
    assert event_payload["key"] == "sc/abc123/raw.mp4"


def test_invidious_companion_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upload = MagicMock(return_value="http://s3/abc123.raw")
    supa_insert = MagicMock()
    supa_upsert = MagicMock()
    supa_update = MagicMock()
    publisher = MagicMock()

    yt.upload_to_s3 = upload
    yt.supa_insert = supa_insert
    yt.supa_upsert = supa_upsert
    yt.supa_update = supa_update
    yt._publish_event = publisher
    monkeypatch.setenv("YT_TEMP_ROOT", str(tmp_path))
    monkeypatch.setenv("INVIDIOUS_COMPANION_URL", "http://invidious-companion:8282")
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", "secret")
    yt.YT_TEMP_ROOT = tmp_path
    yt.INVIDIOUS_COMPANION_URL = "http://invidious-companion:8282"
    yt.INVIDIOUS_COMPANION_KEY = "secret"

    class DummyPostResponse:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Dict[str, Any]:
            return {
                "videoDetails": {
                    "title": "Companion Title",
                    "author": "Channel",
                    "channelId": "channel-xyz",
                    "thumbnail": {
                        "thumbnails": [
                            {"url": "http://thumb/1.jpg", "width": 120},
                            {"url": "http://thumb/2.jpg", "width": 480},
                        ]
                    },
                },
                "streamingData": {
                    "formats": [
                        {
                            "qualityLabel": "1080p",
                            "mimeType": "video/mp4",
                            "url": "http://media/video.mp4",
                        }
                    ]
                },
            }

    class DummyGetResponse:
        def __init__(self, content: bytes, headers: Dict[str, str] | None = None):
            self._content = content
            self.status_code = 200
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, _chunk: int):
            yield self._content

        @property
        def content(self) -> bytes:
            return self._content

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    post_calls: Dict[str, Any] = {}

    def fake_post(url: str, json: Dict[str, Any], headers: Dict[str, Any], timeout: int):
        post_calls["url"] = url
        post_calls["json"] = json
        post_calls["headers"] = headers
        return DummyPostResponse()

    def fake_get(url: str, stream: bool = False, timeout: int = 0):
        if "thumb" in url:
            return DummyGetResponse(b"thumb-bytes", {"content-type": "image/jpeg"})
        return DummyGetResponse(b"video-bytes")

    monkeypatch.setattr(yt.requests, "post", fake_post)
    monkeypatch.setattr(yt.requests, "get", fake_get)

    result = yt._download_with_companion(
        "https://youtu.be/abc123def45",
        "ns",
        "bucket",
        job_id=None,
        entry_meta={},
        platform="youtube",
    )

    assert result["video_id"] == "abc123def45"
    assert post_calls["url"].endswith("/companion/youtubei/v1/player")
    assert post_calls["json"] == {"videoId": "abc123def45"}
    assert post_calls["headers"]["Authorization"] == "Bearer secret"
    upload.assert_any_call(
        str(tmp_path / "abc123def45" / "abc123def45.mp4"), "bucket", "yt/abc123def45/raw.mp4"
    )
