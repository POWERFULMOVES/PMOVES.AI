
"""Whisper transcription service with WhisperX diarisation support."""

from __future__ import annotations
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

import boto3
import requests
from fastapi import Body, FastAPI, HTTPException

import logging
import os, tempfile, shutil, subprocess
from typing import Dict, Any, Optional

from fastapi import FastAPI, Body, HTTPException

try:  # pragma: no cover - exercised via tests with monkeypatching
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

try:  # pragma: no cover - exercised via tests with monkeypatching
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore
import shutil as _shutil


from services.common.supabase import insert_segments


logger = logging.getLogger(__name__)


app = FastAPI(title="FFmpeg+WhisperX", version="3.0.0")


MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"

MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

MEDIA_AUDIO_URL = os.environ.get("MEDIA_AUDIO_URL")
PYANNOTE_AUTH_TOKEN = os.environ.get("PYANNOTE_AUTH_TOKEN")

MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")
MEDIA_AUDIO_URL = os.environ.get("MEDIA_AUDIO_URL")


logger = logging.getLogger(__name__)


def _coerce_timeout(value: Optional[str]) -> float:
    if not value:
        return 10.0
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid MEDIA_AUDIO_TIMEOUT value '%s'; using default", value)
        return 10.0


MEDIA_AUDIO_TIMEOUT = _coerce_timeout(os.environ.get("MEDIA_AUDIO_TIMEOUT"))


