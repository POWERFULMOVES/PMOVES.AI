"""Supabase client for yt_oauth_cookies table with Fernet encryption."""
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
        key_bytes = bytes.fromhex(key_hex)
        key_bytes = (key_bytes + b"\x00" * 32)[:32]
        return Fernet(base64.urlsafe_b64encode(key_bytes))
    except Exception:
        return None


def encrypt(value: str, fernet: Optional[Fernet] = None) -> str:
    """Encrypt value with Fernet, or return as-is."""
    f = fernet or _get_fernet()
    if f is None or not value:
        return value
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
    key = os.environ.get("SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_row(user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """Fetch current OAuth row."""
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
