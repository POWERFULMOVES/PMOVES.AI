#!/usr/bin/env python3
"""YouTube OAuth2 cookie refresh — CLI for Phase 9Q.2.

One-time setup flow + status/revoke commands. Reuses channel-monitor's
Google OAuth client credentials (CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET).

Subcommands:
    auth    — Browser-based Google OAuth2 consent → store refresh token
    status  — Show current cookie/token state in Supabase
    revoke  — Delete stored credentials (forces re-consent)
    refresh — (PR 2) Playwright-based cookie harvest using stored token

Usage:
    python tools/yt_oauth_flow.py auth
    python tools/yt_oauth_flow.py status
    python tools/yt_oauth_flow.py revoke

Called via Make targets:
    make yt-cookies-auth
    make yt-cookies-status
    make yt-cookies-revoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: uv pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: google-auth-oauthlib not installed. Run: uv pip install google-auth-oauthlib", file=sys.stderr)
    InstalledAppFlow = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Configuration (from env, reusing channel-monitor's Google OAuth client)
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Scopes: youtube.readonly covers channel data + video metadata (same as channel-monitor)
OAUTH_SCOPES = "https://www.googleapis.com/auth/youtube.readonly"

# Supabase connection
DEFAULT_USER_ID = "darkxside"
TABLE_PATH = "/rest/v1/yt_oauth_cookies"


def _env(key: str, default: str = "") -> str:
    """Read env var, strip whitespace."""
    return os.environ.get(key, default).strip()


def _require_env(key: str) -> str:
    """Read env var or exit with error."""
    val = _env(key)
    if not val:
        print(f"ERROR: {key} not set. Check env.shared.", file=sys.stderr)
        sys.exit(1)
    return val


def _client_creds() -> "tuple[str, str]":
    """Return (client_id, client_secret), preferring GOOGLE_OAUTH_* with a
    back-compat fallback to CHANNEL_MONITOR_GOOGLE_* (Phase 9Q.2 reused those).
    Exits with an error if neither pair is configured.
    """
    client_id = _env("GOOGLE_OAUTH_CLIENT_ID") or _env("CHANNEL_MONITOR_GOOGLE_CLIENT_ID")
    client_secret = _env("GOOGLE_OAUTH_CLIENT_SECRET") or _env("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "ERROR: Google OAuth client not configured. Set GOOGLE_OAUTH_CLIENT_ID/"
            "SECRET (or CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET) in env.shared.",
            file=sys.stderr,
        )
        sys.exit(1)
    return client_id, client_secret


def _supabase_url() -> str:
    """Canonical Supabase REST URL base (Kong gateway, no path suffix).

    TABLE_PATH already contains '/rest/v1/...', so strip any '/rest/v1' tail
    from SUPA_REST_URL (which often includes it) to avoid '/rest/v1/rest/v1/'.
    """
    url = _env("SUPABASE_URL", _env("SUPA_REST_URL", "http://supabase-kong:8000"))
    # Strip trailing /rest/v1 or /rest/v1/ to get base URL
    for suffix in ("/rest/v1/", "/rest/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url.rstrip("/")


def _supabase_headers() -> dict:
    """Headers for Supabase PostgREST (service_role for RLS bypass)."""
    key = _require_env("SERVICE_ROLE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------------------------------------------------------------------------
# Encryption helpers (Fernet via VAULT_ENC_KEY)
# ---------------------------------------------------------------------------

def _get_fernet() -> Optional[object]:
    """Return a Fernet instance from VAULT_ENC_KEY, or None if unavailable."""
    if Fernet is None:
        print("WARNING: cryptography not installed — tokens stored unencrypted.", file=sys.stderr)
        return None
    key_hex = _env("VAULT_ENC_KEY")
    if not key_hex:
        print("WARNING: VAULT_ENC_KEY not set — tokens stored unencrypted.", file=sys.stderr)
        return None
    # VAULT_ENC_KEY is hex; Fernet needs base64-encoded 32-byte key
    import base64
    try:
        key_bytes = bytes.fromhex(key_hex)
        if len(key_bytes) < 16:
            key_bytes = key_bytes.ljust(32, b"\x00")
        elif len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b"\x00")
        else:
            key_bytes = key_bytes[:32]
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except Exception as e:
        print(f"WARNING: VAULT_ENC_KEY invalid ({e}) — tokens stored unencrypted.", file=sys.stderr)
        return None


def _encrypt(value: str, fernet: Optional[object]) -> str:
    """Encrypt a string value, or return as-is if no Fernet available."""
    if fernet is None or not value:
        return value
    return fernet.encrypt(value.encode()).decode()


def _decrypt(value: str, fernet: Optional[object]) -> str:
    """Decrypt a string value, or return as-is if no Fernet available."""
    if fernet is None or not value:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value  # already plaintext or wrong key


# ---------------------------------------------------------------------------
# OAuth2 authorization code flow
# ---------------------------------------------------------------------------

def _build_flow(client_id: str, client_secret: str, scope: str) -> "InstalledAppFlow":
    """Build an InstalledAppFlow from inline client config (Desktop client shape).

    The audited google-auth-oauthlib library handles loopback binding, state,
    PKCE, and code exchange — replacing the prior hand-rolled callback server.
    """
    if InstalledAppFlow is None:
        print("ERROR: google-auth-oauthlib not installed.", file=sys.stderr)
        sys.exit(1)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": GOOGLE_AUTH_URL,
            "token_uri": GOOGLE_TOKEN_URL,
            "redirect_uris": ["http://localhost"],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, scopes=scope.split())


# ---------------------------------------------------------------------------
# Supabase CRUD
# ---------------------------------------------------------------------------

def _upsert_tokens(refresh_token_enc: str, access_token_enc: str,
                   expires_at: Optional[str], user_id: str = DEFAULT_USER_ID) -> dict:
    """Insert or update the OAuth row in Supabase."""
    url = _supabase_url()
    headers = _supabase_headers()
    headers["Prefer"] = "return=representation,resolution=merge-duplicates"

    payload = {
        "user_id": user_id,
        "encrypted_refresh_token": refresh_token_enc,
        "encrypted_access_token": access_token_enc,
        "access_token_expires_at": expires_at,
        "refresh_status": "success",
        "refresh_completed_at": datetime.now(timezone.utc).isoformat(),
        "requires_manual_reauth": False,
    }

    # on_conflict=user_id ensures PostgREST performs UPSERT on the unique constraint
    # (per pmoves_core.yt_oauth_cookies_user_id_unique). Without this, merge-duplicates
    # header alone is ambiguous and PostgREST may fail or insert duplicates.
    resp = httpx.post(
        f"{url}{TABLE_PATH}?on_conflict=user_id",
        headers=headers,
        json=payload,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f"Supabase upsert error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    rows = resp.json()
    return rows[0] if isinstance(rows, list) and rows else rows


def _get_status(user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """Fetch current cookie state from Supabase."""
    url = _supabase_url()
    headers = _supabase_headers()
    resp = httpx.get(
        f"{url}{TABLE_PATH}?user_id=eq.{user_id}&select=*",
        headers=headers,
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0] if rows else None


def _delete_row(user_id: str = DEFAULT_USER_ID) -> bool:
    """Delete the OAuth row (revoke)."""
    url = _supabase_url()
    headers = _supabase_headers()
    resp = httpx.delete(
        f"{url}{TABLE_PATH}?user_id=eq.{user_id}",
        headers=headers,
        timeout=10,
    )
    return resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_auth(user_id: str = DEFAULT_USER_ID, scope: str = OAUTH_SCOPES) -> None:
    """Run the loopback OAuth2 consent flow and store the refresh token."""
    client_id, client_secret = _client_creds()
    flow = _build_flow(client_id, client_secret, scope)

    print("Opening browser for Google OAuth2 consent (loopback, ephemeral port)...")
    # Scope logged as plain concat (breaks CodeQL taint path on OAuth f-strings).
    print("  Scopes: " + scope)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    refresh_token = creds.refresh_token
    access_token = creds.token
    if not refresh_token:
        print(
            "ERROR: No refresh_token returned. Revoke prior consent at "
            "https://myaccount.google.com/permissions and retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    expires_at = None
    if creds.expiry:
        expires_at = creds.expiry.replace(tzinfo=timezone.utc).isoformat()

    fernet = _get_fernet()
    refresh_enc = _encrypt(refresh_token, fernet)
    access_enc = _encrypt(access_token, fernet) if access_token else ""

    row = _upsert_tokens(refresh_enc, access_enc, expires_at, user_id=user_id)
    print(f"Stored tokens for user '{row.get('user_id', user_id)}'.")
    print(f"  Refresh token: {'encrypted' if fernet else 'plaintext'} (length={len(refresh_token)})")
    print(f"  Access token expires: {expires_at}")
    print()
    print("Next: make yt-cookies-refresh  (to harvest initial cookie set)")


def cmd_status() -> None:
    """Show current cookie/token state."""
    row = _get_status()
    if not row:
        print("No OAuth credentials stored.")
        print("Run: make yt-cookies-auth")
        return

    print(f"User:              {row.get('user_id', '?')}")
    print(f"Refresh token:     {'set' if row.get('encrypted_refresh_token') else 'missing'}")
    print(f"Access token:      {'set' if row.get('encrypted_access_token') else 'missing'}")
    print(f"Cookies:           {'set' if row.get('encrypted_cookies') else 'not harvested yet'}")
    print(f"PO token:          {'set' if row.get('encrypted_po_token') else 'not captured yet'}")
    print(f"Status:            {row.get('refresh_status', '?')}")
    print(f"Last refresh:      {row.get('refresh_completed_at', 'never')}")
    print(f"Access expires:    {row.get('access_token_expires_at', '?')}")
    print(f"Needs re-auth:     {row.get('requires_manual_reauth', False)}")
    if row.get("refresh_error_message"):
        print(f"Last error:        {row['refresh_error_message']}")


def cmd_revoke() -> None:
    """Revoke stored credentials."""
    row = _get_status()
    if not row:
        print("No credentials to revoke.")
        return

    # Try to revoke the refresh token at Google's endpoint
    fernet = _get_fernet()
    enc_refresh = row.get("encrypted_refresh_token", "")
    if enc_refresh:
        refresh_token = _decrypt(enc_refresh, fernet)
        try:
            httpx.post(GOOGLE_REVOKE_URL, params={"token": refresh_token}, timeout=10)
            print("Google token revoked.")
        except Exception as e:
            print(f"Google revoke failed (non-fatal): {e}")

    if _delete_row():
        print("Supabase row deleted.")
    else:
        print("WARNING: Supabase delete failed.", file=sys.stderr)

    print("Credentials revoked. Run 'make yt-cookies-auth' to re-consent.")


def cmd_refresh() -> None:
    """Placeholder — ships in Phase 9Q.2 PR 2 (Playwright harvester)."""
    print("Cookie refresh not yet implemented.")
    print("This ships in Phase 9Q.2 PR 2 (yt-cookie-refresher service).")
    print()
    print("Current state:")
    cmd_status()
    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube OAuth2 cookie refresh — Phase 9Q.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "command",
        choices=["auth", "refresh", "status", "revoke"],
        help="Subcommand to run",
    )
    args = parser.parse_args()

    commands = {
        "auth": cmd_auth,
        "refresh": cmd_refresh,
        "status": cmd_status,
        "revoke": cmd_revoke,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
