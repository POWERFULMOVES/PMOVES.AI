#!/usr/bin/env python3
"""Seed local media assets for the Jellyfin AI stack.

The script prepares a predictable directory layout under
``pmoves/jellyfin-ai/media`` and drops a couple of sample assets so the
pre-provisioned Jellyfin libraries pick them up immediately after a
refresh.  It intentionally keeps the assets lightweight so the command can
run during CI smoke or on fresh developer machines without large
downloads.

What it does:

* ensures music/podcasts/videos/youtube folders exist (mirrors volume mount)
* generates a short 440Hz sine-wave WAV file for the music library
* (best effort) downloads the Creative Commons `yt-dlp` test video so the
  YouTube watch folder has playable content
* triggers a Jellyfin library refresh when `JELLYFIN_URL` + `JELLYFIN_API_KEY`
  are present in the environment

Usage::

    python scripts/seed_jellyfin_media.py

Run it once after `make up-jellyfin-ai`; the sample files will live under
`pmoves/jellyfin-ai/media` so you can add or replace content locally later.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Optional

BASE_MEDIA_DIR = Path(__file__).resolve().parent.parent / "pmoves" / "jellyfin-ai" / "media"
TONE_FILENAME = "pmoves-tone.wav"
TONE_DURATION_SECONDS = 8
TONE_FREQUENCY_HZ = 440
SAMPLE_VIDEO_URL = "https://www.youtube.com/watch?v=BaW_jenozKc"  # yt-dlp CC test clip
SAMPLE_VIDEO_FILENAME = "yt-dlp-test.mp4"


def ensure_directories() -> None:
    """Create the watch folders Jellyfin expects."""

    for subdir in ("music", "videos", "podcasts", "youtube"):
        directory = BASE_MEDIA_DIR / subdir
        directory.mkdir(parents=True, exist_ok=True)


def write_tone_wav(path: Path, *, frequency: float = TONE_FREQUENCY_HZ, duration: int = TONE_DURATION_SECONDS) -> None:
    """Generate a simple mono sine-wave WAV so the music library has content."""

    if path.exists():
        return

    sample_rate = 44100
    amplitude = 32767
    total_frames = int(duration * sample_rate)

    frames = bytearray()
    for i in range(total_frames):
        value = int(amplitude * math.sin(2 * math.pi * frequency * (i / sample_rate)))
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit audio
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def download_sample_video(path: Path, *, url: str = SAMPLE_VIDEO_URL) -> None:
    """Download a small Creative Commons video using yt-dlp (best effort)."""

    if path.exists():
        return

    try:
        import yt_dlp  # type: ignore
    except ImportError:
        print("yt-dlp not available; skipping sample video download", file=sys.stderr)
        return

    ydl_opts = {
        "outtmpl": str(path),
        "format": "mp4/best",
        "quiet": True,
        "noprogress": True,
        "restrictfilenames": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print(f"Downloading sample video from {url} ...")
            ydl.download([url])
        except Exception as exc:  # pragma: no cover - network dependent
            print(f"Failed to download sample video: {exc}", file=sys.stderr)
            if path.exists():
                path.unlink(missing_ok=True)


def trigger_library_refresh() -> None:
    """Ask Jellyfin to rescan libraries if credentials are configured."""

    base_url = os.environ.get("JELLYFIN_URL")
    api_key = os.environ.get("JELLYFIN_API_KEY")
    if not base_url or not api_key:
        return

    refresh_url = (
        f"{base_url.rstrip('/')}/Library/Refresh"
        "?metadataRefreshMode=Full&imageRefreshMode=None&replaceAllMetadata=false&replaceAllImages=false"
    )
    request = urllib.request.Request(refresh_url, method="POST")
    request.add_header("X-Emby-Token", api_key)

    try:
        with urllib.request.urlopen(request, timeout=10):
            print("Triggered Jellyfin library refresh")
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        print(f"Warning: unable to trigger Jellyfin library refresh: {exc}", file=sys.stderr)


def seed_media(skip_refresh: bool = False) -> None:
    ensure_directories()

    tone_path = BASE_MEDIA_DIR / "music" / TONE_FILENAME
    write_tone_wav(tone_path)
    print(f"Created sample tone: {tone_path.relative_to(BASE_MEDIA_DIR.parent)}")

    video_path = BASE_MEDIA_DIR / "youtube" / SAMPLE_VIDEO_FILENAME
    download_sample_video(video_path)
    if video_path.exists():
        print(f"Sample video ready: {video_path.relative_to(BASE_MEDIA_DIR.parent)}")

    if not skip_refresh:
        trigger_library_refresh()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed sample media into the Jellyfin watch folders")
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Do not call the Jellyfin refresh API even if credentials are available.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    seed_media(skip_refresh=args.skip_refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