def s3_client():
    if boto3 is None:  # pragma: no cover - real runtime will have boto3
        raise RuntimeError("boto3 is required but not installed")
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client(
        "s3",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        endpoint_url=endpoint_url,
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _select_device() -> str:
    device = os.environ.get("WHISPER_DEVICE")
    if device:
        return device
    if os.environ.get("USE_CUDA", "false").lower() == "true":
        return "cuda"
    if shutil.which("nvidia-smi"):
        return "cuda"
    return "cpu"


def _ffmpeg_extract_wav(src: str, dst: str, sample_rate: int = 16000) -> None:
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


def _summarise_speakers(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    compute_type = os.environ.get("WHISPER_COMPUTE_TYPE") or ("float16" if device == "cuda" else "int8")
    try:
        import whisperx  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on deployment
        raise HTTPException(500, "whisperx package is required") from exc

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
    }


def _forward_to_audio_service(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not MEDIA_AUDIO_URL:
        return None
    url = MEDIA_AUDIO_URL.rstrip("/") + "/ingest-transcript"
    timeout = float(os.environ.get("MEDIA_AUDIO_TIMEOUT", "120"))
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # pragma: no cover - network conditions
        logger.warning("unable to forward transcript to media-audio: %s", exc)
        return None


def _prepare_segment_rows(
    video_id: Optional[str],
    audio_uri: Optional[str],
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
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


@app.post("/transcribe")
def transcribe(body: Dict[str, Any] = Body(...)):
    bucket = body.get("bucket")
    key = body.get("key")
    video_id = body.get("video_id")
    namespace = body.get("namespace")

def _forward_to_audio_service(payload: Dict[str, Any]) -> bool:
    """Forward transcription metadata to the media-audio service.

    Returns True when forwarding succeeds, False otherwise. When forwarding is
    disabled (MEDIA_AUDIO_URL unset) or encounters an error, False is returned
    so the caller can fall back to inserting segments locally.
    """

    if not MEDIA_AUDIO_URL:
        return False

    try:
        import requests  # type: ignore
    except ImportError:  # pragma: no cover - should not happen in production
        logger.warning("requests is unavailable; skipping media-audio forwarding")
        return False

    try:
        resp = requests.post(MEDIA_AUDIO_URL, json=payload, timeout=MEDIA_AUDIO_TIMEOUT)
    except Exception as exc:  # pragma: no cover - network failures are rare in tests
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


@app.post('/transcribe')
def transcribe(body: Dict[str,Any] = Body(...)):
    bucket = body.get('bucket'); key = body.get('key'); vid = body.get('video_id')

    if not bucket or not key:
        raise HTTPException(400, "bucket and key required")

    language = body.get("language")
    model_name = body.get("whisper_model") or os.environ.get("WHISPER_MODEL", "large-v3")
    diarize = body.get("diarize", True)
    out_audio_key = body.get("out_audio_key")

    tmpdir = tempfile.mkdtemp(prefix="ffw-")
    client = s3_client()
    try:
        source_path = os.path.join(tmpdir, "source")
        with open(source_path, "wb") as fh:
            client.download_fileobj(bucket, key, fh)

        wav_path = os.path.join(tmpdir, "audio.wav")
        _ffmpeg_extract_wav(source_path, wav_path)

        if out_audio_key:

            client.upload_file(wav_path, bucket, out_audio_key)
            audio_uri = _build_s3_uri(bucket, out_audio_key)
        else:
            audio_uri = _build_s3_uri(bucket, key)

        transcript = _run_whisperx(wav_path, language=language, model_name=model_name, diarize=diarize)
        transcript["audio_uri"] = audio_uri

        rows = _prepare_segment_rows(video_id, audio_uri, transcript.get("segments", []))
        forwarded = None
        if MEDIA_AUDIO_URL:
            forward_payload = {
                "bucket": bucket,
                "key": key,
                "video_id": video_id,
                "namespace": namespace,
                "language": transcript.get("language") or language,
                "whisper_model": model_name,
                "diarize": diarize,
                "transcript": transcript,
            }
            forwarded = _forward_to_audio_service(forward_payload)
        else:
            insert_segments(rows)

        return {
            "ok": True,
            "text": transcript.get("text"),
            "language": transcript.get("language") or language,
            "segments": transcript.get("segments"),
            "word_segments": transcript.get("word_segments"),
            "speakers": transcript.get("speakers"),
            "audio_uri": audio_uri,
            "model": model_name,
            "forwarded": forwarded,
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"ffmpeg error: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("transcription error")
        raise HTTPException(500, f"transcribe error: {exc}") from exc

            s3.upload_file(audio_path, bucket, out_audio_key)
            scheme = 'https' if MINIO_SECURE else 'http'
            s3_uri = f"{scheme}://{MINIO_ENDPOINT}/{bucket}/{out_audio_key}"
        # faster-whisper (ctranslate2). Uses CUDA if available.
        device = _select_device()
        compute_type = 'float16' if device == 'cuda' else 'int8'
        if WhisperModel is None:
            raise HTTPException(500, 'WhisperModel backend not available')
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(audio_path, language=lang)
        segs = []
        text_parts = []
        for seg in segments_iter:
            try:
                segs.append({
                    'start': float(getattr(seg, 'start', 0.0) or 0.0),
                    'end': float(getattr(seg, 'end', 0.0) or 0.0),
                    'text': (getattr(seg, 'text', '') or '').strip()
                })
                text_parts.append((getattr(seg, 'text', '') or ''))
            except Exception:
                continue
        text = ''.join(text_parts)
        rows = [
            {
                'video_id': vid,
                'ts_start': s['start'],
                'ts_end': s['end'],
                'uri': s3_uri,
                'meta': {'text': s['text']}
            }
            for s in segs
        ]
        payload = {
            'video_id': vid,
            'segments': segs,
            'rows': rows,
            'bucket': bucket,
            'key': key,
            'audio_uri': s3_uri,
            'language': getattr(info, 'language', None) or lang,
            'text': text,
        }
        forwarded = _forward_to_audio_service(payload)
        if not forwarded:
            if MEDIA_AUDIO_URL:
                logger.info("media-audio forwarding unavailable; inserting segments locally for video_id=%s", vid)
            insert_segments(rows)
        return {'ok': True, 'text': text, 'segments': segs, 'language': getattr(info, 'language', None) or lang, 's3_uri': s3_uri, 'device': device}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"ffmpeg error: {e}")
    except Exception as e:
        raise HTTPException(500, f"transcribe error: {e}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

