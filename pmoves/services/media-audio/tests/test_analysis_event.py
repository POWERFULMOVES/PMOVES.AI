"""Tests for the analysis.audio.v1 adapter (issue #2186).

These import `analysis_event` directly rather than `server`, because server.py pulls in
torch/fastapi at module scope and the mapping under test is pure dict manipulation. Keeping
the adapter importable without the GPU stack is the point of it being its own module.

The validation tests check against the REAL registered schema, not a local copy, so a drift
between adapter and contract fails here rather than on the bus.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parents[2]
SCHEMA = REPO_ROOT / "pmoves/contracts/schemas/analysis/audio.v1.schema.json"


def _load_adapter():
    spec = importlib.util.spec_from_file_location(
        "media_audio_analysis_event", SERVICE_DIR / "analysis_event.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()
build_analysis_event = adapter.build_analysis_event
assign_speakers = adapter.assign_speakers


def _validate(payload):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


def native_full_result(**overrides):
    """A representative AudioProcessor.full() result, shaped as the service really emits it."""
    result = {
        "task_id": "11111111-2222-3333-4444-555555555555",
        "file_path": "/tmp/media-audio-abc123/deadbeef",
        "timestamp": "2026-08-04T18:00:00+00:00",
        "features": {
            "duration": 12.5,
            "sample_rate": 16000,
            "rms_energy": 0.11,
            "spectral_centroid": 2200.0,
            "zero_crossing_rate": 0.07,
            "tempo": 96.0,
            "beat_count": 20,
        },
        "transcription": {
            "text": "hello there general kenobi",
            "chunks": [
                {"timestamp": (0.0, 2.0), "text": "hello there"},
                {"timestamp": (2.0, 4.0), "text": "general kenobi"},
            ],
            "model": "openai/whisper-large-v3-turbo",
        },
        "emotion": {
            "emotions": [{"label": "neu", "score": 0.8}, {"label": "hap", "score": 0.2}],
            "dominant": {"label": "neu", "score": 0.8},
            "model": "superb/hubert-large-superb-er",
        },
        "diarization": {
            "turns": [
                {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
                {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
            ],
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "num_speakers": 2,
            "model": "pyannote/speaker-diarization-3.1",
        },
        "processing_time": 3.2,
        "status": "completed",
    }
    result.update(overrides)
    return result


class TestContractConformance:
    def test_native_result_alone_does_not_satisfy_the_contract(self):
        """The regression that made this adapter necessary.

        full() emits `emotion` (singular). The contract requires a top-level `emotions`
        array. Publishing the native result unmapped could never validate — which is why
        the service had never successfully published.
        """
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=native_full_result(), schema=schema)

    def test_adapted_payload_validates(self):
        _validate(build_analysis_event(native_full_result()))

    def test_emotions_lifted_to_top_level(self):
        payload = build_analysis_event(native_full_result())
        assert payload["emotions"] == [
            {"label": "neu", "score": 0.8},
            {"label": "hap", "score": 0.2},
        ]

    def test_features_nested_under_global_and_rms_renamed(self):
        payload = build_analysis_event(native_full_result())
        assert payload["features"]["global"]["rms"] == 0.11
        assert payload["features"]["global"]["tempo"] == 96.0
        # beat_count is signal the beats lane consumes; it must survive the reshape.
        assert payload["features"]["global"]["beat_count"] == 20

    def test_local_temp_path_is_not_leaked(self):
        """file_path is an internal temp path; it must not reach the bus as audio_uri."""
        payload = build_analysis_event(native_full_result())
        assert "file_path" not in payload
        assert payload.get("audio_uri") is None or "/tmp/" not in str(payload.get("audio_uri"))

    def test_caller_supplied_audio_uri_is_used(self):
        payload = build_analysis_event(native_full_result(), audio_uri="s3://bucket/key.wav")
        assert payload["audio_uri"] == "s3://bucket/key.wav"
        _validate(payload)


class TestSpeakerJoin:
    def test_segments_receive_speakers_from_diarization(self):
        payload = build_analysis_event(native_full_result())
        segs = payload["transcript"]["segments"]
        assert [s["speaker"] for s in segs] == ["SPEAKER_00", "SPEAKER_01"]

    def test_straddling_segment_credited_to_majority_overlap(self):
        segments = [{"start": 0.0, "end": 10.0}]
        turns = [
            {"start": 0.0, "end": 3.0, "speaker": "A"},
            {"start": 3.0, "end": 10.0, "speaker": "B"},
        ]
        assert assign_speakers(segments, turns)[0]["speaker"] == "B"

    def test_no_overlap_yields_none_rather_than_a_guess(self):
        """A wrong speaker on a quotable segment is a misattribution; absent is safer."""
        segments = [{"start": 100.0, "end": 101.0}]
        turns = [{"start": 0.0, "end": 3.0, "speaker": "A"}]
        assert assign_speakers(segments, turns)[0]["speaker"] is None

    def test_missing_timestamps_do_not_raise(self):
        segments = [{"start": None, "end": None}]
        turns = [{"start": 0.0, "end": 3.0, "speaker": "A"}]
        assert assign_speakers(segments, turns)[0]["speaker"] is None


class TestPartialAnalysis:
    def test_failed_emotion_still_publishes_with_empty_emotions(self):
        """Losing a good transcript because one stage failed is the worse outcome."""
        result = native_full_result(
            emotion={"error": "no emotion model loaded"},
            status="partial",
            failed_stages=["emotion"],
        )
        payload = build_analysis_event(result)
        assert payload["emotions"] == []
        assert payload["failed_stages"] == ["emotion"]
        _validate(payload)

    def test_diarization_disabled_still_validates(self):
        """Diarization is gated on HF_TOKEN; absent speakers must not break the contract."""
        result = native_full_result(
            diarization={"error": "diarization not enabled (set HF_TOKEN)"},
            status="partial",
            failed_stages=["diarization"],
        )
        payload = build_analysis_event(result)
        assert all(s["speaker"] is None for s in payload["transcript"]["segments"])
        _validate(payload)

    def test_all_stages_failed_still_validates(self):
        result = native_full_result(
            features={"error": "x"},
            transcription={"error": "x"},
            emotion={"error": "x"},
            diarization={"error": "x"},
            status="partial",
            failed_stages=["features", "transcription", "emotion", "diarization"],
        )
        payload = build_analysis_event(result)
        assert payload["emotions"] == []
        assert payload["transcript"] is None
        assert payload["features"] is None
        _validate(payload)

    def test_malformed_emotion_entries_are_dropped_not_published(self):
        result = native_full_result(
            emotion={"emotions": [{"label": "neu", "score": 0.8}, {"nope": 1}, "junk"]}
        )
        payload = build_analysis_event(result)
        assert payload["emotions"] == [{"label": "neu", "score": 0.8}]
        _validate(payload)


class TestTranscriptSegments:
    def test_open_ended_final_chunk_is_normalized(self):
        """Transformers can emit a trailing chunk with a None end timestamp."""
        result = native_full_result(
            transcription={
                "text": "trailing",
                "chunks": [{"timestamp": (4.0, None), "text": "trailing"}],
            }
        )
        payload = build_analysis_event(result)
        seg = payload["transcript"]["segments"][0]
        assert seg["start"] == 4.0 and seg["end"] is None
        _validate(payload)

    def test_speakers_map_is_an_object_not_a_list(self):
        """The contract types transcript.speakers as an object; diarization emits a list."""
        payload = build_analysis_event(native_full_result())
        assert isinstance(payload["transcript"]["speakers"], dict)
        assert set(payload["transcript"]["speakers"]) == {"SPEAKER_00", "SPEAKER_01"}
        _validate(payload)
