#!/usr/bin/env python3
"""
voice_cast_on_sign.py -- CHIT-sign-triggered expressive voice (Phase 0).

Listens on ``agent.graphiti.signed.v1`` (the canonical RAW signature.v1
subject -- NOT the multi-consumer ``chit.signed.v1`` production channel). An
agent's normal CHIT trail-sign (``pmoves/tools/sign_trail.py`` with
``CHIT_SIGN_PUBLISH=1``) becomes an audible, persona-shaped utterance -- with
NO speak tool call anywhere in the pipeline. A payload discriminator (glyph +
agent_id) ensures only genuine signature.v1 payloads are voice-cast, never a
stray envelope. See ``pmoves/tools/VOICE_CAST_ON_SIGN.md`` for the full flow.

Pipeline per message:
    1. JSON-decode the ``agent.graphiti.signed.v1`` payload.
    2. ``text = payload["summary"]`` (already <=200 chars per sign_trail.py).
    3. ``voice_persona_bridge.resolve(payload)`` -> intent + persona_id
       (FlOO$ suit mapping, e.g. mr-clean -> dramatic/chatterbox).
    4. Deterministic health check against Flute-Gateway. If it's unreachable,
       OR reachable but no expressive provider (ultimate_tts/omnivoice) is
       healthy, fall back to the STANDALONE Kokoro CPU-floor deploy unit
       (``pmoves/services/kokoro-tts``, #2024) at ``KOKORO_URL`` -- a
       genuinely independent process, not a route through the same
       Flute-Gateway/ultimate_tts stack that just failed (5090-CLAUDE
       pair-review PR #2048, finding #4).
    5. POST to Flute-Gateway ``/v1/voice/synthesize/audio`` (expressive path)
       or the Kokoro deploy unit's ``POST /synthesize`` (CPU-floor path) ->
       WAV bytes.
    6. Optional ffmpeg atempo tempo recovery (bpm/tempo field or
       intent=bpm_sync) -- expressive engines lack native tempo control.
    7. Write ``pmoves/out/voice_cast_<ts>.wav`` and attempt host playback
       (both best-effort; never crash the daemon). The intermediate
       ``*_tempo.wav`` (if tempo recovery ran) is cleaned up after playback;
       the primary cast WAV is left in place (gitignored ``/out/``).

Modeled on ``pmoves/tools/voice_follow_cast_agent.py`` (NATS URL resolution,
subscribe/handler/daemon-loop structure).

CLI:
    python pmoves/tools/voice_cast_on_sign.py --subjects agent.graphiti.signed.v1

Config via env (see VOICE_CAST_ON_SIGN.md for the full reference):
    NATS_URL / VOICE_CAST_NATS_URL -- NATS connection URL (host default:
                                       localhost -- the Docker-internal `nats`
                                       hostname only resolves inside the
                                       compose network; containers should pass
                                       NATS_URL explicitly)
    FLUTE_GATEWAY_URL              -- default http://localhost:8055
    FLUTE_API_KEY                  -- X-API-Key for the Flute-Gateway synth endpoint
    KOKORO_URL                     -- standalone Kokoro CPU-floor unit, default http://localhost:8004
    KOKORO_TOKEN                   -- X-Kokoro-Token for the Kokoro unit (optional)
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
import wave
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

DEFAULT_SUBJECTS = ["agent.graphiti.signed.v1"]  # raw signature.v1 subject, NOT the multi-consumer chit.signed.v1
# Host default -- this daemon is designed to run on the host (see module docstring),
# and the Docker-internal hostname `nats` only resolves inside the compose network
# (fails opaquely from a host shell). Containers running this inside the compose
# network must pass NATS_URL=nats://nats:pmoves@nats:4222 explicitly (5090-CLAUDE
# pair-review PR #2048, finding #6).
DEFAULT_NATS_URL = "nats://nats:pmoves@127.0.0.1:4222"
FALLBACK_INTENT = "narrate"  # kokoro CPU floor -- always available without GPU
DEFAULT_KOKORO_URL = "http://localhost:8004"  # standalone Kokoro CPU-floor deploy unit (#2024)
# Baseline tempo reference (BPM "moderato"/phrase level per shift-from-bpm skill).
_BPM_BASELINE = 120.0
_ATEMPO_MIN, _ATEMPO_MAX = 0.5, 2.0


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _resolve_nats_url() -> str:
    """Resolve NATS URL for host-run service.

    Handles Docker-internal URLs by translating them to host-accessible URLs
    (DEFAULT_NATS_URL targets 127.0.0.1 -- the docker `nats` hostname doesn't
    resolve on the host, and `localhost` may resolve to ::1 while NATS binds
    IPv4 only). Same pattern as ``voice_follow_cast_agent._resolve_nats_url()``.
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


