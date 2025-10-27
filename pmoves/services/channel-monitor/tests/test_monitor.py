from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SERVICE_ROOT = ROOT / "pmoves" / "services" / "channel-monitor"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

if "asyncpg" not in sys.modules:
    asyncpg_stub = ModuleType("asyncpg")

    async def _stub_create_pool(*_args, **_kwargs):  # pragma: no cover - guard path
        raise RuntimeError("asyncpg stub is not configured for unit tests")

    asyncpg_stub.create_pool = _stub_create_pool  # type: ignore[attr-defined]
    asyncpg_stub.Pool = object  # type: ignore[attr-defined]
    sys.modules["asyncpg"] = asyncpg_stub

try:  # pragma: no cover - allow real httpx when available
    import httpx  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test envs
    httpx_stub = ModuleType("httpx")

    class _AsyncClient:  # pragma: no cover - guard path
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("httpx stub is not configured for unit tests")

    class _HTTPError(Exception):
        pass

    httpx_stub.AsyncClient = _AsyncClient  # type: ignore[attr-defined]
    httpx_stub.HTTPError = _HTTPError  # type: ignore[attr-defined]
    sys.modules["httpx"] = httpx_stub

if "feedparser" not in sys.modules:
    feedparser_stub = ModuleType("feedparser")

    def _stub_parse(*_args, **_kwargs):  # pragma: no cover - guard path
        return SimpleNamespace(entries=[])

    feedparser_stub.parse = _stub_parse  # type: ignore[attr-defined]
    sys.modules["feedparser"] = feedparser_stub

if "dateutil" not in sys.modules:
    dateutil_stub = ModuleType("dateutil")
    dateutil_parser_stub = ModuleType("dateutil.parser")

    def _stub_date_parse(value):  # pragma: no cover - guard path
        raise RuntimeError(f"dateutil parser stub invoked for value={value!r}")

    dateutil_parser_stub.parse = _stub_date_parse  # type: ignore[attr-defined]
    dateutil_stub.parser = dateutil_parser_stub  # type: ignore[attr-defined]
    sys.modules["dateutil"] = dateutil_stub
    sys.modules["dateutil.parser"] = dateutil_parser_stub

if "yt_dlp" not in sys.modules:
    yt_dlp_stub = ModuleType("yt_dlp")

    class _YoutubeDL:  # pragma: no cover - guard path
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, *_args, **_kwargs):
            raise RuntimeError("yt_dlp stub extract_info called during tests")

    yt_dlp_stub.YoutubeDL = _YoutubeDL  # type: ignore[attr-defined]
    sys.modules["yt_dlp"] = yt_dlp_stub

from channel_monitor.monitor import ChannelMonitor


def _build_monitor(tmp_path, config_name: str = "channel.json") -> ChannelMonitor:
    config_path = tmp_path / config_name
    return ChannelMonitor(
        config_path=config_path,
        queue_url="http://example.test/yt/ingest",
        database_url="postgresql://pmoves:pmoves@localhost:5432/pmoves",
    )


def test_apply_filters_respects_age_and_keywords(tmp_path):
    monitor = _build_monitor(tmp_path)
    now = datetime.now(timezone.utc)
    videos = [
        {
            "video_id": "vid-1",
            "title": "Weekly Update: PMOVES status report",
            "published": now - timedelta(days=1),
        },
        {
            "video_id": "vid-2",
            "title": "Legacy recap",
            "published": now - timedelta(days=10),
        },
        {
            "video_id": "vid-3",
            "title": "Behind the scenes #shorts",
            "published": now - timedelta(hours=6),
        },
    ]
    filters = {
        "max_age_days": 7,
        "exclude_keywords": ["#shorts"],
        "title_keywords": ["update"],
    }

    filtered = monitor._apply_filters(videos, filters)

    assert [video["video_id"] for video in filtered] == ["vid-1"]


