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
    # Preserve OAuth error payload BEFORE raising. Google returns structured errors
    # like {"error":"invalid_grant","error_description":"..."} with 400 — raise_for_status()
    # would discard that context. Read first, then decide.
    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code >= 400 or "error" in data:
        err_code = data.get("error", f"http_{resp.status_code}")
        err_desc = data.get("error_description", resp.text[:200])
        raise RuntimeError(f"OAuth token refresh failed ({err_code}): {err_desc}")

    access_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))
    return access_token, expires_at
