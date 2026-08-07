"""Voice Sampler — media-sourced voice references (VOICE_SAMPLER_SPEC.md v1).

Thin orchestrator over existing services; owns no models:
  SOURCE    POST /sample {bucket,key,room,persona_id} — media already in MinIO
  ANALYZE   media-audio /analyze {analysis_type: diarization} → speaker turns
  AUDITION  cut per-speaker candidate clips (pydub), stage in JuiceFS
            rooms/<room>/creator/references/voice-candidates/<batch>/...
            → NATS voice.sample.candidates.v1 (room app renders audition lanes)
  APPROVE   room posts voice.reference.approved.v1 (owner-only pub-gate)
  PUBLISH   approved clips → JuiceFS references path + OmniVoice catalog dir
            (+ flute /v1/voice/clone/register when enabled — routes are still
            TODO in flute-gateway main.py, so default off)
  ANNOUNCE  NATS voice.reference.published.v1

Voice references are personal data: JuiceFS + local catalog only — never git,
never artifacts, never public surfaces.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests as http
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("voice-sampler")

# ── Config ──────────────────────────────────────────────────────────────────
MEDIA_AUDIO_URL = os.environ.get("MEDIA_AUDIO_URL", "http://media-audio:8082")
FLUTE_URL = os.environ.get("FLUTE_URL", "http://flute-gateway:8110")
CLONE_REGISTER_ENABLED = os.environ.get("VOICE_CLONE_REGISTER_ENABLED", "0") == "1"

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "")

JUICEFS_ENDPOINT = os.environ.get("JUICEFS_ENDPOINT", "juicefs-gateway:9000")
JUICEFS_ACCESS_KEY = os.environ.get("JUICEFS_ACCESS_KEY", MINIO_ACCESS_KEY)
JUICEFS_SECRET_KEY = os.environ.get("JUICEFS_SECRET_KEY", MINIO_SECRET_KEY)
JUICEFS_BUCKET = os.environ.get("JUICEFS_BUCKET", "rooms")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUBJECT_CANDIDATES = "voice.sample.candidates.v1"
SUBJECT_APPROVED = "voice.reference.approved.v1"
SUBJECT_PUBLISHED = "voice.reference.published.v1"

# Owner-only gate (spec §Gates). v1 is single-tenant: the approval payload's
# owner_id must equal this. Empty value disables PUBLISH entirely (fail closed).
OWNER_ID = os.environ.get("VOICE_SAMPLER_OWNER_ID", "")

# OmniVoice ref-voice catalog (host bind shared with omnivoice-server, rw here,
# ro there). Unset = skip the catalog write.
OMNIVOICE_CATALOG_DIR = os.environ.get("OMNIVOICE_CATALOG_DIR", "")

MIN_SEGMENT_SEC = float(os.environ.get("VOICE_MIN_SEGMENT_SEC", "3"))
MAX_SEGMENT_SEC = float(os.environ.get("VOICE_MAX_SEGMENT_SEC", "15"))
MAX_CLIPS_PER_SPEAKER = int(os.environ.get("VOICE_MAX_CLIPS_PER_SPEAKER", "5"))

samples_total = Counter("voice_sampler_samples_total", "Sampling runs", ["status"])
candidates_total = Counter("voice_sampler_candidates_total", "Candidate clips staged")
published_total = Counter("voice_sampler_published_total", "References published", ["status"])


def _s3(endpoint: str, access: str, secret: str):
    import boto3

    scheme = "https" if MINIO_SECURE else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{endpoint}",
        aws_access_key_id=access,
        aws_secret_access_key=secret,
    )


def _minio():
    return _s3(MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY)


def _juicefs():
    return _s3(JUICEFS_ENDPOINT, JUICEFS_ACCESS_KEY, JUICEFS_SECRET_KEY)


# ── SOURCE → ANALYZE → AUDITION ─────────────────────────────────────────────
class SampleRequest(BaseModel):
    bucket: str
    key: str
    room: str
    persona_id: Optional[str] = None
    language: str = "auto"

    @model_validator(mode="after")
    def _no_traversal(self) -> "SampleRequest":
        # room/persona become JuiceFS key components and (for persona) a catalog
        # filename — refuse separators outright rather than sanitize.
        for field in ("room", "persona_id"):
            val = getattr(self, field)
            if val and any(c in val for c in ("/", "\\", "..")):
                raise ValueError(f"{field} must not contain path separators")
        return self


def _diarize(bucket: str, key: str) -> Dict[str, Any]:
    resp = http.post(
        f"{MEDIA_AUDIO_URL}/analyze",
        json={"bucket": bucket, "key": key, "analysis_type": "diarization"},
        timeout=int(os.environ.get("DIARIZE_TIMEOUT_SEC", "900")),
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("error"):
        raise HTTPException(status_code=502, detail=f"diarization error: {body['error']}")
    return body


def _pick_turns(turns: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Longest usable turns per speaker — the operator auditions few, good clips."""
    per: Dict[str, List[Dict[str, Any]]] = {}
    for t in turns:
        dur = t["end"] - t["start"]
        if dur >= MIN_SEGMENT_SEC:
            per.setdefault(t["speaker"], []).append({**t, "duration": dur})
    return {
        spk: sorted(ts, key=lambda t: -t["duration"])[:MAX_CLIPS_PER_SPEAKER]
        for spk, ts in per.items()
    }


