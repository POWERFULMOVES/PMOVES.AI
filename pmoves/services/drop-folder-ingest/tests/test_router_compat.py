"""The drop folder is only useful if watch-folder-router actually routes its events.

drop-folder-ingest publishes the standard PMOVES envelope (``{id, topic, ts,
version, source, payload}`` -- the envelope schema forbids extra top-level keys),
so ``bucket`` / ``key`` / ``mime_type`` live inside ``payload``. The router used
to read those at the TOP level of the message, which made every enveloped
``ingest.file.added.v1`` a "missing bucket/key" reject. These tests feed the
router a real drop-folder event and assert it routes, and that the old flat shape
still works.

worker.py imports fastapi / prometheus_client / requests at module scope; none
are needed to exercise the routing function, so they are stubbed for the import.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
ROUTER = SERVICE_DIR.parent / "watch-folder-router" / "worker.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


di = _load("drop_folder_ingest_core_rc", SERVICE_DIR / "drop_ingest.py")


class _Counter:
    def __init__(self, *a, **k):
        self.incs = []

    def labels(self, **k):
        outer = self

        class _L:
            def inc(self, n=1):
                outer.incs.append(k)

        return _L()


class _FastAPI:
    def __init__(self, *a, **k):
        pass

    def get(self, *a, **k):
        return lambda fn: fn


@pytest.fixture()
def router(monkeypatch):
    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FastAPI
    fastapi.Response = object
    prom = types.ModuleType("prometheus_client")
    prom.Counter = _Counter
    prom.CONTENT_TYPE_LATEST = "text/plain"
    prom.generate_latest = lambda: b""
    requests = types.ModuleType("requests")
    for name, mod in (("fastapi", fastapi), ("prometheus_client", prom), ("requests", requests)):
        monkeypatch.setitem(sys.modules, name, mod)
    mod = _load("watch_folder_router_worker_under_test", ROUTER)
    published: list[tuple[str, dict, dict]] = []

    async def _capture(topic, payload, src_event):
        published.append((topic, payload, src_event))

    monkeypatch.setattr(mod, "_publish", _capture)
    mod.published = published
    return mod


class _Msg:
    def __init__(self, obj):
        self.data = json.dumps(obj).encode()


def _drop_event(name: str, mime: str):
    return di.build_event(
        bucket="assets",
        key=f"drop/2026/10/21/abcdef012345-{name}",
        sha256="cd" * 32,
        size=42,
        mime_type=mime,
        original_filename=name,
        relative_path=name,
        namespace="pmoves",
        now=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )


def test_router_routes_an_enveloped_drop_folder_document(router):
    env = _drop_event("paper.pdf", "application/pdf")
    asyncio.run(router._handle_file_added(_Msg(env)))
    assert len(router.published) == 1
    topic, payload, src = router.published[0]
    assert topic == router.SUBJECT_DOCUMENT
    assert payload["bucket"] == "assets"
    assert payload["key"] == env["payload"]["key"]
    assert payload["file_id"] == env["payload"]["file_id"]
    # correlation survives the unwrap so the constellation can trace end-to-end
    assert src["correlation_id"] == env["correlation_id"]


def test_router_routes_an_enveloped_drop_folder_text_file(router):
    asyncio.run(router._handle_file_added(_Msg(_drop_event("notes.txt", "text/plain"))))
    assert router.published[0][0] == router.SUBJECT_TEXT


def test_router_transcribes_an_enveloped_drop_folder_audio_file(router, monkeypatch):
    seen = {}

    def _fake_transcribe(bucket, key):
        seen["args"] = (bucket, key)
        return {"text": "hello world", "chunks": [], "model": "fake"}

    monkeypatch.setattr(router, "_transcribe", _fake_transcribe)
    env = _drop_event("talk.mp3", "audio/mpeg")
    asyncio.run(router._handle_file_added(_Msg(env)))
    assert seen["args"] == ("assets", env["payload"]["key"])
    topic, payload, _ = router.published[0]
    assert topic == router.SUBJECT_TRANSCRIPT
    assert payload["text"] == "hello world"


def test_router_still_accepts_the_legacy_flat_shape(router):
    flat = {"file_id": "f1", "bucket": "assets", "key": "x/paper.pdf", "mime_type": "application/pdf"}
    asyncio.run(router._handle_file_added(_Msg(flat)))
    assert router.published[0][0] == router.SUBJECT_DOCUMENT


def test_router_still_rejects_an_envelope_without_bucket_and_key(router):
    """pdf-ingest's own file.added payload carries uri but no bucket/key. It must
    stay a reject: routing it would re-announce a document pdf-ingest has already
    processed and announced itself."""
    env = {"id": "1", "topic": "ingest.file.added.v1", "ts": "t", "version": "v1",
           "source": "pdf-ingest",
           "payload": {"file_id": "pdf:x", "uri": "s3://assets/x.pdf", "kind": "document"}}
    asyncio.run(router._handle_file_added(_Msg(env)))
    assert router.published == []
