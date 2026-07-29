#!/usr/bin/env python3
"""
Crawl a YouTube playlist via Data API v3 and upsert metadata into Supabase.

Designed to run inside the pmoves-yt container where the OAuth refresh token
is available at /app/config/cookies/yt-refresh-token.txt.

Usage:
    python3 yt_playlist_crawl.py --playlist PL... --namespace darkxside

Environment:
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET  — OAuth app credentials
    SUPABASE_SERVICE_KEY                     — Supabase service role key
    SUPABASE_URL or SUPA_REST_URL            — Supabase REST endpoint
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yt-crawl")

PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
TOKEN_URL = "https://oauth2.googleapis.com/token"

ISO8601_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def parse_iso8601_duration(duration: str) -> int | None:
    """Parse ISO 8601 duration (PT1H30M15S) to seconds."""
    if not duration:
        return None
    m = ISO8601_RE.match(duration)
    if not m:
        return None
    parts = {k: int(v) for k, v in m.groupdict(default="0").items()}
    return parts.get("hours", 0) * 3600 + parts.get("minutes", 0) * 60 + parts.get("seconds", 0)


def get_access_token(refresh_token: str, client_id: str, client_secret: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_playlist_items(
    access_token: str, playlist_id: str
) -> list[dict]:
    """Paginate through all playlist items, return raw API response items."""
    items: list[dict] = []
    page_token: str | None = None
    page_num = 0

    while True:
        params: dict = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            PLAYLIST_ITEMS_URL,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            log.error(f"playlistItems API error: {resp.status_code} {resp.text[:200]}")
            break

        data = resp.json()
        batch = data.get("items", [])
        items.extend(batch)
        page_num += 1
        total = data.get("pageInfo", {}).get("totalResults", "?")
        log.info(
            f"Page {page_num}: +{len(batch)} items "
            f"(total fetched: {len(items)}/{total})"
        )

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.3)  # gentle rate limit

    return items


def hydrate_video_details(
    access_token: str, video_ids: list[str]
) -> dict[str, dict]:
    """Fetch video details (duration, stats, tags) in batches of 50."""
    details: dict[str, dict] = {}
    batches = [video_ids[i : i + 50] for i in range(0, len(video_ids), 50)]

    for i, batch in enumerate(batches):
        resp = requests.get(
            VIDEOS_URL,
            params={
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(batch),
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            log.error(f"videos.list error batch {i}: {resp.status_code}")
            continue

        for item in resp.json().get("items", []):
            details[item["id"]] = item

        log.info(f"Hydrated batch {i + 1}/{len(batches)} ({len(batch)} videos)")
        time.sleep(0.3)

    return details


def build_video_record(
    playlist_item: dict,
    detail: dict | None,
    playlist_id: str,
    crawl_batch: str,
) -> dict | None:
    """Merge playlist item + video detail into a Supabase-ready record."""
    snippet = playlist_item.get("snippet", {})
    content = playlist_item.get("contentDetails", {})
    video_id = content.get("videoId") or snippet.get("resourceId", {}).get("videoId")
    if not video_id:
        return None

    position = snippet.get("position")
    published_raw = snippet.get("publishedAt") or (
        detail.get("snippet", {}).get("publishedAt") if detail else None
    )

    # Use detail (videos.list) as primary source for richer metadata
    d_snippet = detail.get("snippet", {}) if detail else {}
    d_content = detail.get("contentDetails", {}) if detail else {}
    d_stats = detail.get("statistics", {}) if detail else {}

    def safe_int(val) -> int | None:
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    thumbnails = d_snippet.get("thumbnails", {}) or snippet.get("thumbnails", {})

    return {
        "video_id": video_id,
        "playlist_id": playlist_id,
        "playlist_position": safe_int(position),
        "title": d_snippet.get("title") or snippet.get("title"),
        "description": d_snippet.get("description") or snippet.get("description"),
        "channel_id": d_snippet.get("channelId") or snippet.get("channelId")
        or snippet.get("videoOwnerChannelId"),
        "channel_title": d_snippet.get("channelTitle") or snippet.get("channelTitle")
        or snippet.get("videoOwnerChannelTitle"),
        "published_at": published_raw,
        "duration_seconds": parse_iso8601_duration(d_content.get("duration")),
        "view_count": safe_int(d_stats.get("viewCount")),
        "like_count": safe_int(d_stats.get("likeCount")),
        "comment_count": safe_int(d_stats.get("commentCount")),
        "tags": d_snippet.get("tags") or [],
        "category_id": d_snippet.get("categoryId"),
        "thumbnail_default": (thumbnails.get("default") or {}).get("url"),
        "thumbnail_medium": (thumbnails.get("medium") or {}).get("url"),
        "thumbnail_high": (thumbnails.get("high") or {}).get("url"),
        "crawl_batch": crawl_batch,
    }


def upsert_to_supabase(
    records: list[dict],
    rest_url: str,
    service_key: str,
) -> tuple[int, int]:
    """Upsert records into pmoves_core.youtube_videos via REST API."""
    success = 0
    errors = 0
    # Batch in groups of 25 to keep payloads reasonable
    for i in range(0, len(records), 25):
        batch = records[i : i + 25]
        base = rest_url.rstrip("/")
        if not base.endswith("/rest/v1"):
            base = f"{base}/rest/v1"
        resp = requests.post(
            f"{base}/youtube_videos",
            json=batch,
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Content-Profile": "pmoves_core",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            success += len(batch)
        else:
            log.error(
                f"Upsert batch {i//25} failed: {resp.status_code} {resp.text[:200]}"
            )
            errors += len(batch)
        time.sleep(0.1)

    return success, errors


def categorize_videos(records: list[dict]) -> dict:
    """Produce a summary categorization of crawled videos."""
    total = len(records)
    if total == 0:
        return {"total": 0}

    durations = [r["duration_seconds"] for r in records if r["duration_seconds"]]
    views = [r["view_count"] for r in records if r["view_count"]]

    # Duration buckets
    short = sum(1 for d in durations if d and d < 300)  # < 5 min
    medium = sum(1 for d in durations if d and 300 <= d < 1200)  # 5-20 min
    long = sum(1 for d in durations if d and 1200 <= d < 3600)  # 20-60 min
    very_long = sum(1 for d in durations if d and d >= 3600)  # 1hr+

    # Keyword clusters
    keywords = {
        "AI/ML": ["ai", "artificial intelligence", "llm", "machine learning", "gpt", "neural", "transformer", "agent", "rag"],
        "energy": ["solar", "battery", "energy", "grid", "power", "electric", "ev", "fusion"],
        "crypto/web3": ["crypto", "blockchain", "bitcoin", "ethereum", "token", "dao", "defi", "nft"],
        "community": ["community", "cooperative", "co-op", "mesh", "neighborhood", "local"],
        "dev/tools": ["python", "javascript", "docker", "kubernetes", "git", "code", "programming", "api"],
        "media/creative": ["music", "video", "art", "creative", "design", "animation", "render"],
        "business": ["startup", "business", "market", "invest", "economy", "finance", "revenue"],
    }
    keyword_counts: dict[str, int] = {k: 0 for k in keywords}
    for r in records:
        text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
        for cluster, words in keywords.items():
            if any(w in text for w in words):
                keyword_counts[cluster] += 1

    # Date range
    dates = sorted(
        [r["published_at"] for r in records if r["published_at"]],
    )

    avg_views = sum(views) // len(views) if views else 0

    return {
        "total": total,
        "with_duration": len(durations),
        "duration_buckets": {
            "short (<5min)": short,
            "medium (5-20min)": medium,
            "long (20-60min)": long,
            "very_long (1hr+)": very_long,
        },
        "avg_views": avg_views,
        "top_views": sorted(views, reverse=True)[:10],
        "keyword_clusters": dict(
            sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "date_range": {
            "earliest": dates[0][:10] if dates else None,
            "latest": dates[-1][:10] if dates else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Crawl YouTube playlist via Data API")
    parser.add_argument(
        "--playlist",
        default="PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8",
        help="YouTube playlist ID",
    )
    parser.add_argument(
        "--namespace",
        default="darkxside",
        help="Namespace label for this crawl batch",
    )
    parser.add_argument(
        "--token-path",
        default="/app/config/cookies/yt-refresh-token.txt",
        help="Path to OAuth refresh token file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch metadata but don't write to Supabase",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only output the categorization summary (skip Supabase write)",
    )
    args = parser.parse_args()

    # --- Get credentials ---
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        log.error("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        sys.exit(1)

    token_path = Path(args.token_path)
    if not token_path.exists():
        log.error(f"Refresh token file not found: {token_path}")
        sys.exit(1)

    refresh_token = token_path.read_text().strip()

    service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY", ""
    )
    rest_url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPA_REST_URL", "")

    # --- Exchange refresh token ---
    log.info("Exchanging refresh token for access token...")
    access_token = get_access_token(refresh_token, client_id, client_secret)
    log.info("Access token acquired")

    # --- Paginate playlist items ---
    log.info(f"Fetching playlist items for {args.playlist}...")
    raw_items = fetch_playlist_items(access_token, args.playlist)
    log.info(f"Total playlist items fetched: {len(raw_items)}")

    # Filter out private/deleted videos
    valid_items = [
        item
        for item in raw_items
        if item.get("snippet", {}).get("title") != "Private video"
        and item.get("snippet", {}).get("title") != "Deleted video"
    ]
    log.info(
        f"Valid items (excluding private/deleted): {len(valid_items)} "
        f"({len(raw_items) - len(valid_items)} excluded)"
    )

    # --- Hydrate video details ---
    video_ids = [
        item.get("contentDetails", {}).get("videoId")
        or item.get("snippet", {}).get("resourceId", {}).get("videoId")
        for item in valid_items
    ]
    video_ids = [vid for vid in video_ids if vid]
    log.info(f"Hydrating details for {len(video_ids)} videos...")
    details = hydrate_video_details(access_token, video_ids)
    log.info(f"Got details for {len(details)}/{len(video_ids)} videos")

    # --- Build records ---
    crawl_batch = f"{args.namespace}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    records: list[dict] = []
    for item in valid_items:
        vid = (
            item.get("contentDetails", {}).get("videoId")
            or item.get("snippet", {}).get("resourceId", {}).get("videoId")
        )
        if not vid:
            continue
        detail = details.get(vid)
        record = build_video_record(item, detail, args.playlist, crawl_batch)
        if record:
            records.append(record)

    log.info(f"Built {len(records)} video records")

    # --- Summary ---
    summary = categorize_videos(records)
    log.info("=== CRAWL SUMMARY ===")
    log.info(json.dumps(summary, indent=2, default=str))

    # --- Write to Supabase ---
    if args.dry_run or args.summary_only:
        log.info("Skipping Supabase write (dry-run/summary-only)")
    elif not service_key or not rest_url:
        log.warning("Missing Supabase credentials — skipping write")
    else:
        log.info(f"Upserting {len(records)} records to Supabase...")
        success, errors = upsert_to_supabase(records, rest_url, service_key)
        log.info(f"Upsert complete: {success} success, {errors} errors")

    # Output summary as JSON for downstream processing
    print(json.dumps({"summary": summary, "crawl_batch": crawl_batch}, default=str))


if __name__ == "__main__":
    main()
