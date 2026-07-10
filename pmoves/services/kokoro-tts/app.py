"""Kokoro CPU TTS — standalone HTTP synthesis service.

Kokoro-82M (Apache-2.0) served via kokoro-onnx (onnxruntime, CPU). This is the
missing piece for "voice on a GPU-less node": the two CPU-viable engines
(Kokoro, KittenTTS) otherwise ship ONLY bundled inside the GPU-hosted
Ultimate-TTS-Studio Pinokio app. This unit lets a KVM VPS synthesize speech.

Endpoints:
    POST /synthesize  {text, voice?, speed?, lang?} -> audio/wav (PCM16, 24kHz)
    GET  /voices      -> {voices: [...], default}
    GET  /healthz     -> {status, model_loaded, ...}

Auth: if KOKORO_TOKEN is set, /synthesize requires header X-Kokoro-Token to match
(mirrors the OmniVoice token gate). /healthz + /voices stay open.

Model files (kokoro-v1.0.onnx + voices-v1.0.bin) live at KOKORO_MODEL_DIR
(default /models); Dockerfile.kokoro fetches the pinned Apache-2.0 model at build,
so the image is self-contained + offline-capable.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

import soundfile as sf
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("KOKORO_LOG_LEVEL", "INFO"))
logger = logging.getLogger("kokoro-tts")

MODEL_DIR = os.getenv("KOKORO_MODEL_DIR", "/models")
MODEL_PATH = os.getenv("KOKORO_MODEL_PATH", os.path.join(MODEL_DIR, "kokoro-v1.0.onnx"))
VOICES_PATH = os.getenv("KOKORO_VOICES_PATH", os.path.join(MODEL_DIR, "voices-v1.0.bin"))
DEFAULT_VOICE = os.getenv("KOKORO_DEFAULT_VOICE", "af_heart")
DEFAULT_LANG = os.getenv("KOKORO_DEFAULT_LANG", "en-us")
TOKEN = os.getenv("KOKORO_TOKEN", "")

app = FastAPI(title="Kokoro CPU TTS", version="1.0.0")
_kokoro = None  # lazy singleton — kept out of import time so /healthz answers pre-load


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro  # lazy import: heavy, and lets healthz work while loading

        if not (os.path.exists(MODEL_PATH) and os.path.exists(VOICES_PATH)):
            raise RuntimeError(f"Kokoro model files missing: {MODEL_PATH} / {VOICES_PATH}")
        logger.info("loading Kokoro model from %s", MODEL_PATH)
        _kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    return _kokoro


def _voice_names(kok) -> list[str]:
    if hasattr(kok, "get_voices"):
        try:
            return sorted(kok.get_voices())
        except Exception:  # noqa: BLE001
            pass
    v = getattr(kok, "voices", None)
    if isinstance(v, dict):
        return sorted(v.keys())
    if v:
        return sorted(v)
    return []


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: Optional[str] = None
    speed: float = 1.0
    lang: Optional[str] = None


@app.on_event("startup")
def _warm() -> None:
    try:
        _get_kokoro()
    except Exception as exc:  # noqa: BLE001 — don't crash the container; /healthz reports it
        logger.warning("Kokoro not preloaded at startup: %s", exc)


def _check_token(supplied: Optional[str]) -> None:
    if TOKEN and supplied != TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing X-Kokoro-Token")


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest, x_kokoro_token: Optional[str] = Header(default=None)):
    _check_token(x_kokoro_token)
    try:
        kokoro = _get_kokoro()
        samples, sample_rate = kokoro.create(
            req.text,
            voice=req.voice or DEFAULT_VOICE,
            speed=req.speed,
            lang=req.lang or DEFAULT_LANG,
        )
    except RuntimeError as exc:  # model not loaded / files missing
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("synthesis failed")
        raise HTTPException(status_code=500, detail=f"synthesis failed: {exc}") from exc

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.get("/voices")
def voices():
    try:
        kokoro = _get_kokoro()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"voices": _voice_names(kokoro), "default": DEFAULT_VOICE}


@app.get("/healthz")
def healthz():
    loaded = _kokoro is not None
    return JSONResponse(
        {
            "status": "ok" if loaded else "loading",
            "model_loaded": loaded,
            "model_path": MODEL_PATH,
            "default_voice": DEFAULT_VOICE,
        }
    )
