#!/usr/bin/env python3
"""
PMOVES Danger Room — container-build theme player.

Plays an audio theme around Docker builds. The audio can come from:

1. A URL or local file via DANGER_ROOM_THEME_URL (downloaded/copied and played).
2. A Flute Gateway TTS synthesis via DANGER_ROOM_THEME_TEXT / ENGINE / PROVIDER.
3. A fallback spoken announcement if nothing else is configured.

The script is best-effort: it logs warnings but exits 0 so a build never fails
because of a missing audio player or unreachable gateway.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

FLUTE_GATEWAY_URL = os.getenv("FLUTE_GATEWAY_URL", "http://localhost:8055")

DEFAULT_TEXT = "Playing X-Men Animated Series Theme. Danger Room Active."
DEFAULT_PROVIDER = "ultimate_tts"
DEFAULT_ENGINE = "kitten_tts"


def _find_player() -> str | None:
    """Return the first available audio-player binary, or None."""
    for cmd in ("paplay", "aplay", "ffplay", "mpv"):
        if shutil.which(cmd):
            return cmd
    return None


def _play_file(path: Path) -> bool:
    player = _find_player()
    if not player:
        print("[!] No host audio player found (paplay/aplay/ffplay/mpv). Skipping playback.")
        return False

    cmd: list[str]
    if player == "ffplay":
        cmd = [player, "-nodisp", "-autoexit", str(path)]
    elif player == "mpv":
        cmd = [player, "--no-video", str(path)]
    else:
        cmd = [player, str(path)]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Audio player exited {e.returncode}: {player}")
        return False


def _synthesize_flute(text: str, provider: str, engine: str, dry_run: bool) -> Path | None:
    """Synthesize audio via Flute Gateway and return the path to the WAV file."""
    url = f"{FLUTE_GATEWAY_URL}/v1/voice/synthesize/audio"
    payload = {
        "text": text,
        "provider": provider,
        "engine": engine,
        "output_format": "wav",
    }

    if dry_run:
        print(f"[dry-run] Would POST to {url}: {payload}")
        return None

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if not data:
                print("[!] Flute Gateway returned empty audio.")
                return None
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(data)
            tmp.close()
            return Path(tmp.name)
    except urllib.error.URLError as e:
        print(f"[!] Flute Gateway unreachable: {e}. (Is it running on {FLUTE_GATEWAY_URL}?)")
        return None


def _fetch_url(source: str, dry_run: bool) -> Path | None:
    """Fetch a URL or copy a local file to a temp path."""
    if dry_run:
        print(f"[dry-run] Would fetch/copy theme source: {source}")
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".audio", delete=False)
    tmp.close()
    dest = Path(tmp.name)

    if source.startswith(("http://", "https://")):
        try:
            urllib.request.urlretrieve(source, dest)
            return dest
        except urllib.error.URLError as e:
            print(f"[!] Could not download theme: {e}")
            return None
    else:
        src = Path(source).expanduser()
        if not src.exists():
            print(f"[!] Theme file not found: {src}")
            return None
        shutil.copy2(src, dest)
        return dest


def _resolve_theme() -> tuple[str, str, str, str | None]:
    text = os.getenv("DANGER_ROOM_THEME_TEXT", DEFAULT_TEXT)
    provider = os.getenv("DANGER_ROOM_THEME_PROVIDER", DEFAULT_PROVIDER)
    engine = os.getenv("DANGER_ROOM_THEME_ENGINE", DEFAULT_ENGINE)
    url = os.getenv("DANGER_ROOM_THEME_URL") or None
    return text, provider, engine, url


def main() -> int:
    parser = argparse.ArgumentParser(description="Play the Danger Room build theme.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without playing audio.")
    parser.add_argument("--phase", default="start", choices=("start", "end"), help="Build phase cue.")
    args = parser.parse_args()

    text, provider, engine, url = _resolve_theme()

    if args.phase == "end":
        print("[+] Danger Room build complete.")
        return 0

    print("[*] Danger Room build starting. Dispatching theme...")

    audio_file: Path | None = None
    try:
        if url:
            print(f"[*] Theme source: {url}")
            audio_file = _fetch_url(url, args.dry_run)
        else:
            print(f"[*] Synthesizing via Flute: provider={provider} engine={engine}")
            audio_file = _synthesize_flute(text, provider, engine, args.dry_run)

        if args.dry_run:
            print("[dry-run] Theme dispatch complete.")
            return 0

        if audio_file:
            if _play_file(audio_file):
                print("[+] Theme playback complete.")
            try:
                audio_file.unlink(missing_ok=True)
            except OSError:
                pass
        else:
            print("[!] No audio produced; continuing build silently.")

    except Exception as e:  # noqa: BLE001 — best-effort audio must never break a build
        print(f"[!] Theme playback failed ({type(e).__name__}): {e}. Continuing build.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
