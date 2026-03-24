"""FFmpeg transcription service with multi-provider support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone as tz
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile

# NATS service announcement integration
try:
    from services.common.nats_service_listener import announce_service, ServiceTier
    NATS_ANNOUNCE_AVAILABLE = True
except ImportError:
    NATS_ANNOUNCE_AVAILABLE = False

# NATS CGP publishing
try:
    import nats as nats_pkg
    NATS_CGP_AVAILABLE = True
except ImportError:
    nats_pkg = None  # type: ignore
    NATS_CGP_AVAILABLE = False

try:  # pragma: no cover - exercised in production
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

import requests

try:  # pragma: no cover - exercised when optional dependency available
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

from services.common.supabase import insert_segments


ProviderLiteral = Literal["faster-whisper", "whisper", "qwen2-audio"]


logger = logging.getLogger(__name__)

# ── CHIT / NATS CGP publishing ───────────────────────────────────────────────
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
CGP_PUBLISH_ENABLED = os.environ.get(
    "FFW_CGP_PUBLISH", "true"
).lower() in ("1", "true", "yes")
CGP_SPEC_VERSION = "chit.cgp.v1.0"
CGP_SUBJECT = "tokenism.cgp.ready.v1"
TRANSCRIPT_READY_SUBJECT = "ingest.transcript.ready.v1"

_nats_client = None  # persistent NATS connection, set in lifespan


def _build_transcription_cgp(
    transcript: Dict[str, Any],
    video_id: Optional[str],
    audio_uri: Optional[str],
    request_id: str,
) -> Dict[str, Any]:
    """Build a CGP v1.0 packet from transcription results."""
    segments = transcript.get("segments") or []
    points = []
    for i, seg in enumerate(segments[:50]):
        text = (seg.get("text") or "").strip()
        duration = max(seg.get("end", 0.0) - seg.get("start", 0.0), 0.0)
        points.append({
            "id": f"seg:{i}",
            "modality": "audio",
            "proj": round(min(duration / 30.0, 1.0), 3),
            "conf": 0.9,
            "summary": text[:200],
        })

    speakers = transcript.get("speakers") or {}
    total_duration = max(
        (seg.get("end", 0.0) for seg in segments), default=0.0
    )
    spectrum = [
        round(min(len(segments) / 100.0, 1.0), 3),      # segment density
        round(min(total_duration / 3600.0, 1.0), 3),     # duration (norm to 1h)
        round(min(len(speakers) / 5.0, 1.0), 3),         # speaker diversity
    ]

    return {
        "spec": CGP_SPEC_VERSION,
        "summary": f"ffmpeg-whisper: transcribed {len(segments)} segments",
        "created_at": datetime.now(tz.utc).isoformat(),
        "super_nodes": [{
            "id": f"transcription:{request_id}",
            "label": "ffmpeg-whisper",
            "x": 0.0, "y": 0.0, "r": 0.3,
            "constellations": [{
                "id": f"transcription.segments.{request_id}",
                "anchor": [0.5, 0.5, 0.5],
                "spectrum": spectrum,
                "points": points,
            }],
        }],
        "meta": {
            "source": CGP_SUBJECT,
            "tags": ["transcription", "audio", "whisper"],
            "language": transcript.get("language"),
            "model": transcript.get("model"),
            "provider": transcript.get("provider"),
            "video_id": video_id,
            "audio_uri": audio_uri,
            "speaker_count": len(speakers),
        },
    }


async def _publish_cgp_async(subject: str, payload: Dict[str, Any]) -> None:
    """Publish to NATS via persistent client (best-effort, async)."""
    global _nats_client
    if _nats_client is None or _nats_client.is_closed:
        logger.warning("NATS client not connected, skipping publish to %s", subject)
        return
    try:
        await _nats_client.publish(subject, json.dumps(payload).encode("utf-8"))
        await _nats_client.flush()
        logger.info("Published CGP to %s", subject)
    except Exception as exc:
        logger.warning("NATS publish to %s failed (non-fatal): %s", subject, exc)


def _publish_cgp(subject: str, payload: Dict[str, Any]) -> None:
    """Publish to NATS, works from both sync and async contexts."""
    import threading

    async def _do():
        await _publish_cgp_async(subject, payload)

    # If called from a sync FastAPI endpoint (threadpool), schedule on the main loop
    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(_do(), loop)
    except RuntimeError:
        # No running loop — fallback to fire-and-forget thread
        t = threading.Thread(target=lambda: asyncio.run(_do()), daemon=True)
        t.start()
# ── end CHIT ──────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan with NATS service announcement
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FFmpeg-Whisper service lifespan with NATS service announcement."""
    # Get service configuration for announcement
    port = int(os.getenv("PORT", "8078"))
    hostname = os.getenv("HOSTNAME", socket.gethostname())
    slug = os.getenv("SERVICE_SLUG", "ffmpeg-whisper")
    name = os.getenv("SERVICE_NAME", "PMOVES FFmpeg-Whisper")
    url = os.getenv("SERVICE_URL") or f"http://{hostname}:{port}"
    health_check = f"{url}/healthz"

    # Announce service on NATS
    if NATS_ANNOUNCE_AVAILABLE:
        try:
            await announce_service(
                nats_url=os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222"),
                slug=slug,
                name=name,
                url=url,
                health_check=health_check,
                tier=ServiceTier.MEDIA,
                port=port,
                metadata={"version": "4.0.0"},
                retry=True,
            )
            logger.info("NATS service announcement published: %s at %s", slug, url)
        except Exception as e:
            logger.warning("Failed to publish NATS service announcement: %s", e)

    # Connect persistent NATS client for CGP publishing
    global _nats_client
    if NATS_CGP_AVAILABLE and CGP_PUBLISH_ENABLED:
        try:
            _nats_client = await nats_pkg.connect(NATS_URL)
            logger.info("NATS CGP client connected to %s", NATS_URL)
        except Exception as e:
            logger.warning("NATS CGP client connection failed (non-fatal): %s", e)

    yield

    # Shutdown: close persistent NATS client
    if _nats_client and not _nats_client.is_closed:
        try:
            await _nats_client.close()
            logger.info("NATS CGP client closed")
        except Exception:
            pass


