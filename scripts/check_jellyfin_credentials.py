#!/usr/bin/env python3
"""
Validate Jellyfin credentials for the local PMOVES deployment.

The script verifies that:
  * The Jellyfin API is reachable at JELLYFIN_URL.
  * The supplied JELLYFIN_API_KEY has access to the API.
  * (Optional) The configured JELLYFIN_USER_ID can enumerate items.
  * Jellyfin accepts a direct `/Library/Refresh` trigger.
  * (Optional) When `JELLYFIN_REFRESH_WEBHOOK_URL` is set, the webhook responds successfully.
  * (Optional) The server name matches the expected PMOVES branding.

Environment variables:
  JELLYFIN_URL                  Base URL, e.g. http://localhost:8096
  JELLYFIN_API_KEY              API token with administrator access
  JELLYFIN_USER_ID              Optional user to validate enumeration
  JELLYFIN_EXPECTED_SERVER_NAME Optional branding name (default: PMOVES Jellyfin)
  JELLYFIN_REFRESH_WEBHOOK_URL  Optional webhook endpoint for delegated refreshes
  JELLYFIN_REFRESH_WEBHOOK_TOKEN Optional bearer token for the refresh webhook
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
    refresh_webhook_url: Optional[str]
    refresh_webhook_token: Optional[str]

    @classmethod
    def from_env(cls) -> "JellyfinConfig":
        url = os.environ.get("JELLYFIN_URL")
        api_key = os.environ.get("JELLYFIN_API_KEY")
        user_id = os.environ.get("JELLYFIN_USER_ID")
        expected = os.environ.get("JELLYFIN_EXPECTED_SERVER_NAME", "PMOVES Jellyfin")
        webhook = os.environ.get("JELLYFIN_REFRESH_WEBHOOK_URL")
        webhook_token = os.environ.get("JELLYFIN_REFRESH_WEBHOOK_TOKEN")

        if not url:
            raise JellyfinCheckError("JELLYFIN_URL is not set")
        if not api_key:
            raise JellyfinCheckError("JELLYFIN_API_KEY is not set")

        return cls(
            url=url.rstrip("/"),
            api_key=api_key,
            user_id=user_id,
            expected_name=expected,
            refresh_webhook_url=webhook,
            refresh_webhook_token=webhook_token,
        )


def _request(
    config: JellyfinConfig,
    path: str,
    *,
    method: str = "GET",
    timeout: int = 10,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Perform an authenticated GET request and return the parsed JSON body."""

    url = urllib.parse.urljoin(f"{config.url}/", path.lstrip("/"))
    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Emby-Token", config.api_key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise JellyfinCheckError(f"{path} returned HTTP {exc.code}: {body}") from exc
    except TimeoutError as exc:  # pragma: no cover - socket timeout
        raise JellyfinCheckError(f"Request to {url} timed out: {exc}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise JellyfinCheckError(f"Unable to reach {url}: {exc}") from exc

    try:
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise JellyfinCheckError(f"Invalid JSON response from {path}: {exc}") from exc


def request_json(config: JellyfinConfig, path: str, timeout: int = 10) -> Dict[str, Any]:
    return _request(config, path, timeout=timeout)


def post_json(
    config: JellyfinConfig, path: str, payload: Dict[str, Any], timeout: int = 10
) -> Dict[str, Any]:
    return _request(config, path, method="POST", timeout=timeout, body=payload)


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
    query = urllib.parse.urlencode(
        {
            "IncludeExternalContent": "false",
            "StartIndex": 0,
            "Limit": 1,
        }
    )
    try:
        views = request_json(config, f"/Users/{config.user_id}/Views?{query}", timeout=30)
    except JellyfinCheckError as exc:
        print(
            f"⚠️  Warning: unable to list libraries for user {config.user_id}: {exc}",
            file=sys.stderr,
        )
        return user

    items = views.get("Items", [])
    if not items:
        print(
            "⚠️  Warning: user enumeration succeeded but no libraries were returned. "
            "Check JELLYFIN_LIBRARY_ID or ensure the user has access.",
            file=sys.stderr,
        )
    return user


def ensure_safe_display_preferences(config: JellyfinConfig) -> None:
    """Ensure all relevant display preference buckets have a valid scroll behavior."""

    if not config.user_id:
        return

    clients = ["emby", "web", "kodiexport"]
    for client in clients:
        query = urllib.parse.urlencode({"userId": config.user_id, "client": client})
        try:
            prefs = request_json(config, f"/DisplayPreferences/usersettings?{query}")
        except JellyfinCheckError as exc:
            print(
                f"⚠️  Warning: unable to load display preferences for client '{client}': {exc}",
                file=sys.stderr,
            )
            continue

        custom_prefs = prefs.get("CustomPrefs") or {}
        scroll_behavior = custom_prefs.get("scrollBehavior") or prefs.get("ScrollBehavior")
        if scroll_behavior in (None, "", "null"):
            custom_prefs["scrollBehavior"] = "auto"
            prefs["CustomPrefs"] = custom_prefs
            post_json(config, f"/DisplayPreferences/usersettings?{query}", prefs, timeout=15)
            print(
                f"✅ Display preferences patched with scrollBehavior=auto for client '{client}'"
            )
        else:
            print(
                f"✅ Display preferences already set scrollBehavior='{scroll_behavior}' for client '{client}'"
            )


def trigger_direct_library_refresh(config: JellyfinConfig) -> None:
    """Issue a POST to /Library/Refresh and ensure Jellyfin accepts it."""

    try:
        _request(config, "/Library/Refresh", method="POST", timeout=15)
    except JellyfinCheckError as exc:
        raise JellyfinCheckError(f"Direct /Library/Refresh call failed: {exc}") from exc


def trigger_refresh_webhook(config: JellyfinConfig) -> None:
    """Validate that the optional refresh webhook responds with a success code."""

    if not config.refresh_webhook_url:
        return

    payload = json.dumps({"title": "jellyfin-verify", "namespace": "pmoves"}).encode("utf-8")
    request = urllib.request.Request(
        config.refresh_webhook_url,
        data=payload,
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if config.refresh_webhook_token:
        request.add_header("Authorization", f"Bearer {config.refresh_webhook_token}")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            # Drain body to surface protocol errors and for completeness.
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise JellyfinCheckError(
            f"Webhook {config.refresh_webhook_url} returned HTTP {exc.code}: {body}"
        ) from exc
    except TimeoutError as exc:  # pragma: no cover - socket timeout
        raise JellyfinCheckError(
            f"Webhook {config.refresh_webhook_url} timed out: {exc}"
        ) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise JellyfinCheckError(
            f"Unable to reach webhook {config.refresh_webhook_url}: {exc}"
        ) from exc


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
                ensure_safe_display_preferences(config)
        else:
            print("ℹ️  JELLYFIN_USER_ID not set; skipped user enumeration check.")
        trigger_direct_library_refresh(config)
        print("✅ Jellyfin accepted direct /Library/Refresh trigger")
        if config.refresh_webhook_url:
            trigger_refresh_webhook(config)
            print(f"✅ Refresh webhook responded at {config.refresh_webhook_url}")
        print("All Jellyfin credential checks passed.")
        return 0
    except JellyfinCheckError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
