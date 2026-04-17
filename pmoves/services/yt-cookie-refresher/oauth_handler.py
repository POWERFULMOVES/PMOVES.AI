"""Google OAuth2 token refresh — adapted from channel-monitor's youtube_api.py."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"


def refresh_access_token(refresh_token: str) -> tuple[str, datetime]:
    """Exchange a refresh token for a fresh access token.

    Returns (access_token, expires_at).
    Raises httpx.HTTPStatusError on failure.
    """
    client_id = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET", "")

    resp = httpx.post(
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
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"OAuth token refresh failed: {data}")

    access_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))
    return access_token, expires_at