app = FastAPI(title="FFmpeg+Whisper", version="4.0.0", lifespan=lifespan)


MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID", "")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

MEDIA_AUDIO_URL = os.environ.get("MEDIA_AUDIO_URL")
PYANNOTE_AUTH_TOKEN = os.environ.get("PYANNOTE_AUTH_TOKEN")


def _coerce_timeout(value: Optional[str], default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:  # pragma: no cover - defensive guard
        logger.warning("Invalid timeout value '%s'; falling back to %s", value, default)
        return default


MEDIA_AUDIO_TIMEOUT = _coerce_timeout(os.environ.get("MEDIA_AUDIO_TIMEOUT"), 120.0)


DEFAULT_PROVIDER = os.environ.get("FFW_PROVIDER", "faster-whisper").lower()
SUPPORTED_PROVIDERS: Tuple[ProviderLiteral, ...] = ("faster-whisper", "whisper", "qwen2-audio")
if DEFAULT_PROVIDER not in SUPPORTED_PROVIDERS:
    DEFAULT_PROVIDER = "faster-whisper"

DEFAULT_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
QWEN2_AUDIO_MODEL = os.environ.get("QWEN2_AUDIO_MODEL", "Qwen/Qwen2-Audio-7B-Instruct")
QWEN2_AUDIO_MAX_NEW_TOKENS = int(os.environ.get("QWEN2_AUDIO_MAX_NEW_TOKENS", "512"))


def s3_client():
    if boto3 is None:  # pragma: no cover - real runtime installs boto3
        raise RuntimeError("boto3 is required but not installed")
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client(
        "s3",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        endpoint_url=endpoint_url,
    )


@app.get("/healthz")
def healthz() -> Dict[str, bool]:
    return {"ok": True}


def _detect_cuda_available() -> bool:
    forced = os.environ.get("USE_CUDA")
    if forced:
        if forced.lower() == "true":
            return True
        if forced.lower() == "false":
            return False
    if torch is not None and hasattr(torch, "cuda"):
        try:  # pragma: no cover - hardware dependent
            if torch.cuda.is_available():
                return True
        except Exception:  # pragma: no cover - defensive
            logger.debug("torch.cuda.is_available() raised", exc_info=True)
    return shutil.which("nvidia-smi") is not None


def _select_device() -> str:
    explicit = os.environ.get("WHISPER_DEVICE")
    if explicit:
        return explicit
    return "cuda" if _detect_cuda_available() else "cpu"


def _compute_type(device: str) -> str:
    return os.environ.get("WHISPER_COMPUTE_TYPE") or ("float16" if device.startswith("cuda") else "int8")


def ffmpeg_extract_audio(src: str, dst: str, sample_rate: int = 16000) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        dst,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _clean_segment(seg: Dict[str, Any], index: int) -> Dict[str, Any]:
    cleaned = {
        "id": seg.get("id", index),
        "start": float(seg.get("start", 0.0)),
        "end": float(seg.get("end", 0.0)),
        "text": (seg.get("text") or "").strip(),
        "speaker": seg.get("speaker"),
    }
    words = seg.get("words") or seg.get("word_segments")
    if words:
        cleaned["words"] = [_clean_word(w) for w in words]
    return cleaned


def _clean_word(word: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "start": float(word.get("start", 0.0)) if word.get("start") is not None else None,
        "end": float(word.get("end", 0.0)) if word.get("end") is not None else None,
        "word": word.get("word") or word.get("text"),
        "confidence": float(word.get("confidence", 0.0)) if word.get("confidence") is not None else None,
        "speaker": word.get("speaker"),
    }


def _summarise_speakers(segments: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Dict[str, Any]] = {}
    for seg in segments:
        speaker = seg.get("speaker")
        if not speaker:
            continue
        entry = summary.setdefault(
            speaker,
            {
                "speaker": speaker,
                "duration": 0.0,
                "segments": 0,
            },
        )
        entry["duration"] += max(seg.get("end", 0.0) - seg.get("start", 0.0), 0.0)
        entry["segments"] += 1
    return summary


def _run_whisperx(audio_path: str, *, language: Optional[str], model_name: str, diarize: bool) -> Dict[str, Any]:
    device = _select_device()
    compute_type = _compute_type(device)
    try:  # pragma: no cover - optional dependency
        import whisperx  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(500, "whisperx package is required for provider=whisper") from exc

    logger.info("loading WhisperX model %s on %s", model_name, device)
    model = whisperx.load_model(model_name, device=device, compute_type=compute_type)
    transcription = model.transcribe(audio_path, language=language)
    detected_language = transcription.get("language") or language
    align_model, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
    aligned = whisperx.align(transcription["segments"], align_model, metadata, audio_path, device=device)
    if diarize and PYANNOTE_AUTH_TOKEN:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=PYANNOTE_AUTH_TOKEN, device=device)
        diarization = diarize_model(audio_path)
        aligned = whisperx.assign_word_speakers(diarization, aligned)

    segments = [_clean_segment(seg, idx) for idx, seg in enumerate(aligned.get("segments", []))]
    words = aligned.get("word_segments") or aligned.get("words")
    if words:
        words = [_clean_word(word) for word in words]
    text = transcription.get("text") or "".join(seg.get("text", "") for seg in segments)
    return {
        "text": text.strip(),
        "language": detected_language,
        "segments": segments,
        "word_segments": words,
        "speakers": _summarise_speakers(segments),
        "device": device,
        "model": model_name,
    }


