from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CONFIG: Dict[str, Any] = {
    "channels": [
        {
            "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
            "channel_name": "Google Developers",
            "platform": "youtube",
            "source_type": "channel",
            "source_url": "https://www.youtube.com/@GoogleDevelopers",
            "enabled": False,
            "check_interval_minutes": 60,
            "auto_process": True,
            "filters": {
                "min_duration_seconds": 60,
                "max_age_days": 30,
                "exclude_keywords": ["#shorts"],
                "title_keywords": [],
            },
            "priority": 1,
            "namespace": "pmoves",
            "tags": ["tech"],
            "format": None,
            "media_type": "video",
            "cookies_path": None,
            "yt_options": {
                "download_archive": "/data/yt-dlp/google-developers.archive",
                "subtitle_langs": ["en"],
                "write_info_json": True,
            },
        }
    ],
    "global_settings": {
        "max_videos_per_check": 10,
        "use_rss_feed": True,
        "use_youtube_api": False,
        "youtube_api_key": "",
        "check_on_startup": True,
        "notification_webhook": "",
        "batch_processing": True,
        "batch_size": 5,
        "yt_options": {
            "write_info_json": True,
        },
    },
    "monitoring_schedule": {
        "enabled": True,
        "interval_minutes": 30,
    },
}


def ensure_config(path: Path) -> Dict[str, Any]:
    """
    Ensure the configuration file exists. If missing, write defaults.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    with path.open("r") as handle:
        loaded = json.load(handle)
    merged = DEFAULT_CONFIG.copy()
    merged.update(loaded)
    channels: List[Dict[str, Any]] = []
    for channel in merged.get("channels", []):
        merged_channel = DEFAULT_CONFIG["channels"][0].copy()
        merged_channel.update(channel)
        channels.append(merged_channel)
    merged["channels"] = channels
    return merged


def save_config(path: Path, config: Dict[str, Any]) -> None:
    """
    Persist configuration to disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        json.dump(config, handle, indent=2)


def config_path_from_env() -> Path:
    """
    Resolve configuration path from environment (default: config/channel_monitor.json).
    """
    env_path = os.getenv("CHANNEL_MONITOR_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path("/app/config/channel_monitor.json")
