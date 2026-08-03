"""Minimal Google OAuth2 client for refreshing provider_token from provider_refresh_token.

Lane 2228 refactor (2026-08-03): replaces the hand-rolled `oauth_handler.py` (50 lines
of direct `httpx.post(TOKEN_URL, ...)`) with a focused 30-line module. The token
*storage* now lives in Supabase Auth identities (managed by Supabase, not us),
but the *exchange* still has to be a direct HTTP call because Supabase does
not auto-refresh Google provider_token server-side.

Wire:
  - CHANNEL_MONITOR_GOOGLE_CLIENT_ID + CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET come
    from env.tier-agent (operator-managed Google OAuth app credentials, shared
    with channel-monitor and pinokio_apps).
  - provider_refresh_token is read from `auth.identities.identity_data` for the
    `darkxside@pmoves.ai` user (see `supabase_auth.py`).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import httpx

logger = logging.getLogger("yt-cookie-refresher.oauth")

TOKEN_URL = "https://oauth2.googleapis.com/token"


def refresh_provider_token(provider_refresh_token: str) -> Tuple[str, datetime]:
    """Exchange a Google provider_refresh_token for a fresh provider_token.

    Returns (provider_token, expires_at). Raises RuntimeError on failure with
    the structured OAuth error payload preserved (Google returns
    {"error": "invalid_grant", "error_description": "..."} on 400).
    """
    client_id = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "missing CHANNEL_MONITOR_GOOGLE_CLIENT_ID or CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET"
        )

    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": provider_refresh_token,
        },
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code >= 400 or "error" in data:
        err_code = data.get("error", f"http_{resp.status_code}")
        err_desc = data.get("error_description", resp.text[:200])
        raise RuntimeError(f"Google provider_token refresh failed ({err_code}): {err_desc}")

    provider_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))
    logger.info(f"Google provider_token refreshed (expires {expires_at.isoformat()})")
    return provider_token, expires_at
