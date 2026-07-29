#!/usr/bin/env python3
"""
Batch download YouTube videos and upload to MinIO.

Runs inside the pmoves-yt container where yt-dlp + cookies + MinIO are all
reachable. Reads priority queue from Supabase, downloads, uploads, updates
downloaded=true.

Usage:
    python3 yt_batch_download.py --limit 10 --tier 1
    python3 yt_batch_download.py --channel "Fahd Mirza" --limit 5
    python3 yt_batch_download.py --video-id ucRulNQsuYQ
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests
import yt_dlp

try:
    from minio import Minio
except ImportError:
    Minio = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("yt-batch")

TOKEN_URL = "https://oauth2.googleapis.com/token"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

YT_TEMP = Path("/tmp/yt-batch")
YT_TEMP.mkdir(parents=True, exist_ok=True)


def get_minio_client():
    if Minio is None:
        return None
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("MINIO_USER", "")
    secret_key = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("MINIO_PASSWORD", "")
    secure = os.environ.get("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def ensure_bucket(client, bucket: str):
    if client is None:
        return
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info(f"Created bucket: {bucket}")


def get_supabase_records(
    rest_url: str, service_key: str, filters: dict, limit: int = 10
) -> list[dict]:
    """Fetch undownloaded videos from Supabase with optional filters."""
    params = {
        "select": "video_id,title,channel_title,duration_seconds,view_count",
        "downloaded": "eq.false",
        "limit": str(limit),
        "order": "view_count.desc",
    }
    for k, v in filters.items():
        params[k] = v

    resp = requests.get(
        f"{rest_url}/youtube_videos",
        params=params,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept-Profile": "pmoves_core",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        log.error(f"Supabase query failed: {resp.status_code} {resp.text[:200]}")
        return []
    return resp.json()


def update_downloaded(rest_url: str, service_key: str, video_id: str, s3_path: str):
    resp = requests.patch(
        f"{rest_url}/youtube_videos",
        params={"video_id": f"eq.{video_id}"},
        json={"downloaded": True, "updated_at": "now()"},
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Content-Profile": "pmoves_core",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    if resp.status_code not in (200, 204):
        log.warning(f"Failed to update {video_id}: {resp.status_code}")


def download_and_upload(
    video: dict,
    minio_client,
    bucket: str,
    namespace: str,
    cookiefile: str | None = None,
) -> bool:
    vid = video["video_id"]
    title = video.get("title", vid)[:60]
    url = f"https://www.youtube.com/watch?v={vid}"

    log.info(f"Downloading: {title} ({vid})")

    ydl_opts: dict = {
        "outtmpl": str(YT_TEMP / vid / "%(id)s.%(ext)s"),
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "merge_output_format": "mp4",
        "writethumbnail": True,
        "quiet": True,
        "noprogress": True,
        "postprocessors": [
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
    }
    if cookiefile and Path(cookiefile).exists():
        ydl_opts["cookiefile"] = cookiefile

    vid_dir = YT_TEMP / vid
    vid_dir.mkdir(parents=True, exist_ok=True)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                log.error(f"  yt-dlp returned no info for {vid}")
                return False
    except Exception as e:
        log.error(f"  Download failed: {type(e).__name__}: {str(e)[:150]}")
        return False

    uploaded_files = []
    for f in vid_dir.iterdir():
        if f.is_file() and f.suffix in (".mp4", ".webm", ".mkv"):
            s3_path = f"{namespace}/{vid}/raw{f.suffix}"
            if minio_client is not None:
                try:
                    minio_client.fput_object(bucket, s3_path, str(f))
                    uploaded_files.append(s3_path)
                    log.info(f"  Uploaded: s3://{bucket}/{s3_path} ({f.stat().st_size // 1024}KB)")
                except Exception as e:
                    log.error(f"  Upload failed: {e}")
                    return False
            else:
                # Fallback: just keep the local file
                uploaded_files.append(str(f))
                log.info(f"  Downloaded (no MinIO): {f} ({f.stat().st_size // 1024}KB)")

    if not uploaded_files:
        log.error(f"  No video file found in {vid_dir}")
        return False

    # Cleanup temp files
    for f in vid_dir.iterdir():
        try:
            f.unlink()
        except OSError:
            pass
    vid_dir.rmdir()

    return True


def main():
    parser = argparse.ArgumentParser(description="Batch download YouTube videos")
    parser.add_argument("--limit", type=int, default=5, help="Max videos to download")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Priority tier filter")
    parser.add_argument("--channel", help="Filter by channel name")
    parser.add_argument("--video-id", help="Download specific video ID")
    parser.add_argument("--min-duration", type=int, help="Min duration in seconds")
    parser.add_argument("--max-duration", type=int, help="Max duration in seconds")
    parser.add_argument("--namespace", default="darkxside")
    parser.add_argument("--bucket", default=os.environ.get("YT_BUCKET", "assets"))
    parser.add_argument("--dry-run", action="store_true", help="List targets without downloading")
    args = parser.parse_args()

    # --- Credentials ---
    service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    rest_url = os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_URL", "")
    # Normalize: strip trailing slash, ensure it ends with /rest/v1
    rest_url = rest_url.rstrip("/")
    if not rest_url.endswith("/rest/v1"):
        rest_url = f"{rest_url}/rest/v1"

    cookiefile = os.environ.get("YT_COOKIES")

    if args.video_id:
        videos = [{"video_id": args.video_id, "title": "manual", "channel_title": "manual"}]
    elif not service_key or not rest_url:
        log.error("Missing Supabase credentials")
        sys.exit(1)
    else:
        filters = {}
        if args.channel:
            filters["channel_title"] = f"eq.{args.channel}"
        if args.min_duration:
            filters["duration_seconds"] = f"gte.{args.min_duration}"
        videos = get_supabase_records(rest_url, service_key, filters, args.limit)

    if not videos:
        log.info("No matching undownloaded videos found")
        return

    log.info(f"Found {len(videos)} videos to process:")
    for v in videos:
        dur = v.get("duration_seconds", 0) or 0
        log.info(f"  {v['video_id']}: {v.get('title','?')[:50]} ({dur//60}m, {v.get('view_count',0)} views)")

    if args.dry_run:
        log.info("Dry run — not downloading")
        return

    # --- Setup MinIO ---
    minio_client = get_minio_client()
    ensure_bucket(minio_client, args.bucket)

    # --- Download loop ---
    success = 0
    failed = 0
    for video in videos:
        ok = download_and_upload(video, minio_client, args.bucket, args.namespace, cookiefile)
        if ok:
            success += 1
            if service_key and rest_url:
                update_downloaded(rest_url, service_key, video["video_id"], "")
        else:
            failed += 1
        time.sleep(2)  # gentle rate limit

    log.info(f"Done: {success} downloaded, {failed} failed")


if __name__ == "__main__":
    main()
