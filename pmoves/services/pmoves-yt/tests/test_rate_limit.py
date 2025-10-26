import asyncio
from pathlib import Path
import sys
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[5]
PM = Path(__file__).resolve().parents[4]
for p in (str(ROOT), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from pmoves.services.pmoves_yt import yt as ytmod  # noqa: E402


@pytest.mark.asyncio
async def test_playlist_rate_limit_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: List[float] = []
    monkeypatch.setenv("YT_RATE_LIMIT", "0.2")
    monkeypatch.setenv("YT_CONCURRENCY", "1")

    async def fake_sleep(delay: float) -> None:
        if delay > 0:
            sleeps.append(delay)

    entries = [{"id": "id1", "title": "t1"}, {"id": "id2", "title": "t2"}]

    async def fake_ingest(url: str, ns: str, bucket: str, **kwargs) -> dict:
        return {"ok": True, "video_id": url.split("=")[-1], "download": {}, "transcript": {}}

    monkeypatch.setattr(ytmod, "_extract_entries", lambda url: entries)
    monkeypatch.setattr(ytmod, "_ingest_one_async", fake_ingest)
    monkeypatch.setattr(ytmod, "_job_create", lambda *a, **k: "job1")
    monkeypatch.setattr(ytmod, "_job_update", lambda *a, **k: None)
    monkeypatch.setattr(ytmod, "_item_upsert", lambda *a, **k: None)
    monkeypatch.setattr(ytmod, "_item_update", lambda *a, **k: None)
    monkeypatch.setattr(ytmod, "YT_CONCURRENCY", 1)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    out = await ytmod.yt_playlist({"url": "https://www.youtube.com/playlist?list=PL1", "namespace": "pm", "bucket": "b"})
    assert out.get("ok") is True
    assert sleeps, "rate limiter did not invoke sleep"
    assert any(abs(s - 0.2) < 1e-3 for s in sleeps)
