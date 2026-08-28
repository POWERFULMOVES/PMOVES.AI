#!/usr/bin/env python3
"""End-to-end creator pipeline test: Flute-Gateway voice → Discord attachment.

Two modes:
1. Live mode (default): synthesize via Flute-Gateway prosodic endpoint, post WAV to Discord
2. Synthetic mode (--synthetic): generate a sine wave WAV, post to Discord
   (proves the Discord attachment path works even if TTS backend is offline)

Usage:
    python pmoves/tools/voice_to_discord_test.py             # live mode
    python pmoves/tools/voice_to_discord_test.py --synthetic # synthetic mode
"""
import argparse
import base64
import io
import json
import math
import struct
import sys
import urllib.error
import urllib.request
import wave


FLUTE_URL = "http://127.0.0.1:8055/v1/voice/synthesize/prosodic"
DISCORD_URL = "http://127.0.0.1:8094/publish"
TEST_TEXT = (
    "Hello from PMOVES AI. This is an end-to-end creator pipeline test. "
    "Voice was synthesized via Flute-Gateway prosodic endpoint and posted "
    "to Discord as an audio attachment."
)


def synthesize_live() -> bytes:
    """Call Flute-Gateway prosodic endpoint and return WAV bytes."""
    req = urllib.request.Request(
        FLUTE_URL,
        data=json.dumps({
            "text": TEST_TEXT,
            "engine": "kokoro",
            "provider": "ultimate_tts",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio = resp.read()
            chunks = resp.headers.get("X-Prosodic-Chunks", "?")
            bpm = resp.headers.get("X-Prosodic-BPM", "?")
            print(f"  Synthesized: {len(audio)} bytes, {chunks} chunks, {bpm} BPM avg")
            return audio
    except urllib.error.HTTPError as exc:
        print(f"  Flute-Gateway error: HTTP {exc.code}")
        raise


def synthesize_synthetic() -> bytes:
    """Generate a 2-second 440 Hz sine wave WAV."""
    sample_rate = 22050
    duration = 2.0
    freq = 440.0
    amplitude = 16000

    samples = []
    for i in range(int(sample_rate * duration)):
        value = int(amplitude * math.sin(2.0 * math.pi * freq * i / sample_rate))
        samples.append(struct.pack("<h", value))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(samples))
    audio = buf.getvalue()
    print(f"  Synthetic WAV: {len(audio)} bytes ({duration}s, {freq} Hz sine wave)")
    return audio


def post_to_discord(audio_bytes: bytes, label: str) -> dict:
    """Post audio attachment to publisher-discord /publish endpoint."""
    payload = {
        "content": f"PMOVES creator pipeline test: {label}",
        "file": {
            "name": "pmoves_voice_test.wav",
            "content_type": "audio/wav",
            "content_b64": base64.b64encode(audio_bytes).decode("ascii"),
        },
    }
    req = urllib.request.Request(
        DISCORD_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"  Discord POST: HTTP {resp.status} -> {result}")
            return result
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"  Discord error: HTTP {exc.code} -> {body}")
        raise


def main() -> int:
    """Run the end-to-end creator pipeline test."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic sine wave instead of live TTS")
    args = parser.parse_args()

    mode = "synthetic sine wave" if args.synthetic else "Flute-Gateway live synthesis"
    print(f"=== Creator Pipeline Test ({mode}) ===")

    print("1. Generating audio...")
    if args.synthetic:
        audio = synthesize_synthetic()
        label = "synthetic 440Hz sine (TTS backend path test)"
    else:
        audio = synthesize_live()
        label = "Kokoro prosodic synthesis"

    print(f"2. Posting to publisher-discord ({len(audio) / 1024:.1f} KB)...")
    result = post_to_discord(audio, label)

    if result.get("ok"):
        print("SUCCESS: creator pipeline end-to-end verified")
        return 0
    print("FAIL: creator pipeline test")
    return 1


if __name__ == "__main__":
    sys.exit(main())
