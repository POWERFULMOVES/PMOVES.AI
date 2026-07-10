#!/usr/bin/env python3
"""
voice_cast_on_sign.py -- CHIT-sign-triggered expressive voice (Phase 0).

The ONLY listener on ``chit.signed.v1``. An agent's normal CHIT trail-sign
(``pmoves/tools/sign_trail.py`` with ``CHIT_SIGN_PUBLISH=1``) becomes an
audible, persona-shaped utterance -- with NO speak tool call anywhere in the
pipeline. See ``pmoves/tools/VOICE_CAST_ON_SIGN.md`` for the full flow.

Pipeline per message:
    1. JSON-decode the ``agent.graphiti.signed.v1`` payload.
    2. ``text = payload["summary"]`` (already <=200 chars per sign_trail.py).
    3. ``voice_persona_bridge.resolve(payload)`` -> intent + persona_id
       (FlOO$ suit mapping, e.g. mr-clean -> dramatic/chatterbox).
    4. Deterministic health check against Flute-Gateway; if the expressive
       engines are unavailable, fall back to intent="narrate" (kokoro CPU
       floor) so the pipeline stays audible even without GPU.
    5. POST to Flute-Gateway ``/v1/voice/synthesize/audio`` -> WAV bytes.
    6. Optional ffmpeg atempo tempo recovery (bpm/tempo field or
       intent=bpm_sync) -- expressive engines lack native tempo control.
    7. Write ``pmoves/out/voice_cast_<ts>.wav`` and attempt host playback
       (both best-effort; never crash the daemon).

Modeled on ``pmoves/tools/voice_follow_cast_agent.py`` (NATS URL resolution,
subscribe/handler/daemon-loop structure).

CLI:
    python pmoves/tools/voice_cast_on_sign.py --subjects chit.signed.v1

Config via env:
    NATS_URL / VOICE_CAST_NATS_URL -- NATS connection URL
    FLUTE_GATEWAY_URL              -- default http://localhost:8055
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from nats.aio.client import Client as NATS

# Sibling module import (same directory) -- Phase 0 persona bridge.
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from voice_persona_bridge import resolve as resolve_persona  # noqa: E402

_PMOVES_ROOT = _TOOLS_DIR.parent
_OUT_DIR = _PMOVES_ROOT / "out"

DEFAULT_SUBJECTS = ["chit.signed.v1"]
DEFAULT_NATS_URL = "nats://nats:pmoves@nats:4222"
FALLBACK_INTENT = "narrate"  # kokoro CPU floor -- always available without GPU
# Baseline tempo reference (BPM "moderato"/phrase level per shift-from-bpm skill).
_BPM_BASELINE = 120.0
_ATEMPO_MIN, _ATEMPO_MAX = 0.5, 2.0


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _resolve_nats_url() -> str:
    """Resolve NATS URL for host-run service.

    Handles Docker-internal URLs by translating them to host-accessible URLs.
    Same pattern as ``voice_follow_cast_agent._resolve_nats_url()``.
    """
    explicit = os.getenv("VOICE_CAST_NATS_URL")
    if explicit and explicit.strip():
        return explicit.strip()

    nats_url = os.getenv("NATS_URL", "").strip()
    if nats_url:
        if nats_url.startswith("nats://nats:") or nats_url.startswith("tls://nats:"):
            return DEFAULT_NATS_URL
        if nats_url.startswith("nats://localhost:") or nats_url.startswith("tls://localhost:"):
            return nats_url.replace("://localhost:", "://127.0.0.1:", 1)
        return nats_url

    return DEFAULT_NATS_URL


def _compute_atempo_ratio(payload: Dict[str, Any], intent: str) -> Optional[float]:
    """Return an ffmpeg ``atempo`` ratio if the payload/intent implies a tempo.

    Priority: explicit ``tempo_ratio`` field -> ``bpm``/``tempo`` field
    (normalized against the 120 BPM "moderato" baseline) -> None (no tempo
    recovery needed). Clamped to ffmpeg's single-filter ``atempo`` range
    (0.5-2.0) -- values outside that need chained filters, out of scope here.
    """
    tempo_ratio = payload.get("tempo_ratio")
    if isinstance(tempo_ratio, (int, float)) and tempo_ratio > 0:
        return max(_ATEMPO_MIN, min(_ATEMPO_MAX, float(tempo_ratio)))

    bpm = payload.get("bpm") or payload.get("tempo")
    if isinstance(bpm, (int, float)) and bpm > 0:
        ratio = float(bpm) / _BPM_BASELINE
        return max(_ATEMPO_MIN, min(_ATEMPO_MAX, ratio))

    if intent == "bpm_sync":
        # bpm_sync requested but no explicit bpm/tempo/tempo_ratio field --
        # nothing to recover against, skip.
        return None

    return None


def _apply_atempo(in_path: Path, ratio: float) -> Optional[Path]:
    """Run ``ffmpeg -filter:a atempo=<ratio>`` on in_path. Best-effort.

    Returns the tempo-adjusted file path, or None if ffmpeg is missing or
    the conversion fails (caller falls back to the untouched WAV).
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.stderr.write(
            "[voice-cast-on-sign] ffmpeg not found on PATH -- skipping tempo recovery\n"
        )
        return None

    out_path = in_path.with_name(in_path.stem + "_tempo" + in_path.suffix)
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", str(in_path),
                "-filter:a", f"atempo={ratio:.3f}",
                str(out_path),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        sys.stderr.write(
            f"[voice-cast-on-sign] tempo recovery applied (atempo={ratio:.3f}) -> {out_path.name}\n"
        )
        return out_path
    except Exception as exc:
        sys.stderr.write(f"[voice-cast-on-sign] ffmpeg atempo failed (skipping): {exc}\n")
        return None


