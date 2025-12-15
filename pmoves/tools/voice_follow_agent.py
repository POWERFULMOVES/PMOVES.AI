#!/usr/bin/env python3
"""
Voice Follow (host-run)

Subscribes to NATS for agent/voice responses and forwards text to the local
voice-speaker so the operator hears replies in realtime.

Default subjects:
  - voice.agent.response.v1
  - agent.response.v1

Config via env:
  - NATS_URL (default: nats://localhost:4222)
  - VOICE_FOLLOW_SUBJECTS (comma-separated)
  - VOICE_SPEAKER_URL (default: http://127.0.0.1:8120)
  - VOICE_SPEAKER_MODE (stream|batch, default: stream)
  - VOICE_SPEAKER_VOICE (optional)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests
from nats.aio.client import Client as NATS


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _extract_text(payload: Dict[str, Any]) -> Optional[str]:
    # Common envelope shapes in this repo:
    #  - {"payload":{"response_text":"..."}} (voice.agent.response.v1)
    #  - {"response_text":"..."} or {"text":"..."} for looser publishers
    inner = payload.get("payload")
    if isinstance(inner, dict):
        for key in ("response_text", "text", "content", "message"):
            val = inner.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    for key in ("response_text", "text", "content", "message"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def speak(text: str) -> None:
    speaker_url = _env("VOICE_SPEAKER_URL", "http://127.0.0.1:8120").rstrip("/")
    mode = _env("VOICE_SPEAKER_MODE", "stream")
    voice = os.getenv("VOICE_SPEAKER_VOICE") or None
    try:
        resp = requests.post(
            f"{speaker_url}/say",
            json={"text": text, "mode": mode, "voice": voice},
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as e:
        sys.stderr.write(f"[voice-follow] speaker POST failed: {type(e).__name__}: {e}\n")


async def run() -> None:
    nats_url = _env("NATS_URL", "nats://localhost:4222")
    subjects = _env("VOICE_FOLLOW_SUBJECTS", "voice.agent.response.v1,agent.response.v1")
    subject_list = [s.strip() for s in subjects.split(",") if s.strip()]

    nc = NATS()
    await nc.connect(nats_url)
    sys.stderr.write(f"✔ voice-follow connected to {nats_url}\n")
    sys.stderr.write(f"  ↳ subjects: {', '.join(subject_list)}\n")

    async def handler(msg) -> None:
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        text = _extract_text(data)
        if not text:
            return
        # Avoid spamming super long content into TTS
        if len(text) > 800:
            text = text[:800].rstrip() + "…"
        speak(text)

    for subj in subject_list:
        await nc.subscribe(subj, cb=handler)

    while True:
        await nc.flush()
        await nc._client._loop.run_in_executor(None, time.sleep, 1)  # type: ignore[attr-defined]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="voice_follow_agent")
    parser.add_argument("--once", action="store_true", help="Exit after first spoken message")
    args = parser.parse_args(argv)
    # --once is not implemented yet; keep interface stable for make targets.
    if args.once:
        sys.stderr.write("✖ --once not implemented; run without it.\n")
        return 2
    import asyncio

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

