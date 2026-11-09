"""Adapter: AudioProcessor.full() result -> the `analysis.audio.v1` event contract.

Why this module exists (issue #2186)
------------------------------------
The native synchronous result returned by ``POST /analyze`` / ``POST /process`` and the
NATS event payload are **deliberately different documents**. They were being conflated:
``_maybe_publish`` serialized the native result straight onto the wire.

They are not interchangeable. The native result nests the required ``emotions`` array one
level down under ``emotion``, names the transcript ``transcription``, emits ``features``
flat where the contract nests them under ``global``, and carries diarization as a separate
top-level block where the contract models speakers *inside* the transcript.

The practical consequence, before this adapter: ``analysis.audio.v1`` requires an
``emotions`` array at the top level, and ``full()`` has never produced one — it produces
``emotion``. So **every** publish was dropped by the pre-publish guard. The service has
never successfully emitted this event.

This module is kept free of heavy imports (no torch / fastapi) so the mapping can be tested
without a GPU image.

Contract: ``pmoves/contracts/schemas/analysis/audio.v1.schema.json``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["build_analysis_event", "assign_speakers"]


def _err(block: Any) -> bool:
    """A sub-analysis reports failure as ``{"error": ...}`` rather than raising."""
    return not isinstance(block, dict) or bool(block.get("error"))


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Seconds of overlap between two intervals; 0.0 when they do not intersect."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(
    segments: List[Dict[str, Any]], turns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Attach a ``speaker`` to each transcript segment from diarization turns.

    This is the ASR/diarization seam. The contract puts the speaker label on the transcript
    segment (``transcript.segments[].speaker``), not in a parallel diarization block, so the
    two analyses have to be joined here rather than shipped side by side and joined by every
    downstream consumer.

    A segment is credited to the turn it overlaps most, which is the honest reading when a
    segment straddles a speaker change. Ties and zero-overlap leave ``speaker`` as ``None``
    rather than guessing — a wrong speaker label on a quotable segment is a misattribution,
    which is worse than an absent one.
    """
    out: List[Dict[str, Any]] = []
    for seg in segments:
        seg = dict(seg)
        start, end = seg.get("start"), seg.get("end")
        best_speaker: Optional[str] = None
        best_overlap = 0.0
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            for turn in turns:
                t_start, t_end, spk = turn.get("start"), turn.get("end"), turn.get("speaker")
                if not isinstance(t_start, (int, float)) or not isinstance(t_end, (int, float)):
                    continue
                ov = _overlap(float(start), float(end), float(t_start), float(t_end))
                if ov > best_overlap:
                    best_overlap, best_speaker = ov, (str(spk) if spk is not None else None)
        seg["speaker"] = best_speaker
        out.append(seg)
    return out


def _segments_from_chunks(chunks: Any) -> List[Dict[str, Any]]:
    """Map HF ASR ``chunks`` to contract ``transcript.segments``.

    Transformers emits ``{"timestamp": (start, end), "text": ...}``. The trailing chunk of a
    stream can carry ``None`` for its end timestamp, so both bounds are normalized rather
    than assumed numeric.
    """
    segments: List[Dict[str, Any]] = []
    if not isinstance(chunks, list):
        return segments
    for idx, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        ts = chunk.get("timestamp") or (None, None)
        start = ts[0] if isinstance(ts, (list, tuple)) and len(ts) > 0 else None
        end = ts[1] if isinstance(ts, (list, tuple)) and len(ts) > 1 else None
        segments.append(
            {
                "id": idx,
                "start": float(start) if isinstance(start, (int, float)) else None,
                "end": float(end) if isinstance(end, (int, float)) else None,
                "text": chunk.get("text"),
                # Always present, even when diarization is unavailable (it is gated on
                # HF_TOKEN). The schema permits the key to be absent, but a field that
                # appears only sometimes forces every consumer to handle both shapes —
                # `None` means "unknown speaker", which is a stable thing to read.
                "speaker": None,
            }
        )
    return segments


def build_analysis_event(
    result: Dict[str, Any], *, audio_uri: Optional[str] = None
) -> Dict[str, Any]:
    """Build an ``analysis.audio.v1`` payload from a native ``full()`` result.

    ``audio_uri`` is passed in by the caller rather than derived from ``result``. The native
    result's ``file_path`` is a local temp path (``/tmp/media-audio-*/<uuid>``): it is
    meaningless to a consumer and leaks internal filesystem layout onto the bus, so it is
    deliberately **not** mapped. Callers that know a real URI (e.g. the MinIO object they
    fetched) supply it; otherwise the field is omitted, which the contract permits.

    A partial analysis still publishes. ``emotions`` is required by the contract, so a failed
    emotion stage yields ``[]`` rather than dropping the event — losing a good transcript and
    diarization because one stage failed would be the worse outcome. ``status`` and
    ``failed_stages`` ride along so consumers can tell partial from complete.
    """
    emotion_block = result.get("emotion")
    emotions: List[Dict[str, Any]] = []
    if not _err(emotion_block):
        candidate = emotion_block.get("emotions")
        if isinstance(candidate, list):
            # Contract requires label+score on every item; drop malformed entries rather
            # than failing validation for the whole event.
            emotions = [
                e
                for e in candidate
                if isinstance(e, dict)
                and isinstance(e.get("label"), str)
                and isinstance(e.get("score"), (int, float))
            ]

    transcription = result.get("transcription")
    transcript: Optional[Dict[str, Any]] = None
    if not _err(transcription):
        segments = _segments_from_chunks(transcription.get("chunks"))
        diarization = result.get("diarization")
        if not _err(diarization):
            turns = diarization.get("turns")
            if isinstance(turns, list):
                segments = assign_speakers(segments, turns)
        transcript = {
            "text": transcription.get("text"),
            "language": transcription.get("language"),
            "segments": segments,
        }
        if not _err(diarization):
            speakers = diarization.get("speakers")
            if isinstance(speakers, list):
                # Contract types `speakers` as an object, not an array.
                transcript["speakers"] = {
                    str(s): {"id": str(s)} for s in speakers if s is not None
                }

    native_features = result.get("features")
    features: Optional[Dict[str, Any]] = None
    if not _err(native_features):
        # Native emits these flat; the contract nests them under `global`. `rms_energy`
        # is the contract's `rms`. Extras (sample_rate, beat_count) are preserved —
        # `global` allows additionalProperties, and beat_count is signal the beats lane uses.
        features = {
            "global": {
                "duration": native_features.get("duration"),
                "rms": native_features.get("rms_energy"),
                "spectral_centroid": native_features.get("spectral_centroid"),
                "zero_crossing_rate": native_features.get("zero_crossing_rate"),
                "tempo": native_features.get("tempo"),
                "sample_rate": native_features.get("sample_rate"),
                "beat_count": native_features.get("beat_count"),
            }
        }

    payload: Dict[str, Any] = {
        "video_id": result.get("video_id"),
        "namespace": result.get("namespace"),
        "emotions": emotions,
        "transcript": transcript,
        "features": features,
        # Provenance the contract permits via additionalProperties. `task_id` correlates the
        # event with the synchronous response; `status`/`failed_stages` distinguish a partial
        # analysis from a complete one. `file_path` is intentionally absent (see docstring).
        "task_id": result.get("task_id"),
        "timestamp": result.get("timestamp"),
        "status": result.get("status"),
        "diarization": result.get("diarization"),
    }
    if audio_uri is not None:
        payload["audio_uri"] = audio_uri
    if result.get("failed_stages"):
        payload["failed_stages"] = result["failed_stages"]
    return payload
