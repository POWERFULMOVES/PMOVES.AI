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
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
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

# ---------------------------------------------------------------------------
# Configuration (from env, reusing channel-monitor's Google OAuth client)
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Scopes: youtube.readonly covers channel data + video metadata (same as channel-monitor)
OAUTH_SCOPES = "https://www.googleapis.com/auth/youtube.readonly"

# Callback server for OAuth2 code exchange
CALLBACK_PORT = 8199
CALLBACK_PATH = "/oauth/callback"

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


def _supabase_url() -> str:
    """Canonical Supabase REST URL (Kong gateway)."""
    return _env("SUPABASE_URL", _env("SUPA_REST_URL", "http://supabase-kong:8000"))


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

class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler to capture OAuth2 callback code."""

    code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        if "error" in params:
            _OAuthCallbackHandler.error = params["error"][0]
            body = f"<h2>OAuth Error: {params['error'][0]}</h2><p>You can close this tab.</p>"
        elif "code" in params:
            _OAuthCallbackHandler.code = params["code"][0]
            body = "<h2>Authorization successful!</h2><p>You can close this tab and return to the terminal.</p>"
        else:
            body = "<h2>Unexpected response</h2>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args) -> None:  # noqa: D102
        pass  # suppress server log noise


def _build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build Google OAuth2 authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "access_type": "offline",       # get refresh_token
        "prompt": "consent",            # always prompt (ensures refresh_token)
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens."""
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = httpx.post(GOOGLE_TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


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

    resp = httpx.post(
        f"{url}{TABLE_PATH}",
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

def cmd_auth() -> None:
    """Run the OAuth2 consent flow and store the refresh token."""
    client_id = _require_env("CHANNEL_MONITOR_GOOGLE_CLIENT_ID")
    client_secret = _require_env("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET")
    redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

    state = secrets.token_urlsafe(16)
    auth_url = _build_auth_url(client_id, redirect_uri, state)

    # Start callback server
    server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print(f"Opening browser for Google OAuth2 consent...")
    print(f"  Redirect URI: {redirect_uri}")
    print(f"  Scopes: {OAUTH_SCOPES}")
    print()
    webbrowser.open(auth_url)
    print("Waiting for OAuth2 callback... (Ctrl+C to cancel)")

    server_thread.join(timeout=300)  # 5 min timeout
    server.server_close()

    if _OAuthCallbackHandler.error:
        print(f"ERROR: OAuth2 denied: {_OAuthCallbackHandler.error}", file=sys.stderr)
        sys.exit(1)

    code = _OAuthCallbackHandler.code
    if not code:
        print("ERROR: No authorization code received (timeout?).", file=sys.stderr)
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")
    token_data = _exchange_code(code, client_id, client_secret, redirect_uri)

    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in", 3600)

    if not refresh_token:
        print("ERROR: No refresh_token in response. Ensure 'access_type=offline' and 'prompt=consent'.", file=sys.stderr)
        sys.exit(1)

    expires_at = datetime.now(timezone.utc).isoformat()
    if expires_in:
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()

    # Encrypt before storage
    fernet = _get_fernet()
    refresh_enc = _encrypt(refresh_token, fernet)
    access_enc = _encrypt(access_token, fernet) if access_token else ""

    row = _upsert_tokens(refresh_enc, access_enc, expires_at)
    print(f"Stored tokens for user '{row.get('user_id', DEFAULT_USER_ID)}'.")
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
