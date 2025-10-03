import os, time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
PM = Path(__file__).resolve().parents[4]
for p in (str(ROOT), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from pmoves.services.pmoves_yt import yt as ytmod


def test_playlist_rate_limit_sleep(monkeypatch):
    calls = []
    monkeypatch.setenv("YT_RATE_LIMIT", "0.2")

    def fake_extract(url):
        return [{"id": "id1", "title": "t1"}, {"id": "id2", "title": "t2"}]

    def fake_download(body):
        return {"ok": True, "video_id": body["url"].split("=")[-1], "s3_url": "s3://x", "thumb": None, "title": "t"}

    def fake_transcript(body):
        return {"ok": True, "text": "..."}

    monkeypatch.setattr(ytmod, "_extract_entries", lambda url: fake_extract(url))
    monkeypatch.setattr(ytmod, "yt_download", fake_download)
    monkeypatch.setattr(ytmod, "yt_transcript", fake_transcript)
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))

    out = ytmod.yt_playlist({"url": "https://www.youtube.com/playlist?list=PL1", "namespace": "pm", "bucket": "b"})
    assert out.get("ok") is True
    # Two entries → one inter-iteration sleep
    assert calls and abs(calls[0] - 0.2) < 1e-6