def _run_sample(req: SampleRequest) -> Dict[str, Any]:
    """Download once; diarize a 16k-mono WAV derivative (pyannote's soundfile
    backend can't read m4a/AAC and torchcodec is deliberately absent from the
    media-audio image); cut clips from the original-quality audio."""
    from pydub import AudioSegment

    batch_id = uuid.uuid4().hex[:12]
    tmpdir = tempfile.mkdtemp(prefix="voice-sampler-")
    minio = _minio()
    scratch_key = f"voice-sampler-derived/{batch_id}.wav"
    try:
        src = os.path.join(tmpdir, uuid.uuid4().hex)
        minio.download_file(req.bucket, req.key, src)
        audio = AudioSegment.from_file(src)
        wav16 = os.path.join(tmpdir, "diarize.wav")
        audio.set_frame_rate(16000).set_channels(1).export(wav16, format="wav")
        minio.upload_file(wav16, req.bucket, scratch_key)
        diar = _diarize(req.bucket, scratch_key)
        picked = _pick_turns(diar.get("turns", []))
        if not picked:
            samples_total.labels(status="no_candidates").inc()
            return {
                "batch_id": None,
                "speakers": [],
                "detail": f"no turns >= {MIN_SEGMENT_SEC}s among {diar.get('num_speakers', 0)} speakers",
            }
        prefix = f"{req.room}/creator/references/voice-candidates/{batch_id}"
        jfs = _juicefs()
        speakers: List[Dict[str, Any]] = []
        for spk, ts in picked.items():
            clips = []
            for i, t in enumerate(ts):
                end = min(t["end"], t["start"] + MAX_SEGMENT_SEC)
                clip = audio[int(t["start"] * 1000): int(end * 1000)]
                local = os.path.join(tmpdir, f"{spk}_{i}.wav")
                clip.export(local, format="wav")
                clip_key = f"{prefix}/{spk}/{i:02d}_{t['start']:.1f}-{end:.1f}.wav"
                jfs.upload_file(local, JUICEFS_BUCKET, clip_key)
                clips.append(
                    {"key": clip_key, "start": t["start"], "end": end, "duration": end - t["start"]}
                )
                candidates_total.inc()
            speakers.append({"speaker": spk, "clips": clips})
        return {
            "batch_id": batch_id,
            "bucket": JUICEFS_BUCKET,
            "prefix": prefix,
            "speakers": speakers,
            "diarization_model": diar.get("model"),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            minio.delete_object(Bucket=req.bucket, Key=scratch_key)
        except Exception:  # noqa: BLE001
            logger.warning("scratch cleanup failed for %s", scratch_key)


# ── APPROVE → PUBLISH → ANNOUNCE ────────────────────────────────────────────
async def _handle_approval(msg) -> None:
    try:
        payload = json.loads(msg.data.decode())
    except Exception:  # noqa: BLE001
        logger.exception("unparseable approval event")
        published_total.labels(status="rejected").inc()
        return
    persona = payload.get("persona_id") or ""
    owner = payload.get("owner_id") or ""
    clips = payload.get("clips") or []
    room = payload.get("room") or ""
    chit_sig = payload.get("chit_sig") or ""
    # Owner-only pub-gate (spec §Gates): fail closed on any missing piece.
    # CHIT signature *verification* (not just presence) is the follow-up once
    # the room app signs approvals through the CHIT service.
    if not (OWNER_ID and owner == OWNER_ID and chit_sig and persona and clips and room):
        logger.warning(
            "approval REFUSED (owner_gate=%s persona=%s clips=%d room=%s)",
            bool(OWNER_ID and owner == OWNER_ID and chit_sig), persona, len(clips), bool(room),
        )
        published_total.labels(status="rejected").inc()
        return
    if any(c.startswith("/") or ".." in c for c in clips):
        logger.warning("approval REFUSED: clip key traversal attempt")
        published_total.labels(status="rejected").inc()
        return
    try:
        refs = await asyncio.to_thread(_publish_references, room, persona, clips, payload)
        published_total.labels(status="ok").inc()
        if _nc is not None:
            await _nc.publish(
                SUBJECT_PUBLISHED,
                json.dumps(
                    {
                        "persona_id": persona,
                        "catalog_id": payload.get("catalog_id") or persona,
                        "room": room,
                        "refs": refs,
                        "source_batch": payload.get("batch_id"),
                        "chit_sig": chit_sig,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ).encode(),
            )
    except Exception:  # noqa: BLE001
        logger.exception("PUBLISH failed for persona %s", persona)
        published_total.labels(status="error").inc()


def _publish_references(room: str, persona: str, clips: List[str], payload: Dict[str, Any]) -> List[str]:
    jfs = _juicefs()
    catalog_id = payload.get("catalog_id") or persona
    ref_prefix = f"{room}/creator/references/voice/{persona}"
    refs: List[str] = []
    tmpdir = tempfile.mkdtemp(prefix="voice-publish-")
    try:
        for i, clip_key in enumerate(clips):
            local = os.path.join(tmpdir, f"{i}.wav")
            jfs.download_file(JUICEFS_BUCKET, clip_key, local)
            ref_key = f"{ref_prefix}/{os.path.basename(clip_key)}"
            jfs.upload_file(local, JUICEFS_BUCKET, ref_key)
            refs.append(ref_key)
            if i == 0:
                if OMNIVOICE_CATALOG_DIR and os.path.isdir(OMNIVOICE_CATALOG_DIR):
                    shutil.copyfile(local, os.path.join(OMNIVOICE_CATALOG_DIR, f"{catalog_id}.wav"))
                if CLONE_REGISTER_ENABLED:
                    _flute_register(persona, local)
        return refs
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _flute_register(persona: str, wav_path: str) -> None:
    try:
        with open(wav_path, "rb") as fh:
            resp = http.post(
                f"{FLUTE_URL}/v1/voice/clone/register",
                files={"sample": (f"{persona}.wav", fh, "audio/wav")},
                data={"persona_slug": persona},
                timeout=120,
            )
        logger.info("flute clone register %s → %s", persona, resp.status_code)
    except Exception:  # noqa: BLE001
        # Best-effort: the flute routes are still TODO upstream.
        logger.warning("flute clone register unavailable", exc_info=True)


# ── App / NATS lifecycle ────────────────────────────────────────────────────
_nc = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nc
    try:
        import nats

        _nc = await nats.connect(NATS_URL, max_reconnect_attempts=-1)
        await _nc.subscribe(SUBJECT_APPROVED, cb=_handle_approval)
        logger.info("NATS connected; subscribed %s", SUBJECT_APPROVED)
    except Exception:  # noqa: BLE001
        # Sampling still works without NATS; PUBLISH (approval-driven) does not.
        logger.exception("NATS connect failed — approvals will not be processed")
        _nc = None
    yield
    if _nc is not None:
        await _nc.drain()


app = FastAPI(title="voice-sampler", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {
        "status": "healthy",
        "service": "voice-sampler",
        "nats_connected": _nc is not None and not _nc.is_closed,
        "owner_gate_configured": bool(OWNER_ID),
        "omnivoice_catalog": bool(OMNIVOICE_CATALOG_DIR),
        "clone_register_enabled": CLONE_REGISTER_ENABLED,
    }


@app.get("/metrics")
async def metrics():
    from fastapi import Response

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/sample")
async def sample(req: SampleRequest):
    staged = await asyncio.to_thread(_run_sample, req)
    if not staged.get("batch_id"):
        return staged
    event = {
        **staged,
        "room": req.room,
        "persona_id": req.persona_id,
        "source": {"bucket": req.bucket, "key": req.key},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if _nc is not None:
        await _nc.publish(SUBJECT_CANDIDATES, json.dumps(event).encode())
    samples_total.labels(status="ok").inc()
    return event