@lru_cache(maxsize=4)
def _load_faster_whisper(model_name: str, device: str, compute_type: str):
    if WhisperModel is None:
        raise HTTPException(500, "faster-whisper backend not available")
    logger.info("loading faster-whisper model %s (device=%s, compute_type=%s)", model_name, device, compute_type)
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def _run_faster_whisper(audio_path: str, *, language: Optional[str], model_name: str) -> Dict[str, Any]:
    device = _select_device()
    compute_type = _compute_type(device)
    model = _load_faster_whisper(model_name, device, compute_type)
    segments_iter, info = model.transcribe(audio_path, language=language)

    segments: List[Dict[str, Any]] = []
    text_parts: List[str] = []
    for idx, seg in enumerate(segments_iter):
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", 0.0) or 0.0)
        text = (getattr(seg, "text", "") or "").strip()
        segments.append({"id": idx, "start": start, "end": end, "text": text, "speaker": None})
        text_parts.append(text)

    text = "".join(text_parts).strip()
    language_out = getattr(info, "language", None) or language
    return {
        "text": text,
        "language": language_out,
        "segments": segments,
        "word_segments": None,
        "speakers": _summarise_speakers(segments),
        "device": device,
        "model": model_name,
    }


@lru_cache(maxsize=2)
def _load_qwen2_audio(model_name: str, device: str, dtype_name: str):
    if torch is None:  # pragma: no cover - optional dependency
        raise HTTPException(500, "torch is required for provider=qwen2-audio")
    try:  # pragma: no cover - optional dependency
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(500, "transformers is required for provider=qwen2-audio") from exc

    dtype = getattr(torch, dtype_name)
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name, torch_dtype=dtype, low_cpu_mem_usage=True)
    model.to(device)
    model.eval()
    return processor, model


