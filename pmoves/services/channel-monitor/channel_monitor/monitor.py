from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

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
        self._dynamic_channels: List[Dict[str, Any]] = []

    async def start(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        await self._ensure_tables()
        await self._load_processed_videos()
        await self._load_user_sources()

        if self.config["global_settings"].get("check_on_startup", True):
            await self.check_all_channels()

        for channel in self._active_channels():
            if not channel.get("enabled", True):
                continue
            interval = channel.get("check_interval_minutes") or self._default_interval()
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
                WHERE processing_status IN ('queued', 'processing', 'completed')
                """
            )
        self._processed_video_ids = {row["video_id"] for row in rows}
        LOGGER.info("Loaded %s processed videos", len(self._processed_video_ids))

    async def check_all_channels(self) -> int:
        total_new = 0
        channels = self._active_channels()
        for channel in channels:
            total_new += await self.check_single_channel(channel)
        return total_new

    async def check_single_channel(self, channel: Dict[str, Any]) -> int:
        channel_name = channel.get("channel_name") or channel.get("source_url") or channel.get("channel_id")
        platform = channel.get("platform", "youtube").lower()
        source_type = channel.get("source_type", "channel").lower()
        cookies_path = channel.get("cookies_path")
        max_videos = channel.get("max_items") or self.config["global_settings"].get("max_videos_per_check", 10)
        channel_id = channel.get("channel_id") or channel.get("source_id")
        source_url = channel.get("source_url")
        LOGGER.info("Checking channel %s", channel_name)

        videos: List[Dict[str, Any]] = []
        if platform == "youtube":
            if source_type == "playlist" and source_url:
                videos = await self._fetch_youtube_flat(source_url, cookies_path, max_videos)
            elif source_url:
                videos = await self._fetch_youtube_flat(source_url, cookies_path, max_videos)
            else:
                if self.config["global_settings"].get("use_rss_feed", True) and channel_id:
                    videos = await self._fetch_via_rss(channel_id)
                elif channel_id:
                    playlist_url = f"https://www.youtube.com/channel/{channel_id}"
                    videos = await self._fetch_youtube_flat(playlist_url, cookies_path, max_videos)
        elif platform == "soundcloud" and source_url:
            videos = await self._fetch_soundcloud(source_url, cookies_path, max_videos)
        else:
            LOGGER.warning("Unsupported platform %s for channel %s", platform, channel_name)
            return 0

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

        await self._update_user_source_status(channel, len(new_videos))

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
                channel_identifier = self._resolve_channel_identifier(channel)
                for video in videos:
                    published = video["published"]
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                    metadata = json.dumps(
                        {
                            "description": video.get("description", ""),
                            "author": video.get("author", ""),
                            "platform": channel.get("platform"),
                            "source_type": channel.get("source_type"),
                            "source_url": channel.get("source_url"),
                        }
                    )
                    await conn.execute(
                        """
                        INSERT INTO pmoves.channel_monitoring (
                            channel_id, channel_name, video_id, video_title, video_url,
                            published_at, priority, namespace, tags, metadata
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        ON CONFLICT (channel_id, video_id) DO NOTHING
                        """,
                        channel_identifier,
                        channel.get("channel_name"),
                        video["video_id"],
                        video["title"],
                        video["url"],
                        published,
                        channel.get("priority", 0),
                        channel.get("namespace", self.namespace_default),
                        channel.get("tags", []),
                        metadata,
                    )
        for video in videos:
            self._processed_video_ids.add(video["video_id"])

    async def _queue_videos(self, channel: Dict[str, Any], videos: List[Dict[str, Any]]) -> None:
        namespace = channel.get("namespace", self.namespace_default)
        payloads = []
        yt_options = self._build_yt_options(channel)
        format_override = channel.get("format")
        media_type = channel.get("media_type") or "video"
        channel_label = (
            channel.get("channel_name")
            or channel.get("source_url")
            or channel.get("channel_id")
            or channel.get("source_id")
            or "unknown"
        )
        channel_identifier = self._resolve_channel_identifier(channel)
        for video in videos:
            payloads.append(
                {
                    "url": video["url"],
                    "namespace": namespace,
                    "auto_emit": False,
                    "source": "channel_monitor",
                    "tags": channel.get("tags", []),
                    "media_type": media_type,
                    "format": format_override,
                    "yt_options": yt_options,
                    "metadata": {
                        "platform": channel.get("platform", "youtube"),
                        "source_type": channel.get("source_type", "channel"),
                        "channel_name": channel_label,
                        "channel_id": channel_identifier,
                    },
                }
            )
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
        if channel.get("cookies_path"):
            # yt-dlp expects `cookiefile`; preserve backward compat with older configs that used `cookies`
            merged.pop("cookies", None)
            merged.setdefault("cookiefile", channel["cookies_path"])
        return merged

    async def _fetch_youtube_flat(
        self,
        url: str,
        cookies_path: Optional[str],
        max_items: Optional[int],
    ) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._yt_dlp_extract, url, cookies_path, max_items, platform="youtube"),
        )

    async def _fetch_soundcloud(
        self,
        url: str,
        cookies_path: Optional[str],
        max_items: Optional[int],
    ) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._yt_dlp_extract, url, cookies_path, max_items, platform="soundcloud"),
        )

    @staticmethod
    def _yt_dlp_extract(
        url: str,
        cookies_path: Optional[str],
        max_items: Optional[int],
        platform: str,
    ) -> List[Dict[str, Any]]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
        }
        if cookies_path:
            opts["cookiefile"] = cookies_path
        results: List[Dict[str, Any]] = []
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get("entries")
            if entries is None:
                entries = [info]
            if isinstance(entries, dict):
                entries = entries.values()
            for entry in entries:
                if max_items and len(results) >= max_items:
                    break
                video_id = entry.get("id") or entry.get("url")
                if not video_id:
                    continue
                webpage_url = entry.get("webpage_url") or entry.get("url")
                if platform == "youtube" and video_id and not webpage_url:
                    webpage_url = f"https://www.youtube.com/watch?v={video_id}"
                published_ts = entry.get("timestamp") or entry.get("release_timestamp")
                if entry.get("upload_date") and not published_ts:
                    try:
                        published_ts = datetime.strptime(entry["upload_date"], "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
                    except Exception:
                        published_ts = None
                if published_ts:
                    published = datetime.fromtimestamp(published_ts, tz=timezone.utc)
                else:
                    published = utcnow()
                results.append(
                    {
                        "video_id": str(video_id),
                        "title": entry.get("title") or video_id,
                        "url": webpage_url,
                        "published": published,
                        "author": entry.get("uploader") or entry.get("channel") or "",
                        "description": entry.get("description") or "",
                    }
                )
        return results

    def _default_interval(self) -> int:
        return max(1, int(self.config.get("monitoring_schedule", {}).get("interval_minutes") or 30))

    def _active_channels(self) -> List[Dict[str, Any]]:
        channels = [c for c in self.config.get("channels", []) if c.get("enabled", True)]
        channels.extend([c for c in self._dynamic_channels if c.get("enabled", True)])
        return channels

    def _resolve_channel_identifier(self, channel: Dict[str, Any]) -> str:
        identifier = (
            channel.get("channel_id")
            or channel.get("source_identifier")
            or channel.get("source_url")
            or channel.get("channel_name")
        )
        if identifier:
            return str(identifier)
        raise ValueError("channel configuration missing identifier")

    async def _load_user_sources(self) -> None:
        assert self._pool
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT us.*, ut.refresh_token
                FROM pmoves.user_sources us
                LEFT JOIN pmoves.user_tokens ut ON us.token_id = ut.id
                WHERE us.status = 'active'
                """
            )

        dynamic: List[Dict[str, Any]] = []
        for row in rows:
            entry = self._build_dynamic_channel(row)
            dynamic.append(entry)

        self._dynamic_channels = dynamic

    def _build_dynamic_channel(self, row: asyncpg.Record) -> Dict[str, Any]:
        record = dict(row)
        config = record.get("config") or {}
        if not isinstance(config, dict):
            try:
                config = dict(config)
            except Exception:
                config = {}
        filters = record.get("filters") or config.get("filters") or {}
        if not isinstance(filters, dict):
            filters = {}
        yt_options = dict(self.config.get("global_settings", {}).get("yt_options") or {})
        extra_opts = record.get("yt_options") or config.get("yt_options") or {}
        if isinstance(extra_opts, list):
            try:
                extra_opts = dict(extra_opts)
            except Exception:
                extra_opts = {}
        if extra_opts and not isinstance(extra_opts, dict):
            extra_opts = {}
        yt_options.update(extra_opts)
        refresh_token = record.get("refresh_token")
        if refresh_token:
            yt_options.setdefault("oauth_refresh_token", refresh_token)

        source_identifier = record.get("source_identifier") or record.get("source_url") or str(record["id"])
        user_ref = record.get('user_id')
        user_label = str(user_ref) if user_ref else 'system'
        channel_id = f"user:{user_label}:{source_identifier}"

        entry = {
            "channel_id": channel_id,
            "channel_name": record.get("source_url") or source_identifier,
            "platform": record.get("provider", "youtube"),
            "source_type": record.get("source_type", "channel"),
            "source_identifier": source_identifier,
            "source_url": record.get("source_url"),
            "enabled": record.get("status") == "active",
            "auto_process": record.get("auto_process", True),
            "namespace": record.get("namespace") or self.namespace_default,
            "tags": record.get("tags") or [],
            "filters": filters,
            "yt_options": yt_options,
            "check_interval_minutes": record.get("check_interval_minutes") or config.get("check_interval_minutes"),
            "user_source_id": str(record["id"]),
            "user_id": str(user_ref) if user_ref else None,
            "cookies_path": record.get("cookies_path") or config.get("cookies_path"),
            "media_type": config.get("media_type", "video"),
            "format": config.get("format"),
        }
        return entry

    async def _update_user_source_status(self, channel: Dict[str, Any], discovered: int) -> None:
        user_source_id = channel.get("user_source_id")
        if not user_source_id or not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pmoves.user_sources
                SET last_check_at = timezone('utc', now()),
                    last_ingest_at = CASE WHEN $2 > 0 THEN timezone('utc', now()) ELSE last_ingest_at END
                WHERE id = $1
                """,
                UUID(user_source_id),
                discovered,
            )

    async def upsert_user_token(self, payload: Dict[str, Any]) -> UUID:
        assert self._pool
        user_id = UUID(payload["user_id"])
        provider = payload.get("provider", "youtube")
        refresh_token = payload["refresh_token"]
        scope = payload.get("scope") or []
        if isinstance(scope, str):
            scope = [scope]
        expires_at = payload.get("expires_at")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO pmoves.user_tokens (user_id, provider, scope, refresh_token, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, provider)
                DO UPDATE SET scope = EXCLUDED.scope,
                              refresh_token = EXCLUDED.refresh_token,
                              expires_at = EXCLUDED.expires_at,
                              updated_at = timezone('utc', now())
                RETURNING id
                """,
                user_id,
                provider,
                scope,
                refresh_token,
                expires_at,
            )
        await self._load_user_sources()
        return row["id"]

    async def upsert_user_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        assert self._pool
        user_id = UUID(payload["user_id"])
        provider = payload.get("provider", "youtube")
        source_type = payload["source_type"].lower()
        source_identifier = payload.get("source_identifier") or payload.get("source_url")
        source_url = payload.get("source_url")
        namespace = payload.get("namespace") or self.namespace_default
        tags = payload.get("tags") or []
        auto_process = payload.get("auto_process", True)
        check_interval = payload.get("check_interval_minutes")
        filters = payload.get("filters") or {}
        yt_options = payload.get("yt_options") or {}
        token_id = payload.get("token_id")
        status = payload.get("status", "active")

        token_uuid = UUID(token_id) if token_id else None

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO pmoves.user_sources (
                    user_id, provider, source_type, source_identifier, source_url,
                    namespace, tags, status, auto_process, check_interval_minutes,
                    filters, yt_options, token_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (user_id, provider, COALESCE(source_identifier, ''), COALESCE(source_url, ''))
                DO UPDATE SET namespace = EXCLUDED.namespace,
                              tags = EXCLUDED.tags,
                              status = EXCLUDED.status,
                              auto_process = EXCLUDED.auto_process,
                              check_interval_minutes = EXCLUDED.check_interval_minutes,
                              filters = EXCLUDED.filters,
                              yt_options = EXCLUDED.yt_options,
                              token_id = EXCLUDED.token_id,
                              updated_at = timezone('utc', now())
                RETURNING *
                """,
                user_id,
                provider,
                source_type,
                source_identifier,
                source_url,
                namespace,
                tags,
                status,
                auto_process,
                check_interval,
                filters,
                yt_options,
                token_uuid,
            )

        await self._load_user_sources()
        return dict(row)

    async def list_user_sources(self) -> List[Dict[str, Any]]:
        assert self._pool
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM pmoves.user_sources ORDER BY created_at DESC")
        return [dict(row) for row in rows]

    def list_channels(self) -> List[Dict[str, Any]]:
        return self._active_channels()

    def channel_count(self) -> int:
        return len(self._active_channels())

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
        elif status in {"pending", "failed"}:
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
            "active_channels": len(self._active_channels()),
            "dynamic_channels": len([c for c in self._dynamic_channels if c.get("enabled", True)]),
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
