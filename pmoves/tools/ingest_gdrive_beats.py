#!/usr/bin/env python3
"""
ingest_gdrive_beats.py — DARKXSIDE Google Drive Beats Folder Ingest

Syncs a Google Drive beats folder to a local staging directory via rclone,
then batch-publishes each audio file as a `media.ingest.request.v1` NATS event
so the PMOVES channel-monitor / hi-rag pipeline can process them into
Holographic CHIT Geometry Blocks.

Usage:
    python pmoves/tools/ingest_gdrive_beats.py \\
        --remote "gdrive:Beats" \\
        --local "/data/beats/gdrive" \\
        --nats-url "nats://nats:pmoves@nats:4222"

Prerequisites:
    - rclone configured with a 'gdrive' remote (rclone config)
    - NATS running (make -C pmoves up)
    - pip install nats-py asyncio

Env overrides:
    NATS_URL            — default nats://nats:pmoves@nats:4222
    BEATS_REMOTE        — default gdrive:Beats
    BEATS_LOCAL_DIR     — default /data/beats/gdrive
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".aiff", ".ogg", ".m4a", ".aac"}
NATS_SUBJECT = "media.ingest.request.v1"


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest Google Drive beats folder into PMOVES.")
    parser.add_argument(
        "--remote",
        default=os.environ.get("BEATS_REMOTE", "gdrive:Beats"),
        help="rclone remote path (e.g. gdrive:Beats)",
    )
    parser.add_argument(
        "--local",
        default=os.environ.get("BEATS_LOCAL_DIR", "/data/beats/gdrive"),
        help="Local staging directory for synced beats",
    )
    parser.add_argument(
        "--nats-url",
        default=os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222"),
        help="NATS server URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sync files but do not publish NATS events",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip rclone sync step (use existing local files)",
    )
    return parser.parse_args()


def rclone_sync(remote: str, local: str) -> int:
    """Sync remote beats folder to local staging directory via rclone."""
    local_path = Path(local)
    local_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "rclone", "copy",       # copy, not sync — don't delete local extras
        remote, str(local_path),
        "--progress",
        "--transfers", "4",
        "--include", "*.wav",
        "--include", "*.mp3",
        "--include", "*.flac",
        "--include", "*.aiff",
        "--include", "*.ogg",
        "--include", "*.m4a",
        "--include", "*.aac",
    ]

    print(f"[rclone] Copying {remote} → {local}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[warn] rclone exited with code {result.returncode} — some files may have been skipped.")
    return result.returncode


def collect_audio_files(local: str) -> list[Path]:
    """Walk local staging dir and collect all audio files."""
    base = Path(local)
    files = [p for p in base.rglob("*") if p.suffix.lower() in AUDIO_EXTENSIONS and p.is_file()]
    files.sort()
    print(f"[ingest] Found {len(files)} audio file(s) in {local}")
    return files


async def publish_ingest_events(files: list[Path], nats_url: str, dry_run: bool):
    """Publish a media.ingest.request.v1 event per audio file over NATS."""
    try:
        import nats
    except ImportError:
        print("[error] nats-py not installed. Run: pip install nats-py", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("[dry-run] Would publish the following NATS events:")
        for f in files:
            print(f"  → {NATS_SUBJECT}: {f.name}")
        return

    nc = await nats.connect(nats_url)
    published = 0
    skipped = 0

    for f in files:
        payload = {
            "source": "gdrive_beats_ingest",
            "namespace": "pmoves.darkxside.beats",
            "file_path": str(f),
            "file_name": f.name,
            "media_type": "audio",
            "tags": ["darkxside", "beats", "holographic", "gdrive"],
            "platform": "local",
            "auto_process": True,
        }
        try:
            await nc.publish(NATS_SUBJECT, json.dumps(payload).encode())
            print(f"[published] {f.name}")
            published += 1
        except Exception as e:
            print(f"[error] Failed to publish {f.name}: {e}")
            skipped += 1

    await nc.drain()
    print(f"\n[done] Published {published} events, skipped {skipped}.")


def main():
    args = parse_args()

    if not args.no_sync:
        rclone_sync(args.remote, args.local)

    files = collect_audio_files(args.local)
    if not files:
        print("[warn] No audio files found. Check your rclone remote path and filters.")
        sys.exit(0)

    asyncio.run(publish_ingest_events(files, args.nats_url, args.dry_run))


if __name__ == "__main__":
    main()
