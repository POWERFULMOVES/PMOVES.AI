from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx
from dateutil import parser as date_parser


class YouTubeAPIError(RuntimeError):
    """Raised when the YouTube Data API responds with an error."""


@dataclass(slots=True)
class AccessToken:
    token: str
    expires_at: datetime
    scope: Optional[str] = None
    token_type: Optional[str] = None


def _iso_to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _parse_duration(duration: Optional[str]) -> Optional[float]:
    """Convert ISO 8601 duration (PT#M#S) to seconds."""
    if not duration:
        return None
    # Manual parser to avoid pulling in isodate dependency
    total_seconds = 0
    current = ""
    multiplier = {"H": 3600, "M": 60, "S": 1}
    try:
        if not duration.startswith("PT"):
            return None
        duration = duration[2:]
        for char in duration:
            if char.isdigit() or char == ".":
                current += char
                continue
            if char in multiplier and current:
                total_seconds += float(current) * multiplier[char]
                current = ""
        return total_seconds or None
    except Exception:
        return None


class YouTubeAPIClient:
    API_BASE = "https://www.googleapis.com/youtube/v3"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        redirect_uri: Optional[str] = None,
        default_scopes: Optional[Iterable[str]] = None,
        timeout: float = 30.0,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("client_id and client_secret are required")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.default_scopes = list(default_scopes or [])
        self._client = httpx.AsyncClient(timeout=timeout)
        self._client_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        redirect_uri: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.redirect_uri,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier
        async with self._client_lock:
            response = await self._client.post(self.TOKEN_URL, data=payload)
        data = response.json()
        if response.status_code >= 400 or "error" in data:
            raise YouTubeAPIError(str(data))
        return data

    async def refresh_access_token(
        self,
        refresh_token: str,
        *,
        scope: Optional[Iterable[str]] = None,
    ) -> AccessToken:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if scope:
            payload["scope"] = " ".join(scope)
        async with self._client_lock:
            response = await self._client.post(self.TOKEN_URL, data=payload)
        data = response.json()
        if response.status_code >= 400 or "error" in data:
            raise YouTubeAPIError(str(data))
        expires_in = data.get("expires_in") or 0
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(int(expires_in), 0))
        return AccessToken(
            token=data.get("access_token"),
            expires_at=expires_at,
            scope=data.get("scope"),
            token_type=data.get("token_type"),
        )

    async def fetch_playlist_videos(
        self,
        access_token: str,
        playlist_id: str,
        *,
        max_items: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        remaining = max_items or 50
        while remaining > 0:
            batch_size = min(remaining, 50)
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": batch_size,
            }
            if page_token:
                params["pageToken"] = page_token
            data = await self._get("playlistItems", params, access_token)
            entries = data.get("items", [])
            if not entries:
                break
            mapped = self._map_playlist_items(entries)
            results.extend(mapped)
            remaining = remaining - len(mapped)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return await self._hydrate_video_details(access_token, results)

    async def fetch_channel_recent_videos(
        self,
        access_token: str,
        channel_id: str,
        *,
        max_items: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        remaining = max_items or 50
        while remaining > 0:
            batch_size = min(remaining, 50)
            params = {
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "type": "video",
                "maxResults": batch_size,
            }
            if page_token:
                params["pageToken"] = page_token
            data = await self._get("search", params, access_token)
            items = data.get("items", [])
            if not items:
                break
            mapped = self._map_search_items(items)
            results.extend(mapped)
            remaining = remaining - len(mapped)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return await self._hydrate_video_details(access_token, results)

    async def resolve_channel_handle(self, access_token: str, handle: str) -> Optional[str]:
        normalized = handle.lstrip("@")
        # Attempt direct channel lookup using forHandle when supported
        params = {
            "part": "id",
            "forHandle": normalized,
        }
        try:
            data = await self._get("channels", params, access_token)
        except YouTubeAPIError:
            data = {}
        items = data.get("items") if isinstance(data, dict) else None
        if items:
            first = items[0]
            channel_id = first.get("id") if isinstance(first, dict) else None
            if channel_id:
                return channel_id
        # Fallback to search when direct lookup fails or unsupported
        search_params = {
            "part": "snippet",
            "q": f"@{normalized}",
            "type": "channel",
            "maxResults": 5,
        }
        try:
            search = await self._get("search", search_params, access_token)
        except YouTubeAPIError:
            return None
        for item in search.get("items", []):
            if not isinstance(item, dict):
                continue
            channel_info = item.get("id", {})
            if isinstance(channel_info, dict):
                candidate = channel_info.get("channelId")
                if candidate:
                    return candidate
        return None

    async def _hydrate_video_details(
        self,
        access_token: str,
        videos: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for i in range(0, len(videos), 50):
            batch = videos[i : i + 50]
            ids = ",".join(video["video_id"] for video in batch if video.get("video_id"))
            if not ids:
                enriched.extend(batch)
                continue
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": ids,
            }
            details = await self._get("videos", params, access_token)
            detail_map = {
                item.get("id"): item for item in details.get("items", []) if item.get("id")
            }
            for video in batch:
                payload = detail_map.get(video.get("video_id"))
                if payload:
                    enriched.append(self._merge_video_detail(video, payload))
                else:
                    enriched.append(video)
        return enriched

    async def _get(self, path: str, params: Dict[str, Any], access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.API_BASE}/{path}"
        async with self._client_lock:
            response = await self._client.get(url, params=params, headers=headers)
        data = response.json()
        if response.status_code >= 400 or "error" in data:
            raise YouTubeAPIError(str(data))
        return data

    @staticmethod
    def _map_playlist_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mapped: List[Dict[str, Any]] = []
        for item in items:
            snippet = item.get("snippet", {}) or {}
            content_details = item.get("contentDetails", {}) or {}
            video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue
            published_raw = snippet.get("publishedAt") or content_details.get("videoPublishedAt")
            mapped.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title") or video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_raw": published_raw,
                    "description": snippet.get("description") or "",
                    "thumbnails": snippet.get("thumbnails"),
                    "channel": {
                        "id": snippet.get("channelId"),
                        "name": snippet.get("channelTitle"),
                    },
                }
            )
        return mapped

    @staticmethod
    def _map_search_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mapped: List[Dict[str, Any]] = []
        for item in items:
            id_payload = item.get("id", {}) or {}
            video_id = id_payload.get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {}) or {}
            mapped.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title") or video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_raw": snippet.get("publishedAt"),
                    "description": snippet.get("description") or "",
                    "thumbnails": snippet.get("thumbnails"),
                    "channel": {
                        "id": snippet.get("channelId"),
                        "name": snippet.get("channelTitle"),
                    },
                }
            )
        return mapped

    @staticmethod
    def _merge_video_detail(
        base: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        snippet = payload.get("snippet", {}) or {}
        content_details = payload.get("contentDetails", {}) or {}
        statistics = payload.get("statistics", {}) or {}
        published_at = snippet.get("publishedAt") or base.get("published_raw")
        channel_section = base.get("channel") or {}
        if snippet:
            channel_section = {
                "id": snippet.get("channelId") or channel_section.get("id"),
                "name": snippet.get("channelTitle") or channel_section.get("name"),
                "url": f"https://www.youtube.com/channel/{snippet.get('channelId')}"
                if snippet.get("channelId")
                else channel_section.get("url"),
                "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url"),
            }
        duration_seconds = _parse_duration(content_details.get("duration"))
        published_dt = _iso_to_datetime(published_at)
        thumbnails = snippet.get("thumbnails") or base.get("thumbnails")
        best_thumb = None
        if isinstance(thumbnails, dict):
            best = max(thumbnails.values(), key=lambda meta: meta.get("width", 0)) if thumbnails else None
            if best and isinstance(best, dict):
                best_thumb = best.get("url")
        return {
            "video_id": base.get("video_id"),
            "title": snippet.get("title") or base.get("title"),
            "url": base.get("url"),
            "published": published_dt,
            "author": snippet.get("channelTitle"),
            "description": snippet.get("description") or base.get("description") or "",
            "duration": duration_seconds,
            "thumbnails": thumbnails,
            "thumbnail": best_thumb,
            "tags": snippet.get("tags"),
            "categories": None,
            "channel": channel_section,
            "stats": {
                "view_count": _safe_int(statistics.get("viewCount")),
                "like_count": _safe_int(statistics.get("likeCount")),
                "comment_count": _safe_int(statistics.get("commentCount")),
            },
        }


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
