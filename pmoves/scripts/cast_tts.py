#!/usr/bin/env python3
"""Cast TTS audio to Google Nest / Chromecast speakers via catt.

Usage:
    python scripts/cast_tts.py "Hello world"
    python scripts/cast_tts.py -d "Den speaker" "Good morning"
    python scripts/cast_tts.py -d "Speaker group" --list-devices
    python scripts/cast_tts.py -d "Brysons Speaker set" "Alert: deployment complete"

Requires: catt, Ultimate-TTS-Studio running on port 7861
"""
import argparse
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import json
import os

ULTIMATE_TTS_URL = os.environ.get("ULTIMATE_TTS_URL", "http://localhost:7861")
DEFAULT_DEVICE = os.environ.get("CAST_DEFAULT_DEVICE", "Den speaker")


def list_devices():
    """List available Cast devices on the LAN."""
    result = subprocess.run(["catt", "scan"], capture_output=True, text=True, timeout=15)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)


def cast_gtts_fallback(text: str, device: str):
    """Fallback: cast via Google Translate TTS (max ~200 chars, low quality)."""
    encoded = urllib.parse.quote(text[:200])
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en&q={encoded}"
    subprocess.run(["catt", "-d", device, "cast_site", url], check=True)


def cast_via_ultimate_tts(text: str, device: str):
    """Generate TTS via Ultimate-TTS-Studio API, then cast to speaker."""
    # Use Gradio client API to generate audio
    api_url = f"{ULTIMATE_TTS_URL}/gradio_api/call/synthesize"

    payload = json.dumps({
        "data": [text, "kokoro", "af_heart", 1.0]
    })

    try:
        req = urllib.request.Request(
            api_url,
            data=payload.encode(),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        event_id = result.get("event_id")

        if not event_id:
            print("Warning: Ultimate-TTS didn't return event_id, falling back to gTTS")
            cast_gtts_fallback(text, device)
            return

        # Poll for result
        stream_url = f"{ULTIMATE_TTS_URL}/gradio_api/call/synthesize/{event_id}"
        stream_resp = urllib.request.urlopen(stream_url, timeout=60)
        lines = stream_resp.read().decode().strip().split("\n")

        for i, line in enumerate(lines):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if isinstance(data, list) and len(data) > 0:
                    audio_info = data[0]
                    if isinstance(audio_info, dict) and "url" in audio_info:
                        audio_url = audio_info["url"]
                        if not audio_url.startswith("http"):
                            audio_url = f"{ULTIMATE_TTS_URL}{audio_url}"
                        print(f"Casting TTS audio to '{device}'...")
                        subprocess.run(["catt", "-d", device, "cast", audio_url], check=True)
                        return

        print("Warning: couldn't extract audio URL, falling back to gTTS")
        cast_gtts_fallback(text, device)

    except Exception as e:
        print(f"Ultimate-TTS unavailable ({e}), falling back to gTTS")
        cast_gtts_fallback(text, device)


def main():
    parser = argparse.ArgumentParser(description="Cast TTS to Nest/Chromecast speakers")
    parser.add_argument("text", nargs="?", help="Text to speak")
    parser.add_argument("-d", "--device", default=DEFAULT_DEVICE, help="Cast device name")
    parser.add_argument("--list-devices", action="store_true", help="List available Cast devices")
    parser.add_argument("--fallback", action="store_true", help="Use Google TTS fallback only")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    if not args.text:
        parser.error("Text argument required (or use --list-devices)")

    if args.fallback:
        cast_gtts_fallback(args.text, args.device)
    else:
        cast_via_ultimate_tts(args.text, args.device)


if __name__ == "__main__":
    main()
