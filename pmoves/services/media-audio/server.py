"""Media Audio Processing Service.

GPU-enabled audio analysis: STT (whisper-large-v3-turbo) + speaker diarization
(pyannote 3.1, gated on HF_TOKEN) + speech-emotion (hubert) + librosa acoustic
features. Productionized from the `Enhanced Media Stack` prototype, on top of this
service's existing health/GPU/Prometheus scaffolding.

Model choices — 2026-07-21 HF-grounded, license-clean refresh:
  - STT       openai/whisper-large-v3-turbo    (MIT, ~809M)  [STT_MODEL]
  - emotion   superb/hubert-large-superb-er     (Apache)      [EMOTION_MODEL]
  - diarize   pyannote/speaker-diarization-3.1  (MIT, gated)  [DIARIZATION_MODEL + HF_TOKEN]

Fleet-adaptive backend via MEDIA_BACKEND: transformers (default, implemented) |
nemo (SPARK Parakeet/Sortformer, TODO) | vulkan (AMD whisper.cpp/ONNX-RT, TODO).
See project_media_stack_roadmap.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel

logger = logging.getLogger("pmoves.media-audio")

app = FastAPI(
    title="PMOVES Media Audio Service",
    description="GPU-enabled audio analysis (whisper-turbo + pyannote + emotion)",
    version="1.0.0",
)

# --- Metrics (preserved from the prior stub) ---
audio_seconds_processed = Counter(
    "media_audio_seconds_processed_total", "Audio seconds processed", ["model"]
)
transcription_errors = Counter(
    "media_audio_transcription_errors_total", "Transcription errors", ["error_type"]
)

# --- Environment configuration ---
PORT = int(os.environ.get("MEDIA_AUDIO_PORT", "8082"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
MEDIA_BACKEND = os.environ.get("MEDIA_BACKEND", "transformers").lower()
STT_MODEL = os.environ.get("STT_MODEL", "openai/whisper-large-v3-turbo")
EMOTION_MODEL = os.environ.get("EMOTION_MODEL", "superb/hubert-large-superb-er")
DIARIZATION_MODEL = os.environ.get("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
MEDIA_AUDIO_SUBJECT = os.environ.get("MEDIA_AUDIO_SUBJECT", "media.audio.analyzed.v1")


def check_gpu_available() -> dict:
    """Check GPU availability and return info."""
    try:
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0) if device_count > 0 else "unknown"
            return {
                "available": True,
                "device_count": device_count,
                "device_name": device_name,
                "cuda_version": torch.version.cuda,
            }
        return {"available": False, "reason": "CUDA not available"}
    except Exception:
        # CodeQL: never expose exception details to clients — log server-side.
        logger.exception("GPU availability check failed")
        return {"available": False, "reason": "gpu check failed (see service logs)"}


class AudioAnalysisRequest(BaseModel):
    file_path: str
    analysis_type: str = "full"  # full | transcription | emotion | diarization | features
    language: str = "auto"


class AudioProcessor:
    """Loads and runs the transformers-backend audio pipeline (lazy heavy imports)."""

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.models: Dict[str, Any] = {}
        self.backend = MEDIA_BACKEND
        if self.backend != "transformers":
            logger.warning(
                "MEDIA_BACKEND=%s not implemented in v1; using transformers "
                "(nemo=SPARK Parakeet/Sortformer, vulkan=AMD are TODO)",
                self.backend,
            )
            self.backend = "transformers"
        self._load()

    def _load(self) -> None:
        logger.info("Loading audio models on %s (backend=%s)", self.device, self.backend)
        try:
            from transformers import pipeline

            self.models["stt"] = pipeline(
                "automatic-speech-recognition",
                model=STT_MODEL,
                torch_dtype=self.dtype,
                device=0 if self.device == "cuda" else -1,
            )
            logger.info("STT loaded (%s)", STT_MODEL)
        except Exception:
            logger.exception("STT load failed")
        try:
            from transformers import pipeline

            self.models["emotion"] = pipeline(
                "audio-classification",
                model=EMOTION_MODEL,
                device=0 if self.device == "cuda" else -1,
            )
            logger.info("emotion loaded (%s)", EMOTION_MODEL)
        except Exception:
            logger.exception("emotion load failed")
        if HF_TOKEN:
            try:
                from pyannote.audio import Pipeline as PyannotePipeline

                pipe = PyannotePipeline.from_pretrained(DIARIZATION_MODEL, use_auth_token=HF_TOKEN)
                if self.device == "cuda":
                    pipe.to(torch.device("cuda"))
                self.models["diarization"] = pipe
                logger.info("diarization loaded (%s)", DIARIZATION_MODEL)
            except Exception:
                logger.exception("diarization load failed")
        else:
            logger.info("diarization skipped — set HF_TOKEN to enable pyannote")
        logger.info("models ready: %s", list(self.models))

    def features(self, path: str) -> Dict[str, Any]:
        try:
            import librosa

            y, sr = librosa.load(path, sr=16000)
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            audio_seconds_processed.labels(model="librosa").inc(len(y) / sr)
            return {
                "duration": float(len(y) / sr),
                "sample_rate": int(sr),
                "rms_energy": float(librosa.feature.rms(y=y).mean()),
                "spectral_centroid": float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
                "zero_crossing_rate": float(librosa.feature.zero_crossing_rate(y).mean()),
                "tempo": float(tempo),
                "beat_count": int(len(beats)),
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("feature extraction failed")
            return {"error": str(e)}

    def transcribe(self, path: str, language: str = "auto") -> Dict[str, Any]:
        if "stt" not in self.models:
            return {"error": "no STT model loaded"}
        try:
            out = self.models["stt"](
                path,
                return_timestamps=True,
                generate_kwargs={
                    "language": None if language == "auto" else language,
                    "task": "transcribe",
                },
            )
            return {"text": out.get("text", ""), "chunks": out.get("chunks", []), "model": STT_MODEL}
        except Exception as e:  # noqa: BLE001
            transcription_errors.labels(error_type=type(e).__name__).inc()
            logger.exception("transcription failed")
            return {"error": str(e)}

    def emotion(self, path: str) -> Dict[str, Any]:
        if "emotion" not in self.models:
            return {"error": "no emotion model loaded"}
        try:
            res = self.models["emotion"](path)
            return {"emotions": res, "dominant": max(res, key=lambda x: x["score"]), "model": EMOTION_MODEL}
        except Exception as e:  # noqa: BLE001
            logger.exception("emotion analysis failed")
            return {"error": str(e)}

    def diarize(self, path: str) -> Dict[str, Any]:
        if "diarization" not in self.models:
            return {"error": "diarization not enabled (set HF_TOKEN)"}
        try:
            ann = self.models["diarization"](path)
            turns = [
                {"start": float(seg.start), "end": float(seg.end), "speaker": str(spk)}
                for seg, _, spk in ann.itertracks(yield_label=True)
            ]
            speakers = sorted({t["speaker"] for t in turns})
            return {"turns": turns, "speakers": speakers, "num_speakers": len(speakers), "model": DIARIZATION_MODEL}
        except Exception as e:  # noqa: BLE001
            logger.exception("diarization failed")
            return {"error": str(e)}

    def full(self, path: str, language: str = "auto") -> Dict[str, Any]:
        started = datetime.now(timezone.utc)
        result: Dict[str, Any] = {
            "task_id": str(uuid.uuid4()),
            "file_path": path,
            "timestamp": started.isoformat(),
            "features": self.features(path),
            "transcription": self.transcribe(path, language),
            "emotion": self.emotion(path),
            "diarization": self.diarize(path),
        }
        result["processing_time"] = (datetime.now(timezone.utc) - started).total_seconds()
        result["status"] = "completed"
        return result


_processor: Optional[AudioProcessor] = None


@app.on_event("startup")
def _startup() -> None:
    global _processor
    try:
        _processor = AudioProcessor()
    except Exception:
        logger.exception("processor init failed — service will report degraded")


async def _maybe_publish(result: Dict[str, Any]) -> None:
    if not NATS_URL:
        return
    try:
        import json

        import nats

        nc = await nats.connect(NATS_URL)
        await nc.publish(MEDIA_AUDIO_SUBJECT, json.dumps(result, default=str).encode("utf-8"))
        await nc.drain()
    except Exception:
        logger.warning("NATS publish skipped/failed", exc_info=True)


@app.get("/healthz")
async def healthz():
    """Health: GPU present AND at least one model loaded."""
    gpu = check_gpu_available()
    models = list(_processor.models) if _processor else []
    healthy = gpu.get("available", False) and bool(models)
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "service": "media-audio",
            "backend": MEDIA_BACKEND,
            "gpu": gpu,
            "models_loaded": models,
            "diarization_enabled": "diarization" in models,
        },
    )


@app.get("/")
async def root():
    return {
        "service": "media-audio",
        "status": "ready" if (_processor and _processor.models) else "loading",
        "version": "1.0.0",
        "gpu": check_gpu_available(),
        "models": {"stt": STT_MODEL, "emotion": EMOTION_MODEL, "diarization": DIARIZATION_MODEL},
    }


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze")
async def analyze(req: AudioAnalysisRequest):
    if _processor is None:
        raise HTTPException(status_code=503, detail="models not ready")
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="audio file not found")
    dispatch = {
        "full": lambda: _processor.full(req.file_path, req.language),
        "transcription": lambda: _processor.transcribe(req.file_path, req.language),
        "emotion": lambda: _processor.emotion(req.file_path),
        "diarization": lambda: _processor.diarize(req.file_path),
        "features": lambda: _processor.features(req.file_path),
    }
    fn = dispatch.get(req.analysis_type)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"invalid analysis_type: {req.analysis_type}")
    result = fn()
    if req.analysis_type == "full":
        await _maybe_publish(result)
    return JSONResponse(content=result)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting media-audio service on port %s", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