def _play_audio(path: Path) -> None:
    """Best-effort host playback. Never raises -- a silent failure is fine."""
    try:
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", str(path)])
        else:
            player = shutil.which("aplay") or shutil.which("paplay") or shutil.which("ffplay")
            if player:
                args = [player, str(path)]
                if player.endswith("ffplay"):
                    args = [player, "-nodisp", "-autoexit", "-loglevel", "error", str(path)]
                subprocess.Popen(args)
            else:
                sys.stderr.write(
                    "[voice-cast-on-sign] No audio player found (aplay/paplay/ffplay) -- "
                    "audio saved but not played\n"
                )
    except Exception as exc:
        sys.stderr.write(f"[voice-cast-on-sign] Playback failed (audio saved to disk): {exc}\n")


class VoiceCastOnSign:
    """Subscribes to signed CHIT trails and casts them as expressive speech."""

    def __init__(self, nats_url: str, flute_gateway_url: str) -> None:
        self.nats_url = nats_url
        self.flute_gateway_url = flute_gateway_url.rstrip("/")
        self.nc: Optional[NATS] = None
        self.running = False

    async def _check_flute_health(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        """Deterministic health check. Returns the /healthz JSON, or None if unreachable.

        Never raises -- an unreachable Flute-Gateway/GPU stack is expected in
        dev/CI and must not crash the daemon.
        """
        try:
            resp = await client.get(f"{self.flute_gateway_url}/healthz", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            sys.stderr.write(
                f"[voice-cast-on-sign] Flute-Gateway health check failed: {exc}\n"
            )
        return None

    async def _synthesize(
        self, client: httpx.AsyncClient, text: str, intent: str, persona_id: Optional[str]
    ) -> Optional[bytes]:
        """POST to /v1/voice/synthesize/audio. Returns WAV bytes or None."""
        url = f"{self.flute_gateway_url}/v1/voice/synthesize/audio"
        body: Dict[str, Any] = {"text": text, "intent": intent}
        if persona_id:
            body["persona_id"] = persona_id
        try:
            resp = await client.post(url, json=body, timeout=60.0)
            if resp.status_code == 200:
                return resp.content
            sys.stderr.write(
                f"[voice-cast-on-sign] Flute-Gateway synthesis failed: "
                f"HTTP {resp.status_code} — {resp.text[:200]}\n"
            )
        except Exception as exc:
            sys.stderr.write(f"[voice-cast-on-sign] Flute-Gateway synthesis error: {exc}\n")
        return None

    async def handle_signed_trail(self, msg) -> None:
        """Handle a chit.signed.v1 message end-to-end. Never raises."""
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception as exc:
            sys.stderr.write(f"[voice-cast-on-sign] Malformed payload (skipping): {exc}\n")
            return

        if not isinstance(payload, dict):
            return

        text = payload.get("summary")
        if not text or not isinstance(text, str):
            sys.stderr.write(
                "[voice-cast-on-sign] Signed trail has no 'summary' text -- skipping\n"
            )
            return

        bridge = resolve_persona(payload)
        intent = bridge["intent"]
        persona_id = bridge["persona_id"]

        agent_id = payload.get("agent_id", "?")
        alter = payload.get("selected_alter") or payload.get("voice") or "default"
        sys.stderr.write(
            f"[voice-cast-on-sign] {agent_id} ({alter}) -> intent={intent} "
            f"persona_id={persona_id}: {text[:120]}\n"
        )

        async with httpx.AsyncClient() as client:
            health = await self._check_flute_health(client)
            if health is None:
                sys.stderr.write(
                    "[voice-cast-on-sign] Flute-Gateway unreachable -- skipping this "
                    "utterance (deterministic health check, daemon stays up)\n"
                )
                return

            providers = health.get("providers", {}) if isinstance(health, dict) else {}
            expressive_ready = bool(providers.get("ultimate_tts") or providers.get("omnivoice"))
            if not expressive_ready:
                sys.stderr.write(
                    "[voice-cast-on-sign] No expressive TTS provider healthy -- "
                    f"falling back to intent={FALLBACK_INTENT!r} (kokoro CPU floor)\n"
                )
                intent = FALLBACK_INTENT

            wav_bytes = await self._synthesize(client, text, intent, persona_id)
            if not wav_bytes:
                return

            _OUT_DIR.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            out_path = _OUT_DIR / f"voice_cast_{ts}.wav"
            try:
                out_path.write_bytes(wav_bytes)
            except Exception as exc:
                sys.stderr.write(f"[voice-cast-on-sign] Failed to write {out_path}: {exc}\n")
                return
            sys.stderr.write(f"[voice-cast-on-sign] Saved {out_path}\n")

            # Optional ffmpeg atempo tempo recovery (best-effort).
            ratio = _compute_atempo_ratio(payload, intent)
            play_path = out_path
            if ratio is not None and abs(ratio - 1.0) > 1e-3:
                tempo_path = _apply_atempo(out_path, ratio)
                if tempo_path is not None:
                    play_path = tempo_path

            _play_audio(play_path)

    async def run(self, subjects: list[str]) -> None:
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        sys.stderr.write(f"[voice-cast-on-sign] connected to {self.nats_url}\n")
        sys.stderr.write(f"[voice-cast-on-sign] subjects: {', '.join(subjects)}\n")
        sys.stderr.write(f"[voice-cast-on-sign] flute_gateway: {self.flute_gateway_url}\n")

        self.running = True

        async def _handler(msg):
            if not self.running:
                return
            await self.handle_signed_trail(msg)

        for subj in subjects:
            await self.nc.subscribe(subj, cb=_handler)

        while self.running:
            await asyncio.sleep(1)

        await self.nc.drain()

    async def stop(self) -> None:
        self.running = False


async def main_async(subjects: list[str]) -> None:
    nats_url = _resolve_nats_url()
    flute_gateway_url = _env("FLUTE_GATEWAY_URL", "http://localhost:8055")

    agent = VoiceCastOnSign(nats_url=nats_url, flute_gateway_url=flute_gateway_url)
    await agent.run(subjects)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="voice_cast_on_sign",
        description=(
            "Subscribe to chit.signed.v1 and cast CHIT trail-signs as expressive "
            "speech via Flute-Gateway (Phase 0 -- no speak tool call)."
        ),
    )
    parser.add_argument(
        "--subjects",
        type=str,
        default=None,
        help=f"Comma-separated NATS subjects (default: {','.join(DEFAULT_SUBJECTS)})",
    )
    args = parser.parse_args(argv)

    if args.subjects:
        subjects = [s.strip() for s in args.subjects.split(",") if s.strip()]
    else:
        subjects = list(DEFAULT_SUBJECTS)

    try:
        asyncio.run(main_async(subjects))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice-cast-on-sign] Shutting down...\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
