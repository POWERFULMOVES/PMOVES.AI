"""Supabase client for yt_oauth_cookies table (operational status + cookie/PO token storage).

Lane 2228 refactor (2026-08-03): the `encrypted_refresh_token` column was removed.
The Google OAuth refresh_token now lives in `auth.identities` for the
`darkxside@pmoves.ai` user (managed by Supabase, not us). What stays here:
  - `encrypted_cookies`: yt-dlp's YouTube session cookies (Fernet-encrypted)
  - `encrypted_po_token`: YouTube PO token (Fernet-encrypted)
  - `refresh_status` / `refresh_completed_at` / `refresh_error_message`:
    operational metadata, useful for the /status endpoint and the AGNOTE trail
  - `requires_manual_reauth`: flag the operator's attention if the refresh breaks

This split is intentional: the OAuth tokens belong to the user identity
(managed by Supabase Auth); the YouTube cookies + PO token are yt-dlp's
session state, not OAuth tokens, and have no Supabase equivalent.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

TABLE_PATH = "/rest/v1/yt_oauth_cookies"
DEFAULT_USER_ID = "darkxside"


def _get_fernet() -> Optional[Fernet]:
    """Build Fernet from VAULT_ENC_KEY (hex). Returns None if unavailable."""
    if Fernet is None:
        return None
    key_hex = os.environ.get("VAULT_ENC_KEY", "").strip()
    if not key_hex:
        return None
    try:
        # VAULT_ENC_KEY_DECODE_V1 -- keep identical in all three consumers:
        #   pmoves/tools/yt_oauth_flow.py
        #   pmoves/services/yt-cookie-writer/main.py
        #   pmoves/services/yt-cookie-refresher/supabase_client.py
        # One side encrypting with a different derivation than the other decrypts
        # with is worse than both failing: consent reports success, ciphertext
        # lands, and the writer silently never produces the refresh-token file.
        # Hex first (the registry's declared spec for this key), then base64url,
        # then raw bytes.
        try:
            key_bytes = bytes.fromhex(key_hex)
        except ValueError:
            try:
                _padded = key_hex + "=" * (-len(key_hex) % 4)
                key_bytes = base64.urlsafe_b64decode(_padded) or key_hex.encode("utf-8")
            except Exception:
                key_bytes = key_hex.encode("utf-8")
        key_bytes = (key_bytes + b"\x00" * 32)[:32]
        return Fernet(base64.urlsafe_b64encode(key_bytes))
    except Exception:
        return None


def encrypt(value: str, fernet: Optional[Fernet] = None) -> str:
    """Encrypt value with Fernet. Raises RuntimeError if encryption unavailable.

    Cookies + PO tokens carry YouTube session auth — they must never land in
    Supabase as plaintext. If VAULT_ENC_KEY is missing or cryptography is
    unavailable, refuse to proceed rather than silently storing plaintext.
    """
    if not value:
        return value
    f = fernet or _get_fernet()
    if f is None:
        raise RuntimeError(
            "Fernet encryption unavailable (VAULT_ENC_KEY missing or cryptography "
            "not installed). Refusing to persist plaintext cookies to Supabase."
        )
    return f.encrypt(value.encode()).decode()


def decrypt(value: str, fernet: Optional[Fernet] = None) -> str:
    """Decrypt value with Fernet, or return as-is."""
    f = fernet or _get_fernet()
    if f is None or not value:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value


def _url() -> str:
    return os.environ.get("SUPABASE_URL", os.environ.get("SUPA_REST_URL", "http://supabase-kong:8000"))


def _headers() -> dict:
    """Prefer the secrets-sync name; fall back to the legacy local name.

    Same preference the OAuth tool adopted in #2333 and the cookie service in
    #2346. Operator's 5090 host may have either; this lets the same image
    work in both.
    """
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        # yt_oauth_cookies lives in pmoves_core; PostgREST only consults the
        # FIRST schema in PGRST_DB_SCHEMAS unless told otherwise.
        "Accept-Profile": "pmoves_core",
        "Content-Profile": "pmoves_core",
    }


def get_row(user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """Fetch the operational row (cookies + PO token + status fields).

    Note: this no longer returns encrypted_refresh_token (that column is gone).
    The refresh_token is in `auth.identities` — see supabase_auth.py.
    """
    resp = httpx.get(
        f"{_url()}{TABLE_PATH}?user_id=eq.{user_id}&select=*",
        headers=_headers(),
        timeout=10,
    )
    rows = resp.json() if resp.status_code == 200 else []
    return rows[0] if rows else None


def update_cookies(
    encrypted_cookies: str,
    encrypted_po_token: str = "",
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Update the cookies + PO token columns after a successful harvest."""
    headers = _headers()
    headers["Prefer"] = "return=representation"
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "encrypted_cookies": encrypted_cookies,
        "encrypted_po_token": encrypted_po_token,
        "refresh_status": "success",
        "refresh_completed_at": now,
        "refresh_error_message": None,
        "requires_manual_reauth": False,
    }
    resp = httpx.patch(
        f"{_url()}{TABLE_PATH}?user_id=eq.{user_id}",
        headers=headers,
        json=payload,
        timeout=15,
    )
    rows = resp.json() if resp.status_code == 200 else []
    return rows[0] if rows else {}


def mark_failed(error: str, user_id: str = DEFAULT_USER_ID, needs_reauth: bool = False) -> None:
    """Mark the row as failed with error message."""
    now = datetime.now(timezone.utc).isoformat()
    httpx.patch(
        f"{_url()}{TABLE_PATH}?user_id=eq.{user_id}",
        headers=_headers(),
        json={
            "refresh_status": "failed",
            "refresh_completed_at": now,
            "refresh_error_message": error[:500],
            "requires_manual_reauth": needs_reauth,
        },
        timeout=10,
    )