def _run_qwen2_audio(audio_path: str, *, language: Optional[str], model_name: str) -> Dict[str, Any]:
    if torch is None:  # pragma: no cover - optional dependency
        raise HTTPException(500, "torch is required for provider=qwen2-audio")
    try:  # pragma: no cover - optional dependency
        import torchaudio
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(500, "torchaudio is required for provider=qwen2-audio") from exc

    device = _select_device()
    dtype_name = "float16" if device.startswith("cuda") else "float32"
    processor, model = _load_qwen2_audio(model_name, device, dtype_name)

    waveform, sample_rate = torchaudio.load(audio_path)
    if waveform.dim() > 1 and waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != 16000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
        sample_rate = 16000

    inputs = processor(waveform.squeeze().numpy(), sampling_rate=sample_rate, return_tensors="pt")
    input_features = inputs["input_features"].to(device)

    with torch.inference_mode():  # pragma: no cover - heavy path
        generated = model.generate(input_features, max_new_tokens=QWEN2_AUDIO_MAX_NEW_TOKENS)

    text = processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
    duration = float(waveform.shape[-1] / sample_rate) if sample_rate else 0.0

    segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": duration,
            "text": text,
            "speaker": None,
        }
    ]

    return {
        "text": text,
        "language": language or "auto",
        "segments": segments,
        "word_segments": None,
        "speakers": _summarise_speakers(segments),
        "device": device,
        "model": model_name,
    }


