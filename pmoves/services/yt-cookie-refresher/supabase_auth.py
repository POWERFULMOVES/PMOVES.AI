"""Read Google provider tokens from Supabase Auth identities.

Lane 2228 refactor (2026-08-03): replaces the hand-rolled `pmoves_core.yt_oauth_cookies`
table's `encrypted_refresh_token` column with a Supabase Auth identity read. The
identity is created when the operator signs in as `darkxside@pmoves.ai` via Google
in the Supabase dashboard (one-time, manual).

The yt-cookie-refresher uses the service_role key to call `auth.admin.get_user_by_id`
and read the Google identity's `identity_data`, which contains
`provider_token` and `provider_refresh_token`. These are sensitive (they grant
YouTube access) but are encrypted at rest by Supabase.

Why this is cleaner than the old custom table:
  1. No SERVICE_ROLE_KEY env var preference dance (Supabase SDK uses the same
     service_role key for everything; no more 3-PR fix cycles).
  2. The `darkxside@pmoves.ai` user is a first-class Supabase entity — you can
     audit it via the dashboard, revoke it, see sign-in history.
  3. Token rotation, refresh_token reuse detection, and PKCE are Supabase's
     problem, not ours.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("yt-cookie-refresher.supabase_auth")

# The Supabase user whose Google identity holds the YouTube Premium tokens.
# Operator creates this user once in the Supabase dashboard and signs in via
# Google (granting cataclysmstudios@gmail.com's Google identity which has
# YouTube Premium access).
DARKXSIDE_USER_EMAIL = os.environ.get(
    "YT_COOKIES_SUPABASE_USER", "darkxside@pmoves.ai"
)


def _admin_url() -> str:
    base = os.environ.get("SUPABASE_URL", os.environ.get("SUPA_REST_URL", ""))
    return f"{base.rstrip('/')}/auth/v1/admin/users"


def _service_role_key() -> str:
    """Prefer the secrets-sync name; fall back to the legacy local name.

    Same preference the OAuth tool adopted in #2333, applied here for the
    Supabase Management API call. Operator's 5090 host may have either; this
    lets the same image work in both.
    """
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SERVICE_ROLE_KEY", ""
    )


def get_user_by_email(email: str = DARKXSIDE_USER_EMAIL) -> Optional[dict]:
    """Fetch the Supabase user record by email. Returns None if not found."""
    headers = {
        "apikey": _service_role_key(),
        "Authorization": f"Bearer {_service_role_key()}",
    }
    # Use params= so httpx percent-encodes the email correctly (Supabase
    # accepts both forms, but the unencoded `?email=x@y` form breaks for any
    # email containing reserved URL characters — and `+` in a Supabase user
    # email is a real concern).
    resp = httpx.get(
        _admin_url(),
        params={"email": email},
        headers=headers,
        timeout=10,
    )
    if resp.status_code != 200:
        logger.error(
            f"Supabase admin getUserByEmail failed: {resp.status_code} {resp.text[:200]}"
        )
        return None
    users = resp.json().get("users", [])
    return users[0] if users else None


def get_google_identity(user_email: str = DARKXSIDE_USER_EMAIL) -> Optional[dict]:
    """Return the Google identity for the given Supabase user, or None.

    The identity has:
      - identity_data: dict with provider_token, provider_refresh_token, sub, email
      - provider: "google"
      - identity_id: stable id for the (user, provider) pair
    """
    user = get_user_by_email(user_email)
    if not user:
        logger.warning(f"Supabase user {user_email!r} not found")
        return None

    for identity in user.get("identities", []):
        if identity.get("provider") == "google":
            return identity
    logger.warning(f"Supabase user {user_email!r} has no Google identity")
    return None


def get_provider_refresh_token(user_email: str = DARKXSIDE_USER_EMAIL) -> Optional[str]:
    """Read the Google provider_refresh_token from the user's Supabase identity.

    Returns None if the user doesn't exist or hasn't signed in via Google yet.
    Operator runs `make yt-cookies-bootstrap` (or the equivalent Supabase dashboard
    action) to seed this.
    """
    identity = get_google_identity(user_email)
    if not identity:
        return None
    return identity.get("identity_data", {}).get("provider_refresh_token")