def _estimate_wav_seconds(path: Path, default: float = 3.0) -> float:
    """Best-effort WAV duration (frames / rate). Returns ``default`` on any error.

    Used to size the delay before cleaning up an intermediate atempo temp file
    -- playback below is fire-and-forget (SND_ASYNC / Popen), so we must not
    delete the file before the player has finished reading it.
    """
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate() or 1
            return frames / float(rate)
    except Exception:
        return default


def _play_audio(path: Path) -> None:
    """Best-effort host playback. Never raises -- a silent failure is fine.

    NOTE: playback is fire-and-forget (winsound SND_ASYNC / subprocess.Popen) --
    it does not block the daemon, but that also means rapid successive signed
    trails can overlap audibly. A simple guard (await playback completion, or a
    lock serializing casts) would fix this; left as-is for Phase 0 since it's a
    nice-to-have, not a correctness issue (5090-CLAUDE pair-review PR #2048,
    finding #7).
    """
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

    def __init__(self, nats_url: str, flute_gateway_url: str, kokoro_url: str) -> None:
        self.nats_url = nats_url
        self.flute_gateway_url = flute_gateway_url.rstrip("/")
        self.nc: Optional[NATS] = None
        self.running = False
        # Synth endpoint sits behind verify_api_key on fleet nodes (skips only when
        # FLUTE_API_KEY is unset). Send it when present, else calls 401 silently
        # (5090-CLAUDE pair-review PR #2048, finding #3).
        self.api_key = _env("FLUTE_API_KEY", "")
        # Standalone Kokoro CPU-floor deploy unit (#2024) -- the genuinely
        # independent fallback when Flute-Gateway/ultimate_tts is unreachable
        # or unhealthy (5090-CLAUDE pair-review PR #2048, finding #4).
        self.kokoro_url = kokoro_url.rstrip("/")
        self.kokoro_token = _env("KOKORO_TOKEN", "")

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
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        try:
            resp = await client.post(url, json=body, headers=headers, timeout=60.0)
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 401:
                sys.stderr.write(
                    "[voice-cast-on-sign] Flute-Gateway 401 Unauthorized — set FLUTE_API_KEY "
                    "(the synth endpoint is behind verify_api_key on fleet nodes)\n"
                )
            else:
                sys.stderr.write(
                    f"[voice-cast-on-sign] Flute-Gateway synthesis failed: "
                    f"HTTP {resp.status_code} — {resp.text[:200]}\n"
                )
        except Exception as exc:
            sys.stderr.write(f"[voice-cast-on-sign] Flute-Gateway synthesis error: {exc}\n")
        return None

    async def _synthesize_kokoro_fallback(
        self, client: httpx.AsyncClient, text: str
    ) -> Optional[bytes]:
        """POST directly to the standalone Kokoro CPU-floor deploy unit (#2024).

        Genuinely independent of Flute-Gateway/ultimate_tts -- a separate
        process (``pmoves/services/kokoro-tts``, port 8004 by default) that
        stays up even when the GPU-hosted expressive stack is down. Used when
        the Flute-Gateway health check fails OR reports no expressive
        provider healthy (5090-CLAUDE pair-review PR #2048, finding #4).
        Best-effort: never raises.
        """
        url = f"{self.kokoro_url}/synthesize"
        headers = {"X-Kokoro-Token": self.kokoro_token} if self.kokoro_token else {}
        try:
            resp = await client.post(
                url,
                json={"text": text, "voice": "af_heart"},
                headers=headers,
                timeout=60.0,
            )
            if resp.status_code == 200:
                return resp.content
            sys.stderr.write(
                f"[voice-cast-on-sign] Kokoro CPU-floor synth failed: "
                f"HTTP {resp.status_code} — {resp.text[:200]}\n"
            )
        except Exception as exc:
            sys.stderr.write(f"[voice-cast-on-sign] Kokoro CPU-floor synth error: {exc}\n")
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

        # Defense-in-depth: only voice-cast genuine signature.v1 payloads. Even on
        # the dedicated agent.graphiti.signed.v1 subject, refuse to speak a stray
        # envelope (e.g. Fordham dues/enrollment/mint receipts) that merely carries
        # a 'summary' field (5090-CLAUDE pair-review PR #2048, finding #2).
        if not (payload.get("glyph") and payload.get("agent_id")):
            sys.stderr.write(
                "[voice-cast-on-sign] Not a signature.v1 payload (no glyph/agent_id) -- skipping\n"
            )
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
            wav_bytes: Optional[bytes] = None
            used_intent = intent

            if health is not None:
                providers = health.get("providers", {}) if isinstance(health, dict) else {}
                expressive_ready = bool(
                    providers.get("ultimate_tts") or providers.get("omnivoice")
                )
                if expressive_ready:
                    wav_bytes = await self._synthesize(client, text, intent, persona_id)
                else:
                    sys.stderr.write(
                        "[voice-cast-on-sign] No expressive TTS provider healthy -- "
                        "falling back to the standalone Kokoro CPU floor\n"
                    )
            else:
                sys.stderr.write(
                    "[voice-cast-on-sign] Flute-Gateway unreachable -- falling back to "
                    "the standalone Kokoro CPU floor (deterministic health check, "
                    "daemon stays up)\n"
                )

            if wav_bytes is None:
                # Genuinely independent CPU floor -- a separate deploy unit (#2024),
                # NOT a route back through the Flute-Gateway/ultimate_tts stack that
                # just failed (5090-CLAUDE pair-review PR #2048, finding #4).
                used_intent = FALLBACK_INTENT
                wav_bytes = await self._synthesize_kokoro_fallback(client, text)

            if not wav_bytes:
                sys.stderr.write(
                    "[voice-cast-on-sign] No synthesis path available (Flute-Gateway "
                    "and Kokoro CPU floor both failed) -- skipping this utterance\n"
                )
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
            ratio = _compute_atempo_ratio(payload, used_intent)
            play_path = out_path
            tempo_path: Optional[Path] = None
            if ratio is not None and abs(ratio - 1.0) > 1e-3:
                tempo_path = _apply_atempo(out_path, ratio)
                if tempo_path is not None:
                    play_path = tempo_path

            _play_audio(play_path)

            if tempo_path is not None:
                asyncio.create_task(self._cleanup_tempo_file(tempo_path))

    @staticmethod
    async def _cleanup_tempo_file(tempo_path: Path) -> None:
        """Unlink the intermediate atempo temp file once playback has likely
        finished (best-effort cleanup nit, 5090-CLAUDE pair-review PR #2048).

        Playback is fire-and-forget (winsound SND_ASYNC / subprocess.Popen), so
        deleting immediately after ``_play_audio`` returns would race the player
        reading the file. Wait roughly the clip's own duration (+ buffer) first.
        The primary cast WAV is intentionally left in place (gitignored /out/).
        """
        delay = _estimate_wav_seconds(tempo_path) + 2.0
        await asyncio.sleep(delay)
        try:
            tempo_path.unlink(missing_ok=True)
        except Exception as exc:
            sys.stderr.write(
                f"[voice-cast-on-sign] Failed to remove temp tempo file {tempo_path}: {exc}\n"
            )

    async def run(self, subjects: list[str]) -> None:
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        sys.stderr.write(f"[voice-cast-on-sign] connected to {self.nats_url}\n")
        sys.stderr.write(f"[voice-cast-on-sign] subjects: {', '.join(subjects)}\n")
        sys.stderr.write(f"[voice-cast-on-sign] flute_gateway: {self.flute_gateway_url}\n")
        sys.stderr.write(f"[voice-cast-on-sign] kokoro_fallback: {self.kokoro_url}\n")

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
    kokoro_url = _env("KOKORO_URL", DEFAULT_KOKORO_URL)

    agent = VoiceCastOnSign(
        nats_url=nats_url, flute_gateway_url=flute_gateway_url, kokoro_url=kokoro_url
    )
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
