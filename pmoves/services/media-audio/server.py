"""Media audio orchestration service.

This service coordinates the full audio analysis pipeline used by PMOVES.

Key capabilities:

* Download audio assets from MinIO/S3
* Trigger Whisper Large-v3 (via WhisperX) transcription and alignment
* Run optional diarisation with Pyannote Audio (requires ``PYANNOTE_AUTH_TOKEN``)
* Aggregate segment level features (RMS energy, spectral centroid, tempo, etc.)
* Evaluate emotion classifiers (standard Hugging Face pipelines or SeaLLM models)
* Persist results to Supabase and emit ``analysis.audio.v1`` envelopes over NATS

Environment variables
----------------------

``MINIO_ENDPOINT``            : MinIO/S3 endpoint (``host:port`` or URL)
``MINIO_ACCESS_KEY``          : MinIO/S3 access key
``MINIO_SECRET_KEY``          : MinIO/S3 secret key
``MINIO_SECURE``              : ``true`` for HTTPS endpoints
``SUPABASE_URL`` / ``SUPABASE_KEY`` : Required for Supabase writes
``NATS_URL``                  : Broker URL for event emission
``EMOTION_MODEL``             : Hugging Face model id for emotion detection
``SEA_LLM_MODEL``             : Optional SeaLLM audio model id (used before ``EMOTION_MODEL``)
``PYANNOTE_AUTH_TOKEN``       : Required for diarisation with Pyannote/WhisperX
``FFMPEG_WHISPER_URL``        : Optional remote transcription service (``ffmpeg-whisper``)
``AUDIO_DEFAULT_NAMESPACE``   : Namespace to stamp on emitted events when missing
``WHISPER_DEVICE``            : Force ``cpu`` / ``cuda``; auto-detects otherwise
``WHISPER_COMPUTE_TYPE``      : Override WhisperX compute type (defaults by device)

The ``/process`` endpoint is the recommended entry point.  It orchestrates the
entire pipeline and returns the consolidated analysis artefacts alongside the
NATS event envelope produced.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
import librosa
import numpy as np
import requests
import soundfile as sf
from fastapi import Body, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from transformers import pipeline

from services.common.events import publish
from services.common.supabase import insert_emotions, insert_segments


logger = logging.getLogger(__name__)


EMOTION_MODEL = os.environ.get("EMOTION_MODEL", "superb/hubert-large-superb-er")
SEA_LLM_MODEL = os.environ.get("SEA_LLM_MODEL")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

FFMPEG_WHISPER_URL = os.environ.get("FFMPEG_WHISPER_URL")
DEFAULT_NAMESPACE = os.environ.get("AUDIO_DEFAULT_NAMESPACE", "pmoves")


def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client(
        "s3",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        endpoint_url=endpoint_url,
    )


@dataclass
class AudioBuffer:
    """Simple container for audio data and temporary file housekeeping."""

    path: str
    samples: np.ndarray
    sample_rate: int
    tmpdir: Optional[str] = None

    def cleanup(self) -> None:
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None


class TranscriptPayload(BaseModel):
    text: str = ""
    language: Optional[str] = None
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    word_segments: Optional[List[Dict[str, Any]]] = None
    speakers: Optional[Dict[str, Any]] = None
    audio_uri: Optional[str] = None


class ProcessRequest(BaseModel):
    bucket: str
    key: str
    video_id: Optional[str] = None
    namespace: Optional[str] = None
    language: Optional[str] = None
    whisper_model: Optional[str] = None
    diarize: bool = True
    compute_emotions: bool = True
    compute_features: bool = True
    transcript: Optional[TranscriptPayload] = None


@dataclass
class ProcessResult:
    transcript: Dict[str, Any]
    segments: List[Dict[str, Any]]
    segment_rows: List[Dict[str, Any]]
    emotions: List[Dict[str, Any]]
    features: Dict[str, Any]
    video_id: Optional[str]
    namespace: Optional[str]
    audio_uri: Optional[str]


class AudioProcessor:
    """Coordinates transcription, diarisation, emotions and feature extraction."""

    def __init__(self) -> None:
        self._emotion_pipeline = None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def process(self, request: ProcessRequest) -> ProcessResult:
        logger.info("processing audio request video_id=%s key=%s", request.video_id, request.key)
        namespace = request.namespace or DEFAULT_NAMESPACE
        audio: Optional[AudioBuffer] = None
        try:
            audio = self._download_audio(request.bucket, request.key)
            transcript = self._resolve_transcript(request, audio)
            segments = transcript.get("segments") or []
            features = (
                self._compute_features(audio.samples, audio.sample_rate, segments)
                if request.compute_features
                else {}
            )
            emotions = (
                self._extract_emotions(
                    request,
                    audio.samples,
                    audio.sample_rate,
                    segments,
                    namespace,
                )
                if request.compute_emotions
                else []
            )
            audio_uri = transcript.get("audio_uri") or self._build_s3_uri(request.bucket, request.key)
            segment_rows = self._prepare_segment_rows(
                request.video_id,
                segments,
                audio_uri,
                features,
                namespace,
            )
            return ProcessResult(
                transcript=transcript,
                segments=segments,
                segment_rows=segment_rows,
                emotions=emotions,
                features=features,
                video_id=request.video_id,
                namespace=namespace,
                audio_uri=audio_uri,
            )
        finally:
            if audio is not None:
                audio.cleanup()

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------
    def _download_audio(self, bucket: str, key: str) -> AudioBuffer:
        tmpdir = tempfile.mkdtemp(prefix="media-audio-")
        raw_path = os.path.join(tmpdir, "source")
        client = s3_client()
        try:
            with open(raw_path, "wb") as fh:
                client.download_fileobj(bucket, key, fh)
        except Exception as exc:  # pragma: no cover - boto errors are contextual
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(500, f"Unable to download audio: {exc}") from exc

        wav_path = self._ensure_wav(raw_path, tmpdir)
        samples, sr = self._load_waveform(wav_path)
        return AudioBuffer(path=wav_path, samples=samples, sample_rate=sr, tmpdir=tmpdir)

    def _ensure_wav(self, source_path: str, tmpdir: str) -> str:
        if source_path.lower().endswith(".wav"):
            return source_path
        wav_path = os.path.join(tmpdir, "audio.wav")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            wav_path,
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on ffmpeg runtime
            raise HTTPException(500, f"ffmpeg conversion failed: {exc}") from exc
        return wav_path

    def _load_waveform(self, path: str) -> Tuple[np.ndarray, int]:
        try:
            data, sr = sf.read(path)
        except RuntimeError:
            data, sr = librosa.load(path, sr=None, mono=False)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        return data.astype(np.float32), int(sr)

    # ------------------------------------------------------------------
    # Transcription helpers
    # ------------------------------------------------------------------
    def _resolve_transcript(self, request: ProcessRequest, audio: AudioBuffer) -> Dict[str, Any]:
        if request.transcript is not None:
            logger.debug("using supplied transcript for key=%s", request.key)
            return json.loads(request.transcript.json())

        transcript = None
        if FFMPEG_WHISPER_URL:
            transcript = self._call_remote_transcription(request)
        if transcript is None:
            transcript = self._run_local_transcription(audio.path, request)
        return transcript

    def _call_remote_transcription(self, request: ProcessRequest) -> Optional[Dict[str, Any]]:
        url = FFMPEG_WHISPER_URL.rstrip("/") + "/transcribe"
        payload = {
            "bucket": request.bucket,
            "key": request.key,
            "video_id": request.video_id,
            "language": request.language,
            "whisper_model": request.whisper_model,
            "namespace": request.namespace,
            "diarize": request.diarize,
            "compute_emotions": request.compute_emotions,
            "compute_features": request.compute_features,
        }
        timeout = float(os.environ.get("FFMPEG_WHISPER_TIMEOUT", "120"))
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # pragma: no cover - network errors are environment specific
            logger.warning("remote transcription failed: %s", exc)
            return None
        if not data.get("ok"):
            return None
        transcript = data.get("transcript")
        if transcript is None:
            transcript = {
                "text": data.get("text", ""),
                "language": data.get("language"),
                "segments": data.get("segments", []),
            }
            if "word_segments" in data:
                transcript["word_segments"] = data["word_segments"]
            if "speakers" in data:
                transcript["speakers"] = data["speakers"]
            if "audio_uri" in data:
                transcript["audio_uri"] = data["audio_uri"]
        return transcript

    def _run_local_transcription(self, audio_path: str, request: ProcessRequest) -> Dict[str, Any]:
        logger.info("running local WhisperX transcription for %s", audio_path)
        device = self._select_device()
        compute_type = os.environ.get("WHISPER_COMPUTE_TYPE") or ("float16" if device == "cuda" else "int8")
        model_name = request.whisper_model or os.environ.get("WHISPER_MODEL", "large-v3")
        try:
            import whisperx  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise HTTPException(500, "whisperx is required for local transcription") from exc

        model = whisperx.load_model(model_name, device=device, compute_type=compute_type)
        result = model.transcribe(audio_path, language=request.language)
        language = result.get("language") or request.language
        align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
        aligned_result = whisperx.align(result["segments"], align_model, metadata, audio_path, device=device)
        if request.diarize and os.environ.get("PYANNOTE_AUTH_TOKEN"):
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=os.environ.get("PYANNOTE_AUTH_TOKEN"),
                device=device,
            )
            diarize_segments = diarize_model(audio_path)
            aligned_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)

        segments = [self._clean_segment(seg, idx) for idx, seg in enumerate(aligned_result.get("segments", []))]
        word_segments = aligned_result.get("word_segments") or aligned_result.get("words")
        if word_segments:
            word_segments = [self._clean_word(word) for word in word_segments]
        text = result.get("text") or "".join(seg.get("text", "") for seg in segments)
        speakers = self._summarise_speakers(segments)
        return {
            "text": text.strip(),
            "language": language,
            "segments": segments,
            "word_segments": word_segments,
            "speakers": speakers,
        }

    # ------------------------------------------------------------------
    # Feature and emotion helpers
    # ------------------------------------------------------------------
    def _compute_features(
        self,
        samples: np.ndarray,
        sample_rate: int,
        segments: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if samples.size == 0:
            return {"global": {}, "by_segment": {}}

        y = samples.astype(np.float32)
        duration = float(len(y) / sample_rate)
        try:
            rms = float(np.mean(librosa.feature.rms(y=y)))
        except Exception:  # pragma: no cover - librosa edge cases
            rms = 0.0
        try:
            centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sample_rate)))
        except Exception:  # pragma: no cover
            centroid = 0.0
        try:
            zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
        except Exception:  # pragma: no cover
            zcr = 0.0
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sample_rate)
            tempo = float(tempo)
        except Exception:  # pragma: no cover
            tempo = 0.0

        by_segment: Dict[str, Dict[str, Any]] = {}
        for idx, segment in enumerate(segments):
            seg_id = str(segment.get("id", idx))
            start = max(float(segment.get("start", 0.0)), 0.0)
            end = max(float(segment.get("end", start)), start)
            s_index = int(math.floor(start * sample_rate))
            e_index = int(math.ceil(end * sample_rate))
            e_index = min(len(y), max(e_index, s_index + 1))
            snippet = y[s_index:e_index]
            if snippet.size == 0:
                continue
            try:
                seg_rms = float(np.mean(librosa.feature.rms(y=snippet)))
            except Exception:
                seg_rms = 0.0
            by_segment[seg_id] = {
                "start": start,
                "end": end,
                "duration": end - start,
                "rms": seg_rms,
                "speaker": segment.get("speaker"),
            }

        return {
            "global": {
                "duration": duration,
                "rms": rms,
                "spectral_centroid": centroid,
                "zero_crossing_rate": zcr,
                "tempo": tempo,
            },
            "by_segment": by_segment,
        }

    def _extract_emotions(
        self,
        request: ProcessRequest,
        samples: np.ndarray,
        sample_rate: int,
        segments: Iterable[Dict[str, Any]],
        namespace: str,
    ) -> List[Dict[str, Any]]:
        clf = self._load_emotion_pipeline()
        if clf is None:
            return []

        waveform = samples
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=1)

        def evaluate_window(start_idx: int, end_idx: int, ts_seconds: float, speaker: Optional[str]) -> Optional[Dict[str, Any]]:
            window = waveform[start_idx:end_idx]
            if window.size == 0:
                return None
            try:
                preds = clf({"array": window, "sampling_rate": sample_rate})
            except Exception:  # pragma: no cover - model/runtime specific
                return None
            if not preds:
                return None
            top = preds[0]
            return {
                "namespace": namespace,
                "video_id": request.video_id,
                "ts_seconds": ts_seconds,
                "label": top.get("label"),
                "score": float(top.get("score", 0.0)),
                "speaker": speaker,
            }

        emotions: List[Dict[str, Any]] = []
        if segments:
            for segment in segments:
                start = max(float(segment.get("start", 0.0)), 0.0)
                end = max(float(segment.get("end", start)), start)
                s_index = int(math.floor(start * sample_rate))
                e_index = int(math.ceil(end * sample_rate))
                e_index = min(len(waveform), max(e_index, s_index + 1))
                row = evaluate_window(s_index, e_index, start, segment.get("speaker"))
                if row:
                    emotions.append(row)
        else:
            window = int(sample_rate * 5)
            for idx in range(0, len(waveform), window):
                row = evaluate_window(idx, min(len(waveform), idx + window), idx / sample_rate, None)
                if row:
                    emotions.append(row)
        return emotions

    def _prepare_segment_rows(
        self,
        video_id: Optional[str],
        segments: Iterable[Dict[str, Any]],
        audio_uri: Optional[str],
        features: Dict[str, Any],
        namespace: str,
    ) -> List[Dict[str, Any]]:
        feature_map = features.get("by_segment", {}) if isinstance(features, dict) else {}
        rows = []
        for idx, segment in enumerate(segments):
            seg_id = str(segment.get("id", idx))
            meta: Dict[str, Any] = {
                "text": segment.get("text"),
                "speaker": segment.get("speaker"),
            }
            words = segment.get("words") or segment.get("word_segments")
            if words:
                meta["words"] = words
            if seg_id in feature_map:
                meta["features"] = feature_map[seg_id]
            rows.append(
                {
                    "namespace": namespace,
                    "video_id": video_id,
                    "ts_start": float(segment.get("start", 0.0)),
                    "ts_end": float(segment.get("end", 0.0)),
                    "uri": audio_uri,
                    "meta": meta,
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _build_s3_uri(self, bucket: str, key: str) -> str:
        scheme = "https" if MINIO_SECURE else "http"
        endpoint = MINIO_ENDPOINT if "://" not in MINIO_ENDPOINT else MINIO_ENDPOINT.split("//", 1)[1]
        return f"{scheme}://{endpoint}/{bucket}/{key}"

    def _select_device(self) -> str:
        device = os.environ.get("WHISPER_DEVICE")
        if device:
            return device
        if os.environ.get("USE_CUDA", "false").lower() == "true":
            return "cuda"
        if shutil.which("nvidia-smi"):
            return "cuda"
        return "cpu"

    def _load_emotion_pipeline(self):  # pragma: no cover - heavy model initialisation
        if self._emotion_pipeline is not None:
            return self._emotion_pipeline
        model_id = SEA_LLM_MODEL or EMOTION_MODEL
        try:
            self._emotion_pipeline = pipeline("audio-classification", model=model_id)
        except Exception as exc:
            logger.warning("failed to initialise emotion pipeline %s: %s", model_id, exc)
            self._emotion_pipeline = None
        return self._emotion_pipeline

    def _clean_segment(self, segment: Dict[str, Any], index: int) -> Dict[str, Any]:
        cleaned = {
            "id": segment.get("id", index),
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "text": (segment.get("text") or "").strip(),
            "speaker": segment.get("speaker"),
        }
        if "words" in segment and segment["words"]:
            cleaned["words"] = [self._clean_word(word) for word in segment["words"]]
        return cleaned

    def _clean_word(self, word: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "start": float(word.get("start", 0.0)) if word.get("start") is not None else None,
            "end": float(word.get("end", 0.0)) if word.get("end") is not None else None,
            "word": word.get("word") or word.get("text"),
            "confidence": float(word.get("confidence", 0.0)) if word.get("confidence") is not None else None,
            "speaker": word.get("speaker"),
        }

    def _summarise_speakers(self, segments: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, Any]] = {}
        for segment in segments:
            speaker = segment.get("speaker")
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
            duration = max(float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)), 0.0)
            entry["duration"] += duration
            entry["segments"] += 1
        return summary


processor = AudioProcessor()
app = FastAPI(title="Media-Audio", version="2.0.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}


async def _execute_pipeline(body: ProcessRequest) -> Dict[str, Any]:
    result: ProcessResult = await run_in_threadpool(processor.process, body)
    insert_segments(result.segment_rows)
    insert_emotions(result.emotions)
    payload = {
        "video_id": result.video_id,
        "namespace": result.namespace,
        "emotions": [
            {
                "label": row.get("label"),
                "score": row.get("score"),
                "ts_seconds": row.get("ts_seconds"),
                "speaker": row.get("speaker"),
            }
            for row in result.emotions
        ],
        "transcript": {
            "text": result.transcript.get("text"),
            "language": result.transcript.get("language"),
            "segments": result.transcript.get("segments"),
            "speakers": result.transcript.get("speakers"),
        },
        "features": result.features,
        "audio_uri": result.audio_uri,
    }
    event = await publish("analysis.audio.v1", payload, source="media-audio")
    return {
        "ok": True,
        "video_id": result.video_id,
        "namespace": result.namespace,
        "transcript": result.transcript,
        "emotions": result.emotions,
        "features": result.features,
        "segments_inserted": len(result.segment_rows),
        "emotions_inserted": len(result.emotions),
        "event": event,
    }


@app.post("/process")
async def process_endpoint(body: ProcessRequest):
    return await _execute_pipeline(body)


@app.post("/ingest-transcript")
async def ingest_transcript(body: ProcessRequest):
    if body.transcript is None:
        raise HTTPException(400, "transcript payload required")
    return await _execute_pipeline(body)


@app.post("/emotion")
async def legacy_emotion(body: Dict[str, Any] = Body(...)):
    request = ProcessRequest(
        bucket=body.get("bucket"),
        key=body.get("key"),
        video_id=body.get("video_id"),
        namespace=body.get("namespace"),
        language=body.get("language"),
        compute_features=body.get("compute_features", False),
    )
    if not request.bucket or not request.key:
        raise HTTPException(400, "bucket and key required")
    result = await _execute_pipeline(request)
    return {
        "ok": result["ok"],
        "count": len(result.get("emotions", [])),
        "emotions": result.get("emotions", []),
        "event": result.get("event"),
    }

