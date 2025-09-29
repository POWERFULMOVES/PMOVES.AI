import asyncio
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
PMOVES_ROOT = Path(__file__).resolve().parents[3]
for candidate in (ROOT, PMOVES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

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

    meta = payload["meta"]
    assert meta["title"] == "Custom Title"
    assert meta["description"] == "A highlight reel"
    assert meta["tags"] == ["events", "summer"]
    assert meta["camera"] == "FX3"
    assert meta["slug"] == "summer-gala-2024"
    assert meta["namespace_slug"] == "creative-works"
    assert meta["filename"] == "creative-works--summer-gala-2024.png"
    assert meta["extension"] == "png"


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
