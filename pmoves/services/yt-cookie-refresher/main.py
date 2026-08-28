"""yt-cookie-refresher — Lane 2228 refactor (2026-08-03).

Automated YouTube cookie harvesting service. Runs on a weekly cron schedule
(configurable via YT_COOKIE_REFRESH_CRON). On each cycle:
1. Reads Google provider_refresh_token from Supabase Auth identities
   (for the `darkxside@pmoves.ai` user, signed in via Google once at setup)
2. Exchanges for fresh provider_token via Google OAuth2 (oauth_client.py)
3. Launches Playwright Chromium, injects session, extracts cookies + PO token
4. Fernet-encrypts cookies, updates Supabase row
5. Publishes ingest.cookies.refreshed.v1 to NATS

Lane 2228 changes vs. the old flow:
- The Google OAuth refresh_token is now in `auth.identities` (managed by
  Supabase), not in our custom `pmoves_core.yt_oauth_cookies` table. This
  removes the 3-PR env var fix dance (SERVICE_ROLE_KEY preference) that
  #2327, #2333, #2346 had to ship — the same dance doesn't apply because
  we use the Supabase Admin API which has its own key.
- The YouTube session cookies + PO token + operational status fields stay
  in the custom table (they're yt-dlp's auth state, not OAuth tokens).

Health endpoint at :8115/healthz. Manual trigger via POST /refresh.
"""
from __future__ import annotations

import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI

from cookie_extractor import extract_cookies_and_po_token
from nats_publisher import publish_cookies_refreshed
from oauth_client import refresh_provider_token
from scheduler import RefreshScheduler
from supabase_auth import get_provider_refresh_token
from supabase_client import encrypt, get_row, mark_failed, update_cookies

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yt-cookie-refresher")

app = FastAPI(title="yt-cookie-refresher", version="0.2.0")
scheduler: RefreshScheduler | None = None


async def do_refresh() -> None:
    """Execute one cookie refresh cycle."""
    logger.info("Starting cookie refresh cycle...")

    # 1. Read provider_refresh_token from Supabase Auth identities.
    #    This is the new home for the Google OAuth refresh token (Lane 2228
    #    refactor). Before this refactor, the refresh token was stored in
    #    the custom pmoves_core.yt_oauth_cookies table as encrypted_refresh_token.
    provider_refresh_token = get_provider_refresh_token()
    if not provider_refresh_token:
        msg = (
            "No Google identity found for the Supabase user. "
            "Sign in once via the Supabase dashboard (Auth > Users > Add user > "
            "Create with Google), then re-run this refresh."
        )
        logger.error(msg)
        mark_failed(msg, needs_reauth=True)
        await publish_cookies_refreshed(status="failed", error="no_provider_identity")
        return

    # 2. Exchange for fresh provider_token via Google OAuth2.
    try:
        provider_token, expires_at = refresh_provider_token(provider_refresh_token)
        logger.info(f"Provider token refreshed (expires {expires_at.isoformat()})")
    except Exception as e:
        err = f"Google provider_token refresh failed: {e}"
        logger.error(err)
        needs_reauth = "invalid_grant" in str(e).lower()
        mark_failed(err, needs_reauth=needs_reauth)
        await publish_cookies_refreshed(status="failed", error=str(e)[:200])
        return

    # 3. Playwright cookie extraction (await — we're already inside the asyncio loop).
    try:
        cookies_str, po_token = await extract_cookies_and_po_token(provider_token)
        logger.info(f"Cookies extracted: {len(cookies_str)} bytes, PO token: {'yes' if po_token else 'no'}")
    except Exception as e:
        err = f"Playwright extraction failed: {e}"
        logger.error(err)
        mark_failed(err)
        await publish_cookies_refreshed(status="failed", error=str(e)[:200])
        return

    # 4. Fernet-encrypt + store the YouTube session cookies (NOT the OAuth tokens).
    enc_cookies = encrypt(cookies_str)
    enc_po = encrypt(po_token) if po_token else ""
    update_cookies(enc_cookies, enc_po)
    logger.info("Encrypted YouTube cookies stored in Supabase")

    # 5. Publish NATS event.
    await publish_cookies_refreshed(status="success")
    logger.info("Cookie refresh cycle complete")


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok", "service": "yt-cookie-refresher", "version": "0.2.0"}


@app.post("/refresh")
async def manual_refresh():
    """Trigger an immediate cookie refresh (used by make yt-cookies-refresh)."""
    asyncio.create_task(do_refresh())
    return {"status": "triggered"}


@app.get("/status")
async def status():
    """Return current cookie state + Supabase Auth identity health."""
    row = get_row()
    supabase_user_email = os.environ.get("YT_COOKIES_SUPABASE_USER", "darkxside@pmoves.ai")
    has_provider_identity = bool(get_provider_refresh_token())
    if not row and not has_provider_identity:
        return {
            "status": "no_credentials",
            "supabase_user": supabase_user_email,
            "has_google_identity": False,
        }
    return {
        "supabase_user": supabase_user_email,
        "has_google_identity": has_provider_identity,
        "user_id": row.get("user_id") if row else None,
        "refresh_status": row.get("refresh_status") if row else None,
        "has_cookies": bool(row.get("encrypted_cookies")) if row else False,
        "has_po_token": bool(row.get("encrypted_po_token")) if row else False,
        "last_refresh": row.get("refresh_completed_at") if row else None,
        "needs_reauth": row.get("requires_manual_reauth", False) if row else False,
    }


@app.on_event("startup")
async def startup():
    """Start the cron scheduler on service boot."""
    global scheduler
    scheduler = RefreshScheduler(do_refresh)
    scheduler.start()
    logger.info("yt-cookie-refresher started (Lane 2228 refactor)")


@app.on_event("shutdown")
async def shutdown():
    """Stop the scheduler."""
    if scheduler:
        await scheduler.stop()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8115"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