def test_queue_videos_success_updates_status(tmp_path, monkeypatch):
    monitor = _build_monitor(tmp_path)

    statuses: list[tuple[str, str, str | None]] = []

    async def record_status(
        video_id: str,
        status: str,
        *,
        error: str | None = None,
        extra_metadata: dict | None = None,
    ) -> None:
        statuses.append((video_id, status, error, extra_metadata))

    monitor._update_status = AsyncMock(side_effect=record_status)  # type: ignore[assignment]

    requests_made: list[tuple[str, dict]] = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup required
            return False

        async def post(self, url, json):
            requests_made.append((url, json))
            return SimpleNamespace(raise_for_status=lambda: None, status_code=202)

    monkeypatch.setattr(
        "channel_monitor.monitor.httpx.AsyncClient",
        DummyAsyncClient,
    )

    channel = {
        "channel_id": "UC123",
        "namespace": "pmoves",
        "tags": ["news"],
    }
    videos = [
        {
            "video_id": "vid-42",
            "url": "https://www.youtube.com/watch?v=vid-42",
            "title": "PMOVES news",
        }
    ]

    asyncio.run(monitor._queue_videos(channel, videos))

    assert requests_made, "Expected POST request to be issued"
    url, payload = requests_made[0]
    assert url == "http://example.test/yt/ingest"
    assert payload["url"] == videos[0]["url"]
    assert payload["source"] == "channel_monitor"
    assert payload["yt_options"] == {"write_info_json": True}
    assert payload["format"] is None
    assert payload["media_type"] == "video"
    metadata = payload["metadata"]
    assert metadata["platform"] == "youtube"
    assert metadata["channel_id"] == "UC123"
    assert metadata["channel_name"] == "UC123"
    assert metadata["channel_namespace"] == "pmoves"
    assert metadata["channel_tags"] == ["news"]
    assert "channel_monitor" in metadata
    monitor_context = metadata["channel_monitor"]
    assert monitor_context["channel"]["id"] == "UC123"
    assert monitor_context["channel"]["namespace"] == "pmoves"
    assert statuses[0][0:3] == ("vid-42", "processing", None)
    assert statuses[1][0:3] == ("vid-42", "queued", None)
    assert statuses[1][3] == {"queue_status_code": 202}


def test_queue_videos_failure_marks_failed(tmp_path, monkeypatch):
    monitor = _build_monitor(tmp_path, config_name="channel_fail.json")

    statuses: list[tuple[str, str, str | None]] = []

    async def record_status(
        video_id: str,
        status: str,
        *,
        error: str | None = None,
        extra_metadata: dict | None = None,
    ) -> None:
        statuses.append((video_id, status, error, extra_metadata))

    monitor._update_status = AsyncMock(side_effect=record_status)  # type: ignore[assignment]

    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup required
            return False

        async def post(self, url, json):
            raise RuntimeError("queue failure")

    monkeypatch.setattr(
        "channel_monitor.monitor.httpx.AsyncClient",
        FailingAsyncClient,
    )

    channel = {"channel_id": "UCFAIL", "tags": []}
    videos = [
        {
            "video_id": "vid-fail",
            "url": "https://www.youtube.com/watch?v=vid-fail",
            "title": "Failure case",
        }
    ]

    asyncio.run(monitor._queue_videos(channel, videos))

    assert statuses[0][0:3] == ("vid-fail", "processing", None)
    assert statuses[1][0:3] == ("vid-fail", "failed", "queue failure")
    assert statuses[1][3] == {"queue_error_type": "RuntimeError"}


def test_build_metadata_respects_overrides(tmp_path):
    monitor = _build_monitor(tmp_path)
    now = datetime.now(timezone.utc)
    channel = {
        "channel_id": "UCOVERRIDE",
        "channel_name": "Override Channel",
        "namespace": "pmoves.override",
        "tags": ["override"],
        "channel_metadata_fields": ["id", "name", "namespace"],
        "video_metadata_fields": ["duration", "thumbnail"],
    }
    video = {
        "video_id": "vid-override",
        "url": "https://www.youtube.com/watch?v=vid-override",
        "title": "Override",
        "published": now,
        "duration": 180,
        "thumbnail": "https://example.test/thumb.jpg",
        "channel": {"id": "UCOVERRIDE", "name": "Override Channel"},
    }

    metadata = monitor._build_metadata(channel, video)

    assert metadata["channel"]["id"] == "UCOVERRIDE"
    assert metadata["channel"]["name"] == "Override Channel"
    assert metadata["channel"]["namespace"] == "pmoves.override"
    assert "tags" not in metadata["channel"]
    assert metadata["namespace"] == "pmoves.override"
    video_section = metadata.get("video")
    assert video_section is not None
    assert video_section["duration_seconds"] == 180.0
    assert video_section["thumbnail"] == "https://example.test/thumb.jpg"


def test_apply_status_update_invokes_internal_update(tmp_path):
    monitor = _build_monitor(tmp_path, config_name="channel_status.json")

    updates: list[tuple[str, str, dict]] = []

    async def recorder(video_id: str, status: str, *, error=None, extra_metadata=None):
        updates.append((video_id, status, extra_metadata or {}))
        return True

    monitor._update_status = AsyncMock(side_effect=recorder)  # type: ignore[assignment]

    result = asyncio.run(
        monitor.apply_status_update(
            "vid-complete",
            "completed",
            metadata={"ingest": {"source": "pmoves-yt"}},
        )
    )

    assert result is True
    assert updates == [
        ("vid-complete", "completed", {"ingest": {"source": "pmoves-yt"}})
    ]


def test_build_yt_options_merges_global_and_channel(tmp_path):
    monitor = _build_monitor(tmp_path)
    channel = {
        "channel_id": "UCmerged",
        "yt_options": {
            "download_archive": "/custom/archive.txt",
            "write_info_json": False,
        },
    }

    merged = monitor._build_yt_options(channel)

    assert merged["download_archive"] == "/custom/archive.txt"
    assert merged["write_info_json"] is False
    assert "write_info_json" in merged
