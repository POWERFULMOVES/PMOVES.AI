import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("PIL")
from fastapi.testclient import TestClient
from PIL import Image

SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
sys.path.insert(0, str(SERVER_PATH.parent.parent))  # pmoves/services
sys.path.insert(0, str(SERVER_PATH.parent.parent.parent))  # pmoves root
SPEC = importlib.util.spec_from_file_location("media_video.server", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)  # type: ignore[arg-type]

app = server.app


class DummyTensor:
    def __init__(self, value: float) -> None:
        self._value = value

    def item(self) -> float:
        return self._value


class DummyBox:
    def __init__(self, cls_id: int = 0, confidence: float = 0.9) -> None:
        self.cls = DummyTensor(cls_id)
        self.conf = DummyTensor(confidence)


class DummyResult:
    def __init__(self) -> None:
        self.names = {0: "person"}
        self.boxes = [DummyBox()]


class DummyYolo:
    def __call__(self, *args: Any, **kwargs: Any) -> List[DummyResult]:
        return [DummyResult()]


def test_detect_endpoint_inserts_namespace(monkeypatch, tmp_path):
    client = TestClient(app)

    recorded: Dict[str, List[Dict[str, Any]]] = {"detections": [], "segments": [], "emotions": []}

    class FakeS3:
        def download_fileobj(self, bucket, key, fh):
            fh.write(b"fake")

        def upload_file(self, src, bucket, key):
            return None

    def fake_ffmpeg(src: str, outdir: str, every: int) -> None:
        image_path = Path(outdir) / "frame_000001.jpg"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (2, 2), color="white").save(image_path)

    monkeypatch.setattr(server, "s3_client", lambda: FakeS3())
    monkeypatch.setattr(server, "ffmpeg_frames", fake_ffmpeg)
    monkeypatch.setattr(server, "load_yolo", lambda: DummyYolo())
    monkeypatch.setattr(server, "load_scene_classifier", lambda: (lambda image: [{"label": "indoors", "score": 0.8}]))
    monkeypatch.setattr(server, "load_caption_generator", lambda: (lambda image: [{"generated_text": "a frame"}]))
    monkeypatch.setattr(server, "load_mood_classifier", lambda: (lambda text: [{"label": "positive", "score": 0.9}]))
    monkeypatch.setattr(server, "load_video_reasoner", lambda: None)
    monkeypatch.setattr(server, "s3_http_base", lambda: "http://minio")
    monkeypatch.setattr(server, "insert_detections", lambda rows: recorded["detections"].extend(rows))
    monkeypatch.setattr(server, "insert_segments", lambda rows: recorded["segments"].extend(rows))
    monkeypatch.setattr(server, "insert_emotions", lambda rows: recorded["emotions"].extend(rows))

    response = client.post(
        "/detect",
        json={"bucket": "media", "key": "video.mp4", "video_id": "vid-001", "namespace": "demo"},
    )

    assert response.status_code == 200
    assert recorded["detections"] and recorded["detections"][0]["namespace"] == "demo"
    assert recorded["segments"] and recorded["segments"][0]["namespace"] == "demo"
    assert recorded["emotions"] and recorded["emotions"][0]["namespace"] == "demo"
