#!/usr/bin/env python3
"""
Local Voice Speaker for PMOVES

Goal: provide a localhost API that turns text into audible speech using Flute Gateway.

This is intentionally host-run (not a docker service) so audio plays on the operator machine.

Endpoints:
  - GET  /healthz
  - POST /say   {"text": "...", "voice": "en-Emma_woman", "mode": "stream"|"batch"}

Playback:
  - Prefers `ffplay` when available (best for streaming PCM).
  - Falls back to `aplay` / `paplay` / `afplay` / `powershell` where possible.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SpeakerConfig:
    bind: str
    port: int
    flute_base_url: str
    flute_api_key: str


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _is_wsl() -> bool:
    # Heuristic: works for WSL1/WSL2.
    if os.getenv("WSL_INTEROP") or os.getenv("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as fp:
            return "microsoft" in fp.read().lower()
    except OSError:
        return False


def load_config() -> SpeakerConfig:
    return SpeakerConfig(
        bind=_env("VOICE_SPEAKER_BIND", "127.0.0.1"),
        port=int(_env("VOICE_SPEAKER_PORT", "8120")),
        flute_base_url=_env("FLUTE_BASE_URL", "http://localhost:8055").rstrip("/"),
        flute_api_key=_env("FLUTE_API_KEY", ""),
    )


def _http_json(url: str, payload: Dict[str, Any], api_key: str, timeout_seconds: float = 60.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8"))


def _http_bytes(url: str, payload: Dict[str, Any], api_key: str, timeout_seconds: float = 120.0) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read()


def _which_any(names: list[str]) -> Optional[str]:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _windows_path_from_wsl(path: str) -> Optional[str]:
    wslpath = _which_any(["wslpath"])
    if not wslpath:
        return None
    try:
        out = subprocess.check_output([wslpath, "-w", path], stderr=subprocess.DEVNULL)
        win = out.decode("utf-8", errors="ignore").strip()
        return win or None
    except Exception:
        return None


def _play_wav_via_windows(wav_bytes: bytes) -> bool:
    """
    If we're running under WSL2, play WAV using Windows' SoundPlayer so audio comes out of the host speakers.

    This is often more reliable than Linux audio output under WSL (depending on WSLg/Pulse config).
    """
    if not _is_wsl():
        return False

    powershell = _which_any(["powershell.exe", "pwsh.exe"])
    if not powershell:
        return False

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
        fp.write(wav_bytes)
        tmp_path = fp.name

    try:
        win_path = _windows_path_from_wsl(tmp_path)
        if not win_path:
            return False
        # Use SoundPlayer (WAV only) and block until completion.
        cmd = f"(New-Object Media.SoundPlayer '{win_path}').PlaySync();"
        subprocess.run([powershell, "-NoProfile", "-Command", cmd], check=False)
        return True
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _play_wav_bytes(wav_bytes: bytes) -> None:
    # Prefer Windows playback when running inside WSL unless explicitly disabled.
    # This makes "local realtime voice" work even when WSL audio is not configured.
    if _env("VOICE_SPEAKER_WSL_WINDOWS_AUDIO", "1") not in {"0", "false", "FALSE", "no", "NO"}:
        if _play_wav_via_windows(wav_bytes):
            return

    ffplay = _which_any(["ffplay"])
    if ffplay:
        subprocess.run(
            [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", "-i", "-"],
            input=wav_bytes,
            check=False,
        )
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
        fp.write(wav_bytes)
        tmp_path = fp.name

    try:
        player = _which_any(["aplay", "paplay", "afplay"])
        if player:
            subprocess.run([player, tmp_path], check=False)
            return
        if sys.platform.startswith("win"):
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(New-Object Media.SoundPlayer '{tmp_path}').PlaySync();",
                ],
                check=False,
            )
            return
        raise RuntimeError("No audio player found (install ffmpeg for ffplay, or ALSA/Pulse tools).")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def speak_batch(config: SpeakerConfig, text: str, voice: Optional[str]) -> None:
    retries = int(_env("VOICE_SPEAKER_RETRIES", "5"))
    last_exc: Optional[Exception] = None
    wav_bytes: Optional[bytes] = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            wav_bytes = _http_bytes(
                f"{config.flute_base_url}/v1/voice/synthesize/audio",
                {
                    "text": text,
                    "provider": "vibevoice",
                    "voice": voice,
                    "output_format": "wav",
                },
                api_key=config.flute_api_key,
                timeout_seconds=180.0,
            )
            break
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in {502, 503} and attempt < retries:
                time.sleep(0.35 * attempt)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.35 * attempt)
                continue
            raise

    if wav_bytes is None:
        raise last_exc or RuntimeError("No WAV bytes received from Flute")
    if _env("VOICE_SPEAKER_DRY_RUN", "0") in {"1", "true", "TRUE", "yes", "YES"}:
        sys.stderr.write(f"[voice-speaker] dry-run: received {len(wav_bytes)} wav bytes\n")
        return
    _play_wav_bytes(wav_bytes)


def speak_stream(config: SpeakerConfig, text: str, voice: Optional[str]) -> None:
    """
    Best-effort real-time playback:
      - Connects to Flute WS `/v1/voice/stream/tts`
      - Receives PCM16 chunks and pipes them to ffplay
    """
    ffplay = _which_any(["ffplay"])
    if not ffplay:
        # Streaming without ffplay is awkward; fall back to batch.
        speak_batch(config, text=text, voice=voice)
        return

    if _env("VOICE_SPEAKER_DRY_RUN", "0") in {"1", "true", "TRUE", "yes", "YES"}:
        # Still hit Flute (so we validate the upstream pipeline), but do not play audio.
        speak_batch(config, text=text, voice=voice)
        return

    try:
        import asyncio
        import websockets
    except Exception:
        speak_batch(config, text=text, voice=voice)
        return

    ws_url = config.flute_base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/v1/voice/stream/tts"

    async def _run() -> None:
        sys.stderr.write("[voice-speaker] streaming via ffplay\n")
        proc = await asyncio.create_subprocess_exec(
            ffplay,
            "-f",
            "s16le",
            "-ar",
            "24000",
            "-ac",
            "1",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-i",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdin is not None

        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"text": text, "voice": voice or "default"}))
                async for msg in ws:
                    if isinstance(msg, (bytes, bytearray)):
                        proc.stdin.write(bytes(msg))
                        await proc.stdin.drain()
                    else:
                        # JSON done/error messages
                        try:
                            obj = json.loads(msg)
                            if obj.get("type") in {"done", "error"}:
                                break
                        except Exception:
                            continue
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass

        if proc.returncode and proc.returncode != 0:
            err = b""
            try:
                assert proc.stderr is not None
                err = await proc.stderr.read()
            except Exception:
                err = b""
            if err:
                try:
                    sys.stderr.write(f"[voice-speaker] ffplay error: {err.decode('utf-8', errors='ignore').strip()}\n")
                except Exception:
                    sys.stderr.write("[voice-speaker] ffplay error (non-utf8)\n")
            raise RuntimeError(f"ffplay exited with code {proc.returncode}")

    try:
        asyncio.run(_run())
    except Exception as e:
        # Stream path is best-effort; fall back to batch for reliability.
        sys.stderr.write(f"[voice-speaker] stream failed; falling back to batch: {type(e).__name__}: {e}\n")
        speak_batch(config, text=text, voice=voice)


class VoiceSpeakerHandler(BaseHTTPRequestHandler):
    server_version = "pmoves-voice-speaker/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep logs minimal
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, code: int, obj: Dict[str, Any]) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/healthz":
            self._send_json(200, {"ok": True, "ts": time.time()})
            return
        self._send_json(404, {"ok": False, "error": f"not found: {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/say":
            self._send_json(404, {"ok": False, "error": f"not found: {self.path}"})
            return

        length = int(self.headers.get("content-length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return

        text = str(payload.get("text") or "").strip()
        voice = payload.get("voice")
        mode = str(payload.get("mode") or "stream").strip().lower()
        if not text:
            self._send_json(400, {"ok": False, "error": "missing text"})
            return
        if mode not in {"stream", "batch"}:
            self._send_json(400, {"ok": False, "error": "mode must be stream or batch"})
            return

        cfg: SpeakerConfig = self.server.config  # type: ignore[attr-defined]
        lock: threading.Lock = self.server.lock  # type: ignore[attr-defined]

        def _worker() -> None:
            with lock:
                try:
                    if mode == "batch":
                        speak_batch(cfg, text=text, voice=voice)
                    else:
                        speak_stream(cfg, text=text, voice=voice)
                except urllib.error.HTTPError as e:
                    sys.stderr.write(f"[voice-speaker] flute HTTPError: {e.code} {e.reason}\n")
                except Exception as e:
                    sys.stderr.write(f"[voice-speaker] speak failed: {type(e).__name__}: {e}\n")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        self._send_json(200, {"ok": True, "queued": True, "mode": mode})


def serve(config: SpeakerConfig) -> None:
    httpd = ThreadingHTTPServer((config.bind, config.port), VoiceSpeakerHandler)
    httpd.config = config  # type: ignore[attr-defined]
    httpd.lock = threading.Lock()  # type: ignore[attr-defined]
    sys.stderr.write(f"✔ voice-speaker listening on http://{config.bind}:{config.port}\n")
    sys.stderr.write(f"  ↳ flute base: {config.flute_base_url}\n")
    httpd.serve_forever()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="voice_speaker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="Run localhost voice speaker HTTP server")

    say = sub.add_parser("say", help="Speak text once (no server)")
    say.add_argument("--text", required=True)
    say.add_argument("--voice", default=None)
    say.add_argument("--mode", choices=["stream", "batch"], default="stream")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.cmd == "serve":
        serve(cfg)
        return 0

    if args.cmd == "say":
        try:
            if args.mode == "batch":
                speak_batch(cfg, text=args.text, voice=args.voice)
            else:
                speak_stream(cfg, text=args.text, voice=args.voice)
            return 0
        except Exception as e:
            sys.stderr.write(f"✖ speak failed: {type(e).__name__}: {e}\n")
            return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
