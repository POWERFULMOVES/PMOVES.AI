"""Media Audio Processing Service.

GPU-enabled audio analysis using Whisper for transcription and emotion detection.
Service is currently a stub with health check and GPU detection.

TODO: Implement Whisper transcription pipeline and emotion detection.
"""

import asyncio
import logging
import os
from typing import Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

# Prometheus metrics
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger("pmoves.media-audio")

# FastAPI app
app = FastAPI(
    title="PMOVES Media Audio Service",
    description="GPU-enabled audio analysis using Whisper",
    version="0.1.0-stub",
)

# Metrics
audio_seconds_processed = Counter(
    "media_audio_seconds_processed_total",
    "Audio seconds processed",
    ["model"],
)
transcription_errors = Counter(
    "media_audio_transcription_errors_total",
    "Transcription errors",
    ["error_type"],
)

# Environment configuration
PORT = int(os.environ.get("MEDIA_AUDIO_PORT", "8082"))

# NATS configuration (stub)
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")


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
        else:
            return {"available": False, "reason": "CUDA not available"}
    except Exception:
        # CodeQL: never expose exception details to clients — log server-side.
        logger.exception("GPU availability check failed")
        return {"available": False, "reason": "gpu check failed (see service logs)"}


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    gpu_info = check_gpu_available()
    healthy = gpu_info.get("available", False)

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "media-audio",
            "gpu": gpu_info,
        },
    )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    gpu_info = check_gpu_available()
    return {
        "service": "media-audio",
        "status": "stub",
        "version": "0.1.0-stub",
        "gpu": gpu_info,
        "config": {
            "port": PORT,
        },
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Stub endpoints for future implementation
@app.post("/transcribe")
async def transcribe_audio():
    """Transcribe audio file using Whisper (STUB)."""
    raise HTTPException(
        status_code=501,
        detail="Audio transcription not yet implemented - service is a stub",
    )


@app.post("/emotion")
async def detect_emotion():
    """Detect emotion from audio (STUB)."""
    raise HTTPException(
        status_code=501,
        detail="Emotion detection not yet implemented - service is a stub",
    )


@app.post("/analyze")
async def analyze_audio():
    """Full audio analysis pipeline (STUB)."""
    raise HTTPException(
        status_code=501,
        detail="Audio analysis not yet implemented - service is a stub",
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info(f"Starting media-audio service on port {PORT}")
    logger.info(f"GPU available: {torch.cuda.is_available()}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
