#!/usr/bin/env python3
"""
Flute TTS helper: text -> WAV (via Flute) -> MP3 -> base64.

Used by Make smoketests so Discord voice-agent publishes never upload empty audio.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _post_json_bytes(url: str, payload: dict, api_key: str, timeout_s: float) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flute-url", default=_env("FLUTE_BASE_URL", "http://localhost:8055").rstrip("/"))
    parser.add_argument("--provider", default="vibevoice")
    parser.add_argument("--voice", default="")
    parser.add_argument("--retries", type=int, default=int(_env("FLUTE_TTS_RETRIES", "5")))
    parser.add_argument("--timeout", type=float, default=float(_env("FLUTE_TTS_TIMEOUT_S", "180")))
    parser.add_argument("--min-mp3-bytes", type=int, default=int(_env("FLUTE_TTS_MIN_MP3_BYTES", "1024")))
    parser.add_argument("text")
    args = parser.parse_args()

    api_key = _env("FLUTE_API_KEY", "")
    url = f"{args.flute_url}/v1/voice/synthesize/audio"
    payload = {
        "text": args.text,
        "provider": args.provider,
        "voice": (args.voice or None),
        "output_format": "wav",
    }

    last_exc: Exception | None = None
    wav: bytes | None = None
    for attempt in range(1, max(1, args.retries) + 1):
        try:
            wav = _post_json_bytes(url, payload, api_key=api_key, timeout_s=args.timeout)
            break
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (502, 503) and attempt < args.retries:
                time.sleep(0.35 * attempt)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < args.retries:
                time.sleep(0.35 * attempt)
                continue
            raise

    if wav is None:
        raise last_exc or RuntimeError("No WAV bytes received")
    if len(wav) <= 44:
        raise RuntimeError(f"Empty WAV from Flute ({len(wav)} bytes)")

    mp3 = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-f", "mp3", "pipe:1"],
        input=wav,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    if len(mp3) < args.min_mp3_bytes:
        raise RuntimeError(f"MP3 too small ({len(mp3)} bytes)")

    print(base64.b64encode(mp3).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