def _prepare_segment_rows(
    video_id: Optional[str],
    audio_uri: Optional[str],
    segments: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for seg in segments:
        rows.append(
            {
                "video_id": video_id,
                "ts_start": float(seg.get("start", 0.0)),
                "ts_end": float(seg.get("end", 0.0)),
                "uri": audio_uri,
                "meta": {
                    "text": seg.get("text"),
                    "speaker": seg.get("speaker"),
                    "words": seg.get("words"),
                },
            }
        )
    return rows


def _build_s3_uri(bucket: str, key: str) -> str:
    scheme = "https" if MINIO_SECURE else "http"
    endpoint = MINIO_ENDPOINT if "://" not in MINIO_ENDPOINT else MINIO_ENDPOINT.split("//", 1)[1]
    return f"{scheme}://{endpoint}/{bucket}/{key}"


def _forward_to_audio_service(payload: Dict[str, Any]) -> bool:
    if not MEDIA_AUDIO_URL:
        return False

    try:
        resp = requests.post(MEDIA_AUDIO_URL, json=payload, timeout=MEDIA_AUDIO_TIMEOUT)
    except Exception as exc:  # pragma: no cover - network failure depends on environment
        logger.warning("Failed to forward transcription to media-audio: %s", exc, exc_info=True)
        return False

    if not resp.ok:
        logger.warning(
            "Media-audio forward returned non-success status %s: %s",
            getattr(resp, "status_code", "?"),
            getattr(resp, "text", ""),
        )
        return False

    return True


def _transcribe_with_provider(
    provider: ProviderLiteral,
    audio_path: str,
    *,
    language: Optional[str],
    model_name: str,
    diarize: bool,
) -> Dict[str, Any]:
    if provider == "faster-whisper":
        return _run_faster_whisper(audio_path, language=language, model_name=model_name)
    if provider == "whisper":
        return _run_whisperx(audio_path, language=language, model_name=model_name, diarize=diarize)
    if provider == "qwen2-audio":
        model = model_name or QWEN2_AUDIO_MODEL
        return _run_qwen2_audio(audio_path, language=language, model_name=model)
    raise HTTPException(400, f"Unsupported provider '{provider}'")


@app.post("/transcribe")
def transcribe(body: Dict[str, Any] = Body(...)):
    bucket = body.get("bucket")
    key = body.get("key")
    video_id = body.get("video_id")
    namespace = body.get("namespace")

    if not bucket or not key:
        raise HTTPException(400, "bucket and key required")

    provider = (body.get("provider") or DEFAULT_PROVIDER).lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, f"provider must be one of {', '.join(SUPPORTED_PROVIDERS)}")

    language = body.get("language")
    model_name = body.get("whisper_model") or DEFAULT_WHISPER_MODEL
    diarize = bool(body.get("diarize", True))
    out_audio_key = body.get("out_audio_key")

    tmpdir = tempfile.mkdtemp(prefix="ffw-")
    client = s3_client()
    forwarded: Optional[bool] = None

    try:
        source_path = os.path.join(tmpdir, "source")
        with open(source_path, "wb") as fh:
            client.download_fileobj(bucket, key, fh)

        audio_path = os.path.join(tmpdir, "audio.wav")
        ffmpeg_extract_audio(source_path, audio_path)

        if out_audio_key:
            client.upload_file(audio_path, bucket, out_audio_key)
            audio_uri = _build_s3_uri(bucket, out_audio_key)
        else:
            audio_uri = _build_s3_uri(bucket, key)

        transcript = _transcribe_with_provider(
            provider, audio_path, language=language, model_name=model_name, diarize=diarize
        )
        transcript["audio_uri"] = audio_uri
        transcript["provider"] = provider

        rows = _prepare_segment_rows(video_id, audio_uri, transcript.get("segments", []))

        if MEDIA_AUDIO_URL:
            forward_payload = {
                "bucket": bucket,
                "key": key,
                "video_id": video_id,
                "namespace": namespace,
                "language": transcript.get("language") or language,
                "whisper_model": model_name,
                "provider": provider,
                "diarize": diarize,
                "transcript": transcript,
            }
            forwarded = _forward_to_audio_service(forward_payload)
            if not forwarded:
                try:
                    insert_segments(rows)
                except Exception as seg_err:
                    logger.warning("Segment storage failed (non-fatal): %s", seg_err)
        else:
            try:
                insert_segments(rows)
            except Exception as seg_err:
                logger.warning("Segment storage failed (non-fatal): %s", seg_err)

        # Publish CGP to GEOMETRY BUS
        if CGP_PUBLISH_ENABLED and NATS_CGP_AVAILABLE:
            try:
                req_id = str(uuid.uuid4())
                cgp = _build_transcription_cgp(transcript, video_id, audio_uri, req_id)
                _publish_cgp(CGP_SUBJECT, cgp)
                _publish_cgp(TRANSCRIPT_READY_SUBJECT, {
                    "service": "ffmpeg-whisper",
                    "request_id": req_id,
                    "video_id": video_id,
                    "audio_uri": audio_uri,
                    "language": transcript.get("language") or language,
                    "segment_count": len(transcript.get("segments") or []),
                    "ts": datetime.now(tz.utc).isoformat(),
                })
            except Exception as cgp_exc:
                logger.warning("CGP publish failed (non-fatal): %s", cgp_exc)

        return {
            "ok": True,
            "text": transcript.get("text"),
            "language": transcript.get("language") or language,
            "segments": transcript.get("segments"),
            "word_segments": transcript.get("word_segments"),
            "speakers": transcript.get("speakers"),
            "audio_uri": audio_uri,
            "s3_uri": audio_uri,
            "model": transcript.get("model") or model_name,
            "device": transcript.get("device"),
            "provider": provider,
            "forwarded": forwarded,
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"ffmpeg error: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("transcription error")
        raise HTTPException(500, f"transcribe error: {exc}") from exc
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/transcribe_file")
async def transcribe_file(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    whisper_model: Optional[str] = Form(None),
    diarize: bool = Form(True),
) -> Dict[str, Any]:
    """
    Transcribe an uploaded audio file directly (multipart/form-data).

    This complements the existing `/transcribe` endpoint (bucket/key JSON) and is used
    by Flute Gateway for ad-hoc STT requests.
    """

    chosen_provider = (provider or DEFAULT_PROVIDER).lower()
    if chosen_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, f"provider must be one of {', '.join(SUPPORTED_PROVIDERS)}")

    model_name = whisper_model or model or DEFAULT_WHISPER_MODEL

    tmpdir = tempfile.mkdtemp(prefix="ffw-upload-")
    try:
        src_path = os.path.join(tmpdir, audio.filename or "source")
        raw_bytes = await audio.read()
        with open(src_path, "wb") as fh:
            fh.write(raw_bytes)

        audio_path = os.path.join(tmpdir, "audio.wav")
        ffmpeg_extract_audio(src_path, audio_path)

        transcript = _transcribe_with_provider(
            chosen_provider,
            audio_path,
            language=language,
            model_name=model_name,
            diarize=diarize,
        )

        # Publish CGP to GEOMETRY BUS
        if CGP_PUBLISH_ENABLED and NATS_CGP_AVAILABLE:
            try:
                req_id = str(uuid.uuid4())
                cgp = _build_transcription_cgp(transcript, None, None, req_id)
                await _publish_cgp_async(CGP_SUBJECT, cgp)
            except Exception as cgp_exc:
                logger.warning("CGP publish failed (non-fatal): %s", cgp_exc)

        return {
            "ok": True,
            "text": transcript.get("text"),
            "language": transcript.get("language") or language,
            "segments": transcript.get("segments"),
            "word_segments": transcript.get("word_segments"),
            "speakers": transcript.get("speakers"),
            "model": transcript.get("model") or model_name,
            "device": transcript.get("device"),
            "provider": chosen_provider,
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"ffmpeg error: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("transcription error")
        raise HTTPException(500, f"transcribe error: {exc}") from exc
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
