import importlib.util
import json
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
sys.path.insert(0, str(SERVER_PATH.parent.parent))  # pmoves/services
sys.path.insert(0, str(SERVER_PATH.parent.parent.parent))  # pmoves root
SPEC = importlib.util.spec_from_file_location("media_audio.server", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)  # type: ignore[arg-type]

ProcessRequest = server.ProcessRequest
ProcessResult = server.ProcessResult
TranscriptPayload = server.TranscriptPayload
app = server.app
processor = server.processor


def _build_process_result(namespace: str = "pmoves") -> ProcessResult:
    segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "hello world",
            "speaker": "SPEAKER_00",
            "words": [
                {"start": 0.0, "end": 0.5, "word": "hello", "confidence": 0.9},
                {"start": 0.5, "end": 1.0, "word": "world", "confidence": 0.8},
            ],
        }
    ]
    segment_rows = [
        {
            "namespace": namespace,
            "video_id": "vid-123",
            "ts_start": 0.0,
            "ts_end": 1.0,
            "uri": "http://minio/bucket/audio.wav",
            "meta": {
                "text": "hello world",
                "speaker": "SPEAKER_00",
                "words": segments[0]["words"],
                "features": {"rms": 0.1},
            },
        }
    ]
    emotions = [
        {
            "namespace": namespace,
            "video_id": "vid-123",
            "ts_seconds": 0.0,
            "label": "happy",
            "score": 0.95,
            "speaker": "SPEAKER_00",
        }
    ]
    features = {
        "global": {"duration": 1.0, "rms": 0.1, "spectral_centroid": 120.0, "zero_crossing_rate": 0.2, "tempo": 0.0},
        "by_segment": {"0": {"start": 0.0, "end": 1.0, "duration": 1.0, "rms": 0.1, "speaker": "SPEAKER_00"}},
    }
    transcript = {
        "text": "hello world",
        "language": "en",
        "segments": segments,
        "speakers": {"SPEAKER_00": {"speaker": "SPEAKER_00", "duration": 1.0, "segments": 1}},
    }
    return ProcessResult(
        transcript=transcript,
        segments=segments,
        segment_rows=segment_rows,
        emotions=emotions,
        features=features,
        video_id="vid-123",
        namespace=namespace,
        audio_uri="http://minio/bucket/audio.wav",
    )


def test_process_endpoint_combines_results(monkeypatch):
    client = TestClient(app)

    recorded_segments = []
    recorded_emotions = []

    monkeypatch.setattr(processor, "process", lambda request: _build_process_result("custom-space"))
    monkeypatch.setattr(server, "insert_segments", lambda rows: recorded_segments.extend(rows))
    monkeypatch.setattr(server, "insert_emotions", lambda rows: recorded_emotions.extend(rows))

    async def fake_publish(topic, payload, **kwargs):
        return {"topic": topic, "payload": payload}

    monkeypatch.setattr(server, "publish", fake_publish)

    response = client.post(
        "/process",
        json={"bucket": "bucket", "key": "audio.wav", "video_id": "vid-123", "namespace": "custom-space"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"]["text"] == "hello world"
    assert recorded_segments and recorded_segments[0]["namespace"] == "custom-space"
    assert recorded_segments[0]["meta"]["speaker"] == "SPEAKER_00"
    assert recorded_emotions and recorded_emotions[0]["namespace"] == "custom-space"
    assert recorded_emotions[0]["label"] == "happy"
    assert data["event"]["payload"]["features"]["global"]["rms"] == 0.1


def test_audio_processor_process_uses_waveform(monkeypatch, tmp_path):
    sample_rate = 16000
    samples = np.sin(2 * np.pi * 220 * np.linspace(0, 1, sample_rate, endpoint=False)).astype(np.float32)
    audio_path = tmp_path / "tone.wav"
    sf.write(audio_path, samples, sample_rate)

    class DummyBuffer:
        def __init__(self) -> None:
            self.path = str(audio_path)
            self.samples = samples
            self.sample_rate = sample_rate

        def cleanup(self) -> None:
            pass

    buffer = DummyBuffer()

    def fake_download(bucket, key):
        return buffer

    transcript = TranscriptPayload(
        text="tone",
        language="en",
        segments=[{"id": 0, "start": 0.0, "end": 1.0, "text": "tone", "speaker": "SPEAKER_00"}],
    )

    monkeypatch.setattr(processor, "_download_audio", fake_download)
    monkeypatch.setattr(processor, "_resolve_transcript", lambda request, audio: json.loads(transcript.json()))
    monkeypatch.setattr(processor, "_load_emotion_pipeline", lambda: None)

    result = processor.process(
        ProcessRequest(
            bucket="bucket",
            key="tone.wav",
            video_id="vid-456",
            transcript=transcript,
        )
    )

    assert result.features["global"]["duration"] == pytest.approx(1.0, rel=1e-2)
    assert result.features["by_segment"]["0"]["speaker"] == "SPEAKER_00"
    assert result.emotions == []
    assert result.segment_rows and result.segment_rows[0]["namespace"] == "pmoves"

