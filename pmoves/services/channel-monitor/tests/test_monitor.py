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

from channel_monitor.monitor import ChannelMonitor, _extract_youtube_video_id  # noqa: E402


def _build_monitor(tmp_path, config_name: str = "channel.json") -> ChannelMonitor:
    config_path = tmp_path / config_name
    return ChannelMonitor(
        config_path=config_path,
        queue_url="http://example.test/yt/ingest",
        database_url="postgresql://pmoves:pmoves@localhost:5432/pmoves",
    )


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


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


def test_queue_videos_uses_custom_ingest_source(tmp_path, monkeypatch):
    monitor = _build_monitor(tmp_path, config_name="channel_custom_source.json")

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
        "channel_id": "discord:feed",
        "namespace": "pmoves",
        "ingest_source": "discord_agent",
        "platform": "discord",
        "source_type": "discord_drop",
        "source_class": "candidate",
    }
    videos = [
        {
            "video_id": "custom-source-1",
            "url": "https://www.youtube.com/watch?v=custom-source-1",
            "title": "Custom source",
        }
    ]

    asyncio.run(monitor._queue_videos(channel, videos))

    assert requests_made, "Expected POST request to be issued"
    _, payload = requests_made[0]
    assert payload["source"] == "discord_agent"
    assert payload["metadata"]["platform"] == "discord"
    assert payload["metadata"]["source_type"] == "discord_drop"
    assert payload["metadata"]["source_class"] == "candidate"
    assert statuses[0][0:3] == ("custom-source-1", "processing", None)
    assert statuses[1][0:3] == ("custom-source-1", "queued", None)


def test_ingest_manual_urls_queues_discord_drop(tmp_path):
    monitor = _build_monitor(tmp_path, config_name="channel_manual_drop.json")
    monitor._persist = AsyncMock()  # type: ignore[assignment]
    monitor._queue_videos = AsyncMock()  # type: ignore[assignment]

    result = asyncio.run(
        monitor.ingest_manual_urls(
            urls=[
                "https://youtu.be/abc123xyz00",
                "https://youtu.be/abc123xyz00",
                "https://example.com/video/standalone.mp4",
            ],
            namespace="pmoves.discord",
            tags=["review"],
            source="discord_agent",
            channel_id="discord:ops",
            channel_name="ops-drops",
            metadata={"guild_id": "guild-1", "source_class": "candidate"},
        )
    )

    assert result["queued"] == 2
    assert result["source"] == "discord_agent"
    assert result["channel_id"] == "discord:ops"
    assert result["accepted"][0]["video_id"] == "abc123xyz00"
    assert result["accepted"][1]["video_id"].startswith("manual-")
    assert result["skipped"] == []

    persist_args = monitor._persist.await_args.args
    channel_payload = persist_args[0]
    queued_videos = persist_args[1]
    assert channel_payload["platform"] == "discord"
    assert channel_payload["ingest_source"] == "discord_agent"
    assert channel_payload["source_class"] == "candidate"
    assert channel_payload["payload_metadata"]["source_context"] == {
        "guild_id": "guild-1",
        "source_class": "candidate",
    }
    assert channel_payload["tags"] == ["review", "discord"]
    assert queued_videos[0]["payload_metadata"]["manual_drop_source"] == "discord_agent"


def test_ingest_manual_urls_ask_mode_stores_pending(tmp_path):
    monitor = _build_monitor(tmp_path, config_name="channel_manual_pending.json")
    monitor._persist = AsyncMock()  # type: ignore[assignment]
    monitor._queue_videos = AsyncMock()  # type: ignore[assignment]

    result = asyncio.run(
        monitor.ingest_manual_urls(
            urls=["https://www.youtube.com/watch?v=pending12345a"],
            namespace="pmoves.discord",
            source="discord_agent",
            queue_immediately=False,
        )
    )

    assert result["queued"] == 0
    assert result["pending"] == 1
    assert result["approval_state"] == "pending_review"
    assert result["accepted"][0]["video_id"] == "pending12345a"
    monitor._persist.assert_awaited_once()
    monitor._queue_videos.assert_not_awaited()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123xyz00", "abc123xyz00"),
        ("https://m.youtube.com/watch?v=abc123xyz00", "abc123xyz00"),
        ("https://music.youtube.com/watch?v=abc123xyz00", "abc123xyz00"),
        ("https://youtu.be/abc123xyz00", "abc123xyz00"),
    ],
)
def test_extract_youtube_video_id_allows_valid_hosts(url, expected):
    assert _extract_youtube_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com.evil.example/watch?v=abc123xyz00",
        "https://notyoutube.com/watch?v=abc123xyz00",
        "https://www.youtube.com.evil.example/watch?v=abc123xyz00",
    ],
)
def test_extract_youtube_video_id_rejects_spoofed_hosts(url):
    assert _extract_youtube_video_id(url) is None


def test_create_youtube_control_request_persists_pending_row(tmp_path):
    monitor = _build_monitor(tmp_path)
    conn = SimpleNamespace(execute=AsyncMock())
    monitor._pool = _FakePool(conn)  # type: ignore[assignment]

    result = asyncio.run(
        monitor.create_youtube_control_request(
            action="playlist_add",
            details={"playlist_id": "PL123", "video_id": "vid-123"},
            request_source="discord_agent",
        )
    )

    assert result["status"] == "pending_review"
    assert result["action"] == "playlist_add"
    conn.execute.assert_awaited_once()


def test_review_youtube_control_actions_executes_pmoves_yt_call(tmp_path, monkeypatch):
    monitor = _build_monitor(tmp_path)
    rows = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "action": "comment_create",
            "details": {"video_id": "vid-123", "text": "hello"},
        }
    ]
    conn = SimpleNamespace(fetch=AsyncMock(return_value=rows), execute=AsyncMock())
    monitor._pool = _FakePool(conn)  # type: ignore[assignment]

    requests_made = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "executed", "result": {"id": "comment-1"}}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            requests_made.append((url, json, headers))
            return DummyResponse()

    monkeypatch.setenv("CHANNEL_MONITOR_YT_API_KEY", "secret-key")
    monkeypatch.setattr("channel_monitor.monitor.httpx.AsyncClient", DummyAsyncClient)

    result = asyncio.run(
        monitor.review_youtube_control_actions(
            action_ids=["11111111-1111-1111-1111-111111111111"],
            approve=True,
            actor="discord-agent",
            reason="approved in ops",
        )
    )

    assert result["approved"] is True
    assert result["processed"] == 1
    assert requests_made[0][0] == "http://example.test/yt/control/comment"
    assert requests_made[0][1]["execute"] is True
    assert requests_made[0][1]["approved_by"] == "discord-agent"
    assert requests_made[0][2]["X-API-Key"] == "secret-key"
    assert conn.execute.await_count == 1
