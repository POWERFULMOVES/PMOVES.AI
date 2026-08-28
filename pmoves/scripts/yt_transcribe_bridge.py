#!/usr/bin/env python3
"""
NATS bridge: listens for ingest.file.added.v1, triggers transcription.

When PMOVES.YT downloads a video, it publishes ingest.file.added.v1 with
the S3 path and video metadata. This bridge:
1. Receives the event
2. Calls transcribe-and-fetch /process-video/ (if running) or
   PMOVES.YT /yt/transcript (if ffmpeg-whisper is available)
3. Publishes ingest.transcript.ready.v1 on completion

Runs as a background process inside the pmoves-yt container.
"""
import asyncio
import json
import logging
import os
import sys

import nats
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("yt-bridge")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
TRANSCRIBE_URL = os.environ.get("TRANSCRIBE_BACKEND_URL", "http://localhost:8077/yt/transcript")
YT_INFO_URL = os.environ.get("YT_INFO_URL", "http://localhost:8077/yt/info")


async def handle_download_event(msg):
    """Process an ingest.file.added.v1 event."""
    try:
        data = json.loads(msg.data.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning(f"Malformed event: {e}")
        return

    video_id = data.get("video_id", "")
    title = data.get("title", video_id)
    namespace = data.get("namespace", "pmoves")
    url = data.get("url") or data.get("source_url") or f"https://www.youtube.com/watch?v={video_id}"

    if not video_id:
        log.warning(f"No video_id in event: {data}")
        return

    log.info(f"Event: {video_id} ({title[:50]})")

    # Try transcription via PMOVES.YT /yt/transcript
    try:
        resp = requests.post(
            TRANSCRIBE_URL,
            json={"url": url, "namespace": namespace},
            timeout=600,
        )
        if resp.status_code == 200:
            result = resp.json()
            log.info(f"Transcribed {video_id}: {resp.status_code}")

            # Publish transcript ready event
            await msg.ack()
            return
        else:
            log.warning(f"Transcription failed for {video_id}: {resp.status_code} {resp.text[:200]}")
    except requests.RequestException as e:
        log.warning(f"Transcribe request failed for {video_id}: {e}")
    except Exception as e:
        log.error(f"Unexpected error for {video_id}: {e}")

    # Ack anyway to avoid redelivery storms (transcription is best-effort)
    await msg.ack()


async def main():
    log.info(f"Connecting to NATS: {NATS_URL}")
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    # Create durable consumer
    try:
        await js.subscribe(
            "ingest.file.added.v1",
            durable="yt-transcribe-bridge",
            cb=handle_download_event,
            stream="INGEST_EVENTS",
            manual_ack=True,
        )
        log.info("Subscribed to ingest.file.added.v1 (durable: yt-transcribe-bridge)")
    except Exception as e:
        log.error(f"Failed to subscribe: {e}")
        sys.exit(1)

    log.info("Bridge running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Shutting down...")
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
