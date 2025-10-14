#!/usr/bin/env python3
"""
Validate Jellyfin credentials for the local PMOVES deployment.

The script verifies that:
  * The Jellyfin API is reachable at JELLYFIN_URL.
  * The supplied JELLYFIN_API_KEY has access to the API.
  * (Optional) The configured JELLYFIN_USER_ID can enumerate items.
  * (Optional) The server name matches the expected PMOVES branding.

Environment variables:
  JELLYFIN_URL                  Base URL, e.g. http://localhost:8096
  JELLYFIN_API_KEY              API token with administrator access
  JELLYFIN_USER_ID              Optional user to validate enumeration
  JELLYFIN_EXPECTED_SERVER_NAME Optional branding name (default: PMOVES Jellyfin)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class JellyfinCheckError(RuntimeError):
    """Raised when any credential validation step fails."""


@dataclass
class JellyfinConfig:
    url: str
    api_key: str
    user_id: Optional[str]
    expected_name: Optional[str]

    @classmethod
    def from_env(cls) -> "JellyfinConfig":
        url = os.environ.get("JELLYFIN_URL")
        api_key = os.environ.get("JELLYFIN_API_KEY")
        user_id = os.environ.get("JELLYFIN_USER_ID")
        expected = os.environ.get("JELLYFIN_EXPECTED_SERVER_NAME", "PMOVES Jellyfin")

        if not url:
            raise JellyfinCheckError("JELLYFIN_URL is not set")
        if not api_key:
            raise JellyfinCheckError("JELLYFIN_API_KEY is not set")

        return cls(url=url.rstrip("/"), api_key=api_key, user_id=user_id, expected_name=expected)


def request_json(config: JellyfinConfig, path: str) -> Dict[str, Any]:
    """Perform an authenticated GET request and return the parsed JSON body."""

    url = urllib.parse.urljoin(f"{config.url}/", path.lstrip("/"))
    req = urllib.request.Request(url)
    req.add_header("X-Emby-Token", config.api_key)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise JellyfinCheckError(f"{path} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise JellyfinCheckError(f"Unable to reach {url}: {exc}") from exc

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise JellyfinCheckError(f"Invalid JSON response from {path}: {exc}") from exc


def validate_server_info(config: JellyfinConfig) -> Dict[str, Any]:
    info = request_json(config, "/System/Info")
    name = info.get("ServerName")
    if config.expected_name and name and config.expected_name not in name:
        raise JellyfinCheckError(
            f"ServerName mismatch: expected to include '{config.expected_name}', got '{name}'"
        )
    return info


def validate_user(config: JellyfinConfig) -> Optional[Dict[str, Any]]:
    if not config.user_id:
        return None

    user = request_json(config, f"/Users/{config.user_id}")
    if user.get("Id") != config.user_id:
        raise JellyfinCheckError(f"User lookup succeeded but returned unexpected Id: {user.get('Id')}")

    # Confirm we can see at least one library/folder for this user.
    items = request_json(config, f"/Users/{config.user_id}/Items?IncludeItemTypes=Folder")
    total = items.get("TotalRecordCount", 0)
    if total == 0:
        print(
            "⚠️  Warning: user enumeration succeeded but no libraries were returned. "
            "Check JELLYFIN_LIBRARY_ID or ensure the user has access.",
            file=sys.stderr,
        )
    return user


def main() -> int:
    try:
        config = JellyfinConfig.from_env()
        info = validate_server_info(config)
        print(f"✅ Jellyfin reachable at {config.url} (version {info.get('Version', 'unknown')})")
        print(f"   Server name: {info.get('ServerName', 'unknown')}")
        if config.user_id:
            user = validate_user(config)
            if user:
                print(f"✅ User {config.user_id} ({user.get('Name', 'unknown')}) can enumerate libraries")
        else:
            print("ℹ️  JELLYFIN_USER_ID not set; skipped user enumeration check.")
        print("All Jellyfin credential checks passed.")
        return 0
    except JellyfinCheckError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
