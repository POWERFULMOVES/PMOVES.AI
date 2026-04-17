"""yt-cookie-refresher — Phase 9Q.2 PR 2.

Automated YouTube cookie harvesting service. Runs on a weekly cron schedule
(configurable via YT_COOKIE_REFRESH_CRON). On each cycle:
1. Reads encrypted refresh_token from Supabase (pmoves_core.yt_oauth_cookies)
2. Exchanges for fresh access_token via Google OAuth2
3. Launches Playwright Chromium, injects session, extracts cookies + PO token
4. Fernet-encrypts cookies, updates Supabase row
5. Publishes ingest.cookies.refreshed.v1 to NATS

Health endpoint at :8115/healthz. Manual trigger via POST /refresh.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI

from cookie_extractor import extract_cookies_and_po_token
from nats_publisher import publish_cookies_refreshed
from oauth_handler import refresh_access_token
from scheduler import RefreshScheduler
from supabase_client import decrypt, encrypt, get_row, mark_failed, update_cookies

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yt-cookie-refresher")

app = FastAPI(title="yt-cookie-refresher", version="0.1.0")
scheduler: RefreshScheduler | None = None


async def do_refresh() -> None:
    """Execute one cookie refresh cycle."""
    logger.info("Starting cookie refresh cycle...")

    # 1. Read stored refresh token
    row = get_row()
    if not row or not row.get("encrypted_refresh_token"):
        logger.error("No refresh token stored. Run: make yt-cookies-auth")
        mark_failed("No refresh token — run make yt-cookies-auth", needs_reauth=True)
        await publish_cookies_refreshed(status="failed", error="no_refresh_token")
        return

    # 2. Decrypt refresh token
    refresh_token = decrypt(row["encrypted_refresh_token"])
    if not refresh_token:
        logger.error("Failed to decrypt refresh token (VAULT_ENC_KEY mismatch?)")
        mark_failed("Decryption failed — check VAULT_ENC_KEY")
        await publish_cookies_refreshed(status="failed", error="decrypt_failed")
        return

    # 3. Exchange for fresh access token
    try:
        access_token, expires_at = refresh_access_token(refresh_token)
        logger.info(f"Access token refreshed (expires {expires_at.isoformat()})")
    except Exception as e:
        err = f"OAuth token refresh failed: {e}"
        logger.error(err)
        needs_reauth = "invalid_grant" in str(e).lower()
        mark_failed(err, needs_reauth=needs_reauth)
        await publish_cookies_refreshed(status="failed", error=str(e)[:200])
        return

    # 4. Playwright cookie extraction (await — we're already inside the asyncio loop)
    try:
        cookies_str, po_token = await extract_cookies_and_po_token(access_token)
        logger.info(f"Cookies extracted: {len(cookies_str)} bytes, PO token: {'yes' if po_token else 'no'}")
    except Exception as e:
        err = f"Playwright extraction failed: {e}"
        logger.error(err)
        mark_failed(err)
        await publish_cookies_refreshed(status="failed", error=str(e)[:200])
        return

    # 5. Encrypt and store
    enc_cookies = encrypt(cookies_str)
    enc_po = encrypt(po_token) if po_token else ""
    update_cookies(enc_cookies, enc_po)
    logger.info("Encrypted cookies stored in Supabase")

    # 6. Publish NATS event
    await publish_cookies_refreshed(status="success")
    logger.info("Cookie refresh cycle complete")


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok", "service": "yt-cookie-refresher"}


@app.post("/refresh")
async def manual_refresh():
    """Trigger an immediate cookie refresh (used by make yt-cookies-refresh)."""
    asyncio.create_task(do_refresh())
    return {"status": "triggered"}


@app.get("/status")
async def status():
    """Return current cookie state."""
    row = get_row()
    if not row:
        return {"status": "no_credentials"}
    return {
        "user_id": row.get("user_id"),
        "refresh_status": row.get("refresh_status"),
        "has_cookies": bool(row.get("encrypted_cookies")),
        "has_po_token": bool(row.get("encrypted_po_token")),
        "last_refresh": row.get("refresh_completed_at"),
        "needs_reauth": row.get("requires_manual_reauth", False),
    }


@app.on_event("startup")
async def startup():
    """Start the cron scheduler on service boot."""
    global scheduler
    scheduler = RefreshScheduler(do_refresh)
    scheduler.start()
    logger.info("yt-cookie-refresher started")


@app.on_event("shutdown")
async def shutdown():
    """Stop the scheduler."""
    if scheduler:
        await scheduler.stop()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8115"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
