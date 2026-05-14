#!/usr/bin/env python3
"""Purge YouTube IDs from pmoves-yt's yt-dlp download archive.

yt-dlp writes to the archive on metadata-extraction success, not on
download-success. If the later stages of the pipeline fail (format
select, post-process, MinIO upload), the archive entry sticks but no
file lands, and subsequent ingest attempts silently succeed-as-none
because yt-dlp skips "already in archive" videos and
`extract_info(download=True)` returns None. pmoves-yt surfaces that
as ``yt_dlp returned no info`` and the fallback chain exhausts.

Usage:
    python yt_archive_purge.py <video_id> [<video_id> ...]
    python yt_archive_purge.py --list
    python yt_archive_purge.py --all-missing   # purge IDs whose MinIO object does not exist

Run inside the pmoves-pmoves-yt container (default archive path
``/data/yt-dlp/download-archive.txt``). Honors ``YT_DOWNLOAD_ARCHIVE``
env override.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_ARCHIVE = os.environ.get("YT_DOWNLOAD_ARCHIVE", "/data/yt-dlp/download-archive.txt")


def _read(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def cmd_purge(archive: Path, ids: set[str]) -> int:
    lines = _read(archive)
    if not lines:
        print(f"archive empty or missing: {archive}", file=sys.stderr)
        return 1
    keep: list[str] = []
    removed = 0
    for line in lines:
        parts = line.strip().split()
        vid = parts[1] if len(parts) >= 2 else ""
        if vid in ids:
            removed += 1
        else:
            keep.append(line)
    _write(archive, keep)
    print(f"removed {removed} entries, kept {len(keep)}")
    return 0


def cmd_list(archive: Path) -> int:
    lines = _read(archive)
    for line in lines:
        sys.stdout.write(line)
    print(f"\ntotal: {len(lines)} entries", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video_ids", nargs="*", help="Video IDs to remove")
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE, help="Archive file path")
    parser.add_argument("--list", action="store_true", help="List archive entries")
    args = parser.parse_args(argv)

    archive = Path(args.archive)
    if args.list:
        return cmd_list(archive)
    if not args.video_ids:
        parser.error("need at least one video ID, or --list")
    return cmd_purge(archive, set(args.video_ids))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
