from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Set
from uuid import UUID
from urllib.parse import parse_qs, urlparse

import asyncpg
import httpx
import feedparser
from dateutil import parser as date_parser
from yt_dlp import YoutubeDL

from .config import ensure_config, save_config
from .youtube_api import AccessToken, YouTubeAPIClient, YouTubeAPIError

LOGGER = logging.getLogger("channel_monitor")

VALID_STATUSES = {"pending", "processing", "queued", "completed", "failed"}
TERMINAL_STATUSES = {"completed", "failed"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, val in value.items():
            compacted = _compact(val)
            if compacted is not None:
                cleaned[key] = compacted
        return cleaned or None
    if isinstance(value, list):
        cleaned_list = [item for item in (_compact(v) for v in value) if item is not None]
        return cleaned_list or None
    if value in (None, "", [], {}):
        return None
    return value


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _best_thumbnail(thumbnails: Any) -> Optional[str]:
    if isinstance(thumbnails, list):
        sorted_entries = sorted(
            (
                entry
                for entry in thumbnails
                if isinstance(entry, dict) and entry.get("url")
            ),
            key=lambda item: item.get("width") or 0,
            reverse=True,
        )
        if sorted_entries:
            return sorted_entries[0]["url"]
    if isinstance(thumbnails, dict):
        url = thumbnails.get("url")
        if isinstance(url, str) and url:
            return url
    if isinstance(thumbnails, str) and thumbnails:
        return thumbnails
    return None


def _extract_playlist_id_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    query_ids = parse_qs(parsed.query).get("list")
    if query_ids:
        candidate = query_ids[0]
        if isinstance(candidate, str) and candidate:
            return candidate
    parts = [segment for segment in parsed.path.split("/") if segment]
    for idx, segment in enumerate(parts):
        if segment.lower() == "playlist" and idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _extract_channel_id_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    parts = [segment for segment in parsed.path.split("/") if segment]
    if not parts:
        return None
    if parts[0].lower() == "channel" and len(parts) > 1:
        return parts[1]
    if parts[0].startswith("UC"):
        return parts[0]
    if parts[0].startswith("@"):  # handle-based URLs; return handle for upstream resolution
        return parts[0]
    return None


def _extract_channel_handle(channel: Dict[str, Any]) -> Optional[str]:
    candidates = [
        channel.get("channel_id"),
        channel.get("source_identifier"),
        channel.get("source_id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("@") and len(candidate) > 1:
            return candidate
    source_url = channel.get("source_url")
    resolved = _extract_channel_id_from_url(source_url)
    if isinstance(resolved, str) and resolved.startswith("@") and len(resolved) > 1:
        return resolved
    return None


class ChannelMonitor:
    def __init__(
        self,
        config_path,
        queue_url: str,
        database_url: str,
        namespace_default: str = "pmoves",
        *,
        google_client_id: Optional[str] = None,
        google_client_secret: Optional[str] = None,
        google_redirect_uri: Optional[str] = None,
        google_scopes: Optional[List[str]] = None,
    ) -> None:
        self.config_path = config_path
        self.config = ensure_config(config_path)
        self.queue_url = queue_url
        self.database_url = database_url
        self.namespace_default = namespace_default
        self.google_client_id = google_client_id
        self.google_client_secret = google_client_secret
        self.google_redirect_uri = google_redirect_uri
        self._google_scopes = list(google_scopes or [])

        self._pool: Optional[asyncpg.Pool] = None
        self._tasks: List[asyncio.Task] = []
        self._processed_video_ids: Set[str] = set()
        self._shutdown = asyncio.Event()
        self._dynamic_channels: List[Dict[str, Any]] = []
        self._youtube_client: Optional[YouTubeAPIClient] = None
        self._token_cache: Dict[str, AccessToken] = {}
        self._channel_handle_cache: Dict[str, str] = {}

        if self.google_client_id and self.google_client_secret:
            try:
                self._youtube_client = YouTubeAPIClient(
                    self.google_client_id,
                    self.google_client_secret,
                    redirect_uri=self.google_redirect_uri,
                    default_scopes=self._google_scopes,
                )
            except (ValueError, TypeError) as exc:  # pragma: no cover - known config errors
                LOGGER.warning("YouTube API integration disabled due to configuration error: %s", exc)
                self._youtube_client = None  # Explicitly disable if init fails

    async def start(self) -> None:
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
            except (asyncpg.PostgresConnectionError, OSError) as exc:
                LOGGER.critical("Failed to connect to database at %s: %s", self.database_url, exc)
                raise RuntimeError(
                    f"Database connection failed for channel-monitor. "
                    f"Check network connectivity and Supabase status. URL: {self.database_url}"
                ) from exc
        await self._ensure_tables()
        await self._load_processed_videos()
        await self._load_user_sources()

        if self._youtube_client:
            LOGGER.info(
                "YouTube API integration enabled (scopes=%s)",
                ",".join(self._google_scopes) or "default",
            )
        else:
            LOGGER.warning("YouTube API integration disabled; missing client credentials")

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
        if self._youtube_client:
            try:
                await self._youtube_client.aclose()
            except Exception:  # pragma: no cover
                LOGGER.debug("Suppressed YouTube client close error", exc_info=True)

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
        used_api = False
        refresh_token = self._extract_refresh_token(channel)
        if platform == "youtube" and refresh_token and self._youtube_client:
            try:
                videos = await self._fetch_via_youtube_api(channel, refresh_token, max_videos)
                used_api = bool(videos)
            except Exception as exc:  # pragma: no cover
                LOGGER.exception("YouTube API fetch failed (%s): %s", channel_name, exc)
                videos = []
                used_api = False

        if platform == "youtube" and (not used_api or not videos):
            if source_type == "playlist":
                playlist_target = source_url or channel.get("source_identifier") or channel_id
                if playlist_target:
                    videos = await self._fetch_youtube_flat(playlist_target, cookies_path, max_videos)
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
            if platform not in {"youtube", "soundcloud"}:
                LOGGER.warning("Unsupported platform %s for channel %s", platform, channel_name)
            if not videos:
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
            media_thumbnail = getattr(entry, "media_thumbnail", None)
            thumbnail_url = None
            thumbnails: Optional[List[Dict[str, Any]]] = None
            if isinstance(media_thumbnail, list):
                thumbnails = [
                    {"url": thumb.get("url"), "width": thumb.get("width"), "height": thumb.get("height")}
                    for thumb in media_thumbnail
                    if isinstance(thumb, dict) and thumb.get("url")
                ]
                thumbnail_url = thumbnails[0]["url"] if thumbnails else None
            elif isinstance(media_thumbnail, dict):
                if media_thumbnail.get("url"):
                    thumbnail_url = media_thumbnail["url"]
                    thumbnails = [media_thumbnail]

            author_detail = getattr(entry, "author_detail", None)
            if isinstance(author_detail, dict):
                channel_href = author_detail.get("href")
            else:
                channel_href = getattr(author_detail, "href", None)

            channel_info = _compact(
                {
                    "id": channel_id,
                    "name": getattr(entry, "author", None),
                    "url": channel_href,
                }
            )

            results.append(
                {
                    "video_id": video_id,
                    "title": entry.title,
                    "url": entry.link,
                    "published": published,
                    "author": getattr(entry, "author", ""),
                    "description": getattr(entry, "summary", ""),
                    "duration": getattr(entry, "media_duration", None),
                    "thumbnails": thumbnails,
                    "thumbnail": thumbnail_url,
                    "tags": getattr(entry, "media_keywords", None),
                    "channel": channel_info or {},
                }
            )
        return results

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
                    metadata_payload = self._build_metadata(channel, video)
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
                        json.dumps(metadata_payload),
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
            monitor_metadata = self._build_metadata(channel, video)
            channel_context = (
                monitor_metadata.get("channel") if isinstance(monitor_metadata.get("channel"), dict) else {}
            )
            video_context = (
                monitor_metadata.get("video") if isinstance(monitor_metadata.get("video"), dict) else {}
            )
            payload_metadata = _compact(
                {
                    "platform": channel.get("platform", "youtube"),
                    "source_type": channel.get("source_type", "channel"),
                    "channel_name": channel_label,
                    "channel_id": channel_identifier,
                    "channel_url": channel_context.get("url"),
                    "channel_thumbnail": channel_context.get("thumbnail"),
                    "channel_namespace": channel_context.get("namespace"),
                    "channel_tags": channel_context.get("tags"),
                    "channel_priority": channel_context.get("priority"),
                    "channel_subscriber_count": channel_context.get("subscriber_count"),
                    "video_thumbnail": video_context.get("thumbnail"),
                    "video_duration_seconds": video_context.get("duration_seconds"),
                    "channel_monitor": monitor_metadata,
                }
            ) or {}
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
                    "metadata": payload_metadata,
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

    async def _get_access_token(self, refresh_token: str) -> AccessToken:
        cached = self._token_cache.get(refresh_token)
        if cached and cached.expires_at > utcnow():
            return cached
        if not self._youtube_client:
            raise RuntimeError("YouTube client not configured")
        token = await self._youtube_client.refresh_access_token(
            refresh_token,
            scope=self._google_scopes or None,
        )
        if not token.token:
            raise YouTubeAPIError("Missing access_token from refresh response")
        safety_margin = timedelta(seconds=60)
        cached_expiry = token.expires_at - safety_margin
        if cached_expiry <= utcnow():
            cached_expiry = token.expires_at
        cached_token = AccessToken(
            token=token.token,
            expires_at=cached_expiry,
            scope=token.scope,
            token_type=token.token_type,
        )
        self._token_cache[refresh_token] = cached_token
        await self._update_user_token_expiry(refresh_token, token.expires_at)
        return cached_token

    async def _resolve_channel_handle_via_api(self, access_token: str, handle: str) -> Optional[str]:
        if not self._youtube_client:
            return None
        normalized = handle if handle.startswith("@") else f"@{handle}"
        cached = self._channel_handle_cache.get(normalized)
        if cached:
            return cached
        try:
            resolved = await self._youtube_client.resolve_channel_handle(access_token, normalized)
        except YouTubeAPIError as exc:
            LOGGER.warning("Failed to resolve YouTube handle %s via API: %s", handle, exc)
            return None
        if resolved:
            self._channel_handle_cache[normalized] = resolved
        return resolved

    async def _update_user_token_expiry(self, refresh_token: str, expires_at: datetime) -> None:
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE pmoves.user_tokens
                    SET expires_at = $1
                    WHERE refresh_token = $2
                    """,
                    expires_at,
                    refresh_token,
                )
        except Exception:  # pragma: no cover
            LOGGER.debug("Failed to persist token expiry for refresh token", exc_info=True)

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

    async def _fetch_via_youtube_api(
        self,
        channel: Dict[str, Any],
        refresh_token: str,
        max_items: int,
    ) -> List[Dict[str, Any]]:
        if not self._youtube_client:
            return []
        token = await self._get_access_token(refresh_token)
        if not token.token:
            LOGGER.warning("Access token missing after refresh for channel %s", channel.get("channel_name"))
            return []

        source_type = channel.get("source_type", "channel").lower()
        videos: List[Dict[str, Any]] = []

        if source_type == "playlist":
            playlist_id = self._resolve_playlist_id(channel)
            if not playlist_id:
                LOGGER.warning("No playlist identifier for channel %s", channel.get("channel_name"))
                return []
            videos = await self._youtube_client.fetch_playlist_videos(
                token.token,
                playlist_id,
                max_items=max_items,
            )
        else:
            channel_identifier = self._resolve_channel_id_for_api(channel)
            if (not channel_identifier or channel_identifier.startswith("@")) and token.token:
                handle = _extract_channel_handle(channel)
                if handle:
                    resolved = await self._resolve_channel_handle_via_api(token.token, handle)
                    if resolved:
                        channel_identifier = resolved
                        channel.setdefault("channel_id", resolved)
                        channel.setdefault("source_identifier", resolved)
                        LOGGER.info("Resolved YouTube handle %s to channel ID %s", handle, resolved)
            if not channel_identifier:
                LOGGER.warning("No channel identifier for API fetch (%s)", channel.get("channel_name"))
                return []
            videos = await self._youtube_client.fetch_channel_recent_videos(
                token.token,
                channel_identifier,
                max_items=max_items,
            )

        normalized: List[Dict[str, Any]] = []
        for video in videos:
            video_id = video.get("video_id")
            if not video_id:
                continue
            item = dict(video)
            item["published"] = self._ensure_datetime(
                item.get("published") or item.get("published_raw")
            )
            if not item.get("author"):
                channel_info = item.get("channel") or {}
                if isinstance(channel_info, dict):
                    item["author"] = channel_info.get("name")
            normalized.append(item)
        return normalized

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
                channel_info = {
                    "id": entry.get("channel_id") or entry.get("uploader_id"),
                    "name": entry.get("uploader") or entry.get("channel"),
                    "url": entry.get("uploader_url") or entry.get("channel_url"),
                    "description": entry.get("channel_description"),
                    "thumbnail": entry.get("channel_thumbnail"),
                    "subscriber_count": entry.get("channel_follower_count")
                    or entry.get("channel_subscriber_count")
                    or entry.get("channel_view_count"),
                    "view_count": entry.get("channel_view_count"),
                }
                stats = {
                    "view_count": entry.get("view_count"),
                    "like_count": entry.get("like_count"),
                    "comment_count": entry.get("comment_count"),
                }
                thumbnails = entry.get("thumbnails")
                results.append(
                    {
                        "video_id": str(video_id),
                        "title": entry.get("title") or video_id,
                        "url": webpage_url,
                        "published": published,
                        "author": entry.get("uploader") or entry.get("channel") or "",
                        "description": entry.get("description") or "",
                        "duration": entry.get("duration"),
                        "thumbnails": thumbnails,
                        "thumbnail": entry.get("thumbnail") or _best_thumbnail(thumbnails),
                        "tags": entry.get("tags"),
                        "categories": entry.get("categories"),
                        "channel": _compact(channel_info) or {},
                        "stats": _compact(stats) or {},
                    }
                )
        return results

    def _default_interval(self) -> int:
        return max(1, int(self.config.get("monitoring_schedule", {}).get("interval_minutes") or 30))

    def _global_channel_metadata_fields(self) -> List[str]:
        fields = self.config.get("global_settings", {}).get("channel_metadata_fields") or []
        if not isinstance(fields, list):
            return []
        return [str(field) for field in fields if isinstance(field, str)]

    def _global_video_metadata_fields(self) -> List[str]:
        fields = self.config.get("global_settings", {}).get("video_metadata_fields") or []
        if not isinstance(fields, list):
            return []
        return [str(field) for field in fields if isinstance(field, str)]

    def _metadata_fields_for(self, channel: Dict[str, Any], key: str, default: List[str]) -> List[str]:
        override = channel.get(key)
        if isinstance(override, list):
            return [str(field) for field in override if isinstance(field, str)]
        return list(default)

    def _resolve_channel_breakdown_limit(self) -> int:
        value = self.config.get("global_settings", {}).get("channel_breakdown_limit")
        try:
            limit = int(value)
        except (TypeError, ValueError):
            limit = 25
        return max(1, limit)

    def _extract_channel_metadata(
        self,
        channel: Dict[str, Any],
        video: Dict[str, Any],
        fields: List[str],
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        video_channel = video.get("channel") if isinstance(video.get("channel"), dict) else {}
        channel_identifier: Optional[str]
        try:
            channel_identifier = self._resolve_channel_identifier(channel)
        except Exception:
            channel_identifier = None

        for field in fields:
            value: Any = None
            if field == "id":
                value = (
                    video_channel.get("id")
                    or channel.get("channel_id")
                    or channel.get("source_identifier")
                    or channel_identifier
                )
            elif field == "name":
                value = channel.get("channel_name") or video_channel.get("name") or video.get("author")
            elif field == "url":
                value = channel.get("source_url") or video_channel.get("url")
                if not value:
                    candidate_id = (
                        video_channel.get("id")
                        or channel.get("channel_id")
                        or channel.get("source_identifier")
                    )
                    if isinstance(candidate_id, str) and candidate_id:
                        value = f"https://www.youtube.com/channel/{candidate_id}"
            elif field == "namespace":
                value = channel.get("namespace", self.namespace_default)
            elif field == "tags":
                tags = channel.get("tags")
                if isinstance(tags, list):
                    value = [str(tag) for tag in tags if isinstance(tag, str)]
            elif field == "priority":
                value = channel.get("priority")
            elif field == "subscriber_count":
                value = video_channel.get("subscriber_count") or video_channel.get("view_count")
            elif field == "thumbnail":
                value = video_channel.get("thumbnail")
            elif field == "description":
                value = video_channel.get("description")
            elif field == "notes":
                value = channel.get("notes")
            if value is not None:
                metadata[field] = value

        return _compact(metadata) or {}

    def _extract_video_metadata(
        self,
        channel: Dict[str, Any],
        video: Dict[str, Any],
        fields: List[str],
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        stats = video.get("stats") if isinstance(video.get("stats"), dict) else {}

        for field in fields:
            value: Any = None
            if field == "duration":
                duration = video.get("duration")
                if isinstance(duration, (int, float)):
                    value = float(duration)
                elif isinstance(duration, str):
                    try:
                        value = float(duration)
                    except ValueError:
                        value = None
                if value is not None:
                    metadata["duration_seconds"] = value
            elif field == "view_count":
                view_count = stats.get("view_count")
                if view_count is None:
                    view_count = video.get("view_count")
                if isinstance(view_count, (int, float)):
                    metadata["view_count"] = int(view_count)
                elif isinstance(view_count, str):
                    try:
                        metadata["view_count"] = int(float(view_count))
                    except ValueError:
                        pass
            elif field == "like_count":
                like_count = stats.get("like_count")
                if like_count is None:
                    like_count = video.get("like_count")
                if isinstance(like_count, (int, float)):
                    metadata["like_count"] = int(like_count)
                elif isinstance(like_count, str):
                    try:
                        metadata["like_count"] = int(float(like_count))
                    except ValueError:
                        pass
            elif field == "thumbnail":
                thumb = video.get("thumbnail") or _best_thumbnail(video.get("thumbnails"))
                if thumb:
                    metadata["thumbnail"] = thumb
            elif field == "published_at":
                published = video.get("published")
                iso = _to_iso(published) if isinstance(published, datetime) else None
                if iso:
                    metadata["published_at"] = iso
            elif field == "categories":
                categories = video.get("categories")
                if isinstance(categories, list):
                    metadata["categories"] = [
                        str(category) for category in categories if isinstance(category, str)
                    ]
            elif field == "tags":
                tags = video.get("tags")
                if isinstance(tags, list):
                    metadata["tags"] = [str(tag) for tag in tags if isinstance(tag, str)]

        return _compact(metadata) or {}

    def _build_metadata(self, channel: Dict[str, Any], video: Dict[str, Any]) -> Dict[str, Any]:
        channel_fields = self._metadata_fields_for(
            channel, "channel_metadata_fields", self._global_channel_metadata_fields()
        )
        video_fields = self._metadata_fields_for(
            channel, "video_metadata_fields", self._global_video_metadata_fields()
        )
        channel_section = self._extract_channel_metadata(channel, video, channel_fields)
        video_section = self._extract_video_metadata(channel, video, video_fields)

        metadata = {
            "platform": channel.get("platform"),
            "source_type": channel.get("source_type"),
            "source_url": channel.get("source_url"),
            "author": video.get("author"),
            "description": video.get("description"),
            "channel": channel_section or None,
            "video": video_section or None,
        }

        stats = video.get("stats")
        if isinstance(stats, dict) and stats:
            metadata["stats"] = stats

        if channel_section:
            metadata.setdefault("channel_id", channel_section.get("id"))
            metadata.setdefault("channel_name", channel_section.get("name"))
            metadata.setdefault("channel_url", channel_section.get("url"))
            metadata.setdefault("channel_thumbnail", channel_section.get("thumbnail"))
            metadata.setdefault("channel_description", channel_section.get("description"))
            metadata.setdefault("channel_namespace", channel_section.get("namespace"))
            metadata.setdefault("channel_tags", channel_section.get("tags"))
            metadata.setdefault("subscriber_count", channel_section.get("subscriber_count"))

        if video_section:
            if "thumbnail" in video_section:
                metadata.setdefault("video_thumbnail", video_section.get("thumbnail"))
            if "duration_seconds" in video_section:
                metadata.setdefault("video_duration_seconds", video_section.get("duration_seconds"))

        metadata.setdefault("namespace", channel.get("namespace", self.namespace_default))
        metadata.setdefault("tags", channel.get("tags"))

        return _compact(metadata) or {}

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
        channel_fields = record.get("channel_metadata_fields") or config.get("channel_metadata_fields")
        if isinstance(channel_fields, list):
            entry["channel_metadata_fields"] = [
                str(field) for field in channel_fields if isinstance(field, str)
            ]
        video_fields = record.get("video_metadata_fields") or config.get("video_metadata_fields")
        if isinstance(video_fields, list):
            entry["video_metadata_fields"] = [
                str(field) for field in video_fields if isinstance(field, str)
            ]
        return entry

    def _extract_refresh_token(self, channel: Dict[str, Any]) -> Optional[str]:
        yt_options = channel.get("yt_options") or {}
        token = yt_options.get("oauth_refresh_token")
        if not token:
            token = channel.get("oauth_refresh_token")
        return token

    def _resolve_playlist_id(self, channel: Dict[str, Any]) -> Optional[str]:
        playlist_id = (
            channel.get("playlist_id")
            or channel.get("source_identifier")
            or channel.get("source_id")
        )
        if isinstance(playlist_id, str) and playlist_id:
            return playlist_id
        source_url = channel.get("source_url")
        return _extract_playlist_id_from_url(source_url)

    def _resolve_channel_id_for_api(self, channel: Dict[str, Any]) -> Optional[str]:
        candidate = (
            channel.get("channel_id")
            or channel.get("source_identifier")
            or channel.get("source_id")
        )
        if isinstance(candidate, str) and candidate.startswith("@"):  # YouTube handle, unsupported directly
            return None
        if isinstance(candidate, str) and candidate:
            return candidate
        source_url = channel.get("source_url")
        resolved = _extract_channel_id_from_url(source_url)
        if isinstance(resolved, str) and resolved.startswith("@"):  # handle still unsupported
            return None
        return resolved

    @staticmethod
    def _ensure_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                parsed = date_parser.parse(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                else:
                    parsed = parsed.astimezone(timezone.utc)
                return parsed
            except (ValueError, TypeError):
                pass
        return utcnow()

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
            scope = [token for token in scope.replace(",", " ").split() if token]
        expires_at = payload.get("expires_at")
        expires_in = payload.get("expires_in")
        if expires_in and not expires_at:
            try:
                expires_at = utcnow() + timedelta(seconds=int(expires_in))
            except (ValueError, TypeError):
                expires_at = None

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
        self._token_cache.clear()
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

    async def check_database_health(self) -> bool:
        """Check if the database connection is alive and queryable.

        Executes a lightweight query to verify connectivity. Returns True if
        the database responds successfully, False otherwise.

        This method is safe to call even if the pool has not been initialized.
        It handles connection errors gracefully and returns False rather than
        raising exceptions.

        Returns:
            True if database connection is healthy, False otherwise.
        """
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                # Use SELECT 1 for a lightweight connection test
                await conn.fetchval("SELECT 1")
            return True
        except (asyncpg.PostgresConnectionError, OSError):  # pragma: no cover
            return False

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
                SELECT channel_id, channel_name, video_title, video_url, discovered_at, processing_status,
                       metadata->>'channel_url' AS channel_url,
                       metadata->>'channel_thumbnail' AS channel_thumbnail
                FROM pmoves.channel_monitoring
                ORDER BY discovered_at DESC
                LIMIT 10
                """
            )
            channel_rows = await conn.fetch(
                """
                SELECT
                    channel_id,
                    MAX(channel_name) AS channel_name,
                    MAX(namespace) AS namespace,
                    (SELECT ARRAY_AGG(DISTINCT tag) FROM (
                        SELECT UNNEST(tags) AS tag FROM pmoves.channel_monitoring cm2
                        WHERE cm2.channel_id = pmoves.channel_monitoring.channel_id
                    ) t) AS tags_collection,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE processing_status='pending') AS pending,
                    COUNT(*) FILTER (WHERE processing_status='queued') AS queued,
                    COUNT(*) FILTER (WHERE processing_status='processing') AS processing,
                    COUNT(*) FILTER (WHERE processing_status='completed') AS completed,
                    COUNT(*) FILTER (WHERE processing_status='failed') AS failed,
                    MAX(discovered_at) AS last_discovered_at,
                    MAX(published_at) AS last_published_at,
                    MAX(metadata->>'channel_url') AS channel_url,
                    MAX(metadata->>'channel_thumbnail') AS channel_thumbnail,
                    MAX(metadata->>'channel_description') AS channel_description,
                    MAX(metadata->>'last_status') AS last_status,
                    MAX(metadata->>'last_status_at') AS last_status_at,
                    MAX(metadata->>'subscriber_count') AS subscriber_count_raw
                FROM pmoves.channel_monitoring
                GROUP BY channel_id
                ORDER BY last_discovered_at DESC NULLS LAST
                LIMIT $1
                """,
                self._resolve_channel_breakdown_limit(),
            )
        summary = dict(row) if row else {}
        if summary.get("first_discovery"):
            summary["first_discovery"] = _to_iso(summary["first_discovery"])
        if summary.get("last_discovery"):
            summary["last_discovery"] = _to_iso(summary["last_discovery"])

        formatted_recent: List[Dict[str, Any]] = []
        for item in recent:
            data = dict(item)
            data["discovered_at"] = _to_iso(data.get("discovered_at"))
            formatted_recent.append(data)

        channel_breakdown: List[Dict[str, Any]] = []
        for item in channel_rows:
            tags_collection = item.get("tags_collection") or []
            # tags_collection is now a flat array of distinct tags
            tag_set = {
                tag for tag in tags_collection
                if isinstance(tag, str) and tag
            }
            subscriber_raw = item.get("subscriber_count_raw")
            try:
                subscriber_count = int(subscriber_raw) if subscriber_raw is not None else None
            except (TypeError, ValueError):
                subscriber_count = None

            channel_breakdown.append(
                {
                    "channel_id": item.get("channel_id"),
                    "channel_name": item.get("channel_name"),
                    "namespace": item.get("namespace"),
                    "tags": sorted(tag_set),
                    "totals": {
                        "total": item.get("total", 0),
                        "pending": item.get("pending", 0),
                        "queued": item.get("queued", 0),
                        "processing": item.get("processing", 0),
                        "completed": item.get("completed", 0),
                        "failed": item.get("failed", 0),
                    },
                    "last_discovered_at": _to_iso(item.get("last_discovered_at")),
                    "last_published_at": _to_iso(item.get("last_published_at")),
                    "channel_url": item.get("channel_url"),
                    "channel_thumbnail": item.get("channel_thumbnail"),
                    "channel_description": item.get("channel_description"),
                    "subscriber_count": subscriber_count,
                    "last_status": item.get("last_status"),
                    "last_status_at": item.get("last_status_at"),
                }
            )

        return {
            "summary": summary,
            "recent": formatted_recent,
            "channels": channel_breakdown,
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
        for key in ("channel_metadata_fields", "video_metadata_fields"):
            value = data.get(key)
            if isinstance(value, list):
                new_channel[key] = [str(field) for field in value if isinstance(field, str)]
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
