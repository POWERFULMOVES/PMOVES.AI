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
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

import requests
from nats.aio.client import Client as NATS


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _resolve_nats_url() -> str:
    """
    Host-run default should connect to the published NATS port.

    env.shared often sets NATS_URL=nats://nats:4222 (valid inside Docker, invalid on host).
    Also, localhost may resolve to ::1 first on some systems while NATS only binds IPv4.
    """
    explicit = os.getenv("VOICE_FOLLOW_NATS_URL")
    if explicit and explicit.strip():
        return explicit.strip()

    nats_url = os.getenv("NATS_URL", "").strip()
    if nats_url:
        # Ignore docker-only alias when running on host.
        if nats_url.startswith("nats://nats:") or nats_url.startswith("tls://nats:"):
            return "nats://127.0.0.1:4222"
        if nats_url.startswith("nats://localhost:") or nats_url.startswith("tls://localhost:"):
            return nats_url.replace("://localhost:", "://127.0.0.1:", 1)
        return nats_url

    return "nats://127.0.0.1:4222"


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
    # Default to batch for reliability (streaming can be choppy depending on TTS backend / host load).
    mode = _env("VOICE_SPEAKER_MODE", "batch")
    voice = os.getenv("VOICE_SPEAKER_VOICE") or None
    try:
        resp = requests.post(
            f"{speaker_url}/say",
            json={"text": text, "mode": mode, "voice": voice},
            timeout=5,
        )
        resp.raise_for_status()
        try:
            obj = resp.json()
        except Exception:
            obj = None
        if isinstance(obj, dict):
            sys.stderr.write(f"[voice-follow] spoke ok mode={obj.get('mode')}\n")
        else:
            sys.stderr.write("[voice-follow] spoke ok\n")
    except Exception as e:
        sys.stderr.write(f"[voice-follow] speaker POST failed: {type(e).__name__}: {e}\n")


async def run(stop_after_one: bool) -> None:
    nats_url = _resolve_nats_url()
    subjects = _env("VOICE_FOLLOW_SUBJECTS", "voice.agent.response.v1,agent.response.v1")
    subject_list = [s.strip() for s in subjects.split(",") if s.strip()]

    nc = NATS()
    await nc.connect(nats_url)
    sys.stderr.write(f"✔ voice-follow connected to {nats_url}\n")
    sys.stderr.write(f"  ↳ subjects: {', '.join(subject_list)}\n")

    done = asyncio.Event()

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
        sys.stderr.write(f"[voice-follow] {msg.subject}: {text[:140]}\n")
        speak(text)
        if stop_after_one:
            done.set()

    for subj in subject_list:
        await nc.subscribe(subj, cb=handler)

    if stop_after_one:
        await done.wait()
        await nc.drain()
        return

    # Daemon mode: sleep forever and let callbacks fire.
    while True:
        await asyncio.sleep(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="voice_follow_agent")
    parser.add_argument("--once", action="store_true", help="Exit after first spoken message")
    args = parser.parse_args(argv)
    asyncio.run(run(stop_after_one=bool(args.once)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
