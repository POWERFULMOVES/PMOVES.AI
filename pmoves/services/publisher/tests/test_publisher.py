import asyncio
import contextlib
import datetime
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[4]
PMOVES_ROOT = Path(__file__).resolve().parents[3]
for candidate in (ROOT, PMOVES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from pmoves.services.common.telemetry import PublisherMetrics
from pmoves.services.publisher import publisher


def test_slugify_and_output_path(tmp_path):
    base = tmp_path / "library"
    slug = publisher.slugify("Summer Gala 2024!!")
    out_path = publisher.derive_output_path(str(base), "Creative Works", slug, ".png")
    expected_dir = base / "creative-works"
    assert Path(out_path).parent == expected_dir
    assert Path(out_path).name == "creative-works--summer-gala-2024.png"
    assert expected_dir.exists()


def test_build_published_payload_merges_metadata():
    payload = publisher.build_published_payload(
        artifact_uri="s3://bucket/key",
        published_path="/library/creative-works/summer-gala-2024.png",
        namespace="Creative Works",
        title="Summer Gala 2024",
        description="A highlight reel",
        tags=["events", "summer"],
        incoming_meta={"title": "Custom Title", "camera": "FX3"},
        public_url="http://media.local/creative-works/summer-gala-2024.png",
        jellyfin_item_id="abc123",
        jellyfin_public_url="http://jf.local/web/index.html#!/details?id=abc123",
        thumbnail_url="http://jf.local/Items/abc123/Images/Primary",
        duration=123.45,
        jellyfin_meta={"jellyfin_item_type": "Movie", "jellyfin_played": False},
        slug="summer-gala-2024",
        namespace_slug="creative-works",
        filename="creative-works--summer-gala-2024.png",
        extension=".png",
    )

    assert payload["artifact_uri"] == "s3://bucket/key"
    assert payload["published_path"].endswith("summer-gala-2024.png")
    assert payload["namespace"] == "Creative Works"
    assert payload["public_url"].endswith("summer-gala-2024.png")
    assert payload["jellyfin_item_id"] == "abc123"
    assert payload["jellyfin_public_url"].endswith("id=abc123")
    assert payload["thumbnail_url"].endswith("Images/Primary")
    assert payload["duration"] == 123.45
    assert payload["title"] == "Summer Gala 2024"
    assert payload["description"] == "A highlight reel"
    assert payload["tags"] == ["events", "summer"]

    meta = payload["meta"]
    assert meta["title"] == "Custom Title"
    assert meta["description"] == "A highlight reel"
    assert meta["tags"] == ["events", "summer"]
    assert meta["camera"] == "FX3"
    assert meta["slug"] == "summer-gala-2024"
    assert meta["namespace_slug"] == "creative-works"
    assert meta["filename"] == "creative-works--summer-gala-2024.png"
    assert meta["extension"] == "png"
    assert meta["thumbnail_url"].endswith("Images/Primary")
    assert meta["duration"] == 123.45
    assert meta["jellyfin_public_url"].endswith("id=abc123")
    assert meta["jellyfin_item_id"] == "abc123"
    assert meta["jellyfin_item_type"] == "Movie"


def test_merge_metadata_preserves_existing_slug_and_namespace():
    meta = publisher.merge_metadata(
        "Test",
        None,
        None,
        {"slug": "custom", "namespace_slug": "custom-ns"},
        slug="generated",
        namespace_slug="generated-ns",
        filename="generated-ns--generated.png",
        extension=".png",
    )

    assert meta["slug"] == "custom"
    assert meta["namespace_slug"] == "custom-ns"
    assert meta["filename"] == "generated-ns--generated.png"
    assert meta["extension"] == "png"


def test_build_failure_payload_includes_details():
    payload = publisher.build_failure_payload(
        stage="download",
        reason="timeout",
        retryable=True,
        outcome="fatal",
        artifact_uri="s3://bucket/key",
        namespace="demo",
        publish_event_id="evt-1",
        public_url="http://public",
        jellyfin_public_url=None,
        jellyfin_item_id="jf-1",
        details={"attempts": 3, "exception": "Timeout"},
        meta={"slug": "demo"},
    )

    assert payload["stage"] == "download"
    assert payload["retryable"] is True
    assert payload["outcome"] == "fatal"
    assert payload["artifact_uri"] == "s3://bucket/key"
    assert payload["details"]["attempts"] == 3
    assert payload["details"]["exception"] == "Timeout"
    assert payload["meta"]["slug"] == "demo"


def test_request_jellyfin_refresh_webhook(monkeypatch):
    attempts_before = publisher.METRICS.refresh_attempts
    success_before = publisher.METRICS.refresh_success
    failures_before = publisher.METRICS.refresh_failures

    class DummyResponse:
        status_code = 204

        def raise_for_status(self) -> None:
            return None

    recorded = {}

    def fake_post(url, json, headers=None, timeout=None):
        recorded["url"] = url
        recorded["json"] = json
        recorded["headers"] = headers
        recorded["timeout"] = timeout
        return DummyResponse()

    try:
        monkeypatch.setattr(publisher, "requests", SimpleNamespace(post=fake_post))
        monkeypatch.setattr(publisher, "_lookup_jellyfin_item", lambda _title: ("http://public/item", "item-123"))
        monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_WEBHOOK_URL", "http://hook.local/refresh")
        monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_WEBHOOK_TOKEN", "secret-token")
        monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_DELAY_SEC", 0)

        url, item_id = asyncio.run(publisher.request_jellyfin_refresh("Sample", "pmoves"))
        assert url == "http://public/item"
        assert item_id == "item-123"
        assert recorded["url"] == "http://hook.local/refresh"
        assert recorded["json"] == {"title": "Sample", "namespace": "pmoves"}
        assert recorded["headers"] == {"Authorization": "Bearer secret-token"}
        assert recorded["timeout"] == 10
        assert publisher.METRICS.refresh_attempts == attempts_before + 1
        assert publisher.METRICS.refresh_success == success_before + 1
        assert publisher.METRICS.refresh_failures == failures_before
    finally:
        publisher.METRICS.refresh_attempts = attempts_before
        publisher.METRICS.refresh_success = success_before
        publisher.METRICS.refresh_failures = failures_before


def test_request_jellyfin_refresh_webhook_http_error(monkeypatch):
    attempts_before = publisher.METRICS.refresh_attempts
    failures_before = publisher.METRICS.refresh_failures

    # Local stand-in for requests.HTTPError to avoid external dependency
    class HTTPError(Exception):
        def __init__(self, msg, response=None):
            super().__init__(msg)
            self.response = response

    class DummyResponse:
        status_code = 401
        text = "Unauthorized"

        def raise_for_status(self):
            raise HTTPError("401 Unauthorized", response=self)

    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResponse()

    monkeypatch.setattr(publisher, "requests", SimpleNamespace(post=fake_post))
    monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_WEBHOOK_URL", "http://hook.local/refresh")
    monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_WEBHOOK_TOKEN", "secret-token")
    monkeypatch.setattr(publisher, "JELLYFIN_REFRESH_DELAY_SEC", 0)

    with pytest.raises(publisher.JellyfinRefreshError):
        asyncio.run(publisher.request_jellyfin_refresh("Sample", "pmoves"))

    assert publisher.METRICS.refresh_attempts == attempts_before + 1
    assert publisher.METRICS.refresh_failures == failures_before + 1


def test_metrics_server_serves_json_payloads():
    original_metrics = publisher.METRICS
    original_host = publisher.METRICS_HOST
    original_port = publisher.METRICS_PORT

    async def _exercise() -> None:
        server: asyncio.AbstractServer | None = None
        try:
            publisher.METRICS = PublisherMetrics()
            publisher.METRICS.record_download_success()
            publisher.METRICS.record_refresh_attempt()
            publisher.METRICS.record_refresh_success()
            publisher.METRICS.record_turnaround(12.5)
            publisher.METRICS.record_approval_latency(5.0)
            publisher.METRICS.record_engagement({"views": 10})
            publisher.METRICS.record_cost({"usd": 1.5})

            publisher.METRICS_HOST = "127.0.0.1"
            publisher.METRICS_PORT = 0

            server = await publisher.start_metrics_server()
            sockets = server.sockets or []
            assert sockets, "metrics server did not expose any sockets"
            sockname = sockets[0].getsockname()
            if isinstance(sockname, tuple):
                port = sockname[1]
            else:
                port = sockname
            host = "127.0.0.1"

            async def _fetch(path: str) -> bytes:
                reader, writer = await asyncio.open_connection(host, port)
                request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                writer.write(request.encode())
                await writer.drain()
                data = await reader.read()
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
                return data

            async def _assert_json_response(path: str) -> dict:
                raw_response = await _fetch(path)
                header, body = raw_response.split(b"\r\n\r\n", 1)
                status_line = header.split(b"\r\n", 1)[0].decode()
                assert "200 OK" in status_line
                payload = json.loads(body.decode())
                assert isinstance(payload, dict)
                return payload

            metrics_payload = await _assert_json_response("/metrics")
            metrics_json_payload = await _assert_json_response("/metrics.json")

            for payload in (metrics_payload, metrics_json_payload):
                assert payload["downloads"] == 1
                assert payload["refresh_attempts"] == 1
                assert payload["refresh_success"] == 1
                assert payload["engagement_totals"]["views"] == 10.0
                assert payload["cost_totals"]["usd"] == 1.5
        finally:
            if server is not None:
                server.close()
                await server.wait_closed()
            publisher._METRICS_SERVER = None
            publisher.METRICS_HOST = original_host
            publisher.METRICS_PORT = original_port
            publisher.METRICS = original_metrics

    asyncio.run(_exercise())


def test_lookup_jellyfin_item_handles_http_error(monkeypatch):
    class HTTPError(Exception):
        def __init__(self, msg, response=None):
            super().__init__(msg)
            self.response = response

    class DummyResponse:
        status_code = 404
        text = "Not Found"

        def raise_for_status(self):
            raise HTTPError("404 Not Found", response=self)

    def fake_get(url, params=None, headers=None, timeout=None):
        return DummyResponse()

    monkeypatch.setattr(publisher, "requests", SimpleNamespace(get=fake_get))
    monkeypatch.setattr(publisher, "JELLYFIN_URL", "http://jf")
    monkeypatch.setattr(publisher, "JELLYFIN_API_KEY", "k")
    monkeypatch.setattr(publisher, "JELLYFIN_USER_ID", "u")

    url, item_id, meta = publisher._lookup_jellyfin_item("Title")
    assert url is None and item_id is None and meta == {}


def test_compute_publish_telemetry_and_metrics_summary():
    published_at = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    incoming_meta = {
        "ingest_started_at": "2024-01-01T09:00:00Z",
        "approved_at": "2024-01-01T11:30:00Z",
        "engagement": {"views": "10", "ctr": 0.25},
        "cost": {"storage_gb": "0.5", "transfer_gb": 0.1},
    }
    telemetry = publisher.compute_publish_telemetry(incoming_meta, "2024-01-01T11:45:00Z", published_at)

    assert telemetry.turnaround_seconds == 10800.0
    assert telemetry.approval_latency_seconds == 1800.0
    assert telemetry.engagement == {"views": 10.0, "ctr": 0.25}
    assert telemetry.cost == {"storage_gb": 0.5, "transfer_gb": 0.1}

    metrics = publisher.PublisherMetrics()
    metrics.record_turnaround(telemetry.turnaround_seconds)
    metrics.record_approval_latency(telemetry.approval_latency_seconds)
    metrics.record_engagement(telemetry.engagement)
    metrics.record_cost(telemetry.cost)

    summary = metrics.summary()
    assert summary["avg_turnaround_seconds"] == 10800.0
    assert summary["avg_approval_latency_seconds"] == 1800.0
    assert summary["engagement_totals"]["views"] == 10.0
    assert summary["cost_totals"]["storage_gb"] == 0.5


def test_handle_download_failed_emits_failure_envelope(monkeypatch, tmp_path):
    published_messages: list[tuple[str, bytes]] = []
    audit_calls: Dict[str, Any] = {}

    async def exercise() -> None:
        subscription_ready: asyncio.Future = asyncio.get_running_loop().create_future()

        class StubNATS:
            def __init__(self) -> None:
                self.published = published_messages

            async def connect(self, servers=None):
                return None

            async def publish(self, subject, data):
                self.published.append((subject, data))

            async def subscribe(self, subject, cb):
                if not subscription_ready.done():
                    subscription_ready.set_result(cb)

        class StubMinio:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def fget_object(self, bucket, key, dest):
                raise publisher.DownloadError("simulated download failure")

        async def fake_start_metrics_server():
            return SimpleNamespace()

        def fake_record_audit(**kwargs):
            audit_calls["kwargs"] = kwargs

        monkeypatch.setattr(publisher, "MEDIA_LIBRARY_PATH", str(tmp_path))
        monkeypatch.setattr(publisher, "DOWNLOAD_RETRIES", 1)
        monkeypatch.setattr(publisher, "_NATSClient", lambda: StubNATS())
        monkeypatch.setattr(publisher, "_MinioClient", lambda *args, **kwargs: StubMinio())
        monkeypatch.setattr(publisher, "start_metrics_server", fake_start_metrics_server)
        monkeypatch.setattr(publisher, "_record_audit", fake_record_audit)
        monkeypatch.setattr(
            publisher,
            "supabase_client",
            SimpleNamespace(upsert_publisher_audit=lambda row: None),
        )

        main_task = asyncio.create_task(publisher.main())
        handle = await asyncio.wait_for(subscription_ready, timeout=1)
        main_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await main_task

        env = {
            "id": "evt-123",
            "ts": "2024-01-01T12:00:00Z",
            "correlation_id": "corr-789",
            "payload": {
                "artifact_uri": "s3://assets/demo/video.mp4",
                "namespace": "Creative Works",
                "title": "Demo Video",
                "meta": {"camera": "FX3", "ingest_started_at": "2024-01-01T10:00:00Z"},
            },
        }

        msg = SimpleNamespace(data=json.dumps(env).encode("utf-8"))
        await handle(msg)

    asyncio.run(exercise())

    assert published_messages, "expected failure envelope to be published"
    subject, data = published_messages[0]
    assert subject == "content.publish.failed.v1"
    evt = json.loads(data.decode("utf-8"))
    payload = evt["payload"]

    assert payload["stage"] == "download"
    assert payload["outcome"] == "fatal"
    assert payload["namespace"] == "Creative Works"
    assert payload["artifact_uri"] == "s3://assets/demo/video.mp4"
    details = payload.get("details")
    assert details["attempts"] == 1
    assert details["stage"] == "download"

    meta = payload["meta"]
    assert meta["stage"] == "download"
    assert meta["bucket"] == "assets"
    assert meta["key"] == "demo/video.mp4"
    assert meta["output_path"].endswith("creative-works/creative-works--demo-video.mp4")
    assert meta["source_meta"]["camera"] == "FX3"

    audit_kwargs = audit_calls["kwargs"]
    assert audit_kwargs["status"] == "failed"
    assert audit_kwargs["publish_event_id"] == "evt-123"
    assert audit_kwargs["failure_reason"].startswith("Failed to download")
    assert audit_kwargs["meta"] == meta
