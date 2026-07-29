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

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, model_validator

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

def _read_secret(name: str) -> Optional[str]:
    """Read a secret from <NAME>_FILE (Docker/K8s secrets mount) or the env var directly."""
    path = os.environ.get(f"{name}_FILE")
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            logger.warning("could not read %s_FILE", name)
    return os.environ.get(name)


# --- Environment configuration ---
PORT = int(os.environ.get("MEDIA_AUDIO_PORT", "8082"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
MEDIA_BACKEND = os.environ.get("MEDIA_BACKEND", "transformers").lower()
STT_MODEL = os.environ.get("STT_MODEL", "openai/whisper-large-v3-turbo")
EMOTION_MODEL = os.environ.get("EMOTION_MODEL", "superb/hubert-large-superb-er")
DIARIZATION_MODEL = os.environ.get("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")
HF_TOKEN = _read_secret("HF_TOKEN") or _read_secret("HUGGING_FACE_HUB_TOKEN")
MEDIA_AUDIO_SUBJECT = os.environ.get("MEDIA_AUDIO_SUBJECT", "analysis.audio.v1")
# Client-provided file paths must resolve within this dir (py/path-injection guard).
MEDIA_INPUT_DIR = os.environ.get("MEDIA_INPUT_DIR", "/data")
# MinIO/S3 (env already wired in docker-compose media-audio block). Mirrors the
# ffmpeg-whisper s3_client() chain so bucket+key jobs can be fetched.
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = _read_secret("MINIO_ACCESS_KEY") or _read_secret("AWS_ACCESS_KEY_ID") or ""
MINIO_SECRET_KEY = _read_secret("MINIO_SECRET_KEY") or _read_secret("AWS_SECRET_ACCESS_KEY") or ""
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").strip().lower() in ("true", "1", "yes")


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
    # Real callers (ffmpeg-whisper forward hook, n8n flow) send a MinIO ref; direct
    # file_path is kept for local/direct-mount + tests. Exactly one source required.
    bucket: Optional[str] = None
    key: Optional[str] = None
    file_path: Optional[str] = None
    video_id: Optional[str] = None
    namespace: Optional[str] = None
    transcript: Optional[Dict[str, Any]] = None  # if forwarded, skip re-running STT
    analysis_type: str = "full"  # full | transcription | emotion | diarization | features
    language: str = "auto"

    @model_validator(mode="after")
    def _one_source(self) -> "AudioAnalysisRequest":
        has_ref = bool(self.bucket and self.key)
        has_path = bool(self.file_path)
        if has_ref == has_path:
            raise ValueError("exactly one of (bucket+key) or file_path is required")
        return self


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

                pipe = PyannotePipeline.from_pretrained(DIARIZATION_MODEL, token=HF_TOKEN)
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

    def full(self, path: str, language: str = "auto", pretranscript: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        started = datetime.now(timezone.utc)
        # If an upstream hop already transcribed (ffmpeg-whisper forwards it), reuse it
        # instead of re-running STT on the GPU.
        transcription = pretranscript if pretranscript is not None else self.transcribe(path, language)
        result: Dict[str, Any] = {
            "task_id": str(uuid.uuid4()),
            "file_path": path,
            "timestamp": started.isoformat(),
            "features": self.features(path),
            "transcription": transcription,
            "emotion": self.emotion(path),
            "diarization": self.diarize(path),
        }
        result["processing_time"] = (datetime.now(timezone.utc) - started).total_seconds()
        # Report "partial" (not "completed") if any sub-analysis returned an error.
        errored = [
            stage
            for stage in ("features", "transcription", "emotion", "diarization")
            if isinstance(result.get(stage), dict) and result[stage].get("error")
        ]
        result["status"] = "completed" if not errored else "partial"
        if errored:
            result["failed_stages"] = errored
        return result


_processor: Optional[AudioProcessor] = None


@app.on_event("startup")
def _startup() -> None:
    # Load models in the background so startup returns immediately and /healthz is
    # reachable while (heavy) model loading proceeds; health reports degraded until ready.
    import threading

    def _load() -> None:
        global _processor
        try:
            _processor = AudioProcessor()
        except Exception:
            logger.exception("processor init failed — service will report degraded")

    threading.Thread(target=_load, name="media-audio-model-loader", daemon=True).start()


async def _maybe_publish(result: Dict[str, Any]) -> None:
    if not NATS_URL:
        return
    # Conform to the registered analysis.audio.v1 contract before emitting: its schema
    # (contracts/schemas/analysis/audio.v1.schema.json) requires an `emotions` array.
    # The build context is ./services/media-audio so the schema file is not in the image;
    # enforce its one hard invariant inline rather than poison consumers with a bad payload.
    if not isinstance(result, dict) or not isinstance(result.get("emotions"), list):
        logger.warning(
            "skipping %s publish: payload missing required 'emotions' array", MEDIA_AUDIO_SUBJECT
        )
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


@app.get("/topology")
async def topology():
    """Network-awareness self-report (HYBRID_TOPOLOGY_NETWORK_AWARENESS.md §4)."""
    try:
        from services.common.topology import get_topology

        topo = get_topology().to_dict()
    except Exception:  # noqa: BLE001
        logger.warning("topology unavailable", exc_info=True)
        topo = {"error": "topology context unavailable"}
    return {"service": "media-audio", "topology": topo}


def _safe_input_path(raw: str) -> str:
    """Resolve a client-provided path within MEDIA_INPUT_DIR; reject traversal (py/path-injection)."""
    base = os.path.realpath(MEDIA_INPUT_DIR)
    candidate = raw if os.path.isabs(raw) else os.path.join(base, raw)
    resolved = os.path.realpath(candidate)
    if resolved != base and os.path.commonpath([base, resolved]) != base:
        raise HTTPException(status_code=400, detail="file_path is outside the allowed media directory")
    return resolved


def _s3_client():
    """boto3 S3 client for MinIO — mirrors ffmpeg-whisper/server.py:329-338."""
    import boto3

    scheme = "https" if MINIO_SECURE else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def _fetch_from_minio(bucket: str, key: str) -> str:
    """Download a MinIO object to a temp file; returns the local path (caller cleans up its dir).

    The local filename is a random UUID (never derived from the user-controlled ``key``) so no
    untrusted data flows into a filesystem path (CodeQL py/path-injection).
    """
    tmpdir = tempfile.mkdtemp(prefix="media-audio-")
    local = os.path.join(tmpdir, uuid.uuid4().hex)
    try:
        with open(local, "wb") as fh:
            _s3_client().download_fileobj(bucket, key, fh)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(tmpdir, ignore_errors=True)  # don't leak the tempdir on failure
        logger.exception("MinIO fetch failed for %s/%s", bucket, key)
        raise HTTPException(status_code=502, detail="could not fetch object from storage") from e
    return local


async def _run_analysis(req: AudioAnalysisRequest) -> JSONResponse:
    if _processor is None:
        raise HTTPException(status_code=503, detail="models not ready")
    cleanup_dir: Optional[str] = None
    if req.bucket and req.key:
        # Blocking network I/O (potentially large download) — keep it off the event
        # loop, same as the inference dispatch below (review #2181 follow-up).
        path = await asyncio.to_thread(_fetch_from_minio, req.bucket, req.key)
        cleanup_dir = os.path.dirname(path)
    else:
        path = _safe_input_path(req.file_path)
        # `_safe_input_path()` already realpath()-resolves the candidate (symlinks and `..`
        # included) and rejects anything outside MEDIA_INPUT_DIR via os.path.commonpath (the
        # exact root-confinement guard CodeQL's own py/path-injection remediation recommends);
        # it just doesn't recognize a custom function as a sanitizer barrier (alert #326).
        if not os.path.exists(path):  # lgtm[py/path-injection]
            raise HTTPException(status_code=404, detail="audio file not found")
    try:
        dispatch = {
            "full": lambda: _processor.full(path, req.language, pretranscript=req.transcript),
            "transcription": lambda: (req.transcript or _processor.transcribe(path, req.language)),
            "emotion": lambda: _processor.emotion(path),
            "diarization": lambda: _processor.diarize(path),
            "features": lambda: _processor.features(path),
        }
        fn = dispatch.get(req.analysis_type)
        if fn is None:
            raise HTTPException(status_code=400, detail=f"invalid analysis_type: {req.analysis_type}")
        # Offload the (blocking) GPU/CPU inference off the event loop.
        result = await asyncio.to_thread(fn)
        if isinstance(result, dict):
            if req.video_id:
                result["video_id"] = req.video_id
            if req.namespace:
                result["namespace"] = req.namespace
        if req.analysis_type == "full":
            await _maybe_publish(result)
        return JSONResponse(content=result)
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


@app.post("/analyze")
async def analyze(req: AudioAnalysisRequest):
    return await _run_analysis(req)


# Alias — the wired n8n flow posts to /process (see media-payload-explorer findings).
@app.post("/process")
async def process(req: AudioAnalysisRequest):
    return await _run_analysis(req)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting media-audio service on port %s", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
