from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import asyncpg
import httpx
import feedparser
from dateutil import parser as date_parser
from yt_dlp import YoutubeDL

from .config import ensure_config, save_config

LOGGER = logging.getLogger("channel_monitor")

VALID_STATUSES = {"pending", "processing", "queued", "completed", "failed"}
TERMINAL_STATUSES = {"completed", "failed"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChannelMonitor:
    def __init__(
        self,
        config_path,
        queue_url: str,
        database_url: str,
        namespace_default: str = "pmoves",
    ) -> None:
        self.config_path = config_path
        self.config = ensure_config(config_path)
        self.queue_url = queue_url
        self.database_url = database_url
        self.namespace_default = namespace_default

        self._pool: Optional[asyncpg.Pool] = None
        self._tasks: List[asyncio.Task] = []
        self._processed_video_ids: Set[str] = set()
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        await self._ensure_tables()
        await self._load_processed_videos()

        if self.config["global_settings"].get("check_on_startup", True):
            await self.check_all_channels()

        interval_default = (
            self.config.get("monitoring_schedule", {}).get("interval_minutes") or 30
        )

        for channel in self.config.get("channels", []):
            if not channel.get("enabled", True):
                continue
            interval = channel.get("check_interval_minutes") or interval_default
            interval = max(1, int(interval))
            task = asyncio.create_task(self._channel_loop(channel, interval))
            self._tasks.append(task)

    async def shutdown(self) -> None:
        self._shutdown.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _channel_loop(self, channel: Dict[str, Any], interval_minutes: int) -> None:
        while not self._shutdown.is_set():
            try:
                await self.check_single_channel(channel)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                LOGGER.exception("Channel check failed (%s): %s", channel.get("channel_name"), exc)
            await asyncio.wait(
                [self._shutdown.wait()], timeout=interval_minutes * 60
            )

    async def _ensure_tables(self) -> None:
        assert self._pool
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE SCHEMA IF NOT EXISTS pmoves;
                CREATE TABLE IF NOT EXISTS pmoves.channel_monitoring (
                    id BIGSERIAL PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT,
                    video_id TEXT NOT NULL,
                    video_title TEXT,
                    video_url TEXT,
                    published_at TIMESTAMPTZ,
                    discovered_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                    processed_at TIMESTAMPTZ,
                    processing_status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    namespace TEXT DEFAULT 'pmoves',
                    tags TEXT[],
                    metadata JSONB DEFAULT '{}'::jsonb,
                    UNIQUE(channel_id, video_id)
                );
                CREATE INDEX IF NOT EXISTS idx_channel_monitoring_status
                    ON pmoves.channel_monitoring(processing_status);
                CREATE INDEX IF NOT EXISTS idx_channel_monitoring_channel
                    ON pmoves.channel_monitoring(channel_id, discovered_at DESC);
                """
            )

    async def _load_processed_videos(self) -> None:
        assert self._pool
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT video_id
                FROM pmoves.channel_monitoring
                WHERE processing_status IN ('queued', 'processing', 'completed', 'failed')
                """
            )
        self._processed_video_ids = {row["video_id"] for row in rows}
        LOGGER.info("Loaded %s processed videos", len(self._processed_video_ids))

    async def check_all_channels(self) -> int:
        total_new = 0
        channels = [c for c in self.config.get("channels", []) if c.get("enabled", True)]
        for channel in channels:
            total_new += await self.check_single_channel(channel)
        return total_new

    async def check_single_channel(self, channel: Dict[str, Any]) -> int:
        channel_id = channel["channel_id"]
        channel_name = channel.get("channel_name", channel_id)
        LOGGER.info("Checking channel %s", channel_name)

        videos: List[Dict[str, Any]]
        if self.config["global_settings"].get("use_rss_feed", True):
            videos = await self._fetch_via_rss(channel_id)
        else:
            videos = await self._fetch_via_api(channel_id)

        filters = channel.get("filters", {})
        filtered = self._apply_filters(videos, filters)
        new_videos = [
            video for video in filtered if video["video_id"] not in self._processed_video_ids
        ]

        if not new_videos:
            LOGGER.info("No new videos for %s", channel_name)
            return 0

        LOGGER.info("Discovered %d new videos for %s", len(new_videos), channel_name)
        await self._persist(channel, new_videos)

        if channel.get("auto_process", True):
            await self._queue_videos(channel, new_videos)

        return len(new_videos)

    async def _fetch_via_rss(self, channel_id: str) -> List[Dict[str, Any]]:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(rss_url)
            response.raise_for_status()
        feed = feedparser.parse(response.text)
        results: List[Dict[str, Any]] = []
        max_items = self.config["global_settings"].get("max_videos_per_check", 10)
        for entry in feed.entries[:max_items]:
            video_id = getattr(entry, "yt_videoid", None)
            if not video_id and entry.link:
                if "watch?v=" in entry.link:
                    video_id = entry.link.split("watch?v=")[-1]
            if not video_id:
                continue
            published_raw = getattr(entry, "published", None)
            if published_raw:
                published = date_parser.parse(published_raw)
            else:
                published = utcnow()
            results.append(
                {
                    "video_id": video_id,
                    "title": entry.title,
                    "url": entry.link,
                    "published": published,
                    "author": getattr(entry, "author", ""),
                    "description": getattr(entry, "summary", ""),
                }
            )
        return results

    async def _fetch_via_api(self, channel_id: str) -> List[Dict[str, Any]]:
        # Placeholder for future YouTube API integration.
        LOGGER.warning("YouTube API fetch not configured; falling back to RSS for %s", channel_id)
        return await self._fetch_via_rss(channel_id)

    def _apply_filters(self, videos: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        max_age_days = filters.get("max_age_days")
        exclude_keywords = [kw.lower() for kw in filters.get("exclude_keywords", [])]
        title_keywords = [kw.lower() for kw in filters.get("title_keywords", [])]

        for video in videos:
            published: datetime = video["published"]
            if max_age_days is not None:
                age_days = (utcnow() - published).days
                if age_days > max_age_days:
                    continue

            title = video["title"].lower()
            if title_keywords and not any(kw in title for kw in title_keywords):
                continue
            if exclude_keywords and any(kw in title for kw in exclude_keywords):
                continue
            filtered.append(video)

        return filtered

    async def _persist(self, channel: Dict[str, Any], videos: List[Dict[str, Any]]) -> None:
        assert self._pool
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for video in videos:
                    published = video["published"]
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                    await conn.execute(
                        """
                        INSERT INTO pmoves.channel_monitoring (
                            channel_id, channel_name, video_id, video_title, video_url,
                            published_at, priority, namespace, tags, metadata
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        ON CONFLICT (channel_id, video_id) DO NOTHING
                        """,
                        channel["channel_id"],
                        channel.get("channel_name"),
                        video["video_id"],
                        video["title"],
                        video["url"],
                        published,
                        channel.get("priority", 0),
                        channel.get("namespace", self.namespace_default),
                        channel.get("tags", []),
                        {
                            "description": video.get("description", ""),
                            "author": video.get("author", ""),
                        },
                    )
        for video in videos:
            self._processed_video_ids.add(video["video_id"])

    async def _queue_videos(self, channel: Dict[str, Any], videos: List[Dict[str, Any]]) -> None:
        namespace = channel.get("namespace", self.namespace_default)
        payloads = [
            {
                "url": video["url"],
                "namespace": namespace,
                "auto_emit": False,
                "source": "channel_monitor",
                "tags": channel.get("tags", []),
                "yt_options": self._build_yt_options(channel),
            }
            for video in videos
        ]
        async with httpx.AsyncClient(timeout=60.0) as client:
            for payload, video in zip(payloads, videos):
                try:
                    await self._update_status(
                        video["video_id"],
                        "processing",
                        extra_metadata={"queue_url": self.queue_url},
                    )
                    resp = await client.post(self.queue_url, json=payload)
                    resp.raise_for_status()
                except Exception as exc:  # pragma: no cover
                    LOGGER.error("Failed to queue %s: %s", video["video_id"], exc)
                    await self._update_status(
                        video["video_id"],
                        "failed",
                        error=str(exc),
                        extra_metadata={"queue_error_type": exc.__class__.__name__},
                    )
                else:
                    LOGGER.info("Queued %s for ingestion", video["video_id"])
                    await self._update_status(
                        video["video_id"],
                        "queued",
                        extra_metadata={"queue_status_code": getattr(resp, "status_code", None)},
                    )

    def _build_yt_options(self, channel: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        global_opts = self.config.get("global_settings", {}).get("yt_options") or {}
        if isinstance(global_opts, dict):
            merged.update(global_opts)
        channel_opts = channel.get("yt_options") or {}
        if isinstance(channel_opts, dict):
            merged.update(channel_opts)
        return merged

    async def _update_status(
        self,
        video_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported status '{status}'")
        assert self._pool
        now_iso = utcnow().isoformat()
        metadata_patch: Dict[str, Any] = {
            "last_status": status,
            "last_status_at": now_iso,
        }
        if error:
            metadata_patch["last_error"] = error
            metadata_patch["last_error_at"] = now_iso
        else:
            metadata_patch["last_error"] = None
        if extra_metadata:
            metadata_patch.update(extra_metadata)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE pmoves.channel_monitoring
                SET processing_status=$1,
                    processed_at=CASE
                        WHEN $1 = ANY($3) THEN timezone('utc', now())
                        WHEN $1='pending' THEN NULL
                        ELSE processed_at
                    END,
                    metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                WHERE video_id=$2
                """,
                status,
                video_id,
                list(TERMINAL_STATUSES),
                json.dumps(metadata_patch),
            )
        updated = result.split()[-1] if isinstance(result, str) else "0"
        updated_bool = updated not in {"0", "0.0"}
        if updated_bool and status in {"queued", "processing", "completed"}:
            self._processed_video_ids.add(video_id)
        elif status == "pending":
            self._processed_video_ids.discard(video_id)
        return updated_bool

    async def apply_status_update(
        self,
        video_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return await self._update_status(video_id, status, error=error, extra_metadata=metadata)

    async def get_stats(self) -> Dict[str, Any]:
        assert self._pool
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE processing_status='queued') AS queued,
                    COUNT(*) FILTER (WHERE processing_status='pending') AS pending,
                    COUNT(*) FILTER (WHERE processing_status='processing') AS processing,
                    COUNT(*) FILTER (WHERE processing_status='completed') AS completed,
                    COUNT(*) FILTER (WHERE processing_status='failed') AS failed,
                    MIN(discovered_at) AS first_discovery,
                    MAX(discovered_at) AS last_discovery
                FROM pmoves.channel_monitoring
                """
            )
            recent = await conn.fetch(
                """
                SELECT channel_name, video_title, video_url, discovered_at, processing_status
                FROM pmoves.channel_monitoring
                ORDER BY discovered_at DESC
                LIMIT 10
                """
            )
        return {
            "summary": dict(row) if row else {},
            "recent": [dict(r) for r in recent],
            "active_channels": len([c for c in self.config.get("channels", []) if c.get("enabled", True)]),
        }

    async def add_channel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        channel_id = data.get("channel_id")
        if not channel_id:
            raise ValueError("channel_id is required")
        channel_name = data.get("channel_name")
        if not channel_name:
            channel_name = await self._resolve_channel_name(channel_id)
        new_channel = {
            "channel_id": channel_id,
            "channel_name": channel_name or channel_id,
            "enabled": data.get("enabled", True),
            "check_interval_minutes": data.get("check_interval_minutes", 60),
            "auto_process": data.get("auto_process", True),
            "filters": data.get("filters", {}),
            "priority": data.get("priority", 0),
            "namespace": data.get("namespace", self.namespace_default),
            "tags": data.get("tags", []),
        }
        self.config.setdefault("channels", []).append(new_channel)
        save_config(self.config_path, self.config)
        if new_channel["enabled"]:
            interval = new_channel.get("check_interval_minutes") or 60
            task = asyncio.create_task(self._channel_loop(new_channel, max(1, int(interval))))
            self._tasks.append(task)
        return new_channel

    async def _resolve_channel_name(self, channel_id: str) -> Optional[str]:
        with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
            try:
                info = ydl.extract_info(
                    f"https://www.youtube.com/channel/{channel_id}", download=False
                )
            except Exception:  # pragma: no cover
                return None
        return info.get("uploader")


@asynccontextmanager
async def lifespan_monitor(monitor: ChannelMonitor):
    await monitor.start()
    try:
        yield monitor
    finally:
        await monitor.shutdown()
