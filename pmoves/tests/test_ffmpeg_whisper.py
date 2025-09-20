from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ffmpeg_server(monkeypatch, load_service_module):
    """Load the ffmpeg-whisper server module with stubbed heavy deps."""
    fake_fw = ModuleType("faster_whisper")

    class _FakeSegment:
        def __init__(self, start: float, end: float, text: str) -> None:
            self.start = start
            self.end = end
            self.text = text

    class _FakeModel:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial
            pass

        def transcribe(self, audio_path: str, language: str | None = None):
            segment = _FakeSegment(0.0, 1.5, "hello world")

            def _iterator():
                yield segment

            info = SimpleNamespace(language=language or "en")
            return _iterator(), info

    fake_fw.WhisperModel = _FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)

    supabase_module = ModuleType("supabase")
    supabase_module.create_client = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    supabase_module.Client = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "supabase", supabase_module)

    server = load_service_module("ffmpeg_whisper_server", "services/ffmpeg-whisper/server.py")
    return server


@pytest.fixture
def transcribe_client(monkeypatch, ffmpeg_server):
    class _FakeS3:
        def download_fileobj(self, bucket: str, key: str, file_obj):  # pragma: no cover - trivial
            file_obj.write(b"video-bytes")

        def upload_file(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial
            return None

    def _fake_extract(src: str, dst: str) -> None:
        Path(dst).write_bytes(b"audio-bytes")

    monkeypatch.setattr(ffmpeg_server, "s3_client", lambda: _FakeS3())
    monkeypatch.setattr(ffmpeg_server, "ffmpeg_extract_audio", _fake_extract)

    client = TestClient(ffmpeg_server.app)
    return ffmpeg_server, client


def _post_transcribe(client: TestClient) -> Dict[str, Any]:
    response = client.post(
        "/transcribe",
        json={"bucket": "demo", "key": "clip.mp4", "video_id": "vid-123"},
    )
    assert response.status_code == 200
    return response.json()


def test_transcribe_falls_back_when_forward_fails(monkeypatch, transcribe_client):
    server, client = transcribe_client
    inserted: Dict[str, Any] = {}
    forwarded: Dict[str, Any] = {}

    def _fake_insert(rows):
        inserted["rows"] = rows

    def _fake_forward(payload):
        forwarded["payload"] = payload
        return False

    monkeypatch.setattr(server, "insert_segments", _fake_insert)
    monkeypatch.setattr(server, "_forward_to_audio_service", _fake_forward)
    monkeypatch.setattr(server, "MEDIA_AUDIO_URL", "https://media-audio.example/ingest")

    body = _post_transcribe(client)

    assert inserted["rows"], "insert_segments should receive rows on forward failure"
    assert inserted["rows"][0]["video_id"] == "vid-123"
    assert forwarded["payload"]["video_id"] == "vid-123"
    assert body["text"] == "hello world"


def test_transcribe_skips_insert_when_forward_succeeds(monkeypatch, transcribe_client):
    server, client = transcribe_client
    inserted = False

    def _fake_insert(rows):
        nonlocal inserted
        inserted = True

    monkeypatch.setattr(server, "insert_segments", _fake_insert)
    monkeypatch.setattr(server, "_forward_to_audio_service", lambda payload: True)
    monkeypatch.setattr(server, "MEDIA_AUDIO_URL", "https://media-audio.example/ingest")

    _post_transcribe(client)

    assert inserted is False, "insert_segments should not be called when forward succeeds"
