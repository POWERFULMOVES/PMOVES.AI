"""
PMOVES Audio Reprocess Service
==============================
Downloads audio, applies noise reduction, transcribes with Whisper,
performs speaker diarization, and publishes completion events to NATS.

Endpoints:
    GET  /healthz
    POST /api/v1/audio/reprocess
    POST /api/v1/audio/reprocess/batch
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

LOG = logging.getLogger("audio-reprocess")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

WHISPER_MODEL_CACHE = Path(os.getenv("WHISPER_MODEL_CACHE", "/models/whisper"))
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", "base")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
NATS_SUBJECT_COMPLETE = "media.audio.reprocess.complete.v1"

# --------------------------------------------------------------------------- #
# GPU detection
# --------------------------------------------------------------------------- #

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    if DEVICE == "cpu":
        LOG.warning("CUDA not available; Whisper will run on CPU — expect slower inference.")
except ImportError:  # torch not installed in dev environments
    torch = None
    DEVICE = "cpu"
    LOG.warning("torch not importable; defaulting to CPU device.")


def _load_whisper():
    """Lazy-load the Whisper model into the shared cache directory."""
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("openai-whisper is required for transcription") from exc
    WHISPER_MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    LOG.info("Loading Whisper model '%s' on %s (cache=%s)", WHISPER_MODEL_NAME, DEVICE, WHISPER_MODEL_CACHE)
    return whisper.load_model(WHISPER_MODEL_NAME, download_root=str(WHISPER_MODEL_CACHE))


_WHISPER_MODEL = None


def get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = _load_whisper()
    return _WHISPER_MODEL


# --------------------------------------------------------------------------- #
# NATS publisher
# --------------------------------------------------------------------------- #

class NATSPublisher:
    def __init__(self, url: str):
        self.url = url
        self._nc = None

    async def connect(self):
        try:
            from nats.aio.client import Client as NATSClient
            self._nc = NATSClient()
            await self._nc.connect(servers=[self.url])
            LOG.info("Connected to NATS at %s", self.url)
        except Exception as exc:
            LOG.warning("NATS connect failed (%s); events will be logged only", exc)
            self._nc = None

    async def publish(self, subject: str, payload: Dict[str, Any]):
        import json
        body = json.dumps(payload).encode()
        if self._nc:
            await self._nc.publish(subject, body)
        LOG.info("NATS publish subject=%s bytes=%d", subject, len(body))


publisher = NATSPublisher(NATS_URL)


# --------------------------------------------------------------------------- #
# Pipeline helpers
# --------------------------------------------------------------------------- #

async def download_audio(url: str, dest: Path) -> Path:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    dest.write_bytes(resp.content)
    LOG.info("Downloaded %s -> %s (%d bytes)", url, dest, dest.stat().st_size)
    return dest


def apply_noise_reduction(path: Path) -> Path:
    """
    Apply spectral-gating noise reduction.
    Falls back to no-op if noisereduce / scipy unavailable.
    """
    try:
        import noisereduce as nr
        import soundfile as sf
        import numpy as np  # noqa: F401  (required by noisereduce)
        data, rate = sf.read(str(path))
        reduced = nr.reduce_noise(y=data, sr=rate)
        out = path.with_suffix(".denoised.wav")
        sf.write(str(out), reduced, rate)
        return out
    except Exception as exc:
        LOG.warning("Noise reduction skipped (%s); using raw audio", exc)
        return path


def transcribe(path: Path) -> Dict[str, Any]:
    model = get_whisper_model()
    result = model.transcribe(str(path))
    return {
        "text": result.get("text", ""),
        "language": result.get("language", "unknown"),
        "segments": [
            {"start": s.get("start"), "end": s.get("end"), "text": s.get("text", "")}
            for s in result.get("segments", [])
        ],
    }


def diarize(path: Path) -> List[Dict[str, Any]]:
    """
    Speaker diarization stub.
    Production wiring: pyannote.audio with HF token from env.
    """
    try:
        # pyannote pipeline would be initialized here
        return [{"speaker": "SPEAKER_00", "start": 0.0, "end": float("inf")}]
    except Exception as exc:
        LOG.warning("Diarization failed (%s); returning single speaker", exc)
        return [{"speaker": "SPEAKER_00", "start": 0.0, "end": float("inf")}]


async def run_pipeline(audio_url: str) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "input.wav"
        await download_audio(audio_url, raw)
        denoised = apply_noise_reduction(raw)
        transcript = await asyncio.to_thread(transcribe, denoised)
        speakers = await asyncio.to_thread(diarize, denoised)
    payload = {
        "job_id": job_id,
        "audio_url": audio_url,
        "device": DEVICE,
        "model": WHISPER_MODEL_NAME,
        "transcript": transcript,
        "speakers": speakers,
        "duration_ms": int((time.time() - started) * 1000),
    }
    await publisher.publish(NATS_SUBJECT_COMPLETE, payload)
    return payload


# --------------------------------------------------------------------------- #
# API models
# --------------------------------------------------------------------------- #

class ReprocessRequest(BaseModel):
    audio_url: str = Field(..., description="URL of the audio asset to reprocess")
    language: Optional[str] = Field(None, description="ISO language hint")


class BatchReprocessRequest(BaseModel):
    audio_urls: List[str] = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #

app = FastAPI(title="PMOVES Audio Reprocess", version="1.0.0")


@app.on_event("startup")
async def _startup():
    await publisher.connect()


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "device": DEVICE, "model": WHISPER_MODEL_NAME}


@app.post("/api/v1/audio/reprocess")
async def reprocess(req: ReprocessRequest):
    try:
        return await run_pipeline(req.audio_url)
    except Exception as exc:
        LOG.exception("reprocess failed for %s", req.audio_url)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/audio/reprocess/batch")
async def reprocess_batch(req: BatchReprocessRequest):
    tasks = [run_pipeline(u) for u in req.audio_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        "total": len(results),
        "succeeded": sum(1 for r in results if not isinstance(r, Exception)),
        "failed": sum(1 for r in results if isinstance(r, Exception)),
        "results": [str(r) if isinstance(r, Exception) else r for r in results],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
