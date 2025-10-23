"""CLI helper to append sources to channel monitor config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = ROOT / "pmoves" / "services" / "channel-monitor"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

PMOVES_ROOT = ROOT / "pmoves"
if str(PMOVES_ROOT) not in sys.path:
    sys.path.insert(0, str(PMOVES_ROOT))

from channel_monitor.config import config_path_from_env, ensure_config, save_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a media source for the channel monitor",
    )
    parser.add_argument("--platform", default="youtube", help="Extractor platform (youtube, soundcloud, twitch, etc.)")
    parser.add_argument("--source-type", default="channel", help="Source type (channel, playlist, likes, user)")
    parser.add_argument("--name", required=True, help="Friendly name for the source")
    parser.add_argument("--url", required=True, help="Primary URL (channel handle, playlist link, etc.)")
    parser.add_argument("--namespace", default="pmoves", help="Namespace used during ingestion")
    parser.add_argument("--tags", default="", help="Comma separated tags")
    parser.add_argument("--format", default="", help="Override yt-dlp format string (e.g. bestaudio/best)")
    parser.add_argument("--media-type", default="video", help="Media type hint (video, audio, podcast)")
    parser.add_argument("--cookies", default="", help="Path to cookies file for authenticated sources")
    parser.add_argument("--yt-options", default="", help="Additional yt_options as JSON (merged with defaults)")
    parser.add_argument("--config", help="Override config path (defaults to CHANNEL_MONITOR_CONFIG_PATH)")
    return parser.parse_args()


def load_options(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - simple CLI guard
        raise SystemExit(f"Invalid JSON for --yt-options: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("--yt-options must be a JSON object")
    return data


def main() -> None:
    args = parse_args()
    config_path = Path(args.config) if args.config else config_path_from_env()
    config = ensure_config(config_path)

    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    yt_options = load_options(args.yt_options)

    entry = {
        "channel_name": args.name,
        "platform": args.platform.lower(),
        "source_type": args.source_type.lower(),
        "source_url": args.url,
        "enabled": True,
        "auto_process": True,
        "namespace": args.namespace,
        "tags": tags,
        "media_type": args.media_type,
        "format": args.format or None,
        "cookies_path": args.cookies or None,
        "yt_options": yt_options,
    }

    config.setdefault("channels", []).append(entry)
    save_config(config_path, config)
    print(f"Registered source '{args.name}' ({args.platform}) in {config_path}")


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
