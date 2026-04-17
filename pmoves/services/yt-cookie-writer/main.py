"""yt-cookie-writer — Phase 9Q.2 PR 3.

NATS sidecar that subscribes to ingest.cookies.refreshed.v1, fetches
encrypted cookies from Supabase, decrypts with Fernet (VAULT_ENC_KEY),
and writes Netscape-format cookie file to the shared volume that
pmoves-yt mounts at /app/config/cookies/.

pmoves-yt's yt-dlp reads the cookiefile per-request — no restart needed.
This sidecar is the bridge between the refresher service and the YT
pipeline, keeping PMOVES.YT submodule untouched.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import nats

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yt-cookie-writer")

NATS_SUBJECT = "ingest.cookies.refreshed.v1"
COOKIE_OUTPUT_PATH = os.environ.get("YT_COOKIE_OUTPUT_PATH", "/app/config/cookies/yt-cookies.txt")
TABLE_PATH = "/rest/v1/yt_oauth_cookies"
DEFAULT_USER_ID = "darkxside"


def _get_fernet() -> Optional[Fernet]:
    """Build Fernet from VAULT_ENC_KEY."""
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


def _decrypt(value: str) -> str:
    """Decrypt Fernet-encrypted value, or return as-is."""
    f = _get_fernet()
    if f is None or not value:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value


def _supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", os.environ.get("SUPA_REST_URL", "http://supabase-kong:8000"))


def _supabase_headers() -> dict:
    key = os.environ.get("SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def fetch_and_write_cookies(user_id: str = DEFAULT_USER_ID) -> bool:
    """Fetch encrypted cookies from Supabase, decrypt, write to disk.

    Returns True on success.
    """
    import httpx

    url = f"{_supabase_url()}{TABLE_PATH}?user_id=eq.{user_id}&select=encrypted_cookies"
    try:
        resp = httpx.get(url, headers=_supabase_headers(), timeout=10)
        rows = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        logger.error(f"Failed to fetch cookies from Supabase: {e}")
        return False

    if not rows or not rows[0].get("encrypted_cookies"):
        logger.warning("No cookies in Supabase — waiting for first refresh")
        return False

    cookies_str = _decrypt(rows[0]["encrypted_cookies"])
    if not cookies_str:
        logger.error("Failed to decrypt cookies (VAULT_ENC_KEY mismatch?)")
        return False

    output = Path(COOKIE_OUTPUT_PATH)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(cookies_str)
    logger.info(f"Wrote {len(cookies_str)} bytes to {output}")
    return True


async def _on_message(msg):
    """Handle ingest.cookies.refreshed.v1 NATS messages."""
    try:
        data = json.loads(msg.data.decode())
        status = data.get("status", "unknown")
        user_id = data.get("user_id", DEFAULT_USER_ID)
        logger.info(f"Received {NATS_SUBJECT}: status={status}, user={user_id}")

        if status == "success":
            ok = await fetch_and_write_cookies(user_id)
            if ok:
                logger.info("Cookie file updated — pmoves-yt will pick up on next request")
            else:
                logger.warning("Cookie write failed — existing file left in place")
        else:
            logger.warning(f"Refresh reported status={status}, skipping write")
    except Exception as e:
        logger.exception(f"Error processing {NATS_SUBJECT}: {e}")


async def run() -> None:
    """Main event loop — connect to NATS, subscribe, wait."""
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
    logger.info(f"Connecting to NATS at {nats_url}")

    nc = await nats.connect(nats_url)
    await nc.subscribe(NATS_SUBJECT, cb=_on_message)
    logger.info(f"Subscribed to {NATS_SUBJECT}")

    # On startup, try to write existing cookies (if any)
    logger.info("Checking for existing cookies on startup...")
    await fetch_and_write_cookies()

    # Wait for signal
    stop = asyncio.Event()

    def _signal_handler():
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    logger.info("yt-cookie-writer running — waiting for NATS events")
    await stop.wait()

    await nc.drain()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(run())
