"""Media Video Processing Service.

GPU-enabled video analysis: frame sampling (OpenCV) -> object detection (DETR).

Productionized from the `Enhanced Media Stack` prototype, on top of this service's
existing health/GPU/Prometheus scaffolding.

License note: the original plan used Ultralytics YOLO, which is **AGPL-3.0** and
violates the project's Apache/MIT/BSD ship rule. This implementation uses
**facebook/detr-resnet-50** (Apache-2.0, ~42M) instead — see the 2026-07-21
HF-grounded model refresh / project_media_stack_roadmap.

Fleet-adaptive backend via MEDIA_BACKEND: transformers (default, implemented) |
nemo (SPARK, TODO) | vulkan (AMD ONNX-RT, TODO).
"""

import logging
import os
import uuid
from collections import Counter as Tally
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel

logger = logging.getLogger("pmoves.media-video")

app = FastAPI(
    title="PMOVES Media Video Service",
    description="GPU-enabled video analysis (DETR object detection)",
    version="1.0.0",
)

# --- Metrics (preserved from the prior stub) ---
video_frames_processed = Counter(
    "media_video_frames_processed_total", "Video frames processed", ["model"]
)
processing_errors = Counter(
    "media_video_processing_errors_total", "Processing errors", ["error_type"]
)

# --- Environment configuration ---
PORT = int(os.environ.get("MEDIA_VIDEO_PORT", "8079"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
MEDIA_BACKEND = os.environ.get("MEDIA_BACKEND", "transformers").lower()
# Detector engine, operator-selectable:
#   "detr" (default) — facebook/detr-resnet-50, Apache-2.0, ships anywhere.
#   "yolo"           — Ultralytics YOLO. AGPL-3.0: fine to RUN on a private/self-hosted
#                      fleet (ideal on Jetson/TensorRT); the license rule governs what
#                      you *ship*, not what you privately *run*. Operator's call.
DETECTION_ENGINE = os.environ.get("DETECTION_ENGINE", "detr").lower()
DETECTION_MODEL = os.environ.get("DETECTION_MODEL", "facebook/detr-resnet-50")
YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")
DETECTION_CONFIDENCE = float(os.environ.get("DETECTION_CONFIDENCE", os.environ.get("YOLO_CONFIDENCE", "0.25")))
FRAME_SAMPLE_RATE = int(os.environ.get("FRAME_SAMPLE_RATE", "5"))
MAX_FRAMES = int(os.environ.get("MEDIA_VIDEO_MAX_FRAMES", "600"))  # cap work per request
MEDIA_VIDEO_SUBJECT = os.environ.get("MEDIA_VIDEO_SUBJECT", "media.video.analyzed.v1")


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


class VideoAnalysisRequest(BaseModel):
    file_path: str
    sample_rate: Optional[int] = None  # override FRAME_SAMPLE_RATE
    confidence: Optional[float] = None  # override DETECTION_CONFIDENCE


class VideoProcessor:
    """DETR object detection over sampled video frames (lazy heavy imports)."""

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.detector = None
        self.engine = DETECTION_ENGINE if DETECTION_ENGINE in ("detr", "yolo") else "detr"
        self.model_name = YOLO_MODEL if self.engine == "yolo" else DETECTION_MODEL
        self.backend = MEDIA_BACKEND
        if self.backend != "transformers":
            logger.warning(
                "MEDIA_BACKEND=%s not implemented in v1; using transformers "
                "(nemo=SPARK, vulkan=AMD ONNX-RT are TODO)",
                self.backend,
            )
            self.backend = "transformers"
        self._load()

    def _load(self) -> None:
        if self.engine == "yolo":
            logger.info("Loading YOLO on %s (%s)", self.device, YOLO_MODEL)
            try:
                from ultralytics import YOLO

                self.detector = YOLO(YOLO_MODEL)
                logger.info("YOLO detector loaded (%s)", YOLO_MODEL)
            except Exception:
                logger.exception("YOLO load failed (is `ultralytics` installed?)")
            return
        logger.info("Loading DETR on %s (%s)", self.device, DETECTION_MODEL)
        try:
            from transformers import pipeline

            self.detector = pipeline(
                "object-detection",
                model=DETECTION_MODEL,
                device=0 if self.device == "cuda" else -1,
            )
            logger.info("DETR detector loaded (%s)", DETECTION_MODEL)
        except Exception:
            logger.exception("detector load failed")

    def _detect(self, pil_image, confidence: float) -> List[Dict[str, Any]]:
        if self.engine == "yolo":
            out: List[Dict[str, Any]] = []
            for r in self.detector(pil_image, conf=confidence, verbose=False):
                names = r.names
                for b in r.boxes:
                    out.append({"label": names[int(b.cls)], "score": float(b.conf)})
            return out
        raw = self.detector(pil_image, threshold=confidence)
        return [{"label": d["label"], "score": float(d["score"])} for d in raw]

    def analyze_frame(self, path: str, confidence: float) -> Dict[str, Any]:
        if self.detector is None:
            return {"error": "no detector loaded"}
        try:
            from PIL import Image

            dets = self._detect(Image.open(path).convert("RGB"), confidence)
            video_frames_processed.labels(model=self.model_name).inc()
            return {"detections": dets, "model": self.model_name, "engine": self.engine}
        except Exception as e:  # noqa: BLE001
            processing_errors.labels(error_type=type(e).__name__).inc()
            logger.exception("frame analysis failed")
            return {"error": str(e)}

    def analyze_video(self, path: str, sample_rate: int, confidence: float) -> Dict[str, Any]:
        if self.detector is None:
            return {"error": "no detector loaded"}
        started = datetime.now(timezone.utc)
        try:
            import cv2
            from PIL import Image
        except Exception as e:  # noqa: BLE001
            return {"error": f"opencv/PIL unavailable: {e}"}

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return {"error": "could not open video"}
        frames: List[Dict[str, Any]] = []
        tally: "Tally[str]" = Tally()
        idx = sampled = 0
        try:
            while sampled < MAX_FRAMES:
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % sample_rate == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    dets = self._detect(Image.fromarray(rgb), confidence)
                    for d in dets:
                        tally[d["label"]] += 1
                    frames.append({"frame": idx, "detections": dets})
                    sampled += 1
                    video_frames_processed.labels(model=self.model_name).inc()
                idx += 1
        finally:
            cap.release()
        return {
            "task_id": str(uuid.uuid4()),
            "file_path": path,
            "timestamp": started.isoformat(),
            "frames_read": idx,
            "frames_sampled": sampled,
            "sample_rate": sample_rate,
            "confidence": confidence,
            "object_counts": dict(tally.most_common()),
            "frames": frames,
            "model": self.model_name,
            "engine": self.engine,
            "truncated": sampled >= MAX_FRAMES,
            "processing_time": (datetime.now(timezone.utc) - started).total_seconds(),
            "status": "completed",
        }


_processor: Optional[VideoProcessor] = None


@app.on_event("startup")
def _startup() -> None:
    global _processor
    try:
        _processor = VideoProcessor()
    except Exception:
        logger.exception("processor init failed — service will report degraded")


async def _maybe_publish(result: Dict[str, Any]) -> None:
    if not NATS_URL:
        return
    try:
        import json

        import nats

        nc = await nats.connect(NATS_URL)
        await nc.publish(MEDIA_VIDEO_SUBJECT, json.dumps(result, default=str).encode("utf-8"))
        await nc.drain()
    except Exception:
        logger.warning("NATS publish skipped/failed", exc_info=True)


@app.get("/healthz")
async def healthz():
    gpu = check_gpu_available()
    ready = _processor is not None and _processor.detector is not None
    healthy = gpu.get("available", False) and ready
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "service": "media-video",
            "backend": MEDIA_BACKEND,
            "engine": _processor.engine if _processor else DETECTION_ENGINE,
            "gpu": gpu,
            "model": _processor.model_name if _processor else DETECTION_MODEL,
            "detector_loaded": ready,
        },
    )


