"""NATS publisher for cookie refresh events."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import nats

logger = logging.getLogger("yt-cookie-refresher.nats")

SUBJECT = "ingest.cookies.refreshed.v1"


async def publish_cookies_refreshed(
    user_id: str = "darkxside",
    status: str = "success",
    error: str = "",
) -> None:
    """Publish ingest.cookies.refreshed.v1 event to NATS."""
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")

    try:
        nc = await nats.connect(nats_url)
        payload = {
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error if error else None,
        }
        await nc.publish(SUBJECT, json.dumps(payload).encode())
        await nc.flush()
        await nc.close()
        logger.info(f"Published {SUBJECT}: status={status}")
    except Exception as e:
        logger.error(f"Failed to publish {SUBJECT}: {e}")
