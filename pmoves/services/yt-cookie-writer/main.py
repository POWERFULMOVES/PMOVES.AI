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
from pathlib import Path
from typing import Optional

import httpx
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
PO_TOKEN_OUTPUT_PATH = os.environ.get("YT_PO_TOKEN_OUTPUT_PATH", "/app/config/cookies/yt-po-token.txt")
TABLE_PATH = "/rest/v1/yt_oauth_cookies"
DEFAULT_USER_ID = "darkxside"
VALID_STATUSES = {"success", "failed", "revoked"}


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
    """Decrypt Fernet-encrypted value. Raises RuntimeError on failure.

    CRITICAL: must NOT fall back to ciphertext — writing encrypted bytes
    as a cookie file corrupts yt-dlp's session and silently breaks the
    YT pipeline. Fail loud so the operator can diagnose key mismatch.
    """
    f = _get_fernet()
    if f is None:
        raise RuntimeError("Fernet unavailable — VAULT_ENC_KEY missing or cryptography not installed")
    if not value:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception as e:
        raise RuntimeError(f"Fernet decryption failed (VAULT_ENC_KEY mismatch?): {e}")


def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", os.environ.get("SUPA_REST_URL", "http://supabase-kong:8000"))
    # Strip trailing /rest/v1 to avoid duplicated path when combined with TABLE_PATH
    for suffix in ("/rest/v1/", "/rest/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url.rstrip("/")


def _supabase_headers() -> dict:
    key = os.environ.get("SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def fetch_and_write_cookies(user_id: str = DEFAULT_USER_ID) -> bool:
    """Fetch encrypted cookies + refresh token from Supabase, decrypt, write to disk.

    Writes the Netscape cookie file AND the plaintext refresh token to the
    shared volume. pmoves-yt reads the refresh token to call YouTube Data API
    v3 for metadata (works from datacenter IPs, unlike yt-dlp extraction).

    Returns True on success. Uses async httpx + atomic write (tmp + rename)
    so the yt-dlp per-request readers never see a torn cookie file.
    """
    url = f"{_supabase_url()}{TABLE_PATH}?user_id=eq.{user_id}&select=encrypted_cookies,encrypted_po_token,encrypted_refresh_token"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=_supabase_headers())
        rows = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        logger.error(f"Failed to fetch cookies from Supabase: {e}")
        return False

    if not rows or not rows[0].get("encrypted_cookies"):
        logger.warning("No cookies in Supabase — waiting for first refresh")
        return False

    try:
        cookies_str = _decrypt(rows[0]["encrypted_cookies"])
    except RuntimeError as e:
        logger.error(f"Decryption failed (will NOT write ciphertext to cookie file): {e}")
        return False

    if not cookies_str:
        logger.error("Decrypted cookie blob is empty — refusing to write")
        return False

    # Atomic write: tmp + rename. yt-dlp reads the cookiefile per-request so
    # a non-atomic write (file truncated mid-rewrite) would produce torn reads.
    output = Path(COOKIE_OUTPUT_PATH)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    try:
        tmp.write_text(cookies_str)
        tmp.replace(output)
    except OSError as e:
        logger.error(f"Cookie write failed: {e}")
        tmp.unlink(missing_ok=True)
        return False

    logger.info(f"Wrote {len(cookies_str)} bytes to {output} (atomic)")

    # Bridge the orphaned PO token: the refresher harvests it alongside cookies
    # but the writer previously discarded it. Writing it to the shared volume
    # lets pmoves-yt use the harvested token instead of relying solely on
    # bgutil-pot-provider's headless browser solver.
    enc_po = rows[0].get("encrypted_po_token")
    if enc_po:
        try:
            po_token = _decrypt(enc_po)
        except RuntimeError as e:
            logger.warning(f"PO token decryption failed (cookies still written): {e}")
            po_token = None

        if po_token and po_token.strip():
            po_output = Path(PO_TOKEN_OUTPUT_PATH)
            po_tmp = po_output.with_suffix(po_output.suffix + ".tmp")
            try:
                po_tmp.write_text(po_token.strip())
                po_tmp.replace(po_output)
                logger.info(f"Wrote PO token ({len(po_token)} bytes) to {po_output}")
            except OSError as e:
                logger.warning(f"PO token write failed (cookies still valid): {e}")
                po_tmp.unlink(missing_ok=True)

    # Write the decrypted OAuth refresh token so pmoves-yt can call YouTube
    # Data API v3 for IP-agnostic metadata enrichment.
    enc_refresh = rows[0].get("encrypted_refresh_token") if rows else None
    if enc_refresh:
        try:
            refresh_token = _decrypt(enc_refresh)
            if refresh_token:
                token_path = output.parent / "yt-refresh-token.txt"
                tmp_tok = token_path.with_suffix(".txt.tmp")
                tmp_tok.write_text(refresh_token.strip())
                tmp_tok.replace(token_path)
                logger.info(f"Wrote refresh token to {token_path}")
        except (RuntimeError, OSError) as e:
            logger.warning(f"Refresh token write failed: {e}")

    return True


async def _on_message(msg):
    """Handle ingest.cookies.refreshed.v1 NATS messages.

    Validates payload shape + user_id match before acting. Silently defaulting
    user_id would apply the wrong account's cookies in a multi-user setup.
    """
    try:
        data = json.loads(msg.data.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.warning(f"Malformed NATS payload on {NATS_SUBJECT}: {e}")
        return

    if not isinstance(data, dict):
        logger.warning(f"NATS payload is not an object: {type(data).__name__}")
        return

    status = data.get("status")
    if status not in VALID_STATUSES:
        logger.warning(f"NATS payload has invalid status={status!r}, expected one of {VALID_STATUSES}")
        return

    # Require explicit user_id — no silent default. If absent, skip the write.
    user_id = data.get("user_id")
    if not user_id or not isinstance(user_id, str):
        logger.warning("NATS payload missing/invalid user_id — skipping")
        return

    logger.info(f"Received {NATS_SUBJECT}: status={status}, user={user_id}")

    if status == "success":
        ok = await fetch_and_write_cookies(user_id)
        if ok:
            logger.info("Cookie file updated — pmoves-yt will pick up on next request")
        else:
            logger.warning("Cookie write failed — existing file left in place")
    else:
        logger.warning(f"Refresh reported status={status}, skipping write")


async def run() -> None:
    """Main event loop — connect to NATS, subscribe, wait."""
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
    logger.info(f"Connecting to NATS at {nats_url}")

    nc = await nats.connect(nats_url)
    await nc.subscribe(NATS_SUBJECT, cb=_on_message)
    logger.info(f"Subscribed to {NATS_SUBJECT}")

    # On startup, try to write existing cookies (catch-up after container restart)
    logger.info("Checking for existing cookies on startup...")
    await fetch_and_write_cookies()

    # Touch liveness marker so the Docker healthcheck knows we reached steady state
    try:
        Path("/tmp/healthy").touch()
    except OSError:
        pass

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
