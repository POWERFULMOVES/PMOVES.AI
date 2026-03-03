#!/usr/bin/env python3
"""Cross-platform smoke for voice-agent -> publisher-discord flow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _validate_http_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme for smoke request: {url}")


def _request_json(url: str, payload: dict | None = None, timeout: float = 20.0) -> tuple[int, dict]:
    _validate_http_url(url)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") if resp.length != 0 else "{}"
        return int(resp.status), json.loads(raw)


def _tts_to_mp3_b64(text: str) -> str:
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "flute_tts_to_mp3_b64.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), text],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("flute_tts_to_mp3_b64 timed out after 60s") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"flute_tts_to_mp3_b64 failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-url", default="http://localhost:5678/webhook/voice-agent/ingest")
    parser.add_argument("--discord-url", default="http://localhost:8094/publish")
    args = parser.parse_args()
    try:
        _validate_http_url(args.voice_url)
        _validate_http_url(args.discord_url)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    print("[Voice->Discord] Trigger voice agent via n8n webhook")
    try:
        code, payload = _request_json(
            args.voice_url,
            {
                "platform": "local",
                "user_id": "smoke",
                "user_name": "Smoke",
                "message_type": "text",
                "content": "Give a 1-sentence greeting for Discord.",
            },
        )
    except urllib.error.URLError as exc:
        print(f"FAIL: voice agent webhook unreachable: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: voice agent request failed: {exc}")
        return 1

    if code != 200:
        print(f"FAIL: voice agent webhook returned HTTP {code}: {payload}")
        return 1

    text = str(payload.get("response_text", "")).strip()
    if not text:
        print(f"FAIL: no response_text from voice agent: {payload}")
        return 1
    if "could not generate a response" in text.lower():
        print(f"FAIL: voice agent fallback response returned: {payload}")
        return 1

    short = text[:1800] + ("..." if len(text) > 1800 else "")

    print("[Voice->Discord] Generating TTS (mp3) via Flute")
    try:
        tts_b64 = _tts_to_mp3_b64(short)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: TTS generation failed: {exc}")
        return 1

    publish_payload = {
        "content": f"\U0001F5E3\uFE0F Voice Agent (smoke)\n\n{short}",
        "embeds": [
            {
                "title": "Voice Agent Smoke",
                "description": short,
                "color": 3447003,
            }
        ],
        "file": {
            "name": "voice_agent_smoke.mp3",
            "content_type": "audio/mpeg",
            "content_b64": tts_b64,
        },
    }

    print("[Voice->Discord] Publishing to publisher-discord")
    try:
        code, publish_resp = _request_json(args.discord_url, publish_payload)
    except urllib.error.URLError as exc:
        print(f"FAIL: publisher-discord unreachable: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: publish request failed: {exc}")
        return 1

    if code != 200 or not (publish_resp.get("ok") is True or publish_resp.get("success") is True):
        print(f"FAIL: Discord publish failed (HTTP {code}): {publish_resp}")
        return 1

    print("PASS: voice-agent-discord smoke complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
