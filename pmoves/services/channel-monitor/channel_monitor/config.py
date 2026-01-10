from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CHANNEL_METADATA_FIELDS = [
    "id",
    "name",
    "url",
    "namespace",
    "tags",
    "priority",
    "subscriber_count",
    "thumbnail",
    "description",
]

DEFAULT_VIDEO_METADATA_FIELDS = [
    "duration",
    "view_count",
    "like_count",
    "thumbnail",
    "published_at",
    "categories",
    "tags",
]


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
            "channel_metadata_fields": None,
            "video_metadata_fields": None,
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
        "channel_metadata_fields": DEFAULT_CHANNEL_METADATA_FIELDS,
        "video_metadata_fields": DEFAULT_VIDEO_METADATA_FIELDS,
        "channel_breakdown_limit": 25,
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
        if merged_channel.get("channel_metadata_fields") is None:
            merged_channel["channel_metadata_fields"] = None
        if merged_channel.get("video_metadata_fields") is None:
            merged_channel["video_metadata_fields"] = None
        channels.append(merged_channel)
    merged["channels"] = channels
    global_settings = DEFAULT_CONFIG["global_settings"].copy()
    global_settings.update(merged.get("global_settings", {}))
    if not isinstance(global_settings.get("channel_metadata_fields"), list):
        global_settings["channel_metadata_fields"] = DEFAULT_CHANNEL_METADATA_FIELDS
    if not isinstance(global_settings.get("video_metadata_fields"), list):
        global_settings["video_metadata_fields"] = DEFAULT_VIDEO_METADATA_FIELDS
    if not isinstance(global_settings.get("channel_breakdown_limit"), int):
        global_settings["channel_breakdown_limit"] = 25
    merged["global_settings"] = global_settings
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
