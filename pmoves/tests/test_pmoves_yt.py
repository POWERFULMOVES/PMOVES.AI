from pathlib import Path

from fastapi.testclient import TestClient


def test_yt_download_uses_stubs(load_service_module, monkeypatch, tmp_path):
    yt = load_service_module("pmoves_yt", "services/pmoves-yt/yt.py")
    # Use temp directory for archive to avoid creating /data/yt-dlp
    monkeypatch.setattr(yt, "YT_ARCHIVE_DIR", tmp_path / "yt-dlp")
    monkeypatch.setattr(yt, "YT_DOWNLOAD_ARCHIVE", str(tmp_path / "yt-dlp" / "archive.txt"))

    uploads = []
    published = []
    inserts = []

    def fake_upload(path: str, bucket: str, key: str) -> str:
        uploads.append((Path(path).name, bucket, key))
        return f"https://local/{bucket}/{key}"

    def fake_publish(topic: str, payload):
        published.append((topic, payload))

    def fake_insert(table: str, row):
        inserts.append((table, row))
        return [{"id": "stub"}]

    monkeypatch.setattr(yt, "upload_to_s3", fake_upload)
    monkeypatch.setattr(yt, "_publish_event", fake_publish)
    monkeypatch.setattr(yt, "supa_insert", fake_insert)

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts
            self._filename: str | None = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            outtmpl = self.opts["outtmpl"]
            video_path = Path(outtmpl.replace("%(id)s", "abc123").replace("%(ext)s", "mp4"))
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"demo")
            self._filename = str(video_path)
            return {
                "id": "abc123",
                "title": "Demo Title",
                "requested_downloads": [{"_filename": self._filename}],
            }

        def prepare_filename(self, info):
            return self._filename or ""

    monkeypatch.setattr(yt.yt_dlp, "YoutubeDL", DummyYDL)

    client = TestClient(yt.app)
    resp = client.post(
        "/yt/download",
        json={"url": "https://youtu.be/example", "bucket": "assets", "namespace": "demo"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["video_id"] == "abc123"
    assert uploads and uploads[0][1] == "assets"
    assert any(topic == "ingest.file.added.v1" for topic, _ in published)
    # Download only inserts into studio_board (transcripts/yt_jobs are separate paths)
    assert {table for table, _ in inserts} == {"studio_board"}