@app.get("/")
async def root():
    return {
        "service": "media-video",
        "status": "ready" if (_processor and _processor.detector) else "loading",
        "version": "1.0.0",
        "gpu": check_gpu_available(),
        "config": {
            "engine": _processor.engine if _processor else DETECTION_ENGINE,
            "model": _processor.model_name if _processor else DETECTION_MODEL,
            "confidence": DETECTION_CONFIDENCE,
            "frame_sample_rate": FRAME_SAMPLE_RATE,
        },
    }


@app.get("/topology")
async def topology():
    """Network-awareness self-report (HYBRID_TOPOLOGY_NETWORK_AWARENESS.md §4)."""
    try:
        from services.common.topology import get_topology

        topo = get_topology().to_dict()
    except Exception:  # noqa: BLE001
        logger.warning("topology unavailable", exc_info=True)
        topo = {"error": "topology context unavailable"}
    return {"service": "media-video", "topology": topo}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze")
async def analyze_video(req: VideoAnalysisRequest):
    if _processor is None:
        raise HTTPException(status_code=503, detail="detector not ready")
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="video file not found")
    result = _processor.analyze_video(
        req.file_path,
        req.sample_rate or FRAME_SAMPLE_RATE,
        req.confidence if req.confidence is not None else DETECTION_CONFIDENCE,
    )
    await _maybe_publish(result)
    return JSONResponse(content=result)


@app.post("/frame")
async def analyze_frame(req: VideoAnalysisRequest):
    if _processor is None:
        raise HTTPException(status_code=503, detail="detector not ready")
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="image file not found")
    result = _processor.analyze_frame(
        req.file_path, req.confidence if req.confidence is not None else DETECTION_CONFIDENCE
    )
    return JSONResponse(content=result)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting media-video service on port %s", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
